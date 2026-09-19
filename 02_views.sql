-- =====================================================================
-- Views de consumo do Looker Studio
-- Execute:  psql -U postgres -d ferramentas -f sql/02_views.sql
-- =====================================================================
SET search_path TO ferramentaria, public;

-- ---------------------------------------------------------------------
-- 1) VIEW PRINCIPAL — é esta que você conecta no Looker Studio
--    Traz uma linha por ferramenta, já com dias restantes e status.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_status_ferramentas AS
SELECT
    f.id,
    f.codigo,
    f.nome,
    f.fabricante,
    f.modelo,
    f.numero_serie,
    COALESCE(c.nome, 'Sem categoria')  AS categoria,
    COALESCE(l.nome, 'Sem local')      AS localizacao,
    COALESCE(l.setor, '-')             AS setor,
    f.responsavel,
    f.data_aquisicao,
    f.data_ultima_calibracao,
    f.data_validade,
    f.periodicidade_meses,
    f.custo_calibracao,
    f.ativo,

    -- Núcleo do cálculo
    (f.data_validade - CURRENT_DATE) AS dias_para_vencer,

    CASE
        WHEN f.data_validade <  CURRENT_DATE                      THEN 'VENCIDA'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '7 days'  THEN 'CRITICO'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '15 days' THEN 'ALERTA'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN 'AVISO'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '60 days' THEN 'ATENCAO'
        ELSE 'OK'
    END AS status,

    -- Campo auxiliar para ordenar o status nos gráficos (1 = pior)
    CASE
        WHEN f.data_validade <  CURRENT_DATE                      THEN 1
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '7 days'  THEN 2
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '15 days' THEN 3
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN 4
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '60 days' THEN 5
        ELSE 6
    END AS ordem_status,

    -- Cor sugerida (use em "Gráfico de barras > cor por dimensão" ou tabela condicional)
    CASE
        WHEN f.data_validade <  CURRENT_DATE                      THEN '#B00020'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '7 days'  THEN '#E53935'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '15 days' THEN '#FB8C00'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '30 days' THEN '#FDD835'
        WHEN f.data_validade <= CURRENT_DATE + INTERVAL '60 days' THEN '#90CAF9'
        ELSE '#2E7D32'
    END AS cor_status,

    -- Flag booleana pedida na regra dos 30 dias
    (f.data_validade BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days') AS vence_em_30_dias,
    (f.data_validade < CURRENT_DATE)                                             AS esta_vencida,

    -- Dimensões de tempo para os gráficos de linha/coluna
    DATE_TRUNC('month', f.data_validade)::DATE            AS mes_vencimento,
    TO_CHAR(f.data_validade, 'YYYY-MM')                   AS ano_mes_vencimento,
    EXTRACT(YEAR  FROM f.data_validade)::INT              AS ano_vencimento,
    CURRENT_DATE                                          AS data_referencia
FROM ferramenta f
LEFT JOIN categoria   c ON c.id = f.categoria_id
LEFT JOIN localizacao l ON l.id = f.localizacao_id
WHERE f.ativo = TRUE;

-- ---------------------------------------------------------------------
-- 2) KPIs — uma única linha, ideal para os "scorecards" do topo
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_kpis AS
SELECT
    COUNT(*)                                              AS total_ferramentas,
    COUNT(*) FILTER (WHERE status = 'OK')                 AS qtd_ok,
    COUNT(*) FILTER (WHERE status = 'ATENCAO')            AS qtd_atencao_60d,
    COUNT(*) FILTER (WHERE vence_em_30_dias)              AS qtd_vencendo_30d,
    COUNT(*) FILTER (WHERE status = 'CRITICO')            AS qtd_critico_7d,
    COUNT(*) FILTER (WHERE esta_vencida)                  AS qtd_vencidas,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT esta_vencida) / NULLIF(COUNT(*),0), 1) AS perc_conformidade,
    MIN(data_validade) FILTER (WHERE NOT esta_vencida)    AS proximo_vencimento
FROM vw_status_ferramentas;

-- ---------------------------------------------------------------------
-- 3) Apenas as que precisam de ação (<= 30 dias ou já vencidas)
--    Use como fonte da tabela "Ferramentas a renovar".
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_alertas_ativos AS
SELECT codigo, nome, categoria, localizacao, responsavel,
       data_ultima_calibracao, data_validade, dias_para_vencer,
       status, ordem_status, cor_status
FROM vw_status_ferramentas
WHERE dias_para_vencer <= 30
ORDER BY dias_para_vencer;

-- ---------------------------------------------------------------------
-- 4) Linha do tempo — vencimentos por mês (próximos 12 meses)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_vencimentos_mensais AS
SELECT
    ano_mes_vencimento,
    mes_vencimento,
    categoria,
    COUNT(*)                                  AS qtd_ferramentas,
    SUM(COALESCE(custo_calibracao,0))         AS custo_previsto
FROM vw_status_ferramentas
WHERE data_validade BETWEEN CURRENT_DATE - INTERVAL '3 months'
                        AND CURRENT_DATE + INTERVAL '12 months'
GROUP BY 1,2,3
ORDER BY 1;

-- ---------------------------------------------------------------------
-- 5) Histórico de alertas disparados pela automação
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_historico_alertas AS
SELECT a.id, f.codigo, f.nome, a.faixa, a.dias_restantes,
       a.data_validade, a.status_envio, a.gerado_em, a.enviado_em,
       DATE_TRUNC('day', a.gerado_em)::DATE AS dia_alerta
FROM alerta a
JOIN ferramenta f ON f.id = a.ferramenta_id;
