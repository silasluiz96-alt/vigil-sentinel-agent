-- ============================================================
-- VIGIL SENTINEL AGENT — Schema do Banco de Dados
-- Supabase (PostgreSQL)
-- ============================================================

-- Eventos (ex: Vigil Summit)
CREATE TABLE IF NOT EXISTS eventos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome        TEXT NOT NULL,
    data        DATE NOT NULL,
    local       TEXT,
    capacidade  INTEGER DEFAULT 120,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Leads captados
CREATE TABLE IF NOT EXISTS leads (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome             TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE,
    telefone         TEXT,
    cargo            TEXT,
    empresa          TEXT,
    linkedin         TEXT,
    areas_interesse  TEXT[],  -- ex: {"Conformidade regulatória","Liderança"}
    formacao_atual   TEXT,    -- ex: "MBA em Gestão de TI", "CISSP em andamento"
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Enriquecimento do perfil (preenchido pelo agente via Tavily + LLM)
CREATE TABLE IF NOT EXISTS enriquecimento (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID REFERENCES leads(id) ON DELETE CASCADE,
    cargo_real          TEXT,
    empresa_confirmada  TEXT,
    setor               TEXT,
    tamanho_empresa     TEXT,
    sinais_interesse       TEXT,
    resumo_perfil          TEXT,
    raw_data               JSONB,
    enriquecido_em         TIMESTAMPTZ DEFAULT NOW()
);

-- Inscrições por evento
CREATE TABLE IF NOT EXISTS inscricoes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID REFERENCES leads(id) ON DELETE CASCADE,
    evento_id       UUID REFERENCES eventos(id) ON DELETE CASCADE,
    status          TEXT DEFAULT 'inscrito'
                    CHECK (status IN ('inscrito','confirmado','presente','no_show')),
    com_acompanhante BOOLEAN DEFAULT FALSE,
    nome_acompanhante TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lead_id, evento_id)
);

-- Comunicações enviadas (pré e pós-evento)
CREATE TABLE IF NOT EXISTS comunicacoes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID REFERENCES leads(id) ON DELETE CASCADE,
    evento_id   UUID REFERENCES eventos(id),
    fase        TEXT NOT NULL
                CHECK (fase IN ('pre_evento','pos_evento')),
    etapa       INTEGER NOT NULL,
    canal       TEXT DEFAULT 'email',
    assunto     TEXT,
    corpo       TEXT,
    status      TEXT DEFAULT 'enviado'
                CHECK (status IN ('enviado','aberto','clicado','sem_resposta')),
    enviado_em  TIMESTAMPTZ DEFAULT NOW()
);

-- Reuniões comerciais agendadas (objetivo final do funil)
CREATE TABLE IF NOT EXISTS reunioes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID REFERENCES leads(id) ON DELETE CASCADE,
    evento_id       UUID REFERENCES eventos(id),
    data_agendada   TIMESTAMPTZ,
    status          TEXT DEFAULT 'agendada'
                    CHECK (status IN ('agendada','realizada','cancelada')),
    observacoes     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Inteligência de mercado por empresa
-- ============================================================

CREATE TABLE IF NOT EXISTS inteligencia_empresa (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa         TEXT NOT NULL UNIQUE,
    incidentes      TEXT,   -- vazamentos, multas, vulnerabilidades públicas
    inovacao        TEXT,   -- IA, cloud, transformação digital, novos produtos
    movimento_rh    TEXT,   -- contratações em TI/segurança, expansão de equipe
    conformidade    TEXT,   -- certificações em andamento, regulatório, auditorias
    crescimento     TEXT,   -- fusões, aquisições, novas unidades, expansão
    resumo_vendas   TEXT,   -- síntese estratégica pronta para o promotor usar
    raw_data        JSONB,
    coletado_em     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Promoter Briefs — roteiro de abordagem por lead
-- ============================================================

CREATE TABLE IF NOT EXISTS promoter_briefs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID REFERENCES leads(id) ON DELETE CASCADE UNIQUE,
    score               NUMERIC(5,2),
    rotulo              TEXT,
    frase_abertura      TEXT,
    demo_recomendada    TEXT,
    argumento           TEXT,
    sinais_interesse    TEXT,
    como_fechar         TEXT,
    alertas             TEXT,
    gerado_em           TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Auditoria: registra toda mudança de status nas inscrições
-- ============================================================

CREATE TABLE IF NOT EXISTS auditoria_inscricoes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inscricao_id    UUID,
    lead_id         UUID,
    status_anterior TEXT,
    status_novo     TEXT,
    alterado_em     TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION fn_auditoria_status_inscricao()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO auditoria_inscricoes (inscricao_id, lead_id, status_anterior, status_novo)
        VALUES (OLD.id, OLD.lead_id, OLD.status, NEW.status);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_auditoria_inscricoes
AFTER UPDATE ON inscricoes
FOR EACH ROW EXECUTE FUNCTION fn_auditoria_status_inscricao();

-- ============================================================
-- Lead Scoring: pontuação de propensão a fechar negócio
-- ============================================================

CREATE TABLE IF NOT EXISTS lead_scores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID REFERENCES leads(id) ON DELETE CASCADE UNIQUE,
    score       NUMERIC(5,2),
    rotulo      TEXT CHECK (rotulo IN ('Alta','Média','Baixa')),
    calculado_em TIMESTAMPTZ DEFAULT NOW()
);

-- View analítica: funil completo com score — alimenta o dashboard
CREATE OR REPLACE VIEW vw_funil_leads AS
SELECT
    l.id,
    l.nome,
    l.email,
    l.cargo,
    l.empresa,
    e.setor,
    e.tamanho_empresa,
    i.status AS status_inscricao,
    ls.score,
    ls.rotulo,
    ls.calculado_em,
    COUNT(c.id) FILTER (WHERE c.status IN ('aberto','clicado')) AS emails_engajados,
    COUNT(c.id) AS emails_enviados,
    CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END AS reuniao_agendada
FROM leads l
LEFT JOIN enriquecimento e ON e.lead_id = l.id
LEFT JOIN inscricoes i ON i.lead_id = l.id
LEFT JOIN comunicacoes c ON c.lead_id = l.id
LEFT JOIN lead_scores ls ON ls.lead_id = l.id
LEFT JOIN reunioes r ON r.lead_id = l.id
GROUP BY l.id, l.nome, l.email, l.cargo, l.empresa,
         e.setor, e.tamanho_empresa, i.status,
         ls.score, ls.rotulo, ls.calculado_em, r.id;

-- ============================================================
-- Dados iniciais: evento Vigil Summit
-- ============================================================
INSERT INTO eventos (nome, data, local, capacidade)
VALUES ('Vigil Summit — Segurança para a Era da IA', '2026-08-15', 'São Paulo, SP', 120)
ON CONFLICT DO NOTHING;
