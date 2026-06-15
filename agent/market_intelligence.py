"""
Inteligência de Mercado por Empresa — dever de casa do vendedor.

Para cada empresa com leads inscritos, o agente pesquisa ativamente
o que está acontecendo com ela no mercado e sintetiza em cinco ângulos:

  1. Incidentes e riscos     — vazamentos, multas LGPD, vulnerabilidades públicas
  2. Inovação e investimento — IA, cloud, transformação digital, novos produtos
  3. Movimento de pessoas    — contratações em TI/segurança (sinal de expansão)
  4. Conformidade            — certificações em andamento, setor regulado, auditorias
  5. Crescimento             — fusões, aquisições, novas unidades, expansão internacional

O resultado alimenta dois consumidores:
  - Promoter Brief: o promotor chega ao evento sabendo mais sobre a empresa
    do que muitos funcionários dela
  - Régua pós-evento: e-mails de follow-up referenciam algo real e recente,
    tornando a abordagem radicalmente diferente de qualquer concorrente

Lógica de pitch por ângulo:
  Inovação em IA     → "cada modelo em produção é uma superfície de ataque"
  Expansão de RH     → "mais endpoints, mais risco"
  Certificação ISO   → "a Vigil.AI automatiza a coleta de evidências"
  Fusão/aquisição    → "integração de sistemas = janela de vulnerabilidade"
  Incidente público  → "sabemos como prevenir que isso aconteça de novo"

Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import os
import json
from datetime import datetime
from openai import OpenAI
from tavily import TavilyClient
from dotenv import load_dotenv
from db.client import get_supabase

load_dotenv()

_llm    = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
_tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# ------------------------------------------------------------------
# Queries de pesquisa — 5 ângulos de inteligência
# ------------------------------------------------------------------

def _queries_por_empresa(empresa: str) -> dict:
    return {
        "incidentes":   f"{empresa} vazamento dados segurança incidente cibernético LGPD multa",
        "inovacao":     f"{empresa} inteligência artificial IA cloud transformação digital inovação tecnologia 2024 2025",
        "movimento_rh": f"{empresa} contratação vagas TI segurança da informação CISO CTO expansão equipe",
        "conformidade": f"{empresa} ISO 27001 SOC 2 LGPD conformidade auditoria certificação regulatório",
        "crescimento":  f"{empresa} fusão aquisição expansão nova unidade crescimento mercado 2024 2025",
    }


def _pesquisar(queries: dict) -> dict:
    """Executa as buscas Tavily para cada ângulo da empresa."""
    resultados = {}
    for angulo, query in queries.items():
        try:
            resp = _tavily.search(query=query, max_results=3, search_depth="basic")
            trechos = [
                f"[{r.get('url','')}]\n{r.get('content','')[:350]}"
                for r in resp.get("results", [])
            ]
            resultados[angulo] = "\n\n".join(trechos) if trechos else "Sem resultados."
        except Exception:
            resultados[angulo] = "Erro na busca."
    return resultados


PROMPT_INTELIGENCIA = """
Você é um analista de inteligência comercial B2B especializado em cibersegurança.
Analise as informações públicas abaixo sobre a empresa "{empresa}" e extraia
insights estratégicos para um time de vendas de uma plataforma de segurança cibernética.

=== INCIDENTES E RISCOS ===
{incidentes}

=== INOVAÇÃO E INVESTIMENTO ===
{inovacao}

=== MOVIMENTO DE PESSOAS (RH/TI) ===
{movimento_rh}

=== CONFORMIDADE E REGULATÓRIO ===
{conformidade}

=== CRESCIMENTO E EXPANSÃO ===
{crescimento}

Retorne APENAS um JSON válido, sem markdown, sem explicações:
{{
  "incidentes": "resumo de incidentes públicos de segurança ou null",
  "inovacao": "resumo de investimentos em IA, cloud ou transformação digital ou null",
  "movimento_rh": "sinais de expansão em TI ou segurança ou null",
  "conformidade": "certificações em andamento ou desafios regulatórios ou null",
  "crescimento": "fusões, aquisições ou expansões recentes ou null",
  "resumo_vendas": "síntese em 3-4 frases para o promotor usar na abordagem. Conecte cada achado ao valor que a plataforma Vigil.AI entrega. Tom direto, orientado a negócio. Se não houver dados suficientes, sugira o ângulo de abertura mais seguro."
}}

Se um campo não tiver dados suficientes, use null. Nunca invente informações.
"""


def _sintetizar(empresa: str, resultados: dict) -> dict:
    """Usa o LLM para sintetizar os resultados em inteligência acionável."""
    prompt = PROMPT_INTELIGENCIA.format(
        empresa=empresa,
        **resultados,
    )
    resposta = _llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=700,
    )
    texto = resposta.choices[0].message.content.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fim    = texto.rfind("}") + 1
        if inicio >= 0 and fim > inicio:
            return json.loads(texto[inicio:fim])
        return {"resumo_vendas": "Não foi possível sintetizar. Pesquisa manual recomendada."}


# ------------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------------

def pesquisar_empresa(empresa: str) -> dict:
    """
    Pipeline completo de inteligência para uma empresa.
    Salva o resultado no Supabase e retorna o resumo.
    """
    db        = get_supabase()
    queries   = _queries_por_empresa(empresa)
    raw       = _pesquisar(queries)
    intel     = _sintetizar(empresa, raw)

    db.table("inteligencia_empresa").upsert({
        "empresa":       empresa,
        "incidentes":    intel.get("incidentes"),
        "inovacao":      intel.get("inovacao"),
        "movimento_rh":  intel.get("movimento_rh"),
        "conformidade":  intel.get("conformidade"),
        "crescimento":   intel.get("crescimento"),
        "resumo_vendas": intel.get("resumo_vendas"),
        "raw_data":      raw,
        "coletado_em":   datetime.utcnow().isoformat(),
    }, on_conflict="empresa").execute()

    return {"empresa": empresa, **intel}


def pesquisar_todas_empresas() -> list:
    """
    Pesquisa inteligência para todas as empresas com leads inscritos.
    Evita reprocessar empresas já pesquisadas nas últimas 24h.
    """
    db = get_supabase()

    empresas_leads = db.table("leads").select("empresa").execute().data
    empresas       = list({r["empresa"] for r in empresas_leads if r.get("empresa")})

    ja_pesquisadas = {
        r["empresa"]
        for r in db.table("inteligencia_empresa").select("empresa").execute().data
    }

    pendentes  = [e for e in empresas if e not in ja_pesquisadas]
    resultados = []

    for empresa in pendentes:
        try:
            resultado = pesquisar_empresa(empresa)
            resultados.append({"status": "ok", **resultado})
        except Exception as ex:
            resultados.append({"empresa": empresa, "status": "erro", "detalhe": str(ex)})

    return resultados


def obter_intel_empresa(empresa: str) -> dict | None:
    """
    Retorna inteligência salva de uma empresa.
    Usado pelo Promoter Brief e pelos agentes de e-mail.
    """
    db     = get_supabase()
    result = (
        db.table("inteligencia_empresa")
        .select("*")
        .ilike("empresa", f"%{empresa.strip()}%")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
