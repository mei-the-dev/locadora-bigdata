# ============================================================================
# fleetlib.billing - motor de cobranca automatica pos-uso (R7).
# Calculo DETERMINISTICO das medidas aditivas de Fato_Cobranca
# (valor_base + acrescimo_km + acrescimo_tempo + acrescimo_consumo*fator_tarifa
#  + multa_infracao - desconto = valor_final). Exactly-once por id_locacao
# (dimensao degenerada UNIQUE): reprocessar a mesma locacao NAO duplica valor
# (Zaharia 2013). Cobranca exige ACID -> reside no PostgreSQL Gold (Cattell 2011).
# ============================================================================
"""Motor de cobranca pos-uso: calculo deterministico + idempotencia."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .scoring import faixa_do_score

# Tabela tarifaria por categoria (diaria base + preco por km). Constantes de
# negocio explicitas (sem numeros magicos espalhados).
TARIFA_DIARIA: dict[str, Decimal] = {
    "Economico": Decimal("89.90"),
    "Intermediario": Decimal("119.90"),
    "SUV": Decimal("189.90"),
    "Executivo": Decimal("249.90"),
    "Utilitario": Decimal("159.90"),
}
PRECO_KM = Decimal("1.20")  # R$/km rodado
PRECO_HORA_EXTRA = Decimal("35.00")  # R$/hora alem da diaria contratada
PRECO_CONSUMO_BASE = Decimal("0.90")  # R$/% de bateria consumida (modulado pela faixa)
CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class LocacaoFaturavel:
    """Entrada do faturamento (uma locacao encerrada)."""

    id_locacao: str
    categoria: str
    dias_contratados: int
    km_rodados: Decimal
    horas_extra: Decimal
    consumo_bateria_pct: Decimal
    score_conducao: float
    multa_infracao: Decimal = Decimal("0")
    desconto: Decimal = Decimal("0")


@dataclass(frozen=True)
class Cobranca:
    """Resultado do faturamento (mapa 1:1 com Fato_Cobranca)."""

    id_locacao: str
    sk_faixa_conducao: int
    valor_base: Decimal
    acrescimo_km: Decimal
    acrescimo_tempo: Decimal
    acrescimo_consumo: Decimal
    multa_infracao: Decimal
    desconto: Decimal
    valor_final: Decimal


def _q(valor: Decimal) -> Decimal:
    """Quantiza para centavos (2 casas, arredondamento comercial)."""
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_cobranca(loc: LocacaoFaturavel) -> Cobranca:
    """Calcula a cobranca de uma locacao (deterministico, aditivo).

    A faixa de conducao (do score) modula APENAS acrescimo_consumo, via
    fator_tarifa (Economico 0.95 / Moderado 1.00 / Agressivo 1.15) - a mesma
    semantica de Dim_FaixaConducao.fator_tarifa no 06_ddl.

    Raises:
        ValueError: categoria desconhecida ou medidas negativas.
    """
    if loc.categoria not in TARIFA_DIARIA:
        raise ValueError(f"categoria desconhecida: {loc.categoria}")
    if loc.dias_contratados < 0 or loc.km_rodados < 0 or loc.horas_extra < 0:
        raise ValueError("medidas de locacao nao podem ser negativas")

    sk_faixa, _faixa, fator = faixa_do_score(loc.score_conducao)
    fator_dec = Decimal(str(fator))

    valor_base = _q(TARIFA_DIARIA[loc.categoria] * Decimal(loc.dias_contratados))
    acrescimo_km = _q(PRECO_KM * loc.km_rodados)
    acrescimo_tempo = _q(PRECO_HORA_EXTRA * loc.horas_extra)
    acrescimo_consumo = _q(PRECO_CONSUMO_BASE * loc.consumo_bateria_pct * fator_dec)
    multa = _q(loc.multa_infracao)
    desconto = _q(loc.desconto)

    valor_final = valor_base + acrescimo_km + acrescimo_tempo + acrescimo_consumo + multa - desconto
    valor_final = _q(max(valor_final, Decimal("0")))  # ck_cob_final: >= 0

    return Cobranca(
        id_locacao=loc.id_locacao,
        sk_faixa_conducao=sk_faixa,
        valor_base=valor_base,
        acrescimo_km=acrescimo_km,
        acrescimo_tempo=acrescimo_tempo,
        acrescimo_consumo=acrescimo_consumo,
        multa_infracao=multa,
        desconto=desconto,
        valor_final=valor_final,
    )


class LivroCobranca:
    """Livro idempotente de cobrancas (emula UNIQUE(id_locacao) do Gold).

    Garante EXACTLY-ONCE de faturamento: registrar a mesma locacao mais de uma
    vez nao altera o total (Zaharia 2013 - discretizacao deterministica evita
    dupla contagem). Espelha o ON CONFLICT (id_locacao) DO NOTHING do Postgres.
    """

    def __init__(self) -> None:
        self._por_locacao: dict[str, Cobranca] = {}

    def registrar(self, cobranca: Cobranca) -> bool:
        """Registra a cobranca; retorna True se inserida, False se ja existia."""
        if cobranca.id_locacao in self._por_locacao:
            return False
        self._por_locacao[cobranca.id_locacao] = cobranca
        return True

    def total_faturado(self) -> Decimal:
        """Soma aditiva de valor_final de todas as cobrancas unicas."""
        return _q(sum((c.valor_final for c in self._por_locacao.values()), Decimal("0")))

    def __len__(self) -> int:
        return len(self._por_locacao)
