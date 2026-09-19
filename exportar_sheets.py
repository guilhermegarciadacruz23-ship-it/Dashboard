"""Exporta a view principal para o Google Sheets.

Use este caminho quando o PostgreSQL estiver em rede interna e o Looker Studio
não conseguir alcançá-lo. O Looker Studio então lê a planilha, que é
atualizada diariamente por este script.

Pré-requisitos:
    1. Criar um projeto no Google Cloud e ativar as APIs Sheets e Drive.
    2. Criar uma conta de serviço e baixar a chave JSON.
    3. Compartilhar a planilha com o e-mail da conta de serviço (editor).
    4. Preencher GOOGLE_CREDENTIALS e GOOGLE_SHEET_ID no .env.
"""
from __future__ import annotations

import os

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from db import consultar

load_dotenv()

CREDENCIAIS = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
ESCOPOS = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ABAS = {
    "ferramentas": "SELECT * FROM vw_status_ferramentas ORDER BY dias_para_vencer",
    "alertas": "SELECT * FROM vw_alertas_ativos",
    "vencimentos_mensais": "SELECT * FROM vw_vencimentos_mensais",
}


def _cliente() -> gspread.Client:
    creds = Credentials.from_service_account_file(CREDENCIAIS, scopes=ESCOPOS)
    return gspread.authorize(creds)


def exportar() -> None:
    if not SHEET_ID:
        raise RuntimeError("Defina GOOGLE_SHEET_ID no arquivo .env")

    planilha = _cliente().open_by_key(SHEET_ID)

    for nome_aba, sql in ABAS.items():
        df = consultar(sql).astype(str)
        try:
            aba = planilha.worksheet(nome_aba)
            aba.clear()
        except gspread.WorksheetNotFound:
            aba = planilha.add_worksheet(title=nome_aba, rows=max(len(df) + 10, 100),
                                         cols=max(len(df.columns) + 2, 20))
        aba.update([df.columns.tolist()] + df.values.tolist())
        print(f"[OK] Aba '{nome_aba}' atualizada com {len(df)} linha(s).")


if __name__ == "__main__":
    exportar()
