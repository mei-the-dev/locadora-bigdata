# ============================================================================
# fleetlib.markov - matriz estocastica de movimentacao entre patios.
# Reproduz, em Python puro, a matriz do 05_relatorios_matriz.sql (P(i->j) =
# mov(i,j)/sum_j mov(i,j)) e estende para a versao CONDICIONAL (faixa horaria /
# categoria) proposta no plano (secao 3.6). Cada linha soma 1.0 (criterio de
# aceite da Fase 5). Fundamento: Zaharia 2012 (iterativo em memoria); modelo DW.
# ============================================================================
"""Cadeia de Markov de redistribuicao de frota (matriz estocastica por linhas)."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

Movimento = tuple[str, str]  # (patio_origem, patio_destino)


def contar_movimentos(movimentos: Iterable[Movimento]) -> dict[Movimento, int]:
    """Conta ocorrencias de (origem, destino) - base da matriz (Fato_Movimentacao)."""
    contagem: dict[Movimento, int] = defaultdict(int)
    for origem, destino in movimentos:
        contagem[(origem, destino)] += 1
    return dict(contagem)


def matriz_transicao(contagem: Mapping[Movimento, int]) -> dict[str, dict[str, float]]:
    """Normaliza contagens em matriz estocastica: linha por origem soma 1.0.

    P(i->j) = mov(i,j) / total_saidas(i). Origens sem saida ficam ausentes
    (nao ha transicao definida). Resultado arredondado a 6 casas para leitura.
    """
    total_saidas: dict[str, int] = defaultdict(int)
    for (origem, _destino), n in contagem.items():
        total_saidas[origem] += n

    matriz: dict[str, dict[str, float]] = defaultdict(dict)
    for (origem, destino), n in contagem.items():
        total = total_saidas[origem]
        matriz[origem][destino] = round(n / total, 6) if total else 0.0
    return {origem: dict(linha) for origem, linha in matriz.items()}


def soma_linhas(matriz: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """Soma de cada linha (deve ser ~1.0 para toda origem com saidas)."""
    return {origem: round(sum(linha.values()), 6) for origem, linha in matriz.items()}


def linha_estocastica(soma: float, tol: float = 1e-6) -> bool:
    """True se a soma de uma linha vale 1.0 dentro da tolerancia."""
    return abs(soma - 1.0) <= tol


def matriz_condicional(
    movimentos: Iterable[tuple[str, str, str]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Matriz CONDICIONAL por contexto (ex.: faixa horaria ou categoria).

    Entrada: iteravel de (contexto, origem, destino). Retorna
    {contexto: {origem: {destino: prob}}}, cada linha (contexto, origem)
    somando 1.0. Fecha a lacuna 9 do modelo atual (Markov homogenea) - plano 3.6.
    """
    por_contexto: dict[str, list[Movimento]] = defaultdict(list)
    for contexto, origem, destino in movimentos:
        por_contexto[contexto].append((origem, destino))

    return {
        contexto: matriz_transicao(contar_movimentos(mv))
        for contexto, mv in por_contexto.items()
    }


def distribuicao_estacionaria(
    matriz: Mapping[str, Mapping[str, float]],
    iteracoes: int = 200,
    tol: float = 1e-9,
) -> dict[str, float]:
    """Distribuicao estacionaria pi (pi = pi P) por iteracao de potencia.

    Util para prever a ocupacao de longo prazo dos patios (reposicionamento do
    veiculo vazio - R12). Metodo iterativo em memoria (Zaharia 2012). Comeca
    uniforme e itera ate convergir ou atingir o limite de iteracoes.
    """
    estados = sorted({o for o in matriz} | {d for linha in matriz.values() for d in linha})
    if not estados:
        return {}
    pi = {s: 1.0 / len(estados) for s in estados}

    for _ in range(iteracoes):
        novo = {s: 0.0 for s in estados}
        for origem in estados:
            linha = matriz.get(origem, {})
            massa = pi[origem]
            if not linha:
                # Estado absorvente/sem saida: mantem a massa (self-loop implicito).
                novo[origem] += massa
                continue
            for destino, prob in linha.items():
                novo[destino] += massa * prob
        delta = sum(abs(novo[s] - pi[s]) for s in estados)
        pi = novo
        if delta < tol:
            break

    total = sum(pi.values()) or 1.0
    return {s: round(pi[s] / total, 6) for s in estados}
