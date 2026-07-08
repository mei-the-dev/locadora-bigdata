# ============================================================================
# fleetlib.scoring - score de conducao (0..100) derivado da telemetria diaria.
# Alimenta Dim_FaixaConducao (Economico/Moderado/Agressivo) e o fator_tarifa do
# motor de cobranca. Featurizacao pura -> testavel; o mesmo calculo e usado pelo
# job Flink (analise continua) e pelo gold_dimensional (Spark). Ementa II/III
# (agente + score); Armbrust 2015 (DataFrame como pipeline de ML).
# ============================================================================
"""Score de conducao e mapeamento para faixa (banda tarifaria)."""

from __future__ import annotations

from dataclasses import dataclass

# Bandas exatamente iguais ao seed do 06_ddl_extensao.sql (Dim_FaixaConducao).
# (sk, faixa, score_min, score_max, fator_tarifa)
BANDAS: tuple[tuple[int, str, float, float, float], ...] = (
    (1, "Economico", 75.00, 100.00, 0.950),
    (2, "Moderado", 50.00, 74.99, 1.000),
    (3, "Agressivo", 0.00, 49.99, 1.150),
)

# Pesos de penalizacao (calibrados; documentados como constantes, nao magicos).
_PESO_EVENTO_BRUSCO = 4.0  # por evento brusco / 100 km
_PESO_EXCESSO_VELOCIDADE = 0.8  # por km/h acima do limite de referencia
_LIMITE_VELOCIDADE_REF = 90.0  # km/h de referencia urbana/rodoviaria
_PESO_CONSUMO = 0.5  # por ponto percentual de bateria/100km acima da referencia
_CONSUMO_REF = 18.0  # % de bateria por 100 km considerado eficiente


@dataclass(frozen=True)
class FeaturesConducao:
    """Features diarias por veiculo para o score (vindas do agregado Silver)."""

    km_rodados: float
    velocidade_media: float
    velocidade_maxima: float
    eventos_bruscos: int
    consumo_bateria_pct: float  # % de bateria consumida no periodo


def calcular_score(f: FeaturesConducao) -> float:
    """Score 0..100 (maior = mais suave/economico). Penaliza excessos.

    Deterministico e monotonico: mais eventos bruscos / velocidade / consumo
    sempre reduzem (ou mantem) o score. Piso 0, teto 100.
    """
    base = 100.0
    km = max(f.km_rodados, 1.0)  # evita divisao por zero em dias parados

    penal_bruscos = _PESO_EVENTO_BRUSCO * (f.eventos_bruscos * 100.0 / km)
    excesso = max(f.velocidade_maxima - _LIMITE_VELOCIDADE_REF, 0.0)
    penal_veloc = _PESO_EXCESSO_VELOCIDADE * excesso
    consumo_por_100km = f.consumo_bateria_pct * 100.0 / km
    penal_consumo = _PESO_CONSUMO * max(consumo_por_100km - _CONSUMO_REF, 0.0)

    score = base - penal_bruscos - penal_veloc - penal_consumo
    return round(max(0.0, min(100.0, score)), 2)


def faixa_do_score(score: float) -> tuple[int, str, float]:
    """Mapeia score -> (sk_faixa_conducao, faixa, fator_tarifa).

    Score fora de 0..100 ou None -> membro -1 (Nao_informado), fator 1.0.
    """
    if score is None or score < 0 or score > 100:
        return (-1, "Nao_informado", 1.000)
    for sk, faixa, smin, smax, fator in BANDAS:
        if smin <= score <= smax:
            return (sk, faixa, fator)
    # Fronteira 74.99..75.00: cai em Economico por seguranca.
    return (1, "Economico", 0.950)


def probabilidade_falha(f: FeaturesConducao, horas_desde_manutencao: float) -> float:
    """Heuristica 0..1 de manutencao preditiva (Fato_Manutencao.probabilidade_falha).

    Combina desgaste por uso (km + eventos bruscos) e tempo desde a ultima
    manutencao via saturacao logistica. Deterministica e limitada a [0,1].
    """
    from math import exp

    desgaste = (
        0.0009 * f.km_rodados
        + 0.02 * f.eventos_bruscos
        + 0.0007 * horas_desde_manutencao
        + 0.01 * max(f.velocidade_maxima - _LIMITE_VELOCIDADE_REF, 0.0)
    )
    prob = 1.0 / (1.0 + exp(-(desgaste - 3.0)))
    return round(max(0.0, min(1.0, prob)), 4)
