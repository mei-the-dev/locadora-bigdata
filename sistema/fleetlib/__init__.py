# ============================================================================
# UFRJ - IM/DMA - MAE016/EEL890 - Big Data e Data Warehouse - 2026.1
# Prof. Milton Ramos Ramirez - Avaliacao 03 (frota autonoma e conectada)
# Grupo: Izabela Lima da Silva (124156557) - Caio Meirelles (122071557)
# ----------------------------------------------------------------------------
# fleetlib: nucleo de LOGICA PURA (sem dependencias pesadas) compartilhado por
# simulador, ponte, jobs Spark/Flink, motor de cobranca, RAG e dashboard.
# Tudo aqui e deterministico e testavel por unidade sem subir o stack.
# ============================================================================
"""Nucleo de logica pura da Solucao Big Data para Frota Autonoma Conectada."""

__all__ = [
    "domain",
    "edge",
    "checksum",
    "conform",
    "scoring",
    "markov",
    "billing",
    "scd2",
    "aggregates",
    "rag",
    "nlp",
]

__version__ = "0.3.0"
