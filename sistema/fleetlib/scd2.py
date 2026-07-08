# ============================================================================
# fleetlib.scd2 - Slowly Changing Dimension Tipo 2 (Dim_Sensor / firmware).
# Substitui o TRUNCATE+ROW_NUMBER (SK nao persistente) da Av.02 por SK estavel +
# versionamento valid_from/valid_to/is_current, viabilizando ingestao incremental
# e reconstrucao point-in-time do dossie regulatorio (R8). Fundamento: Corbett
# 2012 (snapshot read no passado); Armbrust 2020 (time travel). Logica pura.
# ============================================================================
"""Versionamento SCD Tipo 2 para dimensoes auditaveis (ex.: Dim_Sensor)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

DATA_FIM_ABERTO = date(9999, 12, 31)
DATA_INICIO_PADRAO = date(1900, 1, 1)


@dataclass(frozen=True)
class VersaoDim:
    """Uma versao de linha de dimensao SCD2 (SK estavel + vigencia)."""

    sk: int
    natural_key: str  # ex.: id_sensor_origem
    atributos: tuple[tuple[str, str], ...]  # atributos versionados (ordenados)
    valid_from: date
    valid_to: date
    is_current: bool

    def atributos_dict(self) -> dict[str, str]:
        return dict(self.atributos)


def _normalizar_atributos(attrs: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """Ordena atributos para comparacao estavel entre versoes."""
    return tuple(sorted((k, str(v)) for k, v in attrs.items()))


def aplicar_mudanca(
    versoes: list[VersaoDim],
    natural_key: str,
    novos_atributos: dict[str, str],
    vigencia: date,
    proximo_sk: int,
) -> tuple[list[VersaoDim], int]:
    """Aplica uma leitura da fonte ao historico SCD2 de uma natural_key.

    Regras:
      - Se nao ha versao corrente, insere a 1a versao (SK = proximo_sk).
      - Se os atributos versionados sao iguais aos correntes: no-op (idempotente).
      - Se mudaram: fecha a versao corrente (valid_to = vigencia, is_current=False)
        e abre nova versao (valid_from = vigencia, SK novo).

    Retorna (historico_atualizado, proximo_sk_disponivel). Nao muta a lista de
    entrada (retorna nova lista - estilo imutavel).
    """
    novos_norm = _normalizar_atributos(novos_atributos)
    correntes = [v for v in versoes if v.natural_key == natural_key and v.is_current]
    outras = [v for v in versoes if not (v.natural_key == natural_key and v.is_current)]

    if not correntes:
        nova = VersaoDim(
            sk=proximo_sk,
            natural_key=natural_key,
            atributos=novos_norm,
            valid_from=vigencia,
            valid_to=DATA_FIM_ABERTO,
            is_current=True,
        )
        return (outras + [nova], proximo_sk + 1)

    corrente = correntes[0]
    if corrente.atributos == novos_norm:
        # Sem mudanca: historico inalterado, SK preservado (idempotencia).
        return (versoes, proximo_sk)

    fechada = replace(corrente, valid_to=vigencia, is_current=False)
    nova = VersaoDim(
        sk=proximo_sk,
        natural_key=natural_key,
        atributos=novos_norm,
        valid_from=vigencia,
        valid_to=DATA_FIM_ABERTO,
        is_current=True,
    )
    return (outras + [fechada, nova], proximo_sk + 1)


def versao_vigente_em(versoes: list[VersaoDim], natural_key: str, quando: date) -> VersaoDim | None:
    """Retorna a versao vigente da natural_key em uma data (point-in-time).

    Base do dossie regulatorio: "qual firmware o sensor rodava no instante do
    sinistro?" (Armbrust 2020; Corbett 2012). Vigencia = [valid_from, valid_to).
    """
    candidatas = [
        v
        for v in versoes
        if v.natural_key == natural_key and v.valid_from <= quando < v.valid_to
    ]
    if not candidatas:
        return None
    # Em caso de sobreposicao (nao deveria ocorrer), prioriza a de inicio mais recente.
    return max(candidatas, key=lambda v: v.valid_from)
