"""
Landing page de inscrição — Vigil Summit: Segurança para a Era da IA.

Capta nome, e-mail, cargo, empresa, LinkedIn, áreas de interesse
e formação atual. Ao submeter, salva o lead no Supabase e dispara
o enriquecimento de perfil em background.
"""

import streamlit as st
from datetime import datetime
from db.client import get_supabase

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
]

with st.form("inscricao", clear_on_submit=True):
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
    campos_obrigatorios = {"Nome": nome, "E-mail": email, "Cargo": cargo, "Empresa": empresa}
    faltando = [k for k, v in campos_obrigatorios.items() if not v.strip()]

    if faltando:
        st.error(f"Preencha os campos obrigatórios: {', '.join(faltando)}")

    elif not consentimento:
        st.error("É necessário aceitar os termos de consentimento para prosseguir (Art. 8º LGPD).")

    elif not areas:
        st.error("Selecione ao menos uma área de interesse.")

    else:
        try:
            db = get_supabase()

            # Busca o evento ativo
            evento = db.table("eventos").select("id").limit(1).execute().data
            evento_id = evento[0]["id"] if evento else None

            # Salva o lead (ignora duplicata por e-mail)
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

            # Cria a inscrição no evento
            if evento_id:
                db.table("inscricoes").upsert({
                    "lead_id": lead_id,
                    "evento_id": evento_id,
                    "status": "inscrito",
                }, on_conflict="lead_id,evento_id").execute()

            st.success(f"**Inscrição confirmada, {nome.split()[0]}!** 🎉")
            st.info(
                "Em breve você receberá um e-mail de confirmação com os detalhes do evento. "
                "Fique de olho na sua caixa de entrada."
            )

        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                st.warning("Este e-mail já está cadastrado. Você já está na lista! 😊")
            else:
                st.error("Ocorreu um erro ao processar sua inscrição. Tente novamente em instantes.")

# ------------------------------------------------------------------
# Rodapé
# ------------------------------------------------------------------
st.divider()
st.markdown(
    "<center><small>Vigil Summit 2026 · Realização Vigil.AI · "
    "Dúvidas? contato@vigilsummit.com.br</small></center>",
    unsafe_allow_html=True,
)
