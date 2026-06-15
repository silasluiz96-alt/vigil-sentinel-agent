"""
Régua Pós-Evento — Fase 4 do funil.

Dois fluxos paralelos baseados no comparecimento ao evento:

PRESENTES (compareceram):
  Etapa 1 — 1 dia depois  : agradecimento + recapitulação personalizada
  Etapa 2 — 3 dias depois : proposta direta de reunião comercial
  Etapa 3 — 7 dias depois : último contato (encerramento ou abertura futura)

NO-SHOWS (inscreveram mas não foram):
  Etapa 1 — 1 dia depois  : "sentimos sua falta" + conteúdo do evento
  Etapa 2 — 5 dias depois : proposta de demo individual do que perdeu

O tom de cada e-mail é calibrado pelo score do lead:
  Alta  (>=65) → proposta direta, urgência leve, foco em ROI
  Média (>=35) → abordagem consultiva, foco em aprendizado e caso de uso
  Baixa (<35)  → nutrição de longo prazo, sem pressão comercial

Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from db.client import get_supabase

load_dotenv()

_llm = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MAILTRAP_HOST = "sandbox.smtp.mailtrap.io"
MAILTRAP_PORT = 587
MAILTRAP_USER = os.environ.get("MAILTRAP_USER", "")
MAILTRAP_PASS = os.environ.get("MAILTRAP_PASS", "")
REMETENTE     = "contato@vigilsummit.com.br"


# ------------------------------------------------------------------
# Definição das etapas por fluxo
# ------------------------------------------------------------------

ETAPAS_PRESENTES = {
    1: {
        "assunto":     "Foi ótimo ter você no Vigil Summit 🛡️",
        "assunto_alt": "Obrigado pela sua presença — veja o que destacamos para você",
        "dias_apos":   1,
    },
    2: {
        "assunto":     "Que tal continuarmos a conversa? 30 minutos podem mudar sua estratégia",
        "assunto_alt": "Uma reunião rápida sobre o que você viu no Vigil Summit",
        "dias_apos":   3,
    },
    3: {
        "assunto":     "Última mensagem — e uma porta aberta",
        "assunto_alt": "Encerrando o contato por ora, mas a Vigil.AI segue à disposição",
        "dias_apos":   7,
    },
}

ETAPAS_NOSHOW = {
    1: {
        "assunto":     "Sentimos sua falta no Vigil Summit — mas trouxemos o evento até você",
        "assunto_alt": "Não conseguiu vir? Preparamos um resumo exclusivo para você",
        "dias_apos":   1,
    },
    2: {
        "assunto":     "A demo que você não viu — que tal 20 minutos?",
        "assunto_alt": "Uma segunda chance de conhecer a Vigil.AI de perto",
        "dias_apos":   5,
    },
}


# ------------------------------------------------------------------
# Tom por score — calibra a intensidade comercial do e-mail
# ------------------------------------------------------------------

TOM_POR_SCORE = {
    "Alta":  "tom direto e orientado a negócio. Mencione ROI, redução de risco e vantagem competitiva. Proponha uma reunião de 30 minutos com o time comercial da Vigil.AI de forma clara e com senso de oportunidade.",
    "Média": "tom consultivo. Foque em aprendizado, casos de uso do setor do lead e como a Vigil.AI resolve problemas concretos. A proposta de reunião deve aparecer como uma conversa, não uma venda.",
    "Baixa": "tom de relacionamento de longo prazo. Sem pressão comercial. Ofereça conteúdo relevante (relatório, artigo, estudo de caso) e deixe uma porta aberta para o futuro.",
}

CONTEXTO_PRESENTE = {
    1: """
Escreva um e-mail de agradecimento pelo comparecimento ao Vigil Summit.
Recapitule brevemente os temas do evento (IA e cibersegurança, demos da plataforma,
painéis com CISOs e CTOs) conectando com as áreas de interesse específicas do lead.
Use o perfil abaixo para tornar a recapitulação pessoal — mencione algo que
provavelmente foi relevante para alguém com esse background.
Tom: caloroso, grato, sem pressão comercial nesta etapa.
""",
    2: """
Escreva um e-mail propondo uma reunião comercial de 30 minutos com o time da Vigil.AI.
Use o contexto do evento como gancho — o lead viu a demo, ouviu os painéis.
Agora é hora de aprofundar como a plataforma resolve o problema específico dele.
{tom}
Use o perfil abaixo para personalizar o gancho com a realidade do lead.
""",
    3: """
Escreva o último e-mail da sequência. Dois objetivos simultâneos:
1. Encerrar o contato sem pressão, reconhecendo que o momento pode não ser agora
2. Deixar uma porta aberta clara — "quando fizer sentido, estaremos aqui"
Inclua um recurso de valor: ofereça enviar um relatório sobre segurança no setor do lead.
{tom}
""",
}

CONTEXTO_NOSHOW = {
    1: """
Escreva um e-mail para alguém que se inscreveu mas não compareceu ao Vigil Summit.
Tom: compreensivo, sem julgamento. Imprevistos acontecem.
Ofereça um resumo dos principais insights do evento.
Mencione que a plataforma Vigil.AI ficou à disposição para demonstrações individuais.
Use o perfil abaixo para conectar o conteúdo do evento com o interesse específico do lead.
""",
    2: """
Escreva um e-mail propondo uma demo individual de 20 minutos da plataforma Vigil.AI.
Posicione como uma oportunidade exclusiva de ver o que foi apresentado no evento,
no ritmo e com foco nas necessidades específicas do lead.
{tom}
Use o perfil abaixo para personalizar a proposta.
""",
}

PROMPT_EMAIL = """
Você é o assistente de comunicação comercial da Vigil.AI.
Escreva um e-mail em português brasileiro para o seguinte lead:

Nome: {nome}
Cargo: {cargo}
Empresa: {empresa}
Setor: {setor}
Score de propensão: {score} ({rotulo})
Perfil: {resumo_perfil}
Áreas de interesse: {areas_interesse}

Instrução específica para este e-mail:
{instrucao}

Retorne APENAS o corpo do e-mail em HTML simples (sem <html>, <head> ou <body>).
Máximo 220 palavras. Tom: profissional, humano, personalizado — nunca genérico.
Assine como: Equipe Vigil.AI

Inclua SEMPRE ao final o seguinte rodapé de conformidade LGPD (não altere o texto):

<hr style="border:none;border-top:1px solid #eee;margin:24px 0"/>
<p style="font-size:11px;color:#999;text-align:center;">
Você recebe este e-mail por ter participado ou se inscrito no Vigil Summit 2026.<br>
Para cancelar o recebimento, <a href="https://vigilsummit.com.br/descadastro?email={email}">clique aqui</a>.<br>
Seus dados são tratados conforme a <a href="https://vigilsummit.com.br/privacidade">Política de Privacidade</a> e a LGPD (Lei 13.709/2018).
</p>
"""


# ------------------------------------------------------------------
# Funções auxiliares (reaproveitadas do módulo pré-evento)
# ------------------------------------------------------------------

def _abriu_etapa_anterior(lead_id: str, etapa: int, fluxo: str, db) -> bool:
    if etapa <= 1:
        return True
    resultado = (
        db.table("comunicacoes")
        .select("status")
        .eq("lead_id", lead_id)
        .eq("etapa", etapa - 1)
        .eq("fase", "pos_evento")
        .execute()
    )
    if not resultado.data:
        return False
    return resultado.data[0]["status"] in ("aberto", "clicado")


def _gerar_corpo(lead: dict, enriquecimento: dict, score_data: dict, instrucao: str) -> str:
    rotulo = score_data.get("rotulo", "Média")
    prompt = PROMPT_EMAIL.format(
        nome=lead.get("nome", ""),
        cargo=lead.get("cargo") or enriquecimento.get("cargo_real") or "",
        empresa=lead.get("empresa") or enriquecimento.get("empresa_confirmada") or "",
        setor=enriquecimento.get("setor") or "",
        score=score_data.get("score", 0),
        rotulo=rotulo,
        resumo_perfil=enriquecimento.get("resumo_perfil") or "Profissional de TI ou segurança.",
        areas_interesse=", ".join(lead.get("areas_interesse") or []) or "Segurança e tecnologia",
        instrucao=instrucao,
    )
    resposta = _llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500,
    )
    return resposta.choices[0].message.content.strip()


def _enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = REMETENTE
        msg["To"]      = destinatario
        msg.attach(MIMEText(corpo_html, "html"))
        with smtplib.SMTP(MAILTRAP_HOST, MAILTRAP_PORT) as server:
            server.starttls()
            server.login(MAILTRAP_USER, MAILTRAP_PASS)
            server.sendmail(REMETENTE, destinatario, msg.as_string())
        return True
    except Exception:
        return False


def _registrar(lead_id: str, evento_id: str, etapa: int, assunto: str, corpo: str, enviado: bool, db):
    db.table("comunicacoes").insert({
        "lead_id":    lead_id,
        "evento_id":  evento_id,
        "fase":       "pos_evento",
        "etapa":      etapa,
        "canal":      "email",
        "assunto":    assunto,
        "corpo":      corpo,
        "status":     "enviado" if enviado else "sem_resposta",
        "enviado_em": datetime.utcnow().isoformat(),
    }).execute()


# ------------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------------

def enviar_etapa_presente(lead_id: str, etapa: int) -> dict:
    """Envia uma etapa da régua pós-evento para lead que compareceu."""
    db        = get_supabase()
    lead      = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        return {"status": "erro", "motivo": "Lead não encontrado"}
    lead      = lead[0]

    config    = ETAPAS_PRESENTES[etapa]
    abriu     = _abriu_etapa_anterior(lead_id, etapa, "presente", db)
    assunto   = config["assunto"] if abriu else config["assunto_alt"]

    enr       = db.table("enriquecimento").select("*").eq("lead_id", lead_id).execute().data
    enr       = enr[0] if enr else {}
    score_data = db.table("lead_scores").select("*").eq("lead_id", lead_id).execute().data
    score_data = score_data[0] if score_data else {"score": 0, "rotulo": "Média"}

    rotulo    = score_data.get("rotulo", "Média")
    tom       = TOM_POR_SCORE.get(rotulo, TOM_POR_SCORE["Média"])
    instrucao = CONTEXTO_PRESENTE[etapa].format(tom=tom) if "{tom}" in CONTEXTO_PRESENTE[etapa] else CONTEXTO_PRESENTE[etapa]

    corpo     = _gerar_corpo(lead, enr, score_data, instrucao)
    evento    = db.table("eventos").select("id").limit(1).execute().data
    evento_id = evento[0]["id"] if evento else None
    enviado   = _enviar_email(lead["email"], assunto, corpo)
    _registrar(lead_id, evento_id, etapa, assunto, corpo, enviado, db)

    return {"status": "enviado" if enviado else "falha", "lead_id": lead_id, "etapa": etapa, "fluxo": "presente", "score": rotulo}


def enviar_etapa_noshow(lead_id: str, etapa: int) -> dict:
    """Envia uma etapa da régua pós-evento para lead que não compareceu."""
    db        = get_supabase()
    lead      = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        return {"status": "erro", "motivo": "Lead não encontrado"}
    lead      = lead[0]

    config    = ETAPAS_NOSHOW[etapa]
    abriu     = _abriu_etapa_anterior(lead_id, etapa, "noshow", db)
    assunto   = config["assunto"] if abriu else config["assunto_alt"]

    enr       = db.table("enriquecimento").select("*").eq("lead_id", lead_id).execute().data
    enr       = enr[0] if enr else {}
    score_data = db.table("lead_scores").select("*").eq("lead_id", lead_id).execute().data
    score_data = score_data[0] if score_data else {"score": 0, "rotulo": "Média"}

    rotulo    = score_data.get("rotulo", "Média")
    tom       = TOM_POR_SCORE.get(rotulo, TOM_POR_SCORE["Média"])
    instrucao = CONTEXTO_NOSHOW[etapa].format(tom=tom) if "{tom}" in CONTEXTO_NOSHOW[etapa] else CONTEXTO_NOSHOW[etapa]

    corpo     = _gerar_corpo(lead, enr, score_data, instrucao)
    evento    = db.table("eventos").select("id").limit(1).execute().data
    evento_id = evento[0]["id"] if evento else None
    enviado   = _enviar_email(lead["email"], assunto, corpo)
    _registrar(lead_id, evento_id, etapa, assunto, corpo, enviado, db)

    return {"status": "enviado" if enviado else "falha", "lead_id": lead_id, "etapa": etapa, "fluxo": "noshow", "score": rotulo}


def disparar_pos_evento() -> dict:
    """
    Dispara a etapa 1 do pós-evento para todos os leads,
    separando automaticamente presentes de no-shows.
    Deve ser chamado no dia seguinte ao evento.
    """
    db         = get_supabase()
    inscricoes = db.table("inscricoes").select("lead_id, status").execute().data

    presentes  = [i["lead_id"] for i in inscricoes if i["status"] == "presente"]
    no_shows   = [i["lead_id"] for i in inscricoes if i["status"] == "no_show"]

    return {
        "presentes": [enviar_etapa_presente(lid, 1) for lid in presentes],
        "no_shows":  [enviar_etapa_noshow(lid, 1)   for lid in no_shows],
    }
