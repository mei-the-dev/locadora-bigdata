# ============================================================================
# tests/conftest.py - coloca a raiz `sistema/` no sys.path para importar
# `fleetlib` sem instalacao (pip install -e). Compartilhado por unit/integration.
# ============================================================================
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
