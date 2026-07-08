# ============================================================================
# app/dashboard/streamlit_app.py - dashboard de serving (Camada 5).
# OLAP sobre a Gold (PostgreSQL) com cache Redis: frota, emergencias, financeiro,
# DW/Markov e concierge. Drill-down (Chaudhuri & Dayal 1997), cubo executivo com
# subtotais ALL (Gray 1997), matriz de Markov (R12) e IA por RAG local (R9).
# Cada aba e resiliente a falha de dado (o dashboard nunca quebra).
# ============================================================================
"""Dashboard Streamlit da frota autonoma conectada (frota/emergencias/financeiro/IA)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.dashboard import data  # noqa: E402

st.set_page_config(page_title="Frota Autonoma Conectada", page_icon="🚗", layout="wide")

_CSS = """
<style>
:root { --accent:#00b8a9; --ink:#0f172a; }
.block-container { padding-top: 2rem; }
h1, h2, h3 { letter-spacing:-0.01em; }
.hdr { background:linear-gradient(100deg,#0f172a,#134e4a); color:#fff;
       padding:1.1rem 1.4rem; border-radius:14px; margin-bottom:1rem; }
.hdr small { color:#7dd3c8; }
div[data-testid="stMetric"] { background:#f8fafc; border:1px solid #e2e8f0;
       border-radius:12px; padding:0.6rem 0.9rem; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="hdr"><h2 style="margin:0">Frota Autonoma Conectada — Consorcio de 6 Locadoras</h2>'
    '<small>Avaliacao 03 · MAE016/EEL890 · Izabela Lima da Silva (124156557) · '
    'Caio Meirelles (122071557)</small></div>',
    unsafe_allow_html=True,
)


def _fmt_moeda(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:  # noqa: BLE001
        return str(v)


aba_frota, aba_emg, aba_fin, aba_dw, aba_ia = st.tabs(
    ["🚗 Frota", "🚨 Emergencias", "💰 Financeiro", "🧊 DW / Markov", "🤖 Concierge IA"]
)

# --------------------------------------------------------------------------- FROTA
with aba_frota:
    k = data.kpis()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Veiculos", k.get("total_veiculos", "-"))
    c2.metric("Locacoes ativas", k.get("locacoes_ativas", "-"))
    c3.metric("Reservas futuras", k.get("reservas_futuras", "-"))
    c4.metric("Score medio", k.get("score_medio_frota", "-"))
    c5.metric("Sinistros", k.get("sinistros_total", "-"))

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.subheader("Ocupacao por patio")
        oc = data.ocupacao()
        if oc:
            df = pd.DataFrame(oc).set_index("patio")
            st.bar_chart(df["veiculos"], color="#00b8a9")
        else:
            st.info("Sem dados de posicao (rode `make elt` para popular via streaming).")
    with col_b:
        st.subheader("Score de conducao por veiculo")
        sf = data.score_frota()
        if sf:
            df = pd.DataFrame(sf)[["vehicle_id", "categoria", "faixa_conducao", "score_conducao"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem telemetria diaria ainda.")

# --------------------------------------------------------------------------- EMERGENCIAS
with aba_emg:
    st.subheader("Ocorrencias e dossies regulatorios (R8)")
    emg = data.emergencias()
    if emg:
        df = pd.DataFrame(emg)
        st.dataframe(
            df[["id_ocorrencia", "vehicle_id", "empresa", "categoria_evento",
                "gravidade_padrao", "severidade", "tempo_resposta_seg", "flag_dossie"]],
            use_container_width=True, hide_index=True,
        )
        alvo = st.selectbox("Gerar/visualizar dossie point-in-time:",
                            [e["id_ocorrencia"] for e in emg])
        if st.button("Montar dossie (SCD2 firmware + time travel)"):
            try:
                from app.emergency.dossier import montar_dossie

                st.json(montar_dossie(alvo))
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Dossie indisponivel (requer Gold/Mongo no ar): {exc}")
    else:
        st.info("Sem sinistros. Injete emergencias pelo simulador ou use o seed.")

# --------------------------------------------------------------------------- FINANCEIRO
with aba_fin:
    st.subheader("Faturamento (cobranca pos-uso, R7)")
    fat = data.faturamento_dia()
    if fat:
        df = pd.DataFrame(fat)
        total = sum(float(r["faturamento"]) for r in fat)
        st.metric("Faturamento total", _fmt_moeda(total))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Sem cobrancas ainda.")
    st.subheader("Cubo financeiro (subtotais ALL — Gray 1997)")
    cf = data.cubo_financeiro()
    if cf:
        st.dataframe(pd.DataFrame(cf), use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- DW / MARKOV
with aba_dw:
    st.subheader("Matriz de Markov de redistribuicao (cada linha soma 100%)")
    mk = data.markov()
    if mk:
        piv = pd.DataFrame(mk).pivot(index="patio_origem", columns="patio_destino",
                                     values="p_ij_pct").fillna(0.0)
        try:
            st.dataframe(piv.style.background_gradient(cmap="Greens", axis=None)
                         .format("{:.1f}%"), use_container_width=True)
        except Exception:  # noqa: BLE001 - sem matplotlib, mostra sem gradiente
            st.dataframe(piv, use_container_width=True)
        st.caption("Diagonal = % que retorna ao proprio patio. Base do reposicionamento do veiculo vazio (R12).")
    else:
        st.info("Sem movimentacoes.")
    st.subheader("Cubo operacional da frota")
    cfr = data.cubo_frota()
    if cfr:
        st.dataframe(pd.DataFrame(cfr), use_container_width=True, hide_index=True)
    st.subheader("Relatorio de reservas (grupo x patio x cidade)")
    rr = data.relatorio_reservas()
    if rr:
        st.dataframe(pd.DataFrame(rr), use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------- CONCIERGE
with aba_ia:
    st.subheader("Concierge de viagem por IA — RAG local, sem LLM paga (R9)")
    st.caption("PLN por regras (intencao) + recuperacao de passagem citavel (Lewis 2020).")
    pergunta = st.text_input("Pergunte ao concierge:", "Quanto custa alugar um SUV por dia?")
    if st.button("Perguntar") and pergunta:
        try:
            from ai.concierge.service import responder

            resp = responder(pergunta)
            st.markdown(f"**Intencao:** `{resp.get('intencao')}` · confianca {resp.get('confianca')}")
            st.success(resp["resposta"])
            if resp.get("fontes"):
                st.markdown("**Fontes (proveniencia):**")
                st.table(pd.DataFrame(resp["fontes"]))
            if resp.get("disponibilidade"):
                st.markdown("**Disponibilidade:**")
                st.table(pd.DataFrame(resp["disponibilidade"]))
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Concierge indisponivel: {exc}")

st.markdown("---")
st.caption("Cache Redis (staleness limitado) · Gold PostgreSQL (ROLAP/ACID) · "
           "Lakehouse Kappa (Delta/MinIO) · persistencia poliglota.")
