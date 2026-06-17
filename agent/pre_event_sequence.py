"""
Régua Pré-Evento — Fase 3 do funil.

Sequência de 5 e-mails entre a inscrição e o dia do evento.
Objetivo: manter o lead engajado, confirmar presença e reduzir
no-show para menos de 30% (meta: taxa de comparecimento > 70%).

Regras de negócio:
  - Cada e-mail usa o resumo_perfil do enriquecimento para personalizar
    a abertura — o lead sente que a comunicação é para ele, não para uma lista
  - Etapa 2 e 3: se múltiplos leads da mesma empresa estiverem inscritos,
    sugere organização de carona (sem citar nomes — privacidade preservada)
  - Quem não abriu o e-mail anterior recebe o próximo com assunto alternativo
  - Quem não confirma presença até 3 dias antes entra em fluxo de risco
    de no-show com tom mais direto
  - Etapas 4 e 5 só são enviadas para quem confirmou presença

Canal: e-mail via Mailtrap (sandbox para demonstração).
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

# ------------------------------------------------------------------
# Configuração Mailtrap (sandbox — e-mails capturados para demo)
# ------------------------------------------------------------------
MAILTRAP_HOST = "sandbox.smtp.mailtrap.io"
MAILTRAP_PORT = 587
MAILTRAP_USER = os.environ.get("MAILTRAP_USER", "")
MAILTRAP_PASS = os.environ.get("MAILTRAP_PASS", "")
REMETENTE     = "contato@vigilsummit.com.br"


# ------------------------------------------------------------------
# Definição das etapas da régua
# ------------------------------------------------------------------

ETAPAS = {
    1: {
        "assunto":      "Sua inscrição no Vigil Summit está confirmada ✅",
        "assunto_alt":  "Bem-vindo ao Vigil Summit — veja o que esperar",
        "momento":      "imediato após inscrição",
        "apenas_confirmados": False,
    },
    2: {
        "assunto":      "Vigil Summit: o que você vai encontrar em 7 dias",
        "assunto_alt":  "7 dias para o maior evento de segurança do ano",
        "momento":      "7 dias antes do evento",
        "apenas_confirmados": False,
    },
    3: {
        "assunto":      "Confirme sua presença — faltam 3 dias",
        "assunto_alt":  "Só mais 3 dias: você vem ao Vigil Summit?",
        "momento":      "3 dias antes do evento",
        "apenas_confirmados": False,
    },
    4: {
        "assunto":      "Tudo pronto para amanhã? Veja os detalhes finais",
        "assunto_alt":  "Amanhã é o Vigil Summit — não perca nada",
        "momento":      "1 dia antes do evento",
        "apenas_confirmados": True,
    },
    5: {
        "assunto":      "🛡️ Hoje é o dia — Vigil Summit começa às 9h",
        "assunto_alt":  "O Vigil Summit começa hoje. Veja como chegar",
        "momento":      "manhã do evento",
        "apenas_confirmados": True,
    },
}

# ------------------------------------------------------------------
# Templates de contexto por etapa — alimentam o LLM
# ------------------------------------------------------------------

CONTEXTO_ETAPA = {
    1: """
Escreva um e-mail de boas-vindas caloroso confirmando a inscrição do lead no Vigil Summit.
Mencione que o evento acontece em 20 e 21 de setembro de 2026 em São Paulo.
Use o perfil abaixo para personalizar a abertura — faça o lead sentir que o e-mail
foi escrito especificamente para ele, não para uma lista genérica.
Finalize convidando o lead a salvar a data na agenda.
""",
    2: """
Escreva um e-mail de aquecimento faltando 7 dias para o evento.
Destaque três pilares do Vigil Summit: painéis sobre IA e cibersegurança,
demos ao vivo da plataforma Vigil.AI e networking com CISOs e CTOs.
Use o perfil abaixo para conectar o conteúdo do evento com os interesses específicos do lead.
{dica_carona}
""",
    3: """
Escreva um e-mail pedindo confirmação de presença faltando 3 dias.
Seja direto mas cordial. Inclua um botão/link simbólico de confirmação.
Use o perfil abaixo para reforçar por que este evento é relevante para este lead especificamente.
Se o lead ainda não confirmou, use um tom de urgência leve — as vagas são limitadas.
{dica_carona}
""",
    4: """
Escreva um e-mail de lembrete final para o dia seguinte ao evento.
Inclua: endereço do evento (São Paulo, SP), horário de início (9h),
o que trazer (documento de identidade, cartão de visita).
Tom: animado, preparatório, sem pressão.
Use o perfil abaixo para personalizar com algo relacionado às áreas de interesse do lead.
""",
    5: """
Escreva um e-mail curto e energético para a manhã do evento.
Confirme horário (9h), mencione que o credenciamento abre às 8h30.
Finalize com uma frase motivadora conectada ao universo de segurança cibernética.
Tom: breve, empolgante, profissional.
""",
}

DICA_CARONA = """
Inclua também, de forma natural e discreta no corpo do e-mail, uma sugestão de que
outros profissionais da mesma empresa também estão inscritos e que seria ótimo
se organizarem para chegar juntos ao evento — sem citar nomes.
Tom: amigável, prático, sem pressão.
"""

PROMPT_EMAIL = """
Você é o assistente de comunicação do Vigil Summit 2026.
Escreva um e-mail profissional em português brasileiro para o seguinte lead:

Nome: {nome}
Perfil: {resumo_perfil}
Áreas de interesse: {areas_interesse}
Formação atual: {formacao_atual}

Instrução específica para este e-mail:
{instrucao}

Retorne APENAS o corpo do e-mail em HTML simples (sem <html>, <head> ou <body>).
Máximo 250 palavras. Tom: profissional, humano, nunca genérico.

Inclua SEMPRE ao final, após o conteúdo principal, o seguinte rodapé de conformidade LGPD
(não altere o texto, apenas insira-o):

<hr style="border:none;border-top:1px solid #eee;margin:24px 0"/>
<p style="font-size:11px;color:#999;text-align:center;">
Você recebe este e-mail por ter se inscrito no Vigil Summit 2026.<br>
Para cancelar o recebimento, <a href="https://vigilsummit.com.br/descadastro?email={email}">clique aqui</a>.<br>
Seus dados são tratados conforme a <a href="https://vigilsummit.com.br/privacidade">Política de Privacidade</a> e a LGPD (Lei 13.709/2018).
</p>
"""


# ------------------------------------------------------------------
# Funções auxiliares
# ------------------------------------------------------------------

def _tem_colegas_na_empresa(lead_id: str, empresa: str, db) -> bool:
    """Verifica se há outros leads da mesma empresa inscritos no evento."""
    if not empresa:
        return False
    resultado = (
        db.table("leads")
        .select("id")
        .ilike("empresa", f"%{empresa.strip()}%")
        .neq("id", lead_id)
        .execute()
    )
    return len(resultado.data) >= 1


def _abriu_etapa_anterior(lead_id: str, etapa: int, db) -> bool:
    """Retorna True se o lead abriu o e-mail da etapa anterior."""
    if etapa <= 1:
        return True
    resultado = (
        db.table("comunicacoes")
        .select("status")
        .eq("lead_id", lead_id)
        .eq("etapa", etapa - 1)
        .eq("fase", "pre_evento")
        .execute()
    )
    if not resultado.data:
        return False
    return resultado.data[0]["status"] in ("aberto", "clicado")


def _esta_confirmado(lead_id: str, db) -> bool:
    resultado = (
        db.table("inscricoes")
        .select("status")
        .eq("lead_id", lead_id)
        .execute()
    )
    if not resultado.data:
        return False
    return resultado.data[0]["status"] in ("confirmado", "presente")


def _gerar_corpo_email(lead: dict, enriquecimento: dict, etapa: int, com_carona: bool) -> str:
    """Usa o LLM para gerar o corpo do e-mail personalizado."""
    dica = DICA_CARONA if com_carona else ""
    instrucao = CONTEXTO_ETAPA[etapa].format(dica_carona=dica) if "{dica_carona}" in CONTEXTO_ETAPA[etapa] else CONTEXTO_ETAPA[etapa]

    prompt = PROMPT_EMAIL.format(
        nome=lead.get("nome", ""),
        email=lead.get("email", ""),
        resumo_perfil=enriquecimento.get("resumo_perfil") or "Profissional de TI ou segurança.",
        areas_interesse=", ".join(lead.get("areas_interesse") or []) or "Segurança e tecnologia",
        formacao_atual=lead.get("formacao_atual") or "Não informado",
        instrucao=instrucao,
    )

    resposta = _llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600,
    )
    return resposta.choices[0].message.content.strip()


def _enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    """Envia o e-mail via Mailtrap (sandbox para demonstração)."""
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


def _registrar_comunicacao(lead_id: str, evento_id: str, etapa: int, assunto: str, corpo: str, enviado: bool, db):
    """Salva o registro da comunicação no banco independente do resultado."""
    db.table("comunicacoes").insert({
        "lead_id":   lead_id,
        "evento_id": evento_id,
        "fase":      "pre_evento",
        "etapa":     etapa,
        "canal":     "email",
        "assunto":   assunto,
        "corpo":     corpo,
        "status":    "enviado" if enviado else "sem_resposta",
        "enviado_em": datetime.utcnow().isoformat(),
    }).execute()


# ------------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------------

def enviar_etapa(lead_id: str, etapa: int) -> dict:
    """
    Envia uma etapa específica da régua pré-evento para um lead.
    Aplica todas as regras de negócio antes de enviar.
    """
    db = get_supabase()

    lead = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        return {"status": "erro", "motivo": "Lead não encontrado"}
    lead = lead[0]

    if lead.get("opt_out"):
        return {"status": "pulado", "motivo": "Lead optou por não receber comunicações (LGPD)"}

    config = ETAPAS[etapa]

    # Etapas 4 e 5 só para confirmados
    if config["apenas_confirmados"] and not _esta_confirmado(lead_id, db):
        return {"status": "pulado", "motivo": "Lead não confirmado — etapa reservada para confirmados"}

    # Assunto alternativo para quem não abriu o anterior
    abriu_anterior = _abriu_etapa_anterior(lead_id, etapa, db)
    assunto = config["assunto"] if abriu_anterior else config["assunto_alt"]

    # Verifica colegas da mesma empresa (etapas 2 e 3)
    empresa    = lead.get("empresa") or ""
    com_carona = etapa in (2, 3) and _tem_colegas_na_empresa(lead_id, empresa, db)

    enriquecimento = db.table("enriquecimento").select("*").eq("lead_id", lead_id).execute().data
    enriquecimento = enriquecimento[0] if enriquecimento else {}

    corpo = _gerar_corpo_email(lead, enriquecimento, etapa, com_carona)

    evento = db.table("eventos").select("id").limit(1).execute().data
    evento_id = evento[0]["id"] if evento else None

    enviado = _enviar_email(lead["email"], assunto, corpo)
    _registrar_comunicacao(lead_id, evento_id, etapa, assunto, corpo, enviado, db)

    return {
        "status":     "enviado" if enviado else "falha_envio",
        "lead_id":    lead_id,
        "etapa":      etapa,
        "assunto":    assunto,
        "com_carona": com_carona,
    }


def disparar_etapa_para_todos(etapa: int) -> list:
    """
    Dispara uma etapa da régua para todos os leads inscritos.
    Deve ser chamada pelo scheduler no momento correto.
    """
    db = get_supabase()
    leads = db.table("inscricoes").select("lead_id").execute().data
    return [enviar_etapa(row["lead_id"], etapa) for row in leads]
