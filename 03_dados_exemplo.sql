-- =====================================================================
-- Dados de exemplo (datas relativas a hoje, para o dashboard já nascer
-- com ferramentas OK, vencendo em 30 dias e vencidas)
-- =====================================================================
SET search_path TO ferramentaria, public;

INSERT INTO categoria (nome, descricao) VALUES
    ('Metrologia',   'Instrumentos de medição sujeitos a calibração'),
    ('Elétrica',     'Ferramentas e EPIs elétricos'),
    ('Içamento',     'Cintas, talhas, ganchos e acessórios'),
    ('Torque',       'Torquímetros e multiplicadores'),
    ('EPI',          'Equipamentos de proteção individual')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO localizacao (nome, setor, responsavel) VALUES
    ('Almoxarifado Central', 'Suprimentos', 'Ana Ribeiro'),
    ('Oficina Mecânica',     'Manutenção',  'Carlos Souza'),
    ('Linha de Montagem 1',  'Produção',    'Marcos Lima'),
    ('Laboratório',          'Qualidade',   'Juliana Alves')
ON CONFLICT (nome) DO NOTHING;

INSERT INTO ferramenta
    (codigo, nome, fabricante, modelo, numero_serie, categoria_id, localizacao_id,
     responsavel, data_aquisicao, data_ultima_calibracao, data_validade,
     periodicidade_meses, custo_calibracao)
VALUES
    ('FER-0001','Paquímetro digital 150mm','Mitutoyo','500-196-30','A1123',1,4,'Juliana Alves', CURRENT_DATE-INTERVAL '3 years',  CURRENT_DATE-INTERVAL '11 months', CURRENT_DATE+INTERVAL '25 days', 12, 180.00),
    ('FER-0002','Micrômetro externo 0-25mm','Mitutoyo','103-137',  'B2210',1,4,'Juliana Alves', CURRENT_DATE-INTERVAL '4 years',  CURRENT_DATE-INTERVAL '10 months', CURRENT_DATE+INTERVAL '55 days', 12, 160.00),
    ('FER-0003','Torquímetro de estalo 60Nm','Gedore','TBN 60',    'C3345',4,2,'Carlos Souza',  CURRENT_DATE-INTERVAL '2 years',  CURRENT_DATE-INTERVAL '12 months', CURRENT_DATE-INTERVAL '5 days',  12, 240.00),
    ('FER-0004','Alicate amperímetro','Fluke','376 FC',            'D4456',2,2,'Carlos Souza',  CURRENT_DATE-INTERVAL '5 years',  CURRENT_DATE-INTERVAL '11 months', CURRENT_DATE+INTERVAL '6 days',  12, 320.00),
    ('FER-0005','Cinta de elevação 3t','Cavalete','CE-3T',         'E5567',3,1,'Ana Ribeiro',   CURRENT_DATE-INTERVAL '1 year',   CURRENT_DATE-INTERVAL '6 months',  CURRENT_DATE+INTERVAL '12 days', 12,  90.00),
    ('FER-0006','Multímetro digital','Fluke','87V',                'F6678',2,3,'Marcos Lima',   CURRENT_DATE-INTERVAL '3 years',  CURRENT_DATE-INTERVAL '2 months',  CURRENT_DATE+INTERVAL '300 days',12, 280.00),
    ('FER-0007','Relógio comparador 0,01mm','Mitutoyo','2046S',    'G7789',1,4,'Juliana Alves', CURRENT_DATE-INTERVAL '6 years',  CURRENT_DATE-INTERVAL '13 months', CURRENT_DATE-INTERVAL '35 days', 12, 150.00),
    ('FER-0008','Talha manual 2t','Vonder','TMV-2',                'H8890',3,2,'Carlos Souza',  CURRENT_DATE-INTERVAL '2 years',  CURRENT_DATE-INTERVAL '5 months',  CURRENT_DATE+INTERVAL '210 days',12, 130.00),
    ('FER-0009','Luva isolante classe 2','Orion','LI-C2',          'I9901',5,1,'Ana Ribeiro',   CURRENT_DATE-INTERVAL '8 months', CURRENT_DATE-INTERVAL '5 months',  CURRENT_DATE+INTERVAL '29 days',  6,  70.00),
    ('FER-0010','Trena laser 50m','Bosch','GLM 50C',               'J1012',1,3,'Marcos Lima',   CURRENT_DATE-INTERVAL '1 year',   CURRENT_DATE-INTERVAL '9 months',  CURRENT_DATE+INTERVAL '90 days', 12, 110.00),
    ('FER-0011','Torquímetro digital 200Nm','Tramontina','TD-200', 'K1123',4,2,'Carlos Souza',  CURRENT_DATE-INTERVAL '3 years',  CURRENT_DATE-INTERVAL '11 months', CURRENT_DATE+INTERVAL '18 days', 12, 350.00),
    ('FER-0012','Manômetro 0-10 bar','Wika','232.50',              'L1234',1,3,'Marcos Lima',   CURRENT_DATE-INTERVAL '4 years',  CURRENT_DATE-INTERVAL '12 months', CURRENT_DATE+INTERVAL '2 days',  12, 140.00)
ON CONFLICT (codigo) DO NOTHING;
