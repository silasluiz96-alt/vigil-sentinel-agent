# Vigil Sentinel Agent

**Case técnico**

**Silas Luiz Bom Fim**

Sistema autônomo de gestão de funil para o evento **Vigil Summit 2026 — Segurança para a Era da IA** (120 participantes, público B2B: CISOs, CTOs e Diretores de TI).

O agente gerencia o ciclo completo do lead: captação → enriquecimento → engajamento pré-evento → follow-up pós-evento, com o objetivo final de agendar reuniões comerciais.

---

## Arquitetura

```
Home.py                     ← Formulário de captação (Streamlit)
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
    ├── 2_Dashboard.py       ← Painel de monitoramento do funil (Streamlit)
    └── 1_Privacidade.py     ← Política de privacidade (LGPD)
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

## Réguas de Comunicação

### Pré-evento — 5 etapas

| Etapa | Momento | Assunto principal | Assunto alternativo (não abriu anterior) | Regra de negócio |
|---|---|---|---|---|
| 1 | Imediato após inscrição | `Sua inscrição no Vigil Summit está confirmada ✅` | `Bem-vindo ao Vigil Summit — veja o que esperar` | Enviado para todos os inscritos com opt_out=false |
| 2 | 7 dias antes | `Vigil Summit: o que você vai encontrar em 7 dias` | `7 dias para o maior evento de segurança do ano` | Se houver outros leads da mesma empresa, inclui sugestão de carona (sem citar nomes) |
| 3 | 3 dias antes | `Confirme sua presença — faltam 3 dias` | `Só mais 3 dias: você vem ao Vigil Summit?` | Tom de urgência leve para quem ainda não confirmou; mesma regra de carona da etapa 2 |
| 4 | 1 dia antes | `Tudo pronto para amanhã? Veja os detalhes finais` | `Amanhã é o Vigil Summit — não perca nada` | **Somente confirmados** — leads sem confirmação não recebem esta etapa |
| 5 | Manhã do evento | `🛡️ Hoje é o dia — Vigil Summit começa às 9h` | `O Vigil Summit começa hoje. Veja como chegar` | **Somente confirmados** — inclui horário de credenciamento (8h30) |

**Regras globais da régua pré-evento:**
- Todo e-mail é gerado pelo LLM com abertura personalizada baseada no `resumo_perfil` do enriquecimento
- Rodapé LGPD obrigatório em todos os e-mails com link de descadastro
- `opt_out=true` bloqueia o envio antes de qualquer processamento
- Cada envio é registrado na tabela `comunicacoes` com status, assunto e corpo

---

### Pós-evento — 2 fluxos paralelos

**Fluxo A — Presentes** (compareceram ao evento):

| Etapa | Momento | Assunto | Tom por score |
|---|---|---|---|
| 1 | 1 dia depois | `Foi ótimo ter você no Vigil Summit 🛡️` | Caloroso, sem pressão comercial |
| 2 | 3 dias depois | `Que tal continuarmos a conversa? 30 minutos podem mudar sua estratégia` | **Alta:** direto, ROI e urgência leve / **Média:** consultivo / **Baixa:** relacionamento |
| 3 | 7 dias depois | `Última mensagem — e uma porta aberta` | Encerra sem pressão, oferece relatório do setor |

**Fluxo B — No-shows** (inscreveram mas não foram):

| Etapa | Momento | Assunto | Tom |
|---|---|---|---|
| 1 | 1 dia depois | `Sentimos sua falta no Vigil Summit — mas trouxemos o evento até você` | Compreensivo, oferece resumo dos insights |
| 2 | 5 dias depois | `A demo que você não viu — que tal 20 minutos?` | Calibrado por score — proposta de demo individual |

**Separação automática:** `disparar_pos_evento()` lê o status da inscrição (`presente` vs `no_show`) e distribui cada lead para o fluxo correto sem intervenção manual.

---

## Decisões Estratégicas e Racional

### Decisão 1 — Decision Tree em vez de Random Forest ou Regressão Logística

**Escolha:** `DecisionTreeClassifier` (scikit-learn, `max_depth=4`)

**Alternativas descartadas:**
- *Random Forest:* melhor acurácia, mas resultado de conjunto de árvores — não é possível explicar ao promotor por que um lead é Alta sem inspecionar dezenas de árvores. Descartado por falta de interpretabilidade.
- *Regressão Logística:* boa para datasets grandes e balanceados. Com 5 personas sintéticas e features ordinais (pesos manuais), a árvore simples generaliza melhor e é auditável visualmente.

**Por que importa:** o Art. 20 da LGPD exige que decisões automatizadas sejam explicáveis ao titular. A Decision Tree permite mostrar exatamente quais features determinaram o rótulo — requisito legal atendido nativamente.

---

### Decisão 2 — LangGraph em vez de LangChain puro para o Promoter Brief

**Escolha:** `LangGraph` com grafo de 3 nós tipados (`coletar_contexto → gerar_brief → salvar_brief`)

**Alternativas descartadas:**
- *LangChain puro (chain sequencial):* mais simples de implementar, mas o estado entre etapas é implícito — difícil rastrear em qual nó uma falha ocorreu. Descartado por falta de observabilidade.
- *Chamada direta ao LLM sem orquestrador:* funciona para casos simples, mas não escala para pipelines com coleta de múltiplas fontes (lead + enriquecimento + intel de empresa) antes da geração.

**Por que importa:** o Promoter Brief agrega dados de 4 tabelas antes de chamar o LLM. O grafo tipado (`BriefState`) garante que cada nó recebe exatamente o que precisa e que falhas são rastreáveis por nó — essencial para debugging em produção.

---

### Decisão 3 — Mailtrap (sandbox) em vez de SendGrid ou Amazon SES

**Escolha:** Mailtrap sandbox SMTP

**Alternativas descartadas:**
- *SendGrid:* requer domínio verificado e configuração de DNS (SPF, DKIM, DMARC). Inviável para uma demo sem domínio próprio operacional.
- *Amazon SES:* mesma exigência de domínio verificado, mais complexidade de IAM. Custo e setup desproporcional para demonstração.

**Por que importa:** o objetivo da demo é provar que o pipeline de e-mail funciona — geração, personalização, rodapé LGPD e registro no banco. O Mailtrap captura todos os e-mails em sandbox sem risco de spam e com visualização completa do HTML gerado. Em produção, a troca para SendGrid é uma alteração de 3 linhas em `pre_event_sequence.py` e `post_event_sequence.py`.

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
streamlit run Home.py

# Dashboard (monitoramento — abre em nova aba ou porta diferente)
streamlit run pages/2_Dashboard.py
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

## Plano de Execução — Primeiros 5 Dias

> **Contexto:** plano fictício construído sobre o cenário real de implementação deste projeto.

### Dia 1 — Fundação
- Provisionar projeto Supabase (tier gratuito) e criar organização no GitHub
- Executar `db/schema.sql` no SQL Editor do Supabase
- Configurar variáveis de ambiente no `.env` (Supabase, OpenAI, Tavily, Mailtrap)
- Validar conexão e integridade com `scripts/validar_banco.py`

**Critério de sucesso:** banco acessível, evento Vigil Summit inserido, zero erros de conexão.

### Dia 2 — Captação
- Fazer deploy da landing page (`Home.py`) no Streamlit Cloud com secrets configurados
- Cadastrar as primeiras personas de teste manualmente via formulário
- Verificar inscrições, `consentimento_em` e `opt_out` no Table Editor do Supabase

**Critério de sucesso:** leads com `status=inscrito` e `consentimento_em` preenchido; página de privacidade acessível.

### Dia 3 — Inteligência e Scoring
- Rodar `enriquecer_pendentes()` — busca Tavily + extração LLM para todos os leads
- Rodar `calcular_score()` — Decision Tree gera rótulos Alta / Média / Baixa
- Rodar `pesquisar_todas_empresas()` — inteligência de mercado em 5 ângulos por empresa

**Critério de sucesso:** tabelas `enriquecimento`, `lead_scores` e `inteligencia_empresa` populadas sem erros.

### Dia 4 — Briefs e Régua Pré-Evento
- Rodar `gerar_briefs_prioritarios()` — Promoter Briefs para leads Alta e Média via LangGraph
- Enviar etapa 1 da régua pré-evento (`enviar_etapa(lead_id, etapa=1)`) para todos os inscritos
- Validar e-mails gerados no Mailtrap (sandbox): assunto, personalização e rodapé LGPD

**Critério de sucesso:** `promoter_briefs` populada; e-mails visíveis no Mailtrap com abertura de parágrafo personalizada para cada lead.

### Dia 5 — Dashboard e Entrega
- Fazer deploy do dashboard (`pages/2_Dashboard.py`) como segunda app no Streamlit Cloud
- Configurar credenciais de staff em `st.secrets["staff"]` no painel Streamlit
- Enviar URL pública + credenciais de acesso para o time avaliador

**Critério de sucesso:** dashboard acessível via URL pública, login funcional, métricas do funil visíveis (inscritos → confirmados → presentes → reuniões).

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
*Contato: silas.luiz.96@gmail.com*
