# ============================================================================
# app/common/mongo.py - acesso ao MongoDB (cadastrais + dossies). Document store
# para dados aninhados/heterogeneos (variedade R10; Cattell 2011). pymongo
# importado sob demanda.
# ============================================================================
"""Conexao ao MongoDB (veiculos, clientes, dossies)."""

from __future__ import annotations

import os


def _uri() -> str:
    user = os.getenv("MONGO_USER", os.getenv("MONGO_INITDB_ROOT_USERNAME", "frota"))
    pwd = os.getenv("MONGO_PASSWORD", os.getenv("MONGO_INITDB_ROOT_PASSWORD", "frotasecret"))
    host = os.getenv("MONGO_HOST", "mongodb")
    port = os.getenv("MONGO_PORT", "27017")
    return f"mongodb://{user}:{pwd}@{host}:{port}/"


def database():
    """Retorna o handle do banco `frota` (conexao preguicosa)."""
    from pymongo import MongoClient  # lazy

    client = MongoClient(_uri(), serverSelectionTimeoutMS=3000)
    return client[os.getenv("MONGO_DB", "frota")]


def veiculo(vehicle_id: str) -> dict | None:
    """Busca o cadastro de um veiculo (com sensores/firmware aninhados)."""
    return database().veiculos.find_one({"vehicle_id": vehicle_id}, {"_id": 0})


def salvar_dossie(dossie: dict) -> str:
    """Upsert idempotente de um dossie por id_ocorrencia. Retorna o id."""
    db = database()
    db.dossies.update_one(
        {"id_ocorrencia": dossie["id_ocorrencia"]},
        {"$set": dossie},
        upsert=True,
    )
    return dossie["id_ocorrencia"]
