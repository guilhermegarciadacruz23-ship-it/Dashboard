"""Verificação automática de validade das ferramentas.

Regras de faixa:
    VENCIDA    -> dias_para_vencer < 0
    CRITICO_7  -> 0 a 7 dias
    ALERTA_15  -> 8 a 15 dias
    AVISO_30   -> 16 a 30 dias   (o aviso pedido: 30 dias antes de vencer)

Cada combinação (ferramenta + faixa + data_validade) gera um único registro
na tabela `alerta`, então rodar o script várias vezes no dia não duplica aviso.
"""
from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

import pandas as pd
from dotenv import load_dotenv

from db import consultar, executar

load_dotenv()

DIAS_AVISO = int(os.getenv("DIAS_AVISO", "30"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")
EMAIL_DE = os.getenv("EMAIL_REMETENTE", SMTP_USER)
EMAIL_PARA = [e.strip() for e in os.getenv("EMAIL_DESTINATARIOS", "").split(",") if e.strip()]


# ---------------------------------------------------------------------
# 1. Leitura
# ---------------------------------------------------------------------
def buscar_pendencias(dias: int = DIAS_AVISO) -> pd.DataFrame:
    """Ferramentas vencidas ou que vencem dentro da janela informada."""
    return consultar(
        """
        SELECT id, codigo, nome, categoria, localizacao, responsavel,
               data_ultima_calibracao, data_validade, dias_para_vencer, status
        FROM vw_status_ferramentas
        WHERE dias_para_vencer <= :dias
        ORDER BY dias_para_vencer
        """,
        {"dias": dias},
    )


def classificar(dias: int) -> str:
    if dias < 0:
        return "VENCIDA"
    if dias <= 7:
        return "CRITICO_7"
    if dias <= 15:
        return "ALERTA_15"
    return "AVISO_30"


# ---------------------------------------------------------------------
# 2. Gravação dos alertas
# ---------------------------------------------------------------------
def registrar_alertas(df: pd.DataFrame) -> pd.DataFrame:
    """Insere os alertas novos e devolve apenas os que foram criados agora."""
    novos = []
    for _, row in df.iterrows():
        faixa = classificar(int(row["dias_para_vencer"]))
        inseridos = executar(
            """
            INSERT INTO alerta (ferramenta_id, faixa, dias_restantes, data_validade)
            VALUES (:fid, :faixa, :dias, :validade)
            ON CONFLICT ON CONSTRAINT uq_alerta DO NOTHING
            """,
            {
                "fid": int(row["id"]),
                "faixa": faixa,
                "dias": int(row["dias_para_vencer"]),
                "validade": row["data_validade"],
            },
        )
        if inseridos:
            item = row.to_dict()
            item["faixa"] = faixa
            novos.append(item)
    return pd.DataFrame(novos)


def marcar_enviados(codigos: list[str]) -> None:
    if not codigos:
        return
    executar(
        """
        UPDATE alerta a
           SET status_envio = 'ENVIADO', enviado_em = NOW()
          FROM ferramenta f
         WHERE f.id = a.ferramenta_id
           AND a.status_envio = 'PENDENTE'
           AND f.codigo = ANY(:codigos)
        """,
        {"codigos": codigos},
    )


# ---------------------------------------------------------------------
# 3. E-mail
# ---------------------------------------------------------------------
def montar_html(df: pd.DataFrame) -> str:
    cores = {
        "VENCIDA": "#B00020",
        "CRITICO_7": "#E53935",
        "ALERTA_15": "#FB8C00",
        "AVISO_30": "#F9A825",
    }
    linhas = []
    for _, r in df.iterrows():
        cor = cores.get(r["faixa"], "#555")
        dias = int(r["dias_para_vencer"])
        prazo = f"{dias} dia(s)" if dias >= 0 else f"vencida há {abs(dias)} dia(s)"
        linhas.append(
            f"<tr>"
            f"<td>{r['codigo']}</td><td>{r['nome']}</td>"
            f"<td>{r['localizacao']}</td><td>{r['responsavel'] or '-'}</td>"
            f"<td>{r['data_validade']}</td>"
            f"<td style='color:{cor};font-weight:bold'>{prazo}</td>"
            f"<td style='color:{cor};font-weight:bold'>{r['faixa']}</td>"
            f"</tr>"
        )
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#222">
      <h2>Alerta de validade de ferramentas</h2>
      <p>Foram identificadas <b>{len(df)}</b> ferramentas que vencem em até
         {DIAS_AVISO} dias ou já estão vencidas.</p>
      <table border="0" cellpadding="8" cellspacing="0"
             style="border-collapse:collapse;font-size:14px">
        <thead style="background:#f0f0f0">
          <tr><th>Código</th><th>Ferramenta</th><th>Local</th><th>Responsável</th>
              <th>Validade</th><th>Prazo</th><th>Faixa</th></tr>
        </thead>
        <tbody>{''.join(linhas)}</tbody>
      </table>
      <p style="font-size:12px;color:#777">
        Gerado automaticamente em {datetime.now():%d/%m/%Y %H:%M}.
      </p>
    </body></html>
    """


def enviar_email(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    if not (SMTP_USER and SMTP_PASS and EMAIL_PARA):
        print("[AVISO] SMTP não configurado no .env — e-mail não enviado.")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"[Ferramentaria] {len(df)} ferramenta(s) exigem atenção"
    msg["From"] = EMAIL_DE
    msg["To"] = ", ".join(EMAIL_PARA)
    msg.set_content("Seu cliente de e-mail não suporta HTML. Acesse o dashboard.")
    msg.add_alternative(montar_html(df), subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print(f"[OK] E-mail enviado para {len(EMAIL_PARA)} destinatário(s).")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[ERRO] Falha no envio do e-mail: {exc}")
        return False


# ---------------------------------------------------------------------
# 4. Rotina principal
# ---------------------------------------------------------------------
def executar_verificacao(enviar: bool = True, apenas_novos: bool = True) -> pd.DataFrame:
    pendentes = buscar_pendencias()
    print(f"[INFO] {len(pendentes)} ferramenta(s) dentro da janela de {DIAS_AVISO} dias.")
    if pendentes.empty:
        return pendentes

    novos = registrar_alertas(pendentes)
    print(f"[INFO] {len(novos)} alerta(s) novo(s) registrado(s).")

    base = novos if apenas_novos else pendentes
    if enviar and not base.empty:
        if "faixa" not in base.columns:
            base = base.assign(faixa=base["dias_para_vencer"].astype(int).map(classificar))
        if enviar_email(base):
            marcar_enviados(base["codigo"].tolist())

    return pendentes


if __name__ == "__main__":
    executar_verificacao()
