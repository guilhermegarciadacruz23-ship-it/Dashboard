-- =====================================================================
-- Dashboard de Validade de Ferramentas
-- Banco: PostgreSQL 13+
-- Execute:  psql -U postgres -d ferramentas -f sql/01_schema.sql
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS ferramentaria;
SET search_path TO ferramentaria, public;

-- ---------------------------------------------------------------------
-- Tabelas de apoio
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categoria (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL UNIQUE,
    descricao   TEXT
);

CREATE TABLE IF NOT EXISTS localizacao (
    id          SERIAL PRIMARY KEY,
    nome        TEXT NOT NULL UNIQUE,
    setor       TEXT,
    responsavel TEXT
);

-- ---------------------------------------------------------------------
-- Tabela principal
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ferramenta (
    id                    SERIAL PRIMARY KEY,
    codigo                TEXT NOT NULL UNIQUE,          -- patrimônio / TAG
    nome                  TEXT NOT NULL,
    fabricante            TEXT,
    modelo                TEXT,
    numero_serie          TEXT,
    categoria_id          INTEGER REFERENCES categoria(id),
    localizacao_id        INTEGER REFERENCES localizacao(id),
    responsavel           TEXT,
    data_aquisicao        DATE,
    data_ultima_calibracao DATE,
    data_validade         DATE NOT NULL,                 -- vencimento vigente
    periodicidade_meses   INTEGER NOT NULL DEFAULT 12,
    custo_calibracao      NUMERIC(12,2),
    ativo                 BOOLEAN NOT NULL DEFAULT TRUE,
    observacoes           TEXT,
    criado_em             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ferramenta_validade ON ferramenta (data_validade);
CREATE INDEX IF NOT EXISTS idx_ferramenta_ativo    ON ferramenta (ativo);

-- ---------------------------------------------------------------------
-- Histórico de calibrações / renovações
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historico_calibracao (
    id               SERIAL PRIMARY KEY,
    ferramenta_id    INTEGER NOT NULL REFERENCES ferramenta(id) ON DELETE CASCADE,
    data_calibracao  DATE NOT NULL,
    data_validade    DATE NOT NULL,
    certificado      TEXT,
    laboratorio      TEXT,
    custo            NUMERIC(12,2),
    resultado        TEXT CHECK (resultado IN ('APROVADO','APROVADO_COM_RESTRICAO','REPROVADO')),
    registrado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hist_ferramenta ON historico_calibracao (ferramenta_id);

-- ---------------------------------------------------------------------
-- Log de alertas (evita disparo duplicado e alimenta o gráfico de avisos)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerta (
    id             SERIAL PRIMARY KEY,
    ferramenta_id  INTEGER NOT NULL REFERENCES ferramenta(id) ON DELETE CASCADE,
    faixa          TEXT NOT NULL,      -- AVISO_30 | ALERTA_15 | CRITICO_7 | VENCIDA
    dias_restantes INTEGER NOT NULL,
    data_validade  DATE NOT NULL,
    canal          TEXT DEFAULT 'EMAIL',
    status_envio   TEXT DEFAULT 'PENDENTE',
    gerado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enviado_em     TIMESTAMPTZ,
    CONSTRAINT uq_alerta UNIQUE (ferramenta_id, faixa, data_validade)
);

-- ---------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_atualiza_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ferramenta_timestamp ON ferramenta;
CREATE TRIGGER trg_ferramenta_timestamp
    BEFORE UPDATE ON ferramenta
    FOR EACH ROW EXECUTE FUNCTION fn_atualiza_timestamp();

-- Ao registrar uma nova calibração, a ferramenta é atualizada automaticamente
CREATE OR REPLACE FUNCTION fn_sincroniza_calibracao()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE ferramenta
       SET data_ultima_calibracao = NEW.data_calibracao,
           data_validade          = NEW.data_validade,
           custo_calibracao       = COALESCE(NEW.custo, custo_calibracao)
     WHERE id = NEW.ferramenta_id
       AND NEW.data_validade > data_validade;   -- só avança o vencimento
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sincroniza_calibracao ON historico_calibracao;
CREATE TRIGGER trg_sincroniza_calibracao
    AFTER INSERT ON historico_calibracao
    FOR EACH ROW EXECUTE FUNCTION fn_sincroniza_calibracao();
