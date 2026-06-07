import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Controle Álbum Copa 2026", layout="wide")

album = json.loads(Path("album_data.json").read_text(encoding="utf-8"))

SIGLAS = {
    "BRA": ("Grupo C", "Brasil"),
    "MAR": ("Grupo C", "Marrocos"),
    "HAI": ("Grupo C", "Haiti"),
    "SCO": ("Grupo C", "Escócia"),

    "CUR": ("Grupo E", "Curaçao"),
    "CIV": ("Grupo E", "Costa do Marfim"),
    "ECU": ("Grupo E", "Equador"),
    "GER": ("Grupo E", "Alemanha"),

    "NED": ("Grupo F", "Holanda"),
    "JPN": ("Grupo F", "Japão"),
    "SWE": ("Grupo F", "Suécia"),
    "TUN": ("Grupo F", "Tunísia"),

    "FWC": ("Especiais", "FWC"),
    "MAPLE": ("Especiais", "MAPLE"),
    "CC": ("Especiais", "CC Coca-Cola"),
}


def total_slots(nome):
    if nome == "FWC":
        return 8
    if nome == "MAPLE":
        return 2
    if "CC" in nome:
        return 14
    return 20


st.title("🏆 Controle Álbum Copa 2026")
st.write("Use a sigla do álbum. Ex: BRA 5, MAR 8, ECU 14, CIV 11, FWC 2")

consulta = st.text_input("Consulta rápida")

grupo = None
time = None

if consulta:
    texto = consulta.upper().strip()

    sigla = None
    numero = None

    partes = texto.split()

    if len(partes) >= 2:
        sigla = partes[0]

        m = re.search(r"\d+", texto)

        if m:
            numero = int(m.group())

    if sigla in SIGLAS and numero:
        grupo, time = SIGLAS[sigla]

        tenho = set(album[grupo][time])

        if numero in tenho:
            st.success(f"✅ Você JÁ TEM: {sigla} {numero}")
        else:
            st.error(f"❌ Você NÃO TEM: {sigla} {numero}")

        st.subheader(f"{grupo} — {time}")

        total = total_slots(time)

        cols = st.columns(min(total, 10))

        for n in range(1, total + 1):
            if n in tenho:
                st.markdown(
                    f"""
                    <div style="
                    background:#FFD966;
                    color:black;
                    text-align:center;
                    padding:8px;
                    border-radius:5px;
                    margin:2px;">
                    {n}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div style="
                    border:1px solid #666;
                    text-align:center;
                    padding:8px;
                    border-radius:5px;
                    margin:2px;">
                    {n}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        faltam = total - len(tenho)

        c1, c2, c3 = st.columns(3)

        c1.metric("Tenho", len(tenho))
        c2.metric("Faltam", faltam)
        c3.metric("%", round(len(tenho) / total * 100))

st.divider()

resumo = []

for grupo_nome, times in album.items():
    for time_nome, figs in times.items():

        total = total_slots(time_nome)

        resumo.append({
            "Grupo": grupo_nome,
            "Time": time_nome,
            "Tenho": len(set(figs)),
            "Faltam": total - len(set(figs)),
            "%": round(len(set(figs)) / total * 100)
        })

st.subheader("Resumo Geral")

st.dataframe(
    pd.DataFrame(resumo),
    use_container_width=True,
    hide_index=True
)
