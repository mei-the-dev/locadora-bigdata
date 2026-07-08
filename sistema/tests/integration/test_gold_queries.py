# ============================================================================
# Testes de INTEGRACAO da Gold (exigem `make up-core` no ar). Marcados
# `integration` e PULADOS automaticamente se o Postgres/driver nao existir.
# Rodar: make test-int  (ou pytest -m integration tests/integration)
# Validam, contra o banco REAL: matriz de Markov (R1 estocastica), KPIs, cubo
# com subtotais ALL (Gray 1997) e exactly-once da cobranca (R7 - Zaharia 2013).
# ============================================================================
import os

import pytest

pytestmark = pytest.mark.integration
psycopg2 = pytest.importorskip("psycopg2")


@pytest.fixture(scope="module")
def conn():
    try:
        c = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "dw"),
            user=os.getenv("POSTGRES_USER", "dw"),
            password=os.getenv("POSTGRES_PASSWORD", "dwsecret"),
            connect_timeout=3,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres Gold indisponivel: {exc}")
    c.autocommit = True
    with c.cursor() as cur:
        cur.execute("SET search_path TO dw_locadora")
    yield c
    c.close()


def test_markov_cada_linha_soma_um(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT bool_and(ABS(s-1.0) < 0.001) FROM "
            "(SELECT SUM(p_ij) s FROM v_markov GROUP BY patio_origem) q")
        assert cur.fetchone()[0] is True


def test_kpi_frota_tem_doze_veiculos(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT total_veiculos FROM v_kpi_frota")
        assert cur.fetchone()[0] == 12


def test_cubo_tem_grande_total_all(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mv_cubo_frota "
                    "WHERE empresa='ALL' AND patio='ALL' AND faixa_conducao='ALL'")
        assert cur.fetchone()[0] == 1


def test_cobranca_exactly_once(conn):
    """Inserir a mesma locacao 2x nao duplica (ON CONFLICT id_locacao)."""
    idl = "LOC-TEST-INTEG"
    ins = ("INSERT INTO Fato_Cobranca (id_locacao, sk_cliente, sk_veiculo, sk_tempo, "
           "sk_empresa, valor_base, valor_final) VALUES (%s,1,1,"
           "(SELECT sk_tempo FROM Dim_Tempo WHERE data=CURRENT_DATE),1,100,100) "
           "ON CONFLICT (id_locacao) DO NOTHING")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM Fato_Cobranca WHERE id_locacao=%s", (idl,))
        cur.execute(ins, (idl,))
        cur.execute(ins, (idl,))  # replay
        cur.execute("SELECT COUNT(*) FROM Fato_Cobranca WHERE id_locacao=%s", (idl,))
        assert cur.fetchone()[0] == 1
        cur.execute("DELETE FROM Fato_Cobranca WHERE id_locacao=%s", (idl,))
