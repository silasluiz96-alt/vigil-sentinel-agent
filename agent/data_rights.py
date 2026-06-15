"""
Direitos do Titular — LGPD Art. 17º a 22º.

Módulo responsável por atender solicitações dos titulares de dados:
acesso, correção, exclusão, portabilidade e revogação de consentimento.

O DELETE CASCADE já está configurado no schema — excluir o lead
remove automaticamente enriquecimento, inscrições, comunicações e scores.
"""

import json
from datetime import datetime
from db.client import get_supabase


def exportar_dados_lead(email: str) -> dict:
    """
    Portabilidade (Art. 18º, V): retorna todos os dados do titular
    em formato aberto (dict → JSON).
    """
    db   = get_supabase()
    lead = db.table("leads").select("*").eq("email", email.lower()).execute().data
    if not lead:
        return {"erro": "Lead não encontrado para este e-mail."}
    lead = lead[0]
    lid  = lead["id"]

    enr    = db.table("enriquecimento").select("*").eq("lead_id", lid).execute().data
    insc   = db.table("inscricoes").select("*").eq("lead_id", lid).execute().data
    comuns = db.table("comunicacoes").select("*").eq("lead_id", lid).execute().data
    score  = db.table("lead_scores").select("*").eq("lead_id", lid).execute().data

    return {
        "exportado_em":   datetime.utcnow().isoformat(),
        "lead":           lead,
        "enriquecimento": enr[0] if enr else None,
        "inscricoes":     insc,
        "comunicacoes":   comuns,
        "score":          score[0] if score else None,
    }


def excluir_lead(email: str) -> dict:
    """
    Exclusão (Art. 18º, VI): remove o lead e todos os dados associados.
    O DELETE CASCADE no schema garante remoção em cascata de todas as tabelas.
    """
    db   = get_supabase()
    lead = db.table("leads").select("id").eq("email", email.lower()).execute().data
    if not lead:
        return {"status": "nao_encontrado", "mensagem": "Nenhum dado encontrado para este e-mail."}

    lid = lead[0]["id"]
    db.table("leads").delete().eq("id", lid).execute()

    return {
        "status":    "excluido",
        "mensagem":  "Todos os seus dados foram removidos permanentemente.",
        "data":      datetime.utcnow().isoformat(),
    }


def revogar_consentimento(email: str) -> dict:
    """
    Revogação (Art. 8º, §5º): descadastra o lead de futuras comunicações.
    Mantém o registro mínimo necessário para não reenviar (soft opt-out).
    """
    db   = get_supabase()
    lead = db.table("leads").select("id").eq("email", email.lower()).execute().data
    if not lead:
        return {"status": "nao_encontrado"}

    lid = lead[0]["id"]

    # Cancela inscrições ativas sem excluir o registro (evita reenvio acidental)
    db.table("inscricoes").update({"status": "no_show"}).eq("lead_id", lid).execute()

    return {
        "status":   "consentimento_revogado",
        "mensagem": "Você não receberá mais comunicações do Vigil Summit. "
                    "Para exclusão completa dos dados, use a opção de exclusão.",
        "data":     datetime.utcnow().isoformat(),
    }
