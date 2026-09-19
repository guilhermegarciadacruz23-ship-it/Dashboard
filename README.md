# Dashboard de Validade de Ferramentas

Controle de vencimento/calibração de ferramentas com **PostgreSQL + Python + Looker Studio**.
O aviso de 30 dias é calculado no banco (view) e reforçado pela automação em Python, que grava o alerta e dispara e-mail.

```
dashboard-ferramentas/
├── sql/
│   ├── 01_schema.sql          tabelas, triggers e índices
│   ├── 02_views.sql           views que o Looker Studio consome
│   └── 03_dados_exemplo.sql   12 ferramentas de teste (OK, vencendo, vencidas)
├── python/
│   ├── db.py                  conexão (SQLAlchemy)
│   ├── alertas.py             regra dos 30 dias + e-mail HTML
│   ├── importar.py            carga de CSV/Excel com upsert
│   ├── exportar_sheets.py     ponte opcional para Google Sheets
│   ├── main.py                CLI
│   ├── requirements.txt
│   └── .env.example
└── dados/ferramentas_exemplo.csv
```

---

## 1. Banco de dados

```bash
createdb ferramentas
psql -U postgres -d ferramentas -f sql/01_schema.sql
psql -U postgres -d ferramentas -f sql/02_views.sql
psql -U postgres -d ferramentas -f sql/03_dados_exemplo.sql   # opcional
```

**Modelo:** `ferramenta` (cadastro + `data_validade`), `categoria`, `localizacao`,
`historico_calibracao` (cada renovação) e `alerta` (log dos avisos disparados).

Dois gatilhos automáticos:
- `atualizado_em` é preenchido em todo UPDATE;
- ao inserir uma linha em `historico_calibracao`, a `data_validade` da ferramenta é atualizada sozinha. Renovar uma calibração é só isto:

```sql
INSERT INTO ferramentaria.historico_calibracao
    (ferramenta_id, data_calibracao, data_validade, certificado, laboratorio, custo, resultado)
VALUES (3, CURRENT_DATE, CURRENT_DATE + INTERVAL '12 months', 'CERT-2026-0451', 'Lab Alfa', 240.00, 'APROVADO');
```

### As views

| View | Para que serve no painel |
|---|---|
| `vw_status_ferramentas` | **fonte principal**: uma linha por ferramenta com `dias_para_vencer`, `status`, `cor_status` e `vence_em_30_dias` |
| `vw_kpis` | scorecards do topo (total, vencendo em 30 dias, vencidas, % conformidade) |
| `vw_alertas_ativos` | tabela "precisa de ação" (≤ 30 dias ou vencida) |
| `vw_vencimentos_mensais` | gráfico de barras de vencimentos por mês e custo previsto |
| `vw_historico_alertas` | auditoria dos avisos já enviados |

Faixas de `status`: `VENCIDA` · `CRITICO` (≤7d) · `ALERTA` (≤15d) · `AVISO` (≤30d) · `ATENCAO` (≤60d) · `OK`.

---

## 2. Python

```bash
cd python
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # preencha banco e SMTP
python main.py testar
```

Comandos:

```bash
python main.py painel                      # resumo no terminal
python main.py importar ../dados/ferramentas_exemplo.csv
python main.py verificar                   # grava alertas novos e envia e-mail
python main.py verificar --sem-email       # só registra
python main.py exportar                    # atualiza o Google Sheets (opcional)
python main.py web                         # inicia o dashboard web
```

### Dashboard web

Com o PostgreSQL configurado e as views carregadas, instale as dependências e
inicie a interface:

```bash
pip install -r requirements.txt
python main.py web
```

Acesse `http://127.0.0.1:5000`. O dashboard mostra os KPIs, a distribuição por
status, os vencimentos por mês e a lista de produtos que exigem ação. Produtos
vencidos ficam em vermelho com destaque de uso bloqueado; itens que vencem em
até 30 dias aparecem no alerta e na tabela de renovação. O filtro de categoria
recalcula os indicadores e os gráficos. Use o botão **Exportar Excel** para
baixar o cadastro e os status atuais em `.xlsx`; quando houver uma categoria
selecionada, o arquivo respeita esse filtro.
O painel consulta a planilha novamente a cada 60 segundos, atualizando os
gráficos sem exigir recarregar a página. O gráfico **Validade por material**
permite selecionar a identificação e exibe o prazo e o status daquele item.

Por padrão, o dashboard usa a aba principal da planilha Google compartilhada
para leitura. Para trocar a fonte, defina `GOOGLE_SHEETS_CSV_URL` no `.env`
com uma URL de exportação CSV compatível. Se essa variável for removida do
ambiente, a aplicação volta a consultar as views do PostgreSQL.

### Publicar no Render

O arquivo `render.yaml` já contém os comandos de instalação e inicialização em
produção. Para publicar, envie esta pasta para um repositório GitHub e, no
Render, escolha **New + → Blueprint** e selecione o repositório. O Render
criará o serviço `valihub-dashboard` usando `gunicorn` e fornecerá a URL pública.

O `verificar` só envia e-mail de alertas **novos**: a constraint `uq_alerta`
(ferramenta + faixa + data_validade) impede que a mesma ferramenta gere aviso repetido a cada execução. Ela volta a alertar quando muda de faixa (30 → 15 → 7 → vencida) ou quando ganha uma nova validade.

> Gmail exige **Senha de app** (conta com verificação em 2 etapas), não a senha normal.

### Agendamento

Linux/macOS (`crontab -e`) — todo dia útil às 7h:

```cron
0 7 * * 1-5 cd /caminho/dashboard-ferramentas/python && /caminho/.venv/bin/python main.py verificar >> /var/log/ferramentas.log 2>&1
```

Windows — Agendador de Tarefas, ação: `C:\caminho\.venv\Scripts\python.exe`, argumento `main.py verificar`, iniciar em `C:\caminho\python`.

---

## 3. Looker Studio

### Caminho A — conexão direta com o PostgreSQL (recomendado)

1. Em [lookerstudio.google.com](https://lookerstudio.google.com) → **Criar → Fonte de dados → PostgreSQL**.
2. Marque **Consulta personalizada** e cole:
   ```sql
   SELECT * FROM ferramentaria.vw_status_ferramentas
   ```
   (repita o processo para `vw_kpis` e `vw_vencimentos_mensais`, criando uma fonte para cada).
3. Preencha host, porta 5432, banco, usuário e senha. Ative SSL se o servidor exigir.
4. O servidor precisa aceitar os IPs do Looker Studio. Libere no firewall e em `pg_hba.conf` a faixa publicada pelo Google em *Looker Studio → conectores → PostgreSQL*. O ideal é um usuário só de leitura:
   ```sql
   CREATE USER looker WITH PASSWORD 'senha_forte';
   GRANT USAGE ON SCHEMA ferramentaria TO looker;
   GRANT SELECT ON ALL TABLES IN SCHEMA ferramentaria TO looker;
   ```
5. Nos campos, confira os tipos: `data_validade` e `mes_vencimento` como **Data**, `dias_para_vencer` como **Número**.

### Caminho B — Google Sheets (se o banco for interno e não puder ser exposto)

Rode `python main.py exportar` no mesmo agendamento. O script grava as abas
`ferramentas`, `alertas` e `vencimentos_mensais`; no Looker Studio basta conectar a planilha. Em *Configurações da fonte* ative a atualização automática de 15 min.

### Montagem do painel

**Linha 1 — scorecards** (fonte `vw_kpis`): `total_ferramentas`, `qtd_vencendo_30d`, `qtd_critico_7d`, `qtd_vencidas`, `perc_conformidade`.
Em cada um, *Estilo → Condicional*: vermelho quando o valor de vencidas/críticas for > 0.

**Linha 2 — gráfico de rosca "Situação do parque"**
Fonte `vw_status_ferramentas`, dimensão `status`, métrica `Record Count`, ordenação por `ordem_status` crescente. Cores: VENCIDA #B00020, CRITICO #E53935, ALERTA #FB8C00, AVISO #FDD835, ATENCAO #90CAF9, OK #2E7D32.

**Linha 2 — barras "Vencimentos por mês"**
Fonte `vw_vencimentos_mensais`, dimensão `ano_mes_vencimento`, métrica `qtd_ferramentas`, detalhamento opcional por `categoria`.

**Linha 3 — tabela "Ação necessária"**
Fonte `vw_status_ferramentas` com filtro `vence_em_30_dias = true OR esta_vencida = true`.
Campos: código, nome, localização, responsável, data_validade, dias_para_vencer, status.
Ordene por `dias_para_vencer` crescente e aplique formatação condicional na coluna `status`.

**Filtros de página:** categoria, localização, responsável e status.

**Aviso automático dentro do relatório:** crie um campo calculado
```
CASE WHEN dias_para_vencer < 0 THEN "🔴 VENCIDA - USO BLOQUEADO"
     WHEN dias_para_vencer <= 7 THEN "🔴 Calibrar esta semana"
     WHEN dias_para_vencer <= 30 THEN "🟡 Vence em 30 dias - agendar"
     ELSE "🟢 Em dia" END
```
e use como dimensão de um gráfico de barras ou coluna da tabela.

**Envio programado:** no relatório, *Compartilhar → Programar envio por e-mail* — assim a equipe recebe o PDF do painel além do alerta do Python.

---

## Manutenção

- **Nova ferramenta:** `INSERT` na tabela `ferramenta` ou linha nova no CSV + `main.py importar`.
- **Baixa de ferramenta:** `UPDATE ferramenta SET ativo = FALSE WHERE codigo = 'FER-0003';` (sai das views, mas o histórico permanece).
- **Mudar a janela de aviso:** `DIAS_AVISO` no `.env` e os `INTERVAL '30 days'` em `02_views.sql`.
- **Cache do Looker Studio:** 12h por padrão; reduza em *Opções do arquivo → Atualização de dados*.
