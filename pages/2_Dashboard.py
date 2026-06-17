"""
Dashboard de Monitoramento — Vigil Sentinel Agent.

Painel central para a equipe Vigil.AI e para a Pareto avaliarem
o funil de leads em tempo real:

  - Métricas do funil: inscritos → confirmados → presentes → reuniões
  - Ranking de leads por score de propensão (ML)
  - Status de comunicações por fase
  - Cards de Promoter Brief (roteiro de abordagem por lead)
  - Inteligência de mercado por empresa

Consome as tabelas Supabase sem expor dados sensíveis na URL.
Arquitetura compatível com Claude (Anthropic). Chave OpenAI em uso
por disponibilidade durante o desenvolvimento.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from db.client import get_supabase

load_dotenv()

# ------------------------------------------------------------------
# Configuração da página
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Dashboard — Vigil Sentinel",
    page_icon="🛡️",
    layout="wide",
)

# ------------------------------------------------------------------
# Login — acesso restrito à equipe Vigil.AI
# ------------------------------------------------------------------

STAFF_CREDENTIALS = dict(st.secrets.get("staff", {}))

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("""
    <div style="display:flex;justify-content:center;margin-top:80px">
      <div style="background:#0d1628;border:1px solid #1e3a5f;border-radius:16px;
                  padding:48px 40px;width:100%;max-width:420px;text-align:center">
        <div style="font-size:48px;margin-bottom:8px">🛡️</div>
        <h2 style="color:#38bdf8;margin-bottom:4px">Vigil Sentinel</h2>
        <p style="color:#64748b;font-size:13px;margin-bottom:32px">
          Acesso restrito · Somente Staff do evento
        </p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            email_login = st.text_input("E-mail", placeholder="staff@vigilsummit.com.br")
            senha_login = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar →", use_container_width=True)

    if entrar:
        if STAFF_CREDENTIALS.get(email_login) == senha_login:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Credenciais inválidas.")

    st.stop()

# ------------------------------------------------------------------
# A partir daqui só quem autenticou chega
# ------------------------------------------------------------------

# Botão de logout no sidebar
with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# Tema cybersegurança — mesma identidade visual da landing page
st.markdown("""
<style>
  /* Fundo escuro */
  .stApp { background-color: #0a0f1e; color: #e2e8f0; }
  section[data-testid="stSidebar"] { background-color: #0d1628; }

  /* Cards de métricas */
  [data-testid="metric-container"] {
    background: linear-gradient(135deg, #0d1628 0%, #1a2744 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 16px;
  }
  [data-testid="metric-container"] label { color: #94a3b8 !important; }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #38bdf8 !important; font-size: 2rem !important;
  }

  /* Tabelas */
  .stDataFrame { border-radius: 8px; overflow: hidden; }

  /* Badges de score */
  .badge-alta   { background:#065f46; color:#34d399; padding:3px 10px;
                  border-radius:12px; font-size:12px; font-weight:600; }
  .badge-media  { background:#78350f; color:#fbbf24; padding:3px 10px;
                  border-radius:12px; font-size:12px; font-weight:600; }
  .badge-baixa  { background:#450a0a; color:#f87171; padding:3px 10px;
                  border-radius:12px; font-size:12px; font-weight:600; }

  /* Promoter card */
  .promoter-card {
    background: linear-gradient(135deg, #0d1628 0%, #1a2744 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .promoter-card h4 { color: #38bdf8; margin-bottom: 8px; }
  .promoter-card .section-label { color: #64748b; font-size: 11px;
                                   text-transform: uppercase; letter-spacing: 1px; }
  .promoter-card .section-value { color: #e2e8f0; margin-bottom: 12px; }

  h1, h2, h3 { color: #e2e8f0 !important; }
  .stTabs [data-baseweb="tab"] { color: #94a3b8; }
  .stTabs [aria-selected="true"] { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Conexão com Supabase (cacheada por 30 s para não sobrecarregar)
# ------------------------------------------------------------------

@st.cache_data(ttl=30)
def carregar_funil():
    db   = get_supabase()
    rows = db.table("vw_funil_leads").select("*").execute().data
    return pd.DataFrame(rows) if rows else pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_briefs():
    db   = get_supabase()
    rows = (
        db.table("promoter_briefs")
        .select("*, leads(nome, cargo, empresa)")
        .order("score", desc=True)
        .execute()
        .data
    )
    return rows or []

@st.cache_data(ttl=30)
def carregar_comunicacoes():
    db   = get_supabase()
    rows = db.table("comunicacoes").select("fase, etapa, status").execute().data
    return pd.DataFrame(rows) if rows else pd.DataFrame()

@st.cache_data(ttl=30)
def carregar_intel():
    db   = get_supabase()
    rows = (
        db.table("inteligencia_empresa")
        .select("empresa, resumo_vendas, inovacao, incidentes, coletado_em")
        .order("coletado_em", desc=True)
        .execute()
        .data
    )
    return rows or []

@st.cache_data(ttl=30)
def carregar_reunioes():
    db   = get_supabase()
    rows = db.table("reunioes").select("status").execute().data
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ------------------------------------------------------------------
# Cabeçalho
# ------------------------------------------------------------------

col_logo, col_title = st.columns([1, 9])
with col_logo:
    st.markdown("## 🛡️")
with col_title:
    st.markdown("## Vigil Sentinel — Dashboard de Monitoramento")
    st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · Evento: Vigil Summit 2026")

st.divider()

# ------------------------------------------------------------------
# Carregamento de dados
# ------------------------------------------------------------------

df_funil = carregar_funil()
comunicacoes = carregar_comunicacoes()
reunioes     = carregar_reunioes()

# ------------------------------------------------------------------
# Seção 1 — Métricas do funil
# ------------------------------------------------------------------

st.markdown("### Funil de Leads")

total       = len(df_funil) if not df_funil.empty else 0
confirmados = int(df_funil[df_funil["status_inscricao"].isin(["confirmado","presente"])].shape[0]) if not df_funil.empty else 0
presentes   = int(df_funil[df_funil["status_inscricao"] == "presente"].shape[0]) if not df_funil.empty else 0
reunioes_ag = int(df_funil["reuniao_agendada"].sum()) if not df_funil.empty and "reuniao_agendada" in df_funil.columns else 0

alta  = int(df_funil[df_funil["rotulo"] == "Alta"].shape[0])  if not df_funil.empty else 0
media = int(df_funil[df_funil["rotulo"] == "Média"].shape[0]) if not df_funil.empty else 0
baixa = int(df_funil[df_funil["rotulo"] == "Baixa"].shape[0]) if not df_funil.empty else 0

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("Inscritos",    total)
m2.metric("Confirmados",  confirmados)
m3.metric("Presentes",    presentes)
m4.metric("Reuniões",     reunioes_ag)
m5.metric("Score Alta",   alta,  delta=None)
m6.metric("Score Média",  media, delta=None)
m7.metric("Score Baixa",  baixa, delta=None)

# Taxa de conversão visual
if total > 0:
    taxa_confirm = round(confirmados / total * 100, 1)
    taxa_present = round(presentes   / total * 100, 1)
    taxa_reuniao = round(reunioes_ag / total * 100, 1) if total > 0 else 0

    st.markdown(f"""
    <div style="display:flex;gap:24px;margin:8px 0 0 0;">
      <span style="color:#94a3b8;font-size:13px;">
        Confirmação: <strong style="color:#38bdf8">{taxa_confirm}%</strong>
      </span>
      <span style="color:#94a3b8;font-size:13px;">
        Presença: <strong style="color:#38bdf8">{taxa_present}%</strong>
      </span>
      <span style="color:#94a3b8;font-size:13px;">
        Conversão em reunião: <strong style="color:#34d399">{taxa_reuniao}%</strong>
      </span>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ------------------------------------------------------------------
# Seção 2 — Abas principais
# ------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "🏆 Ranking de Leads",
    "📧 Comunicações",
    "🎯 Promoter Briefs",
    "🔍 Inteligência de Mercado",
])

# ── Tab 1: Ranking de leads ──────────────────────────────────────

with tab1:
    if df_funil.empty:
        st.info("Nenhum lead cadastrado ainda. Acesse a Landing Page para começar.")
    else:
        df_rank = df_funil.copy()

        # Formatação de colunas
        df_rank["Score"] = df_rank["score"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "—"
        )

        def badge(rotulo):
            if rotulo == "Alta":
                return '<span class="badge-alta">Alta</span>'
            elif rotulo == "Média":
                return '<span class="badge-media">Média</span>'
            elif rotulo == "Baixa":
                return '<span class="badge-baixa">Baixa</span>'
            return "—"

        df_rank["Propensão"] = df_rank["rotulo"].apply(badge)

        df_rank["Engajamento"] = df_rank.apply(
            lambda r: f"{int(r['emails_engajados'])}/{int(r['emails_enviados'])}"
            if pd.notna(r.get("emails_enviados")) else "—", axis=1
        )

        df_rank["Reunião"] = df_rank["reuniao_agendada"].apply(
            lambda x: "✅" if x else "—"
        )

        # Filtro rápido por score
        filtro = st.selectbox(
            "Filtrar por propensão",
            ["Todos", "Alta", "Média", "Baixa"],
        )
        if filtro != "Todos":
            df_rank = df_rank[df_rank["rotulo"] == filtro]

        df_rank = df_rank.sort_values("score", ascending=False)

        colunas = ["nome", "cargo", "empresa", "setor", "Score", "Propensão",
                   "status_inscricao", "Engajamento", "Reunião"]
        colunas_existentes = [c for c in colunas if c in df_rank.columns]

        st.write(
            df_rank[colunas_existentes].rename(columns={
                "nome": "Nome", "cargo": "Cargo", "empresa": "Empresa",
                "setor": "Setor", "status_inscricao": "Status",
            }).to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

# ── Tab 2: Comunicações ──────────────────────────────────────────

with tab2:
    if comunicacoes.empty:
        st.info("Nenhuma comunicação enviada ainda.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**Pré-evento**")
            df_pre = comunicacoes[comunicacoes["fase"] == "pre_evento"]
            if not df_pre.empty:
                resumo_pre = (
                    df_pre.groupby(["etapa", "status"])
                    .size()
                    .reset_index(name="quantidade")
                    .rename(columns={"etapa": "Etapa", "status": "Status", "quantidade": "Qtd"})
                )
                st.dataframe(resumo_pre, use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhum e-mail pré-evento enviado.")

        with col_b:
            st.markdown("**Pós-evento**")
            df_pos = comunicacoes[comunicacoes["fase"] == "pos_evento"]
            if not df_pos.empty:
                resumo_pos = (
                    df_pos.groupby(["etapa", "status"])
                    .size()
                    .reset_index(name="quantidade")
                    .rename(columns={"etapa": "Etapa", "status": "Status", "quantidade": "Qtd"})
                )
                st.dataframe(resumo_pos, use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhum e-mail pós-evento enviado.")

        st.divider()

        # Taxa de abertura geral
        total_env  = len(comunicacoes)
        total_ab   = len(comunicacoes[comunicacoes["status"].isin(["aberto","clicado"])])
        taxa_ab    = round(total_ab / total_env * 100, 1) if total_env > 0 else 0

        st.metric("Taxa de abertura geral", f"{taxa_ab}%",
                  help="E-mails com status 'aberto' ou 'clicado' ÷ total enviado")

# ── Tab 3: Promoter Briefs ───────────────────────────────────────

with tab3:
    briefs = carregar_briefs()

    if not briefs:
        st.info("""
        Nenhum Promoter Brief gerado ainda.
        Execute `agent/promoter_brief.py → gerar_briefs_prioritarios()` antes do evento.
        """)
    else:
        # Filtro por score
        opcao = st.selectbox(
            "Exibir leads com propensão",
            ["Todos", "Alta", "Média", "Baixa"],
            key="filtro_brief",
        )

        for b in briefs:
            rotulo = b.get("rotulo", "—")
            if opcao != "Todos" and rotulo != opcao:
                continue

            lead   = b.get("leads") or {}
            nome   = lead.get("nome", "—")
            cargo  = lead.get("cargo", "—")
            empresa = lead.get("empresa", "—")
            score  = b.get("score", 0)

            badge_html = (
                '<span class="badge-alta">Alta</span>'   if rotulo == "Alta"  else
                '<span class="badge-media">Média</span>' if rotulo == "Média" else
                '<span class="badge-baixa">Baixa</span>'
            )

            st.markdown(f"""
            <div class="promoter-card">
              <h4>{nome} — {cargo} @ {empresa}</h4>
              <div style="margin-bottom:12px">
                {badge_html}
                <span style="color:#64748b;font-size:13px;margin-left:12px">Score: {score:.1f}</span>
              </div>

              <div class="section-label">Frase de abertura</div>
              <div class="section-value">{b.get('frase_abertura','—')}</div>

              <div class="section-label">Demo recomendada</div>
              <div class="section-value">{b.get('demo_recomendada','—')}</div>

              <div class="section-label">Argumento principal</div>
              <div class="section-value">{b.get('argumento','—')}</div>

              <div class="section-label">Sinais de interesse a observar</div>
              <div class="section-value">{b.get('sinais_interesse','—')}</div>

              <div class="section-label">Como fechar</div>
              <div class="section-value">{b.get('como_fechar','—')}</div>

              <div class="section-label">⚠️ Alertas</div>
              <div class="section-value" style="color:#f87171">{b.get('alertas','—')}</div>
            </div>
            """, unsafe_allow_html=True)

# ── Tab 4: Inteligência de Mercado ───────────────────────────────

with tab4:
    intel_rows = carregar_intel()

    if not intel_rows:
        st.info("""
        Nenhuma inteligência coletada ainda.
        Execute `agent/market_intelligence.py → pesquisar_todas_empresas()`.
        """)
    else:
        for item in intel_rows:
            with st.expander(f"🏢 {item.get('empresa','—')}", expanded=False):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Síntese para o promotor:**\n\n{item.get('resumo_vendas','Sem dados.')}")
                with col2:
                    coletado = item.get("coletado_em","")
                    if coletado:
                        try:
                            dt = datetime.fromisoformat(coletado.replace("Z",""))
                            st.caption(f"Coletado em {dt.strftime('%d/%m/%Y %H:%M')}")
                        except Exception:
                            pass

                if item.get("inovacao"):
                    st.markdown(f"**Inovação:** {item['inovacao']}")
                if item.get("incidentes"):
                    st.markdown(f"**Incidentes/Riscos:** {item['incidentes']}")

st.divider()

# ------------------------------------------------------------------
# Rodapé
# ------------------------------------------------------------------

st.markdown(
    "<center><small style='color:#475569'>"
    "Vigil Sentinel Agent · Desenvolvido por Silas Luiz Bom Fim · "
    "Powered by LangGraph + Supabase + OpenAI GPT-4o-mini"
    "</small></center>",
    unsafe_allow_html=True,
)
