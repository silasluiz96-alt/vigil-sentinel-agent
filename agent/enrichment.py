"""
Agente de Enriquecimento de Leads — Fase 2 do funil.

Para cada lead captado, o agente:
  1. Pesquisa nome + empresa na web via Tavily
  2. Envia os resultados ao LLM para extração estruturada de dados
  3. Salva o perfil enriquecido no Supabase
  4. Dispara o cálculo de score (lead_scoring.py)

O enriquecimento alimenta diretamente a personalização das réguas
de comunicação (Fases 3 e 4) e a acurácia do modelo de ML.

Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient
from db.client import get_supabase
from agent.lead_scoring import calcular_score

load_dotenv()

_llm    = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
_tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

PROMPT_EXTRACAO = """
Você é um analista de inteligência de mercado B2B.
Com base nos resultados de busca abaixo sobre "{nome}" da empresa "{empresa}",
extraia as informações disponíveis publicamente e retorne APENAS um JSON válido,
sem markdown, sem explicações.

Resultados da busca:
{resultados}

JSON esperado:
{{
  "cargo_real": "cargo confirmado ou inferido",
  "empresa_confirmada": "nome oficial da empresa",
  "setor": "setor de atuação (ex: Financeiro, Saúde, Tecnologia)",
  "tamanho_empresa": "faixa de funcionários (ex: 200-500, acima de 1000)",
  "linkedin_encontrado": true ou false,
  "linkedin_atividade": "Alta, Média, Baixa ou Não encontrado",
  "linkedin_observacao": "o que foi observado publicamente: posts recentes, artigos, ausência de rastros etc.",
  "sinais_interesse": "evidências públicas de interesse em segurança, compliance ou TI",
  "resumo_perfil": "2-3 frases sobre o perfil profissional para personalizar comunicações"
}}

Critérios para linkedin_atividade:
- Alta: posts ou artigos recentes indexados, menções em eventos, conteúdo publicado nos últimos meses
- Média: perfil encontrado mas sem publicações recentes visíveis
- Baixa: perfil existe mas completamente inativo, sem rastros de conteúdo
- Não encontrado: nenhum perfil identificado nos resultados

Se um campo não for encontrado, use null. Nunca invente informações nem acesse dados privados.
"""


def _buscar_na_web(nome: str, empresa: str) -> dict:
    """
    Pesquisa o lead na web via Tavily com três ângulos:
    1. Perfil profissional e cargo
    2. Atividade pública no LinkedIn (posts, artigos indexados)
    3. Contexto da empresa (setor, porte, maturidade em segurança)
    Apenas dados públicos — nenhuma tentativa de acessar perfis privados.
    """
    queries = [
        f"{nome} {empresa} LinkedIn cargo",
        f"{nome} LinkedIn posts artigos publicações site:linkedin.com",
        f"{empresa} setor segurança cibernética compliance funcionários",
    ]
    resultados = []
    for query in queries:
        try:
            resp = _tavily.search(query=query, max_results=3, search_depth="basic")
            for r in resp.get("results", []):
                resultados.append(f"Fonte: {r.get('url','')}\n{r.get('content','')[:400]}")
        except Exception:
            pass
    return "\n\n---\n\n".join(resultados) if resultados else "Nenhum resultado encontrado."


def _extrair_perfil(nome: str, empresa: str, resultados_web: str) -> dict:
    """Usa o LLM para extrair dados estruturados dos resultados de busca."""
    prompt = PROMPT_EXTRACAO.format(
        nome=nome,
        empresa=empresa,
        resultados=resultados_web,
    )
    resposta = _llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=600,
    )
    texto = resposta.choices[0].message.content.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # Tenta extrair o JSON mesmo se houver texto ao redor
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1
        if inicio >= 0 and fim > inicio:
            return json.loads(texto[inicio:fim])
        return {}


def enriquecer_lead(lead_id: str) -> dict:
    """
    Pipeline completo de enriquecimento para um lead.
    Retorna o perfil enriquecido salvo no banco.
    """
    db = get_supabase()

    lead = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        raise ValueError(f"Lead {lead_id} não encontrado.")
    lead = lead[0]

    nome    = lead["nome"]
    empresa = lead.get("empresa") or ""

    resultados_web = _buscar_na_web(nome, empresa)
    perfil = _extrair_perfil(nome, empresa, resultados_web)

    linkedin_encontrado = perfil.get("linkedin_encontrado")
    if isinstance(linkedin_encontrado, str):
        linkedin_encontrado = linkedin_encontrado.lower() == "true"

    atividade_valida = {"Alta", "Média", "Baixa", "Não encontrado"}
    linkedin_atividade = perfil.get("linkedin_atividade")
    if linkedin_atividade not in atividade_valida:
        linkedin_atividade = "Não encontrado"

    db.table("enriquecimento").upsert({
        "lead_id": lead_id,
        "cargo_real":            perfil.get("cargo_real"),
        "empresa_confirmada":    perfil.get("empresa_confirmada"),
        "setor":                 perfil.get("setor"),
        "tamanho_empresa":       perfil.get("tamanho_empresa"),
        "linkedin_encontrado":   linkedin_encontrado or False,
        "linkedin_atividade":    linkedin_atividade,
        "linkedin_observacao":   perfil.get("linkedin_observacao"),
        "sinais_interesse":      perfil.get("sinais_interesse"),
        "resumo_perfil":         perfil.get("resumo_perfil"),
        "raw_data":              perfil,
    }, on_conflict="lead_id").execute()

    # Recalcula o score com os dados frescos
    score = calcular_score(lead_id)

    return {**perfil, "lead_id": lead_id, "score": score}


def enriquecer_pendentes() -> list:
    """
    Enriquece todos os leads que ainda não têm perfil no banco.
    Útil para rodar em batch ou agendado.
    """
    db = get_supabase()

    todos_leads = db.table("leads").select("id").execute().data
    ja_enriquecidos = {
        r["lead_id"]
        for r in db.table("enriquecimento").select("lead_id").execute().data
    }

    pendentes = [l["id"] for l in todos_leads if l["id"] not in ja_enriquecidos]
    resultados = []
    for lead_id in pendentes:
        try:
            resultado = enriquecer_lead(lead_id)
            resultados.append({"lead_id": lead_id, "status": "ok", **resultado})
        except Exception as e:
            resultados.append({"lead_id": lead_id, "status": "erro", "detalhe": str(e)})

    return resultados
