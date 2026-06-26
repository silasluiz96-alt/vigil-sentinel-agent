"""
Landing page de inscrição — Vigil Summit: Segurança para a Era da IA.

Capta nome, e-mail, cargo, empresa, LinkedIn, áreas de interesse
e formação atual. Ao submeter, salva o lead no Supabase e dispara
o enriquecimento de perfil em background.
"""

import streamlit as st
import threading
from datetime import datetime
from db.client import get_supabase


def _pipeline_background(lead_id: str) -> None:
    """Roda enriquecimento → scoring → brief (se Alta) → e-mail em background."""
    try:
        from agent.enrichment import enriquecer_lead
        enriquecer_lead(lead_id)
    except Exception:
        pass

    try:
        from agent.lead_scoring import calcular_score
        resultado = calcular_score(lead_id)
        rotulo = resultado.get("rotulo", "")
    except Exception:
        rotulo = ""

    if rotulo == "Alta":
        try:
            from agent.promoter_brief import gerar_brief_lead
            gerar_brief_lead(lead_id)
        except Exception:
            pass

    try:
        from agent.pre_event_sequence import enviar_etapa
        enviar_etapa(lead_id, 1)
    except Exception:
        pass

st.set_page_config(
    page_title="Vigil Summit 2026 — Inscrição",
    page_icon="🛡️",
    layout="centered",
)

# ------------------------------------------------------------------
# Estilo visual alinhado ao universo de cibersegurança
# ------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0a0e1a; }
    .block-container { padding-top: 2rem; }
    h1 { color: #00d4ff; font-size: 2.2rem; }
    h3 { color: #c9d1d9; }
    .stButton > button {
        background-color: #00d4ff;
        color: #0a0e1a;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        border: none;
        width: 100%;
    }
    .stButton > button:hover { background-color: #00b8d9; }
    .badge {
        display: inline-block;
        background: #1a2236;
        border: 1px solid #00d4ff33;
        border-radius: 6px;
        padding: 0.3rem 0.8rem;
        color: #00d4ff;
        font-size: 0.85rem;
        margin: 0.2rem;
    }
    .card-sucesso {
        background: linear-gradient(135deg, #0d2137 0%, #0a1a2e 100%);
        border: 1px solid #00d4ff55;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        margin: 1.5rem 0;
    }
    .card-sucesso h2 { color: #00d4ff; margin-bottom: 0.5rem; }
    .card-sucesso p { color: #c9d1d9; margin: 0.3rem 0; }
    .card-erro {
        background: #1a0d0d;
        border: 1px solid #ff4b4b88;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 0.5rem 0;
        color: #ff6b6b;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Cabeçalho
# ------------------------------------------------------------------
st.markdown("# 🛡️ Vigil Summit 2026")
st.markdown("### Segurança para a Era da IA")
st.markdown("""
**20 e 21 de setembro de 2026 · São Paulo, SP · Evento exclusivo — 120 vagas**

Um dia inteiro dedicado a CISOs, CTOs e gestores de risco que precisam
tomar decisões de segurança em um mundo onde a IA redefine as ameaças a cada semana.
""")

st.markdown("""
<div>
  <span class="badge">🔐 ISO 27001 · LGPD · SOC 2</span>
  <span class="badge">🤖 IA & Cibersegurança</span>
  <span class="badge">📊 Demos ao vivo</span>
  <span class="badge">🤝 Networking executivo</span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------
# Card de confirmação (exibido após inscrição bem-sucedida)
# ------------------------------------------------------------------
if st.session_state.get("inscricao_ok"):
    nome_confirmado = st.session_state.get("nome_confirmado", "")
    st.markdown(f"""
    <div class="card-sucesso">
        <div style="font-size:3rem">🛡️</div>
        <h2>Inscrição confirmada, {nome_confirmado}!</h2>
        <p>Você está na lista do Vigil Summit 2026.</p>
        <p style="margin-top:1rem; color:#00d4ff;">
            📧 Um e-mail de boas-vindas com todos os detalhes do evento<br>
            foi enviado para você. Fique de olho na caixa de entrada.
        </p>
        <p style="margin-top:1rem; font-size:0.85rem; color:#6b7280;">
            20 e 21 de setembro de 2026 · São Paulo, SP
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Indicar um colega →"):
        del st.session_state["inscricao_ok"]
        del st.session_state["nome_confirmado"]
        st.rerun()

    st.divider()
    st.markdown(
        "<center><small>Vigil Summit 2026 · Realização Vigil.AI · "
        "Dúvidas? contato@vigilsummit.com.br</small></center>",
        unsafe_allow_html=True,
    )
    st.stop()

# ------------------------------------------------------------------
# Formulário de inscrição
# ------------------------------------------------------------------
st.markdown("## Garanta sua vaga")

AREAS_INTERESSE = [
    "Conformidade regulatória (LGPD, ISO 27001, SOC 2)",
    "Gestão de riscos corporativos",
    "Proteção de dados",
    "Automação de segurança",
    "Segurança em cloud",
    "Resposta a incidentes",
    "Liderança e gestão de times",
    "Governança de TI",
    "Gestão de identidade e acesso (IAM)",
    "Segurança em aplicações (AppSec)",
    "Threat Intelligence",
    "DevSecOps",
    "Segurança em OT/IoT",
    "Continuidade de negócios (BCP/DRP)",
    "Arquitetura Zero Trust",
]

# Erros da submissão anterior (preservados entre reruns)
erros = st.session_state.get("erros_form", [])
if erros:
    for erro in erros:
        st.markdown(f'<div class="card-erro">⚠️ {erro}</div>', unsafe_allow_html=True)
    st.session_state["erros_form"] = []

with st.form("inscricao", clear_on_submit=False):
    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome completo *", placeholder="Ana Silva")
        cargo = st.text_input("Cargo atual *", placeholder="CISO, Diretor de TI, Analista...")
        empresa = st.text_input("Empresa *", placeholder="Nome da sua empresa")

    with col2:
        email = st.text_input("E-mail corporativo *", placeholder="ana@empresa.com.br")
        telefone = st.text_input("Telefone", placeholder="+55 (11) 9 9999-9999")
        linkedin = st.text_input("LinkedIn (opcional)", placeholder="linkedin.com/in/seu-perfil")

    areas = st.multiselect(
        "Áreas de interesse *",
        options=AREAS_INTERESSE,
        help="Selecione todas que fazem sentido para o seu momento profissional.",
    )

    formacao_atual = st.text_input(
        "Está estudando algo atualmente? (opcional)",
        placeholder="Ex: MBA em Gestão de TI, CISSP em andamento, Pós em Segurança da Informação...",
        help="Campo livre — compartilhe cursos, certificações ou graduações em andamento.",
    )

    st.markdown("---")
    consentimento = st.checkbox(
        "Concordo com o tratamento dos meus dados pessoais conforme a "
        "[Política de Privacidade](Privacidade) e a LGPD (Lei 13.709/2018), "
        "para fins exclusivos de comunicação relacionada ao Vigil Summit. "
        "Sei que posso revogar este consentimento a qualquer momento.",
        value=False,
    )
    st.markdown(
        "<small>🔒 Seus dados são armazenados com segurança e não serão compartilhados "
        "com terceiros. Utilizamos scoring automatizado para personalizar comunicações — "
        "você pode solicitar revisão humana a qualquer momento pelo e-mail "
        "privacidade@vigilsummit.com.br</small>",
        unsafe_allow_html=True,
    )

    submitted = st.form_submit_button("Confirmar inscrição →")

# ------------------------------------------------------------------
# Processamento do formulário
# ------------------------------------------------------------------
if submitted:
    erros = []
    campos_obrigatorios = {"Nome": nome, "E-mail": email, "Cargo": cargo, "Empresa": empresa}
    faltando = [k for k, v in campos_obrigatorios.items() if not v.strip()]
    if faltando:
        erros.append(f"Preencha os campos obrigatórios: {', '.join(faltando)}")
    if not consentimento:
        erros.append("É necessário aceitar os termos de consentimento para prosseguir (Art. 8º LGPD).")
    if not areas:
        erros.append("Selecione ou digite ao menos uma área de interesse.")

    if erros:
        st.session_state["erros_form"] = erros
        st.rerun()
    else:
        try:
            db = get_supabase()

            evento = db.table("eventos").select("id").limit(1).execute().data
            evento_id = evento[0]["id"] if evento else None

            resultado = db.table("leads").upsert({
                "nome": nome.strip(),
                "email": email.strip().lower(),
                "telefone": telefone.strip() or None,
                "cargo": cargo.strip(),
                "empresa": empresa.strip(),
                "linkedin": linkedin.strip() or None,
                "areas_interesse": areas,
                "formacao_atual": formacao_atual.strip() or None,
                "consentimento_em": datetime.utcnow().isoformat(),
            }, on_conflict="email").execute()

            lead_id = resultado.data[0]["id"]

            if evento_id:
                db.table("inscricoes").upsert({
                    "lead_id": lead_id,
                    "evento_id": evento_id,
                    "status": "inscrito",
                }, on_conflict="lead_id,evento_id").execute()

            threading.Thread(target=_pipeline_background, args=(lead_id,), daemon=True).start()

            st.session_state["inscricao_ok"] = True
            st.session_state["nome_confirmado"] = nome.strip().split()[0]
            st.rerun()

        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                st.session_state["erros_form"] = ["Este e-mail já está cadastrado. Você já está na lista!"]
            else:
                st.session_state["erros_form"] = ["Ocorreu um erro ao processar sua inscrição. Tente novamente em instantes."]
            st.rerun()

# ------------------------------------------------------------------
# Rodapé
# ------------------------------------------------------------------
st.divider()
st.markdown(
    "<center><small>Vigil Summit 2026 · Realização Vigil.AI · "
    "Dúvidas? contato@vigilsummit.com.br</small></center>",
    unsafe_allow_html=True,
)
