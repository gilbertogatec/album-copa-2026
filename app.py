import json, re, unicodedata
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Controle Álbum Copa 2026", layout="wide")

album = json.loads(Path("album_data.json").read_text(encoding="utf-8"))

def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()

def total_slots(code):
    code = code.upper()
    if code == "FWC":
        return 8
    if code == "MAPLE":
        return 2
    if code.startswith("CC"):
        return 14
    return 20

def paint_cell(v):
    if v == "✓":
        return "background-color:#FFD966;color:black;font-weight:bold;text-align:center"
    return "background-color:white;color:black;text-align:center"

lookup = {}
for grupo, teams in album.items():
    for code, nums in teams.items():
        lookup[norm(code)] = (grupo, code)

st.title("🏆 Controle Álbum Copa 2026")
st.caption("Use somente as 3 letras do álbum. Ex: BRA 17, HAI 12, MAR 4, FWC 2.")

with st.sidebar:
    st.header("Selecionar página")
    grupo_sel = st.selectbox("Grupo", list(album.keys()))
    time_sel = st.selectbox("Seleção/seção", list(album[grupo_sel].keys()))

    st.header("Consulta rápida")
    q = st.text_input("Digite ou fale", placeholder="Ex: BRA 17")

st.subheader("Consulta")

if q.strip():
    texto = norm(q)
    numero = re.search(r"\d+", texto)

    codigo = None
    for key in lookup:
        if re.search(rf"\b{re.escape(key)}\b", texto):
            codigo = key
            break

    if codigo and numero:
        grupo, time_sel = lookup[codigo]
        n = int(numero.group())
        tenho = set(album[grupo][time_sel])

        if n in tenho:
            st.success(f"✅ Você JÁ TEM: {time_sel} {n}")
        else:
            st.error(f"❌ Você NÃO TEM: {time_sel} {n}")
    else:
        st.warning("Use o formato: BRA 17")

st.divider()

st.subheader(f"{grupo_sel} — {time_sel}")

tenho = set(album[grupo_sel][time_sel])
nums = list(range(1, total_slots(time_sel) + 1))

df = pd.DataFrame(
    [["✓" if n in tenho else "" for n in nums]],
    columns=[str(n) for n in nums]
)

st.dataframe(
    df.style.map(paint_cell),
    use_container_width=True,
    hide_index=True
)

faltam = [n for n in nums if n not in tenho]

c1, c2, c3 = st.columns(3)
c1.metric("Tenho", len(tenho))
c2.metric("Faltam", len(faltam))
c3.metric("% completo", f"{len(tenho) / len(nums) * 100:.0f}%")

st.write("**Tenho:**", ", ".join(map(str, sorted(tenho))) if tenho else "nenhuma")
st.write("**Faltam:**", ", ".join(map(str, faltam)) if faltam else "completo")

st.divider()
st.subheader("Resumo geral")

rows = []
for grupo, teams in album.items():
    for code, lista in teams.items():
        total = total_slots(code)
        tenho_qtd = len(set(lista))
        rows.append({
            "Grupo": grupo,
            "Código": code,
            "Tenho": tenho_qtd,
            "Total": total,
            "Faltam": total - tenho_qtd,
            "%": round(tenho_qtd / total * 100, 1)
        })

resumo = pd.DataFrame(rows)
st.dataframe(resumo, use_container_width=True, hide_index=True)

st.subheader("Matriz completa")

for grupo, teams in album.items():
    st.markdown(f"### {grupo}")
    linhas = []

    max_total = max(total_slots(code) for code in teams.keys())

    for code, lista in teams.items():
        tenho = set(lista)
        linha = {"Código": code}
        for n in range(1, max_total + 1):
            if n <= total_slots(code):
                linha[str(n)] = "✓" if n in tenho else ""
            else:
                linha[str(n)] = ""
        linhas.append(linha)

    matriz = pd.DataFrame(linhas)
    st.dataframe(
        matriz.style.map(paint_cell, subset=[c for c in matriz.columns if c != "Código"]),
        use_container_width=True,
        hide_index=True
    )
