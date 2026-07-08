# ============================================================================
# fleetlib.aggregates - agregacoes do CUBO executivo (Gray 1997).
# Classifica funcoes em DISTRIBUTIVA (SUM/COUNT/MIN/MAX - roll-up direto),
# ALGEBRICA (AVG = SUM/COUNT - roll-up via componentes) e HOLISTICA (MEDIANA/
# DISTINCT - nao faz roll-up incremental). Base do 08_agregados_cube.sql com
# subtotais ALL. Fundamento: Gray 1997 (CUBE, ALL, classes de agregacao).
# ============================================================================
"""Funcoes de agregacao classificadas (distributiva/algebrica/holistica)."""

from __future__ import annotations

from statistics import median
from typing import Iterable, Sequence

ALL = "ALL"  # membro de subtotal do CUBE (Gray 1997)


# --- Distributivas: roll-up direto (o agregado do todo = agg dos parciais) ----
def soma(valores: Iterable[float]) -> float:
    """SUM - distributiva."""
    return float(sum(valores))


def contagem(valores: Sequence) -> int:
    """COUNT - distributiva."""
    return len(valores)


def maximo(valores: Iterable[float]) -> float:
    """MAX - distributiva."""
    vs = list(valores)
    return max(vs) if vs else 0.0


def minimo(valores: Iterable[float]) -> float:
    """MIN - distributiva."""
    vs = list(valores)
    return min(vs) if vs else 0.0


# --- Algebricas: roll-up via componentes distributivos (SUM e COUNT) ----------
def media(valores: Sequence[float]) -> float:
    """AVG = SUM/COUNT - algebrica. Retorna 0.0 para conjunto vazio."""
    if not valores:
        return 0.0
    return soma(valores) / contagem(valores)


def rollup_media(parciais: Iterable[tuple[float, int]]) -> float:
    """Combina medias parciais (soma, contagem) num AVG global (algebrica).

    Demonstra por que AVG e algebrica: guardando (SUM, COUNT) por celula, o
    subtotal ALL sai sem revisitar os dados-base (Gray 1997).
    """
    total_soma = 0.0
    total_cont = 0
    for s, c in parciais:
        total_soma += s
        total_cont += c
    return total_soma / total_cont if total_cont else 0.0


# --- Holisticas: NAO fazem roll-up incremental (precisam dos dados-base) -------
def mediana(valores: Sequence[float]) -> float:
    """MEDIAN - holistica (nao combina a partir de subtotais)."""
    return float(median(valores)) if valores else 0.0


def distintos(valores: Iterable) -> int:
    """COUNT(DISTINCT) - holistica."""
    return len(set(valores))


def cubo_2d(
    fatos: Sequence[tuple[str, str, float]],
) -> dict[tuple[str, str], float]:
    """CUBE de 2 dimensoes com subtotais ALL, medindo SUM (distributiva).

    Entrada: linhas (dim_a, dim_b, medida). Saida: dict {(a,b): sum} incluindo
    as celulas de subtotal (a, ALL), (ALL, b) e o grande total (ALL, ALL) -
    exatamente o comportamento do operador CUBE (Gray 1997).
    """
    resultado: dict[tuple[str, str], float] = {}

    def _add(chave: tuple[str, str], v: float) -> None:
        resultado[chave] = resultado.get(chave, 0.0) + v

    for a, b, medida in fatos:
        _add((a, b), medida)  # celula base
        _add((a, ALL), medida)  # subtotal por dim_a
        _add((ALL, b), medida)  # subtotal por dim_b
        _add((ALL, ALL), medida)  # grande total
    return resultado
