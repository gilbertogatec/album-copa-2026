
import json, re
from pathlib import Path
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Controle Álbum Copa 2026", layout="wide")
album = json.loads(Path("album_data.json").read_text(encoding="utf-8"))

def normalize(s):
    return (s.lower().replace("á","a").replace("à","a").replace("ã","a").replace("â","a")
    .replace("é","e").replace("ê","e").replace("í","i").replace("ó","o").replace("ô","o")
    .replace("õ","o").replace("ú","u").replace("ç","c"))

def total_slots(team):
    if team == "FWC": return 8
    if team == "MAPLE": return 2
    if "CC" in team: return 14
    return 20

lookup = {}
for g, teams in album.items():
    for t in teams:
        lookup[normalize(t)] = (g, t)

st.title("🏆 Controle do Álbum Copa 2026")
st.caption("Amarelo = você já tem. Branco = falta. Use a consulta: 'Brasil 10', 'Marrocos 13', 'FWC 2'.")

with st.sidebar:
    st.header("Abrir página")
    grupo = st.selectbox("Grupo/seção", list(album.keys()))
    time = st.selectbox("Time/seção", list(album[grupo].keys()))
    st.header("Consulta rápida")
    q = st.text_input("Digite ou fale no teclado do celular", placeholder="Ex: Brasil 10")

if q.strip():
    qn = normalize(q)
    m = re.search(r"\d+", qn)
    achou = None
    for key, val in lookup.items():
        if key in qn:
            achou = val
            break
    if achou and m:
        grupo, time = achou
        n = int(m.group())
        if n in set(album[grupo][time]):
            st.success(f"Você JÁ TEM: {time} {n}")
        else:
            st.error(f"Você NÃO TEM: {time} {n}")
    elif m:
        n = int(m.group())
        if n in set(album[grupo][time]):
            st.success(f"Você JÁ TEM: {time} {n}")
        else:
            st.error(f"Você NÃO TEM: {time} {n}")
    else:
        st.warning("Digite no formato: Brasil 10")

st.subheader(f"{grupo} — {time}")
tem = set(album[grupo][time])
nums = list(range(1, total_slots(time)+1))
df = pd.DataFrame([["✓" if n in tem else "" for n in nums]], columns=[str(n) for n in nums])

def paint(v):
    return "background-color:#FFD966;color:black;font-weight:bold;text-align:center" if v == "✓" else "background-color:white;color:black;text-align:center"

st.dataframe(df.style.map(paint), use_container_width=True, hide_index=True)

faltam = [n for n in nums if n not in tem]
c1,c2,c3 = st.columns(3)
c1.metric("Tenho", len(tem))
c2.metric("Faltam", len(faltam))
c3.metric("% completo", f"{len(tem)/len(nums)*100:.0f}%")
st.write("**Tenho:**", ", ".join(map(str, sorted(tem))) if tem else "nenhuma")
st.write("**Faltam:**", ", ".join(map(str, faltam)) if faltam else "completo")

st.divider()
rows=[]
for g, teams in album.items():
    for t, lista in teams.items():
        total=total_slots(t)
        rows.append({"Grupo":g,"Time/Seção":t,"Tenho":len(set(lista)),"Total":total,"Faltam":total-len(set(lista)),"%":round(len(set(lista))/total*100,1)})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
