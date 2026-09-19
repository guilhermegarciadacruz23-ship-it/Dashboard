"""Dashboard web do controle de validade."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import os

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from db import consultar

load_dotenv()

app = Flask(__name__)
GOOGLE_SHEETS_CSV_URL = os.getenv(
    "GOOGLE_SHEETS_CSV_URL",
    "https://docs.google.com/spreadsheets/d/1T7jJofl96ynOGYg5RbRf2iIruN7wo3q7-tL6Bix4ZY0/export?format=csv&gid=0",
)


def serializar(valor):
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def registros(sql: str, params: dict | None = None) -> list[dict]:
    df = consultar(sql, params)
    return [{chave: serializar(valor) for chave, valor in linha.items()}
            for linha in df.to_dict(orient="records")]


def buscar_planilha_google() -> pd.DataFrame:
    """Lê a aba pública e normaliza seus campos para o dashboard."""
    bruto = pd.read_csv(GOOGLE_SHEETS_CSV_URL, dtype=str, keep_default_na=False)
    dados = bruto.iloc[:, [0, 1, 4, 5, 6, 7, 8, 9, 11]].copy()
    dados.columns = [
        "codigo", "numero_serie", "nome", "localizacao", "categoria",
        "data_ultima_calibracao", "data_validade", "situacao_planilha", "setor",
    ]
    dados["data_validade"] = pd.to_datetime(dados["data_validade"], dayfirst=True, errors="coerce")
    dados["data_ultima_calibracao"] = pd.to_datetime(
        dados["data_ultima_calibracao"], dayfirst=True, errors="coerce"
    )
    dados = dados[dados["codigo"].ne("") & dados["data_validade"].notna()].copy()
    dados["dias_para_vencer"] = (dados["data_validade"].dt.normalize() - pd.Timestamp.today().normalize()).dt.days
    dados["status"] = dados["dias_para_vencer"].map(classificar_status)
    dados["cor_status"] = dados["status"].map({
        "VENCIDA": "#B00020", "CRITICO": "#E53935", "ALERTA": "#FB8C00",
        "AVISO": "#FDD835", "ATENCAO": "#90CAF9", "OK": "#2E7D32",
    })
    dados["vence_em_30_dias"] = dados["dias_para_vencer"].between(0, 30)
    dados["esta_vencida"] = dados["dias_para_vencer"] < 0
    return dados


def classificar_status(dias: int) -> str:
    if dias < 0:
        return "VENCIDA"
    if dias <= 7:
        return "CRITICO"
    if dias <= 15:
        return "ALERTA"
    if dias <= 30:
        return "AVISO"
    if dias <= 60:
        return "ATENCAO"
    return "OK"


def dashboard_da_planilha(categoria: str = "") -> dict:
    dados = buscar_planilha_google()
    if categoria:
        dados = dados[dados["categoria"] == categoria]
    total = len(dados)
    vencidas = int(dados["esta_vencida"].sum())
    kpis = {
        "total_ferramentas": total,
        "qtd_ok": int((dados["status"] == "OK").sum()),
        "qtd_atencao_60d": int((dados["status"] == "ATENCAO").sum()),
        "qtd_vencendo_30d": int(dados["vence_em_30_dias"].sum()),
        "qtd_critico_7d": int((dados["status"] == "CRITICO").sum()),
        "qtd_vencidas": vencidas,
        "perc_conformidade": round(100 * (total - vencidas) / total, 1) if total else 0,
        "proximo_vencimento": dados["data_validade"].min() if total else None,
    }
    ferramentas = dados[[
        "codigo", "nome", "categoria", "localizacao", "data_validade",
        "dias_para_vencer", "status", "cor_status", "vence_em_30_dias", "esta_vencida",
    ]].rename(columns={"codigo": "id"}).to_dict(orient="records")
    for ferramenta in ferramentas:
        ferramenta["data_validade"] = serializar(ferramenta["data_validade"])
    dados["ano_mes_vencimento"] = dados["data_validade"].dt.strftime("%Y-%m")
    meses = dados.groupby("ano_mes_vencimento", as_index=False).size().rename(columns={"size": "qtd_ferramentas"}).to_dict(orient="records")
    return {
        "kpis": {chave: serializar(valor) for chave, valor in kpis.items()},
        "ferramentas": ferramentas,
        "meses": meses,
        "categorias": sorted(buscar_planilha_google()["categoria"].unique().tolist()),
        "atualizado_em": date.today().isoformat(),
        "fonte": "Google Sheets",
    }


@app.get("/")
def dashboard():
    return render_template("dashboard.html")


@app.get("/exportar/excel")
def exportar_excel():
    categoria = request.args.get("categoria", "").strip()
    filtro = ""
    params = {}
    if categoria:
        filtro = " WHERE categoria = :categoria"
        params["categoria"] = categoria

    if GOOGLE_SHEETS_CSV_URL:
        dados = buscar_planilha_google()
        if categoria:
            dados = dados[dados["categoria"] == categoria]
        dados = dados.assign(fabricante="", modelo="", responsavel="", custo_calibracao="")
        dados = dados[[
            "codigo", "nome", "fabricante", "modelo", "numero_serie", "categoria",
            "localizacao", "responsavel", "data_validade", "dias_para_vencer",
            "status", "vence_em_30_dias", "esta_vencida", "custo_calibracao",
        ]]
    else:
        dados = consultar(
            """
            SELECT codigo, nome, fabricante, modelo, numero_serie, categoria,
                   localizacao, responsavel, data_validade, dias_para_vencer,
                   status, vence_em_30_dias, esta_vencida, custo_calibracao
            FROM vw_status_ferramentas
            """ + filtro + " ORDER BY dias_para_vencer, nome",
            params,
        )
    dados = dados.rename(columns={
        "codigo": "Código", "nome": "Produto", "fabricante": "Fabricante",
        "modelo": "Modelo", "numero_serie": "Número de série",
        "categoria": "Categoria", "localizacao": "Localização",
        "responsavel": "Responsável", "data_validade": "Data de validade",
        "dias_para_vencer": "Dias para vencer", "status": "Status",
        "vence_em_30_dias": "Vence em até 30 dias", "esta_vencida": "Está vencida",
        "custo_calibracao": "Custo de calibração",
    })
    arquivo = BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        dados.to_excel(writer, index=False, sheet_name="Validades")
        planilha = writer.sheets["Validades"]
        planilha.freeze_panes = "A2"
        planilha.auto_filter.ref = planilha.dimensions
        for coluna in planilha.columns:
            largura = min(max(max(len(str(celula.value or "")) for celula in coluna) + 2, 12), 32)
            planilha.column_dimensions[coluna[0].column_letter].width = largura
    arquivo.seek(0)
    sufixo = f"_{categoria.lower().replace(' ', '_')}" if categoria else ""
    return send_file(
        arquivo,
        as_attachment=True,
        download_name=f"relatorio_validade{sufixo}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/dashboard")
def dados_dashboard():
    categoria = request.args.get("categoria", "").strip()
    if GOOGLE_SHEETS_CSV_URL:
        return jsonify(dashboard_da_planilha(categoria))

    filtro = ""
    params = {}
    if categoria:
        filtro = " WHERE categoria = :categoria"
        params["categoria"] = categoria

    kpis = registros(
        """
        SELECT COUNT(*) AS total_ferramentas,
               COUNT(*) FILTER (WHERE status = 'OK') AS qtd_ok,
               COUNT(*) FILTER (WHERE status = 'ATENCAO') AS qtd_atencao_60d,
               COUNT(*) FILTER (WHERE vence_em_30_dias) AS qtd_vencendo_30d,
               COUNT(*) FILTER (WHERE status = 'CRITICO') AS qtd_critico_7d,
               COUNT(*) FILTER (WHERE esta_vencida) AS qtd_vencidas,
               ROUND(100.0 * COUNT(*) FILTER (WHERE NOT esta_vencida) /
                     NULLIF(COUNT(*), 0), 1) AS perc_conformidade,
               MIN(data_validade) FILTER (WHERE NOT esta_vencida) AS proximo_vencimento
        FROM vw_status_ferramentas
        """ + filtro,
        params,
    )[0]
    ferramentas = registros(
        """
        SELECT id, codigo, nome, categoria, localizacao, responsavel,
               data_validade, dias_para_vencer, status, cor_status,
               vence_em_30_dias, esta_vencida
        FROM vw_status_ferramentas
        """ + filtro + " ORDER BY dias_para_vencer, nome",
        params,
    )
    meses = registros(
        """
        SELECT ano_mes_vencimento, SUM(qtd_ferramentas) AS qtd_ferramentas,
               SUM(custo_previsto) AS custo_previsto
        FROM vw_vencimentos_mensais
        """ + (" WHERE categoria = :categoria" if categoria else "") + """
        GROUP BY ano_mes_vencimento
        ORDER BY ano_mes_vencimento
        """,
        params,
    )
    categorias = registros(
        "SELECT DISTINCT categoria FROM vw_status_ferramentas ORDER BY categoria"
    )
    return jsonify({
        "kpis": kpis,
        "ferramentas": ferramentas,
        "meses": meses,
        "categorias": [item["categoria"] for item in categorias],
        "atualizado_em": date.today().isoformat(),
    })


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
