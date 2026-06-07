import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Controle Álbum Copa 2026", layout="wide")

album = json.loads(Path("album_data.json").read_text(encoding="utf-8"))

SIGLAS = {
    "BRA": "Brasil",
    "MAR": "Marrocos",
    "HAI": "Haiti",
    "SCO": "Escócia",
    "CUR": "Curaçao",
    "CIV": "Costa do Marfim",
    "ECU": "Equador",
    "GER": "Alemanha",
    "NED": "Holanda",
    "JPN": "Japão",
    "SWE": "Suécia",
    "TUN": "Tunísia",
    "FWC": "FWC",
    "MAPLE": "MAPLE",
    "CC": "CC Coca-Cola",
}


def total_slots(nome):
    nome = nome.upper()

    if nome == "FWC":
        return 8
    if nome == "MAPLE":
        return 2
    if "CC" in nome:
        return 14

    return 20


def encontrar_time(sigla):
    sigla = sigla.upper().strip()

    nome_procurado = SIGLAS.get(sigla, sigla)

    for grupo_nome, times in album.items():
        for time_nome in times.keys():
            if time_nome.upper() == nome_procurado.upper():
                return grupo_nome, time_nome

    for grupo_nome, times in album.items():
        for time_nome in times.keys():
            if time_nome.upper().startswith(nome_procurado.upper()):
                return grupo_nome, time_nome

    return None, None


def interpretar_consulta(texto):
    texto = texto.upper().strip()

    partes = texto.split()

    if len(partes) < 2:
        return None, None

    sigla = partes[0]

    numero_match = re.search(r"\d+", texto)

    if not numero_match:
        return sigla, None

    numero = int(numero_match.group())

    return sigla, numero


def mostrar_figurinhas(tenho, total):
    cols = st.columns(10)

    for i, n in enumerate(range(1, total + 1)):
        with cols[i % 10]:
            if n in tenho:
                st.markdown(
                    f"""
                    <div style="
                    background:#FFD966;
                    color:black;
                    text-align:center;
                    padding:8px;
                    border-radius:5px;
                    margin:2px;
                    font-weight:bold;">
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
                    color:#999;
                    text-align:center;
                    padding:8px;
                    border-radius:5px;
                    margin:2px;">
                    {n}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


st.title("🏆 Controle Álbum Copa 2026")

st.write("Use a sigla do álbum. Ex: BRA 5, MAR 8, ECU 14, CIV 11, FWC 2, BRA 2P")

consulta = st.text_input("Consulta rápida")

if consulta:
    sigla, numero = interpretar_consulta(consulta)

    if not sigla or not numero:
        st.warning("Digite no formato: BRA 5")
        st.stop()

    grupo, time = encontrar_time(sigla)

    if not grupo or not time:
        st.error(f"❌ Sigla não encontrada: {sigla}")
        st.write("Siglas cadastradas:", ", ".join(SIGLAS.keys()))
        st.stop()

    figs = album.get(grupo, {}).get(time)

    if figs is None:
        st.error(f"❌ Não encontrei no JSON: {grupo} → {time}")
        st.write("Grupos disponíveis:", list(album.keys()))
        if grupo in album:
            st.write(f"Times em {grupo}:", list(album[grupo].keys()))
        st.stop()

    tenho = set(figs)
    total = total_slots(time)

    if numero < 1 or numero > total:
        st.warning(f"⚠️ Número fora do intervalo. {time} vai de 1 a {total}.")
    elif numero in tenho:
        st.success(f"✅ Você JÁ TEM: {sigla.upper()} {numero}")
    else:
        st.error(f"❌ Você NÃO TEM: {sigla.upper()} {numero}")

    st.subheader(f"{grupo} — {time}")

    mostrar_figurinhas(tenho, total)

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
        tenho = len(set(figs))

        resumo.append({
            "Grupo": grupo_nome,
            "Time": time_nome,
            "Tenho": tenho,
            "Faltam": total - tenho,
            "%": round(tenho / total * 100)
        })

st.subheader("Resumo Geral")

df = pd.DataFrame(resumo)

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
