"""
Test Suite — Vigil Sentinel Agent
Valida o sistema ponta a ponta sem alterar nenhum arquivo da aplicação.

Uso:
    python scripts/test_suite.py

Requer .env configurado com SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY.
Nenhuma chave é exibida no output.
"""

import sys
import io
import os
import urllib.request
import urllib.error

# Força UTF-8 no terminal Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Garante que o root do projeto está no path (script roda de qualquer diretório)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

# ──────────────────────────────────────────────────────────────────────────────
# Utilitários de output
# ──────────────────────────────────────────────────────────────────────────────

VERDE  = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
AZUL   = "\033[94m"
RESET  = "\033[0m"
NEGRITO = "\033[1m"

resultados = []


def ok(msg):
    print(f"  {VERDE}✅ PASS{RESET}  {msg}")
    resultados.append(("PASS", msg))


def fail(msg, detalhe=""):
    sufixo = f" — {detalhe}" if detalhe else ""
    print(f"  {VERMELHO}❌ FAIL{RESET}  {msg}{sufixo}")
    resultados.append(("FAIL", msg))


def warn(msg, detalhe=""):
    sufixo = f" — {detalhe}" if detalhe else ""
    print(f"  {AMARELO}⚠️  WARN{RESET}  {msg}{sufixo}")
    resultados.append(("WARN", msg))


def secao(titulo):
    print(f"\n{NEGRITO}{AZUL}{'─'*60}{RESET}")
    print(f"{NEGRITO}{AZUL}  {titulo}{RESET}")
    print(f"{NEGRITO}{AZUL}{'─'*60}{RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# 1. HTTP — App ao vivo no Streamlit Cloud
# ──────────────────────────────────────────────────────────────────────────────

secao("1. HTTP — Streamlit Cloud")

BASE_URL = "https://vigil-summit-landing.streamlit.app"

PAGINAS = [
    ("Landing page (inscrição)", BASE_URL + "/"),
    ("Dashboard de monitoramento", BASE_URL + "/Dashboard"),
    ("Política de privacidade", BASE_URL + "/Privacidade"),
]

for nome_pagina, url in PAGINAS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vigil-test-suite/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.getcode()
            if status == 200:
                ok(f"{nome_pagina} → HTTP {status}")
            else:
                warn(f"{nome_pagina} → HTTP {status} (inesperado)")
    except urllib.error.HTTPError as e:
        # 3xx são redirecionamentos válidos do Streamlit Cloud (HTTP → HTTPS, slug canônico)
        if 300 <= e.code < 400:
            ok(f"{nome_pagina} → HTTP {e.code} (redirect — app acessível)")
        else:
            fail(f"{nome_pagina}", f"HTTP {e.code}")
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "timed out" in reason.lower():
            warn(f"{nome_pagina}", "timeout — app pode estar em cold start (aguarde 30s e tente novamente)")
        else:
            fail(f"{nome_pagina}", reason)
    except Exception as e:
        fail(f"{nome_pagina}", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 2. Banco de dados — Supabase
# ──────────────────────────────────────────────────────────────────────────────

secao("2. Banco de Dados — Supabase")

try:
    from db.client import get_supabase
    db = get_supabase()
    ok("Conexão com Supabase estabelecida")
except Exception as e:
    fail("Conexão com Supabase", str(e))
    print(f"\n{VERMELHO}Sem conexão com o banco — testes de dados ignorados.{RESET}")
    db = None

if db:
    # Evento
    try:
        eventos = db.table("eventos").select("id, nome, data").execute().data
        if eventos:
            ok(f"Evento cadastrado: {eventos[0]['nome']} ({eventos[0]['data']})")
        else:
            fail("Nenhum evento encontrado na tabela eventos")
    except Exception as e:
        fail("Tabela eventos", str(e))

    # Leads
    try:
        leads = db.table("leads").select("id, nome, email, consentimento_em, opt_out").execute().data
        total = len(leads)
        if total >= 5:
            ok(f"Leads cadastrados: {total} (mínimo esperado: 5)")
        else:
            warn(f"Leads cadastrados: {total} (esperado ≥ 5)")

        sem_consentimento = [l["nome"] for l in leads if not l.get("consentimento_em")]
        if sem_consentimento:
            fail(f"Leads sem consentimento_em (LGPD Art. 8º)", ", ".join(sem_consentimento))
        else:
            ok("Todos os leads têm timestamp de consentimento (LGPD Art. 8º)")

        opt_out_indevido = [l["nome"] for l in leads if l.get("opt_out")]
        if opt_out_indevido:
            warn(f"Leads com opt_out=true", ", ".join(opt_out_indevido))
        else:
            ok("Nenhum lead com opt_out ativo")

    except Exception as e:
        fail("Tabela leads", str(e))
        leads = []

    # Inscrições
    try:
        inscricoes = db.table("inscricoes").select("lead_id, status").execute().data
        ids_leads = {l["id"] for l in leads}
        ids_inscritos = {i["lead_id"] for i in inscricoes}
        sem_inscricao = ids_leads - ids_inscritos
        if sem_inscricao:
            fail(f"Leads sem inscrição no evento", f"{len(sem_inscricao)} lead(s)")
        else:
            ok(f"Todos os leads têm inscrição no evento ({len(inscricoes)} inscrições)")
    except Exception as e:
        fail("Tabela inscricoes", str(e))

    # Enriquecimento
    try:
        enr = db.table("enriquecimento").select("lead_id, setor, cargo_real").execute().data
        if len(enr) >= 5:
            ok(f"Enriquecimento: {len(enr)} perfis registrados")
        else:
            warn(f"Enriquecimento: apenas {len(enr)} perfis (esperado 5)")
        sem_setor = [e for e in enr if not e.get("setor")]
        if sem_setor:
            warn(f"Perfis sem setor definido", f"{len(sem_setor)} registro(s)")
        else:
            ok("Todos os perfis têm setor definido (necessário para ML)")
    except Exception as e:
        fail("Tabela enriquecimento", str(e))

    # Lead Scores
    try:
        scores = db.table("lead_scores").select("lead_id, score, rotulo").execute().data
        if len(scores) >= 5:
            ok(f"Lead scores: {len(scores)} calculados")
        else:
            warn(f"Lead scores: apenas {len(scores)} (esperado 5)")

        rotulos_validos = {"Alta", "Média", "Baixa"}
        invalidos = [s for s in scores if s.get("rotulo") not in rotulos_validos]
        if invalidos:
            fail("Scores com rótulo inválido", f"{len(invalidos)} registro(s)")
        else:
            resumo = {r: sum(1 for s in scores if s["rotulo"] == r) for r in rotulos_validos}
            ok(f"Rótulos válidos — Alta: {resumo['Alta']} | Média: {resumo['Média']} | Baixa: {resumo['Baixa']}")

        scores_zero_todos = all(s.get("score") == 0 for s in scores)
        if scores_zero_todos:
            fail("Todos os scores estão zerados — modelo pode não ter rodado")
        else:
            score_vals = [s["score"] for s in scores if s.get("score") is not None]
            ok(f"Scores variados — min: {min(score_vals):.2f} | max: {max(score_vals):.2f}")

    except Exception as e:
        fail("Tabela lead_scores", str(e))

    # Promoter Briefs
    try:
        briefs = db.table("promoter_briefs").select("lead_id, rotulo, frase_abertura").execute().data
        altas = sum(1 for b in briefs if b.get("rotulo") == "Alta")
        if len(briefs) >= 4:
            ok(f"Promoter briefs gerados: {len(briefs)} ({altas} com rótulo Alta)")
        else:
            warn(f"Promoter briefs: apenas {len(briefs)} (esperado ≥ 4)")

        sem_frase = [b for b in briefs if not b.get("frase_abertura")]
        if sem_frase:
            warn(f"Briefs sem frase de abertura", f"{len(sem_frase)} registro(s)")
        else:
            ok("Todos os briefs têm frase de abertura personalizada")
    except Exception as e:
        fail("Tabela promoter_briefs", str(e))

    # Comunicações
    try:
        comuns = db.table("comunicacoes").select("fase, etapa, status").execute().data
        pre = [c for c in comuns if c["fase"] == "pre_evento"]
        pos = [c for c in comuns if c["fase"] == "pos_evento"]
        if pre:
            ok(f"Comunicações pré-evento: {len(pre)} registros")
        else:
            warn("Nenhuma comunicação pré-evento registrada")
        if pos:
            ok(f"Comunicações pós-evento: {len(pos)} registros")
        else:
            warn("Nenhuma comunicação pós-evento registrada (esperado se evento não ocorreu)")
    except Exception as e:
        fail("Tabela comunicacoes", str(e))

    # View analítica
    try:
        funil = db.table("vw_funil_leads").select("*").execute().data
        if funil:
            ok(f"View vw_funil_leads retorna {len(funil)} linha(s) — dashboard funcional")
        else:
            warn("View vw_funil_leads retornou vazia")
    except Exception as e:
        fail("View vw_funil_leads", str(e))

    # Inteligência de mercado
    try:
        intel = db.table("inteligencia_empresa").select("empresa, resumo_vendas").execute().data
        if intel:
            ok(f"Inteligência de mercado: {len(intel)} empresa(s) analisada(s)")
        else:
            warn("Nenhuma inteligência de mercado registrada")
    except Exception as e:
        fail("Tabela inteligencia_empresa", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 3. Imports dos módulos Python
# ──────────────────────────────────────────────────────────────────────────────

secao("3. Imports — Módulos da Aplicação")

MODULOS = [
    ("agent.enrichment",          "enriquecer_lead"),
    ("agent.lead_scoring",        "calcular_score"),
    ("agent.pre_event_sequence",  "enviar_etapa"),
    ("agent.post_event_sequence", "disparar_pos_evento"),
    ("agent.promoter_brief",      "gerar_briefs_prioritarios"),
    ("agent.market_intelligence", "pesquisar_todas_empresas"),
    ("agent.data_rights",         "exportar_dados_lead"),
]

for modulo, funcao in MODULOS:
    try:
        mod = __import__(modulo, fromlist=[funcao])
        fn = getattr(mod, funcao, None)
        if fn and callable(fn):
            ok(f"{modulo}.{funcao}() — importado e chamável")
        else:
            warn(f"{modulo} — função {funcao} não encontrada")
    except Exception as e:
        fail(f"{modulo}", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 4. Lógica do agente — testes funcionais leves
# ──────────────────────────────────────────────────────────────────────────────

secao("4. Lógica do Agente — Testes Funcionais")

if db:
    # 4a. Lead scoring — recalcula e verifica consistência
    try:
        from agent.lead_scoring import recalcular_todos
        resultados_score = recalcular_todos()
        scores_ok = [r for r in resultados_score if "score" in r]
        if scores_ok:
            ok(f"recalcular_todos() — {len(scores_ok)} scores recalculados com sucesso")
            for r in scores_ok:
                print(f"       {r['lead_id'][:8]}… → {r['score']} ({r['rotulo']})")
        else:
            warn("recalcular_todos() retornou lista vazia")
    except Exception as e:
        fail("agent.lead_scoring.recalcular_todos()", str(e))

    # 4b. Exportação de dados — LGPD Art. 18
    try:
        from agent.data_rights import exportar_dados_lead
        leads_db = db.table("leads").select("email, nome").limit(1).execute().data
        if leads_db:
            email_teste = leads_db[0]["email"]
            nome_teste  = leads_db[0]["nome"]
            export = exportar_dados_lead(email_teste)
            campos_esperados = {"lead", "enriquecimento", "inscricoes", "comunicacoes", "score"}
            campos_presentes = campos_esperados.issubset(export.keys())
            if "erro" not in export and campos_presentes:
                ok(f"exportar_dados_lead() — JSON completo para {nome_teste} (LGPD Art. 18)")
            else:
                warn("exportar_dados_lead() — retornou mas campos incompletos", str(export.keys()))
        else:
            warn("Nenhum lead disponível para testar exportação")
    except Exception as e:
        fail("agent.data_rights.exportar_dados_lead()", str(e))

    # 4c. Opt-out respeita bloqueio — verifica sem disparar e-mail
    try:
        from agent.pre_event_sequence import enviar_etapa
        lead_optout = db.table("leads").select("id").eq("opt_out", True).limit(1).execute().data
        if lead_optout:
            resultado = enviar_etapa(lead_optout[0]["id"], 1)
            if resultado.get("status") == "pulado":
                ok("opt_out bloqueou envio corretamente — LGPD respeitada")
            else:
                fail("opt_out não bloqueou envio", str(resultado))
        else:
            ok("Nenhum lead com opt_out=true — teste de bloqueio não aplicável")
    except Exception as e:
        fail("Teste opt_out pré-evento", str(e))


# ──────────────────────────────────────────────────────────────────────────────
# 5. Relatório final
# ──────────────────────────────────────────────────────────────────────────────

secao("RELATÓRIO FINAL")

total  = len(resultados)
passes = sum(1 for r in resultados if r[0] == "PASS")
warns  = sum(1 for r in resultados if r[0] == "WARN")
fails  = sum(1 for r in resultados if r[0] == "FAIL")

print(f"\n  Total de verificações : {total}")
print(f"  {VERDE}✅ PASS : {passes}{RESET}")
print(f"  {AMARELO}⚠️  WARN : {warns}{RESET}")
print(f"  {VERMELHO}❌ FAIL : {fails}{RESET}")

if fails == 0 and warns == 0:
    print(f"\n  {VERDE}{NEGRITO}Sistema 100% funcional — pronto para avaliação.{RESET}\n")
elif fails == 0:
    print(f"\n  {AMARELO}{NEGRITO}Sistema funcional com {warns} aviso(s) não crítico(s).{RESET}\n")
else:
    print(f"\n  {VERMELHO}{NEGRITO}{fails} falha(s) encontrada(s) — verifique antes da entrega.{RESET}\n")
    print(f"  {VERMELHO}Falhas:{RESET}")
    for tipo, msg in resultados:
        if tipo == "FAIL":
            print(f"    • {msg}")
    print()

sys.exit(0 if fails == 0 else 1)
