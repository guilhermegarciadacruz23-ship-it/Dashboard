"""Conexão com o PostgreSQL e helpers de consulta."""
from __future__ import annotations

import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ferramentas")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_SCHEMA = os.getenv("DB_SCHEMA", "ferramentaria")

_engine: Engine | None = None


def get_engine() -> Engine:
    """Engine singleton, já com o search_path apontando para o schema."""
    global _engine
    if _engine is None:
        url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={DB_SCHEMA},public"},
        )
    return _engine


def consultar(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Executa um SELECT e devolve um DataFrame."""
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def executar(sql: str, params: dict | None = None) -> int:
    """Executa INSERT/UPDATE/DELETE e devolve o número de linhas afetadas."""
    with get_engine().begin() as conn:
        result = conn.execute(text(sql), params or {})
        return result.rowcount or 0


def testar_conexao() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha na conexão: {exc}")
        return False
