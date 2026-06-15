# Vigil Sentinel Agent

**Case técnico — vaga AI Engineer @ Pareto**
Candidato: Silas Luiz Bom Fim

Sistema autônomo de gestão de funil para o evento **Vigil Summit 2026 — Segurança para a Era da IA** (120 participantes, público B2B: CISOs, CTOs e Diretores de TI).

O agente gerencia o ciclo completo do lead: captação → enriquecimento → engajamento pré-evento → follow-up pós-evento, com o objetivo final de agendar reuniões comerciais.

---

## Arquitetura

```
landing.py                  ← Formulário de captação (Streamlit)
│
├── db/schema.sql            ← Schema PostgreSQL (Supabase)
│   └── vw_funil_leads       ← View analítica que alimenta o dashboard
│
├── agent/
│   ├── enrichment.py        ← Fase 2: enriquecimento via Tavily + LLM
│   ├── lead_scoring.py      ← ML: Decision Tree (scikit-learn), 7 features
│   ├── pre_event_sequence.py← Fase 3: régua de e-mails pré-evento (5 etapas)
│   ├── post_event_sequence.py← Fase 4: follow-up pós-evento (presentes + no-shows)
│   ├── market_intelligence.py← Inteligência de mercado por empresa (5 ângulos)
│   ├── promoter_brief.py    ← LangGraph: roteiro de abordagem por lead
│   └── data_rights.py       ← LGPD: exportação, exclusão e revogação
│
└── pages/
    ├── Dashboard.py         ← Painel de monitoramento do funil (Streamlit)
    └── Privacidade.py       ← Política de privacidade (LGPD)
```

### Diagrama do funil

```
[Lead se inscreve] → [Enriquecimento web] → [Score ML]
        ↓                                         ↓
[Régua pré-evento]                     [Promoter Brief gerado]
        ↓                                         ↓
  [Evento]  ────────────────────────────→ [Promotor aborda lead]
  /        \                              com roteiro personalizado
Presente  No-show
   ↓          ↓
[Follow-up 3 etapas] [Follow-up 2 etapas]
        ↓
[Reunião comercial agendada]
```

---

## Stack e justificativas

| Tecnologia | Função | Por que essa escolha |
|---|---|---|
| **Streamlit** | UI (landing + dashboard) | Deploy imediato, zero configuração de frontend |
| **Supabase (PostgreSQL)** | Banco de dados | REST nativo, RLS, triggers e views — sem ORM necessário |
| **LangGraph** | Orquestração do Promoter Brief | Grafo de estados tipado, rastreável, ideal para pipelines multi-etapa |
| **OpenAI GPT-4o-mini** | LLM para enriquecimento e geração de conteúdo | Custo-benefício para volume; arquitetura agnóstica — troca para Claude em uma linha |
| **Tavily** | Busca web para enriquecimento e inteligência de mercado | API limpa, resulta em trechos já extraídos, sem parsing de HTML |
| **scikit-learn Decision Tree** | Lead scoring | Interpretável e auditável — requisito implícito do Art. 20 LGPD (decisão automatizada) |
| **Mailtrap** | Envio de e-mails (sandbox) | Demo funcional sem domínio real ou custo adicional |
| **python-dotenv** | Gestão de secrets | Padrão de mercado — nenhum secret entra no repositório |

> **Nota sobre LLM:** a arquitetura foi projetada para Claude (Anthropic). O uso de GPT-4o-mini é uma adaptação pontual por disponibilidade de chave durante o desenvolvimento. Para migrar, basta substituir o cliente em `enrichment.py`, `promoter_brief.py`, `market_intelligence.py` e nas sequências de e-mail.

> **Nota sobre dbt:** seria a escolha natural para transformações analíticas no Supabase. O tier gratuito já está em uso em outro projeto — documentado aqui como decisão consciente e próximo passo de roadmap.

---

## O que vai além do solicitado

O case pede um agente de funil com as quatro fases. Este projeto entrega isso e mais:

**Lead Scoring com ML (Decision Tree)**
Modelo treinado com 7 features: cargo, setor da empresa, tamanho da empresa, áreas de interesse declaradas, formação atual, taxa de engajamento nos e-mails e comparecimento ao evento. O rótulo (Alta / Média / Baixa) orienta o promotor sobre quem abordar primeiro.

**Inteligência de Mercado por Empresa**
Antes do evento, o agente pesquisa cada empresa em 5 ângulos via Tavily (incidentes de segurança, inovação em IA/cloud, movimento de RH em TI, conformidade regulatória, crescimento/M&A) e sintetiza via LLM um resumo de vendas pronto para uso.

**Promoter Brief (LangGraph)**
Pipeline de 3 nós (coletar contexto → gerar roteiro → salvar) que produz um card acionável por lead: frase de abertura, demo recomendada, argumento principal, sinais de interesse a observar, como propor a reunião e alertas de abordagem. O promotor abre no celular e sabe exatamente o que dizer.

**Dashboard de Monitoramento**
Painel Streamlit com métricas do funil em tempo real, ranking de leads por score, cards de Promoter Brief filtráveis e inteligência de mercado por empresa — tudo em uma tela, sem precisar rodar queries SQL.

**Conformidade LGPD completa**
Consentimento explícito no cadastro (Art. 8), política de privacidade detalhada, nota de decisão automatizada (Art. 20), opt-out em todos os e-mails, trigger de auditoria de status, e módulo `data_rights.py` com exportação de dados, exclusão em cascata e revogação de consentimento.

---

## Como rodar

### 1. Pré-requisitos

- Python 3.11+
- Conta Supabase (gratuita)
- Chaves: OpenAI, Tavily, Mailtrap

### 2. Clone e instale dependências

```bash
git clone https://github.com/silasluiz96-alt/vigil-sentinel-agent.git
cd vigil-sentinel-agent
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas chaves
```

```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...
TAVILY_API_KEY=tvly-...
MAILTRAP_USER=seu_usuario
MAILTRAP_PASS=sua_senha
```

### 4. Configure o banco de dados no Supabase

1. Acesse seu projeto no [Supabase](https://supabase.com)
2. Vá em **SQL Editor**
3. Cole e execute o conteúdo de `db/schema.sql`

O script cria todas as tabelas, o trigger de auditoria, a view analítica e insere o evento Vigil Summit automaticamente.

### 5. Inicie a aplicação

```bash
# Landing page (captação de leads)
streamlit run landing.py

# Dashboard (monitoramento — abre em nova aba ou porta diferente)
streamlit run pages/Dashboard.py
```

### 6. Fluxo de demonstração

```python
from agent.enrichment import enriquecer_lead
from agent.pre_event_sequence import enviar_etapa
from agent.market_intelligence import pesquisar_todas_empresas
from agent.promoter_brief import gerar_briefs_prioritarios

# Após cadastro via landing page:
enriquecer_lead("<lead_id>")          # enriquece e calcula score
pesquisar_todas_empresas()            # coleta inteligência de mercado
gerar_briefs_prioritarios()           # gera roteiros para leads Alta/Média

# Régua pré-evento (executar por etapa conforme cronograma):
enviar_etapa("<lead_id>", etapa=1)

# Pós-evento:
from agent.post_event_sequence import disparar_pos_evento
disparar_pos_evento()                 # separa presentes de no-shows automaticamente
```

---

## Personas de teste

Para demonstrar o fluxo ponta a ponta sem dados reais, insira os leads abaixo via landing page ou diretamente no Supabase:

| Nome | Cargo | Empresa | Área de interesse | Formação | Perfil esperado |
|---|---|---|---|---|---|
| Ana Ribeiro | CISO | Banco Meridional | Conformidade regulatória, Gestão de riscos | CISSP em andamento | **Score Alta** — decisora, setor financeiro, certificação de segurança |
| Carlos Mendes | Gerente de TI | Saúde Total S.A. | Proteção de dados, Segurança em cloud | MBA em Gestão | **Score Média** — setor relevante, cargo intermediário, trajetória de crescimento |
| Fernanda Costa | Analista de Segurança | FinTech Nova | Automação de segurança | Graduação em Sistemas | **Score Média** — setor estratégico, cargo operacional, área alinhada ao produto |
| Roberto Alves | Diretor de TI | Manufatura BR | Liderança e gestão de times | Especialização em TI | **Score Baixa** — cargo alto mas setor periférico, sem formação em segurança |
| Juliana Prates | CTO | GovTech Brasil | Conformidade regulatória, Resposta a incidentes | Pós em Cibersegurança | **Score Alta** — decisora técnica, setor governo, formação e interesse diretos |

---

## Plano de execução (5 dias)

| Dia | Entregável |
|---|---|
| **Dia 1** | Schema do banco, landing page com LGPD, módulo de enriquecimento |
| **Dia 2** | Lead scoring (ML), régua pré-evento, política de privacidade |
| **Dia 3** | Régua pós-evento, módulo de direitos LGPD, trigger de auditoria |
| **Dia 4** | Inteligência de mercado, Promoter Brief (LangGraph), dashboard |
| **Dia 5** | Testes de ponta a ponta, ajustes de qualidade, documentação |

---

## Cenário de escala

Para um evento com 10x o volume (1.200 leads):

- **Banco:** Supabase suporta sem alteração; adicionar índice em `lead_scores.rotulo` e `inscricoes.status`
- **Enriquecimento:** paralelizar com `asyncio` ou fila (Celery + Redis) para processar em batch sem estourar o rate limit da Tavily
- **E-mails:** migrar de Mailtrap para SendGrid ou Resend com domínio verificado
- **LLM:** aumentar `max_tokens` e usar GPT-4o (modelo maior) ou Claude Opus para briefs mais complexos; avaliar cache semântico para empresas repetidas
- **Dashboard:** adicionar filtro por evento (multi-evento) e exportação CSV para o time comercial

---

## Conformidade LGPD — resumo técnico

| Requisito | Implementação |
|---|---|
| Consentimento (Art. 7, I e Art. 8) | Checkbox obrigatório na landing page, bloqueio de envio sem aceite |
| Transparência em decisão automatizada (Art. 20) | Nota visível no formulário + seção dedicada na política de privacidade |
| Direito de acesso (Art. 18, I) | `data_rights.exportar_dados_lead()` retorna JSON completo |
| Direito de exclusão (Art. 18, VI) | `data_rights.excluir_lead()` com CASCADE em todas as tabelas |
| Revogação de consentimento (Art. 8, §5) | `data_rights.revogar_consentimento()` com soft opt-out |
| Opt-out em comunicações | Rodapé com link de descadastro em todos os e-mails |
| Rastreabilidade | Trigger `trg_auditoria_inscricoes` registra toda mudança de status |
| Retenção limitada (Art. 15) | Política define 12 meses; prazo documentado na página de privacidade |

---

*Desenvolvido por Silas Luiz Bom Fim — junho de 2026*
*Contato: ajbomfim.dev@gmail.com*
