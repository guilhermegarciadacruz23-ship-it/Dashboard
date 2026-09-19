"""CLI do sistema de controle de validade de ferramentas.

Exemplos:
    python main.py testar
    python main.py importar ../dados/ferramentas_exemplo.csv
    python main.py verificar               # grava alertas + envia e-mail
    python main.py verificar --sem-email
    python main.py painel                  # resumo no terminal
    python main.py web                     # inicia o dashboard web
    python main.py exportar                # envia para o Google Sheets
"""
from __future__ import annotations

import argparse

from db import consultar, testar_conexao


def cmd_testar() -> None:
    print("[OK] Conexão bem-sucedida." if testar_conexao() else "[ERRO] Sem conexão.")


def cmd_painel() -> None:
    kpis = consultar("SELECT * FROM vw_kpis").iloc[0]
    print("\n=== PAINEL DE VALIDADE DE FERRAMENTAS ===")
    print(f"Total cadastrado ........ {kpis['total_ferramentas']}")
    print(f"Em dia .................. {kpis['qtd_ok']}")
    print(f"Atenção (31-60 dias) .... {kpis['qtd_atencao_60d']}")
    print(f"Vencendo em 30 dias ..... {kpis['qtd_vencendo_30d']}")
    print(f"Crítico (<= 7 dias) ..... {kpis['qtd_critico_7d']}")
    print(f"Vencidas ................ {kpis['qtd_vencidas']}")
    print(f"Conformidade ............ {kpis['perc_conformidade']}%")

    df = consultar("SELECT * FROM vw_alertas_ativos")
    if df.empty:
        print("\nNenhuma pendência nos próximos 30 dias.\n")
        return
    print("\n--- Ferramentas que exigem ação ---")
    print(df[["codigo", "nome", "data_validade", "dias_para_vencer", "status"]]
          .to_string(index=False))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Controle de validade de ferramentas")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("testar", help="Testa a conexão com o banco")
    sub.add_parser("painel", help="Mostra o resumo no terminal")
    sub.add_parser("exportar", help="Exporta as views para o Google Sheets")
    sub.add_parser("web", help="Inicia o dashboard web")

    p_imp = sub.add_parser("importar", help="Importa ferramentas de CSV/Excel")
    p_imp.add_argument("arquivo")

    p_ver = sub.add_parser("verificar", help="Verifica validades e dispara alertas")
    p_ver.add_argument("--sem-email", action="store_true", help="Não envia e-mail")
    p_ver.add_argument("--todos", action="store_true",
                       help="Inclui no e-mail também os alertas já registrados")

    args = parser.parse_args()

    if args.comando == "testar":
        cmd_testar()
    elif args.comando == "painel":
        cmd_painel()
    elif args.comando == "importar":
        from pathlib import Path

        from importar import importar as importar_arquivo

        novos, alterados = importar_arquivo(Path(args.arquivo))
        print(f"[OK] {novos} inserida(s), {alterados} atualizada(s).")
    elif args.comando == "verificar":
        from alertas import executar_verificacao

        executar_verificacao(enviar=not args.sem_email, apenas_novos=not args.todos)
    elif args.comando == "exportar":
        from exportar_sheets import exportar

        exportar()
    elif args.comando == "web":
        from app import app

        app.run(debug=True, host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
