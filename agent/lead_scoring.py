"""
Lead Scoring — propensão de conversão para reunião comercial.

Orienta os promotores do evento a priorizar os leads com maior
chance de fechar negócio, funcionando como um semáforo:
  Alta  (>=65) → abordar primeiro
  Média (>=35) → abordar se sobrar tempo
  Baixa (<35)  → nutrir para eventos futuros

Modelo: Decision Tree (scikit-learn) — simples, interpretável e
auditável. Cada feature é uma função independente: adicionar uma
nova métrica no futuro é apenas escrever mais uma função e
incluí-la em `extrair_features()`. Nenhum outro código muda.

Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import os
import numpy as np
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from dotenv import load_dotenv
from db.client import get_supabase

load_dotenv()

# ------------------------------------------------------------------
# Dicionários de peso — alinhados ao perfil do público Vigil Summit
# ------------------------------------------------------------------

PESO_CARGO = {
    "ciso": 1.0, "cso": 1.0,
    "cto": 0.95, "diretor de ti": 0.9,
    "vp de tecnologia": 0.9, "head de segurança": 0.85,
    "gerente de ti": 0.7, "coordenador": 0.5,
    "analista sênior": 0.4, "analista": 0.3,
    "estagiário": 0.1,
}

PESO_SETOR = {
    "financeiro": 1.0, "bancário": 1.0,
    "saúde": 0.95, "governo": 0.9,
    "tecnologia": 0.85, "telecomunicações": 0.8,
    "varejo": 0.65, "manufatura": 0.6,
    "educação": 0.4,
}

PESO_TAMANHO = {
    "acima de 1000": 1.0,
    "500-1000": 0.85,
    "200-500": 0.7,
    "50-200": 0.45,
    "até 50": 0.2,
}

PESO_FORMACAO = {
    # Certificações diretas de segurança
    "cissp": 1.0, "cism": 1.0, "cisa": 0.95,
    "comptia security": 0.95, "ceh": 0.9,
    "iso 27001": 0.95, "soc 2": 0.9,
    # Gestão e liderança — sinal de futuro decisor
    "mba": 0.85, "gestão": 0.8, "administração": 0.75,
    "liderança": 0.75, "governança": 0.85,
    # TI e tecnologia — relevante mas genérico
    "segurança": 0.9, "cibersegurança": 1.0,
    "cloud": 0.75, "aws": 0.7, "azure": 0.7,
    "ti": 0.6, "tecnologia": 0.6, "sistemas": 0.55,
    # Áreas adjacentes — sinal de transição de carreira
    "compliance": 0.85, "privacidade": 0.8, "lgpd": 0.9,
    "risco": 0.8, "auditoria": 0.75,
}

PESO_AREA_INTERESSE = {
    "conformidade regulatória (lgpd, iso 27001, soc 2)": 1.0,
    "gestão de riscos corporativos": 0.95,
    "proteção de dados": 0.9,
    "automação de segurança": 0.85,
    "segurança em cloud": 0.8,
    "resposta a incidentes": 0.75,
    "liderança e gestão de times": 0.5,   # sinal de comprador futuro
}


# ------------------------------------------------------------------
# Funções de extração de features — ADICIONE NOVAS AQUI NO FUTURO
# ------------------------------------------------------------------

def _f_cargo(enriquecimento: dict) -> float:
    cargo = (enriquecimento.get("cargo_real") or "").lower()
    for chave, peso in PESO_CARGO.items():
        if chave in cargo:
            return peso
    return 0.3


def _f_setor(enriquecimento: dict) -> float:
    setor = (enriquecimento.get("setor") or "").lower()
    for chave, peso in PESO_SETOR.items():
        if chave in setor:
            return peso
    return 0.5


def _f_tamanho(enriquecimento: dict) -> float:
    tamanho = (enriquecimento.get("tamanho_empresa") or "").lower()
    for chave, peso in PESO_TAMANHO.items():
        if chave in tamanho:
            return peso
    return 0.5


def _f_areas_interesse(areas: list) -> float:
    """Retorna o maior peso entre as áreas selecionadas pelo lead."""
    if not areas:
        return 0.0
    pesos = []
    for area in areas:
        area_lower = area.lower()
        for chave, peso in PESO_AREA_INTERESSE.items():
            if chave in area_lower:
                pesos.append(peso)
                break
    return max(pesos) if pesos else 0.2


def _f_engajamento(lead_id: str, db) -> float:
    """Proporção de e-mails abertos ou clicados pelo lead."""
    result = db.table("comunicacoes").select("status").eq("lead_id", lead_id).execute()
    comunicacoes = result.data
    if not comunicacoes:
        return 0.0
    engajados = sum(1 for c in comunicacoes if c["status"] in ("aberto", "clicado"))
    return engajados / len(comunicacoes)


def _f_formacao_atual(formacao: str) -> float:
    """
    Campo livre — o lead descreve o que estuda com suas próprias palavras.
    Detecta palavras-chave de segurança, gestão e certificações.
    Um Analista de RH cursando MBA já sinaliza trajetória de liderança.
    """
    if not formacao:
        return 0.0
    formacao_lower = formacao.lower()
    pesos = [peso for chave, peso in PESO_FORMACAO.items() if chave in formacao_lower]
    return max(pesos) if pesos else 0.1


def _f_compareceu(lead_id: str, db) -> float:
    """1.0 se o lead compareceu ao evento, 0.0 caso contrário."""
    result = db.table("inscricoes").select("status").eq("lead_id", lead_id).execute()
    inscricoes = result.data
    if not inscricoes:
        return 0.0
    return 1.0 if any(i["status"] == "presente" for i in inscricoes) else 0.0


def extrair_features(lead_id: str, enriquecimento: dict, areas: list, formacao: str, db) -> np.ndarray:
    """
    Monta o vetor de features para o modelo.

    Para adicionar uma nova métrica no futuro:
      1. Escreva uma função _f_nova_metrica(...)
      2. Chame-a aqui e adicione o resultado à lista
      3. Adicione a nova coluna em DADOS_TREINO
    """
    return np.array([[
        _f_cargo(enriquecimento),
        _f_setor(enriquecimento),
        _f_tamanho(enriquecimento),
        _f_areas_interesse(areas),
        _f_formacao_atual(formacao),
        _f_engajamento(lead_id, db),
        _f_compareceu(lead_id, db),
    ]])


# ------------------------------------------------------------------
# Dataset sintético para treino
# [cargo, setor, tamanho, area_interesse, formacao, engajamento, compareceu, converteu]
# ------------------------------------------------------------------

DADOS_TREINO = [
    # Decisores claros, alto engajamento → alto potencial
    [1.0,  1.0,  1.0,  1.0,  0.95, 0.9, 1.0, 1],
    [0.95, 1.0,  0.85, 0.95, 0.85, 0.8, 1.0, 1],
    [0.9,  0.95, 1.0,  0.9,  0.9,  0.7, 1.0, 1],
    [0.85, 0.9,  0.85, 0.85, 0.8,  0.6, 1.0, 1],
    [1.0,  0.8,  0.7,  1.0,  0.0,  0.5, 0.0, 1],
    [0.7,  0.65, 0.7,  0.8,  0.75, 0.8, 1.0, 1],
    # Analista com sinais fortes de ascensão → comprador futuro
    [0.3,  0.85, 0.7,  1.0,  1.0,  0.6, 1.0, 1],  # fazendo CISSP
    [0.3,  0.6,  0.45, 0.9,  0.85, 0.5, 0.0, 1],  # MBA, engajado nos e-mails
    # Decisor mas sem engajamento → abordagem presencial
    [0.85, 0.8,  0.85, 0.8,  0.0,  0.2, 1.0, 1],  # converteu via evento presencial
    [0.7,  0.7,  0.7,  0.7,  0.0,  0.1, 0.0, 0],  # sem engajamento, não compareceu
    # Cargo operacional, sem sinais de crescimento → baixo potencial
    [0.3,  0.5,  0.45, 0.5,  0.1,  0.4, 0.0, 0],
    [0.7,  0.5,  0.7,  0.3,  0.0,  0.3, 0.0, 0],
    [0.5,  0.6,  0.45, 0.2,  0.1,  0.2, 0.0, 0],
    [0.3,  0.4,  0.2,  0.0,  0.0,  0.1, 0.0, 0],
    [0.3,  0.5,  0.45, 0.0,  0.0,  0.0, 0.0, 0],
    [0.85, 0.85, 0.85, 0.9,  0.85, 0.6, 1.0, 1],
    [0.9,  0.9,  1.0,  0.95, 0.9,  0.9, 1.0, 1],
    [0.1,  0.4,  0.2,  0.0,  0.0,  0.0, 0.0, 0],
    [0.5,  0.65, 0.45, 0.75, 0.6,  0.5, 0.0, 0],
]

_X = np.array([d[:7] for d in DADOS_TREINO])
_y = np.array([d[7]  for d in DADOS_TREINO])

_modelo = DecisionTreeClassifier(max_depth=4, random_state=42)
_modelo.fit(_X, _y)


# ------------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------------

def calcular_score(lead_id: str) -> dict:
    """
    Calcula o score de propensão do lead e salva em lead_scores.
    Retorna dict com score, rótulo e features usadas.
    """
    db = get_supabase()

    lead = db.table("leads").select("areas_interesse, formacao_atual").eq("id", lead_id).execute().data
    areas    = (lead[0].get("areas_interesse") or []) if lead else []
    formacao = (lead[0].get("formacao_atual") or "")  if lead else ""

    enr = db.table("enriquecimento").select("*").eq("lead_id", lead_id).execute().data
    enriquecimento = enr[0] if enr else {}

    features = extrair_features(lead_id, enriquecimento, areas, formacao, db)
    prob = _modelo.predict_proba(features)[0][1]
    score = round(prob * 100, 2)

    if score >= 65:
        rotulo = "Alta"
    elif score >= 35:
        rotulo = "Média"
    else:
        rotulo = "Baixa"

    db.table("lead_scores").upsert({
        "lead_id": lead_id,
        "score": score,
        "rotulo": rotulo,
        "calculado_em": datetime.utcnow().isoformat(),
    }, on_conflict="lead_id").execute()

    return {"lead_id": lead_id, "score": score, "rotulo": rotulo}


def recalcular_todos() -> list:
    """Recalcula o score de todos os leads com enriquecimento registrado."""
    db = get_supabase()
    leads = db.table("enriquecimento").select("lead_id").execute().data
    return [calcular_score(row["lead_id"]) for row in leads]
