"""Importa/atualiza o cadastro de ferramentas a partir de CSV ou Excel.

Colunas esperadas (as opcionais podem faltar):
    codigo*, nome*, data_validade*, fabricante, modelo, numero_serie,
    categoria, localizacao, responsavel, data_aquisicao,
    data_ultima_calibracao, periodicidade_meses, custo_calibracao, observacoes

Uso:
    python importar.py ../dados/ferramentas_exemplo.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from db import consultar, executar

COLUNAS_OBRIGATORIAS = {"codigo", "nome", "data_validade"}


def ler_arquivo(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(caminho)
    else:
        df = pd.read_csv(caminho, sep=None, engine="python")
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = COLUNAS_OBRIGATORIAS - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(faltando)}")
    return df


def obter_ou_criar(tabela: str, nome: str | None) -> int | None:
    """Retorna o id de categoria/localizacao, criando o registro se não existir."""
    if not nome or pd.isna(nome):
        return None
    nome = str(nome).strip()
    executar(f"INSERT INTO {tabela} (nome) VALUES (:n) ON CONFLICT (nome) DO NOTHING", {"n": nome})
    res = consultar(f"SELECT id FROM {tabela} WHERE nome = :n", {"n": nome})
    return int(res.iloc[0]["id"]) if not res.empty else None


def _data(valor) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    return pd.to_datetime(valor, dayfirst=True).date().isoformat()


def _num(valor):
    return None if valor is None or pd.isna(valor) else float(valor)


def importar(caminho: Path) -> tuple[int, int]:
    df = ler_arquivo(caminho)
    inseridos = atualizados = 0

    for _, row in df.iterrows():
        existe = consultar(
            "SELECT id FROM ferramenta WHERE codigo = :c", {"c": str(row["codigo"]).strip()}
        )
        params = {
            "codigo": str(row["codigo"]).strip(),
            "nome": str(row["nome"]).strip(),
            "fabricante": row.get("fabricante"),
            "modelo": row.get("modelo"),
            "numero_serie": row.get("numero_serie"),
            "categoria_id": obter_ou_criar("categoria", row.get("categoria")),
            "localizacao_id": obter_ou_criar("localizacao", row.get("localizacao")),
            "responsavel": row.get("responsavel"),
            "data_aquisicao": _data(row.get("data_aquisicao")),
            "data_ultima_calibracao": _data(row.get("data_ultima_calibracao")),
            "data_validade": _data(row["data_validade"]),
            "periodicidade_meses": int(row.get("periodicidade_meses") or 12),
            "custo_calibracao": _num(row.get("custo_calibracao")),
            "observacoes": row.get("observacoes"),
        }
        params = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in params.items()}

        executar(
            """
            INSERT INTO ferramenta
                (codigo, nome, fabricante, modelo, numero_serie, categoria_id,
                 localizacao_id, responsavel, data_aquisicao, data_ultima_calibracao,
                 data_validade, periodicidade_meses, custo_calibracao, observacoes)
            VALUES
                (:codigo, :nome, :fabricante, :modelo, :numero_serie, :categoria_id,
                 :localizacao_id, :responsavel, :data_aquisicao, :data_ultima_calibracao,
                 :data_validade, :periodicidade_meses, :custo_calibracao, :observacoes)
            ON CONFLICT (codigo) DO UPDATE SET
                nome = EXCLUDED.nome,
                fabricante = COALESCE(EXCLUDED.fabricante, ferramenta.fabricante),
                modelo = COALESCE(EXCLUDED.modelo, ferramenta.modelo),
                numero_serie = COALESCE(EXCLUDED.numero_serie, ferramenta.numero_serie),
                categoria_id = COALESCE(EXCLUDED.categoria_id, ferramenta.categoria_id),
                localizacao_id = COALESCE(EXCLUDED.localizacao_id, ferramenta.localizacao_id),
                responsavel = COALESCE(EXCLUDED.responsavel, ferramenta.responsavel),
                data_ultima_calibracao = COALESCE(EXCLUDED.data_ultima_calibracao,
                                                  ferramenta.data_ultima_calibracao),
                data_validade = EXCLUDED.data_validade,
                periodicidade_meses = EXCLUDED.periodicidade_meses,
                custo_calibracao = COALESCE(EXCLUDED.custo_calibracao, ferramenta.custo_calibracao),
                observacoes = COALESCE(EXCLUDED.observacoes, ferramenta.observacoes)
            """,
            params,
        )
        if existe.empty:
            inseridos += 1
        else:
            atualizados += 1

    return inseridos, atualizados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importar.py <arquivo.csv|xlsx>")
        raise SystemExit(1)
    novos, alterados = importar(Path(sys.argv[1]))
    print(f"[OK] {novos} ferramenta(s) inserida(s), {alterados} atualizada(s).")
