"""
Promoter Brief — roteiro de abordagem personalizado por lead.

Gerado pelo LangGraph antes do evento, entrega ao promotor um cartão
completo para cada lead de score Alto ou Médio:

  - Quem é a pessoa (cargo, empresa, trajetória)
  - O que a empresa está fazendo no mercado (inteligência de mercado)
  - Qual demo recomendar com base nos interesses do lead
  - A frase de abertura ideal para iniciar a conversa
  - O argumento de negócio mais relevante para fechar a reunião

O promotor abre o celular, vê o card e já sabe exatamente como agir.
Nenhuma abordagem genérica — cada conversa começa no contexto certo.

LangGraph orquestra três nós em sequência:
  1. coletar_contexto  → lê lead, enriquecimento, score e intel de empresa
  2. gerar_brief       → LLM sintetiza tudo num roteiro acionável
  3. salvar_brief      → persiste no Supabase para o dashboard consumir

Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import os
import json
from typing import TypedDict
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END
from db.client import get_supabase
from agent.market_intelligence import obter_intel_empresa

load_dotenv()

_llm = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# ------------------------------------------------------------------
# Estado compartilhado entre os nós do grafo
# ------------------------------------------------------------------

class BriefState(TypedDict):
    lead_id:        str
    lead:           dict
    enriquecimento: dict
    score:          dict
    intel_empresa:  dict
    brief:          dict
    erro:           str


# ------------------------------------------------------------------
# Nó 1 — Coleta de contexto
# ------------------------------------------------------------------

def coletar_contexto(state: BriefState) -> BriefState:
    """Lê todos os dados disponíveis sobre o lead e sua empresa."""
    db      = get_supabase()
    lead_id = state["lead_id"]

    lead = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        return {**state, "erro": f"Lead {lead_id} não encontrado."}
    lead = lead[0]

    enr = db.table("enriquecimento").select("*").eq("lead_id", lead_id).execute().data
    enr = enr[0] if enr else {}

    score = db.table("lead_scores").select("*").eq("lead_id", lead_id).execute().data
    score = score[0] if score else {"score": 0, "rotulo": "Média"}

    empresa       = lead.get("empresa") or enr.get("empresa_confirmada") or ""
    intel_empresa = obter_intel_empresa(empresa) or {}

    return {
        **state,
        "lead":           lead,
        "enriquecimento": enr,
        "score":          score,
        "intel_empresa":  intel_empresa,
        "erro":           "",
    }


# ------------------------------------------------------------------
# Nó 2 — Geração do brief
# ------------------------------------------------------------------

PROMPT_BRIEF = """
Você é um coach de vendas B2B especializado em cibersegurança.
Crie um roteiro de abordagem PERSONALIZADO e ACIONÁVEL para o promotor
abordar este lead durante o Vigil Summit 2026.

=== PERFIL DO LEAD ===
Nome: {nome}
Cargo: {cargo}
Empresa: {empresa}
Setor: {setor}
Tamanho: {tamanho}
Score de propensão: {score} ({rotulo})
Áreas de interesse: {areas_interesse}
Formação atual: {formacao_atual}
Perfil resumido: {resumo_perfil}
Atividade LinkedIn: {linkedin_atividade}

=== INTELIGÊNCIA DA EMPRESA ===
Inovação recente: {inovacao}
Incidentes/riscos: {incidentes}
Movimento de RH em TI: {movimento_rh}
Conformidade/regulatório: {conformidade}
Crescimento: {crescimento}

Retorne APENAS um JSON válido, sem markdown:
{{
  "frase_abertura": "primeira frase para iniciar a conversa — específica, não genérica. Use algo da inteligência da empresa ou do perfil do lead.",
  "demo_recomendada": "qual funcionalidade da Vigil.AI demonstrar primeiro e por quê",
  "argumento_principal": "o argumento de negócio mais relevante para ESTE lead especificamente",
  "sinais_de_interesse": "o que observar durante a conversa que indica abertura para agendar reunião",
  "como_fechar": "abordagem sugerida para propor a reunião comercial de forma natural",
  "alertas": "o que evitar nesta abordagem específica (ex: não mencionar concorrente X, lead parece cético com hype)"
}}
"""


def gerar_brief(state: BriefState) -> BriefState:
    """Usa o LLM para gerar o roteiro de abordagem personalizado."""
    if state.get("erro"):
        return state

    lead  = state["lead"]
    enr   = state["enriquecimento"]
    score = state["score"]
    intel = state["intel_empresa"]

    prompt = PROMPT_BRIEF.format(
        nome=lead.get("nome", ""),
        cargo=lead.get("cargo") or enr.get("cargo_real") or "",
        empresa=lead.get("empresa") or enr.get("empresa_confirmada") or "",
        setor=enr.get("setor") or "",
        tamanho=enr.get("tamanho_empresa") or "",
        score=score.get("score", 0),
        rotulo=score.get("rotulo", "Média"),
        areas_interesse=", ".join(lead.get("areas_interesse") or []) or "Não informado",
        formacao_atual=lead.get("formacao_atual") or "Não informado",
        resumo_perfil=enr.get("resumo_perfil") or "",
        linkedin_atividade=enr.get("linkedin_atividade") or "Não encontrado",
        inovacao=intel.get("inovacao") or "Sem dados",
        incidentes=intel.get("incidentes") or "Sem dados",
        movimento_rh=intel.get("movimento_rh") or "Sem dados",
        conformidade=intel.get("conformidade") or "Sem dados",
        crescimento=intel.get("crescimento") or "Sem dados",
    )

    resposta = _llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=700,
    )

    texto = resposta.choices[0].message.content.strip()
    try:
        brief = json.loads(texto)
    except json.JSONDecodeError:
        inicio = texto.find("{")
        fim    = texto.rfind("}") + 1
        brief  = json.loads(texto[inicio:fim]) if inicio >= 0 and fim > inicio else {}

    return {**state, "brief": brief}


# ------------------------------------------------------------------
# Nó 3 — Persistência
# ------------------------------------------------------------------

def salvar_brief(state: BriefState) -> BriefState:
    """Salva o brief no Supabase para o dashboard consumir."""
    if state.get("erro") or not state.get("brief"):
        return state

    db      = get_supabase()
    lead_id = state["lead_id"]
    brief   = state["brief"]
    score   = state["score"]

    db.table("promoter_briefs").upsert({
        "lead_id":           lead_id,
        "score":             score.get("score", 0),
        "rotulo":            score.get("rotulo", "Média"),
        "frase_abertura":    brief.get("frase_abertura"),
        "demo_recomendada":  brief.get("demo_recomendada"),
        "argumento":         brief.get("argumento_principal"),
        "sinais_interesse":  brief.get("sinais_de_interesse"),
        "como_fechar":       brief.get("como_fechar"),
        "alertas":           brief.get("alertas"),
        "gerado_em":         datetime.utcnow().isoformat(),
    }, on_conflict="lead_id").execute()

    return state


# ------------------------------------------------------------------
# Construção do grafo LangGraph
# ------------------------------------------------------------------

def _construir_grafo() -> StateGraph:
    grafo = StateGraph(BriefState)
    grafo.add_node("coletar_contexto", coletar_contexto)
    grafo.add_node("gerar_brief",      gerar_brief)
    grafo.add_node("salvar_brief",     salvar_brief)

    grafo.set_entry_point("coletar_contexto")
    grafo.add_edge("coletar_contexto", "gerar_brief")
    grafo.add_edge("gerar_brief",      "salvar_brief")
    grafo.add_edge("salvar_brief",     END)

    return grafo.compile()


_pipeline = _construir_grafo()


# ------------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------------

def gerar_brief_lead(lead_id: str) -> dict:
    """Gera e salva o Promoter Brief para um lead específico."""
    estado_inicial: BriefState = {
        "lead_id":        lead_id,
        "lead":           {},
        "enriquecimento": {},
        "score":          {},
        "intel_empresa":  {},
        "brief":          {},
        "erro":           "",
    }
    resultado = _pipeline.invoke(estado_inicial)

    if resultado.get("erro"):
        return {"status": "erro", "motivo": resultado["erro"]}

    return {"status": "ok", "lead_id": lead_id, **resultado["brief"]}


def gerar_briefs_prioritarios() -> list:
    """
    Gera briefs para todos os leads com score Alto ou Médio.
    Executar antes do evento para o dashboard estar pronto
    quando os promotores chegarem.
    """
    db = get_supabase()
    scores = (
        db.table("lead_scores")
        .select("lead_id, rotulo")
        .in_("rotulo", ["Alta", "Média"])
        .execute()
        .data
    )

    return [
        gerar_brief_lead(row["lead_id"])
        for row in scores
    ]
