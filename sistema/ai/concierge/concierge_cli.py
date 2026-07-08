#!/usr/bin/env python3
# ============================================================================
# ai/concierge/concierge_cli.py - CLI do concierge (usado pela demo.sh).
# Uso: python concierge_cli.py "quanto custa alugar um SUV por dia?"
# ============================================================================
"""CLI fino do concierge (delega para ai.concierge.service)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.concierge.service import responder  # noqa: E402


def main() -> None:
    pergunta = " ".join(sys.argv[1:]) or "quanto custa alugar um SUV por dia?"
    resp = responder(pergunta)
    print(f"Pergunta: {pergunta}\n")
    print(f"Intencao: {resp.get('intencao')}  (confianca {resp.get('confianca')})")
    print(f"Resposta: {resp['resposta']}")
    if resp.get("fontes"):
        print(f"Fontes:   {json.dumps(resp['fontes'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
