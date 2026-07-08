# ============================================================================
# app/billing/billing_engine.py - motor de cobranca pos-uso (R7).
# Calcula a cobranca com fleetlib.billing (deterministico, testado) e PERSISTE em
# Fato_Cobranca com INSERT ... ON CONFLICT (id_locacao) DO NOTHING -> EXACTLY-ONCE
# no faturamento: reprocessar a mesma locacao NAO duplica o valor (Zaharia 2013).
# Cobranca exige ACID -> reside no PostgreSQL Gold (Cattell 2011).
# Uso (CLI): python billing_engine.py --id LOC-2001 --categoria SUV --dias 3 \
#            --km 120 --horas-extra 2 --consumo 20 --score 82 \
#            --sk-cliente 1 --sk-veiculo 3 --sk-empresa 3
# ============================================================================
"""Motor de cobrança pós-uso: calcula (fleetlib) e persiste (exactly-once)."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.common import db  # noqa: E402
from fleetlib.billing import LocacaoFaturavel, calcular_cobranca  # noqa: E402
from fleetlib.conform import sk_tempo as _sk_tempo  # noqa: E402


@dataclass(frozen=True)
class ContextoLocacao:
    """Chaves dimensionais para gravar a cobranca na Gold."""

    sk_cliente: int
    sk_veiculo: int
    sk_empresa: int
    sk_patio_retirada: int = -1
    sk_patio_devolucao: int = -1
    sk_tempo: int | None = None  # default: hoje


_SQL_INSERT = """
INSERT INTO Fato_Cobranca
    (id_locacao, sk_cliente, sk_veiculo, sk_patio_retirada, sk_patio_devolucao,
     sk_tempo, sk_tempo_detalhe, sk_empresa, sk_faixa_conducao,
     valor_base, acrescimo_km, acrescimo_tempo, acrescimo_consumo,
     multa_infracao, desconto, valor_final)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id_locacao) DO NOTHING
"""


def faturar(loc: LocacaoFaturavel, ctx: ContextoLocacao) -> dict:
    """Calcula e persiste a cobranca. Retorna dict com o resultado + `inserido`.

    `inserido=False` indica que a locacao ja havia sido faturada (idempotencia
    exactly-once): o total NAO e alterado.
    """
    cobranca = calcular_cobranca(loc)
    from datetime import date

    sk_t = ctx.sk_tempo or _sk_tempo(date.today().year, date.today().month, date.today().day)

    afetadas = db.executar(
        _SQL_INSERT,
        (
            cobranca.id_locacao, ctx.sk_cliente, ctx.sk_veiculo, ctx.sk_patio_retirada,
            ctx.sk_patio_devolucao, sk_t, -1, ctx.sk_empresa, cobranca.sk_faixa_conducao,
            cobranca.valor_base, cobranca.acrescimo_km, cobranca.acrescimo_tempo,
            cobranca.acrescimo_consumo, cobranca.multa_infracao, cobranca.desconto,
            cobranca.valor_final,
        ),
    )
    return {
        "id_locacao": cobranca.id_locacao,
        "valor_final": str(cobranca.valor_final),
        "sk_faixa_conducao": cobranca.sk_faixa_conducao,
        "inserido": afetadas == 1,
        "detalhe": {
            "valor_base": str(cobranca.valor_base),
            "acrescimo_km": str(cobranca.acrescimo_km),
            "acrescimo_tempo": str(cobranca.acrescimo_tempo),
            "acrescimo_consumo": str(cobranca.acrescimo_consumo),
            "multa_infracao": str(cobranca.multa_infracao),
            "desconto": str(cobranca.desconto),
        },
    }


def _cli() -> None:
    ap = argparse.ArgumentParser(description="Cobranca pos-uso (exactly-once)")
    ap.add_argument("--id", required=True)
    ap.add_argument("--categoria", required=True)
    ap.add_argument("--dias", type=int, required=True)
    ap.add_argument("--km", default="0")
    ap.add_argument("--horas-extra", default="0")
    ap.add_argument("--consumo", default="0")
    ap.add_argument("--score", type=float, default=60.0)
    ap.add_argument("--multa", default="0")
    ap.add_argument("--desconto", default="0")
    ap.add_argument("--sk-cliente", type=int, default=-1)
    ap.add_argument("--sk-veiculo", type=int, default=-1)
    ap.add_argument("--sk-empresa", type=int, default=-1)
    args = ap.parse_args()

    loc = LocacaoFaturavel(
        id_locacao=args.id, categoria=args.categoria, dias_contratados=args.dias,
        km_rodados=Decimal(args.km), horas_extra=Decimal(args.horas_extra),
        consumo_bateria_pct=Decimal(args.consumo), score_conducao=args.score,
        multa_infracao=Decimal(args.multa), desconto=Decimal(args.desconto),
    )
    ctx = ContextoLocacao(sk_cliente=args.sk_cliente, sk_veiculo=args.sk_veiculo, sk_empresa=args.sk_empresa)
    import json

    print(json.dumps(faturar(loc, ctx), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _cli()
