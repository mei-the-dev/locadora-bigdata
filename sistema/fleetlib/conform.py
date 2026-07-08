# ============================================================================
# fleetlib.conform - conformacao Silver (equivale as etapas 02/03 do ETL Av.02).
# Normaliza dominios (cambio -> {Automatico|Manual}), UF, faixa etaria e a chave
# de dedup (vehicle_id + timestamp). Usada pelo silver_conform (Spark) e testada
# por unidade. Fundamento: Armbrust 2015 (transformacoes declarativas com
# pushdown); Ghemawat 2003 (dedup por chave na transicao Bronze->Silver).
# ============================================================================
"""Funcoes puras de conformacao/limpeza da camada Silver."""

from __future__ import annotations

import unicodedata

# Dominio fechado de cambio (Dim_Veiculo.mecanizacao).
_AUTOMATICO = {"automatico", "automatica", "auto", "a", "at", "cvt", "automatizado", "tiptronic"}
_MANUAL = {"manual", "m", "mt", "mecanico", "cambio manual"}

_UF_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}

NAO_INFORMADO = "Nao_informado"


def _sem_acento(texto: str) -> str:
    """Remove acentos e normaliza para comparacao de dominio."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def conformar_cambio(valor: str | None) -> str:
    """Conforma o cambio ao dominio fechado {Automatico|Manual|Nao_informado}."""
    if valor is None:
        return NAO_INFORMADO
    chave = _sem_acento(valor.strip().lower())
    if chave in _AUTOMATICO:
        return "Automatico"
    if chave in _MANUAL:
        return "Manual"
    return NAO_INFORMADO


def conformar_uf(valor: str | None) -> str:
    """Valida e normaliza UF (2 letras maiusculas) ou retorna sentinela."""
    if not valor:
        return NAO_INFORMADO
    uf = _sem_acento(valor.strip().upper())
    return uf if uf in _UF_VALIDAS else NAO_INFORMADO


def faixa_etaria(idade: int | None) -> str:
    """Deriva faixa etaria (Jovem/Adulto/Senior) - atributo de Dim_Cliente.

    Jovem: 18..29; Adulto: 30..59; Senior: 60+. Fora de faixa/None -> sentinela.
    """
    if idade is None or idade < 18:
        return NAO_INFORMADO
    if idade <= 29:
        return "Jovem"
    if idade <= 59:
        return "Adulto"
    return "Senior"


def faixa_horaria(hora: int) -> str:
    """Faixa horaria (Dim_Tempo_Detalhe.faixa_horaria) a partir da hora 0..23.

    Alinhada ao CASE do 06_ddl_extensao.sql:
    Madrugada 0-5, Manha 6-11, Tarde 12-17, Noite 18-23.
    """
    if not 0 <= hora <= 23:
        return NAO_INFORMADO
    if hora <= 5:
        return "Madrugada"
    if hora <= 11:
        return "Manha"
    if hora <= 17:
        return "Tarde"
    return "Noite"


def is_horario_pico(hora: int) -> bool:
    """Marca horario de pico (Dim_Tempo_Detalhe.is_horario_pico)."""
    return hora in (7, 8, 9, 17, 18, 19)


def chave_dedup(vehicle_id: str, event_ts: int) -> str:
    """Chave de deduplicacao Bronze->Silver (vehicle_id + timestamp).

    Garante idempotencia do reprocesso (mesmo estado apos rerun) - Zaharia 2013.
    """
    if not vehicle_id:
        raise ValueError("vehicle_id obrigatorio na chave de dedup")
    return f"{vehicle_id}#{event_ts}"


def deduplicar(registros: list[dict]) -> list[dict]:
    """Remove duplicatas por (vehicle_id, event_ts), mantendo a 1a ocorrencia.

    Preserva a ordem de chegada; idempotente. Espera dicts com as chaves
    'vehicle_id' e 'event_ts'.
    """
    vistos: set[str] = set()
    saida: list[dict] = []
    for r in registros:
        k = chave_dedup(r["vehicle_id"], r["event_ts"])
        if k in vistos:
            continue
        vistos.add(k)
        saida.append(r)
    return saida


def sk_tempo(ano: int, mes: int, dia: int) -> int:
    """Surrogate key de Dim_Tempo no formato AAAAMMDD (compat. com 04_carga)."""
    return ano * 10000 + mes * 100 + dia


def sk_tempo_detalhe(hora: int, minuto: int) -> int:
    """Surrogate key de Dim_Tempo_Detalhe no formato HHMM (compat. com 06_ddl)."""
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        return -1
    return hora * 100 + minuto
