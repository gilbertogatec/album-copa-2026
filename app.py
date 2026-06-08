import re

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Controle Álbum Copa 2026", layout="wide")

NOME_PLANILHA = "album_copa_2026"
NOME_ABA = "album"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def conectar_google_sheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    return client.open(NOME_PLANILHA).worksheet(NOME_ABA)


@st.cache_data(ttl=30)
def carregar_dados():
    ws = conectar_google_sheets()
    dados = ws.get_all_records()
    df = pd.DataFrame(dados)

    df["Grupo"] = df["Grupo"].astype(str)
    df["Time"] = df["Time"].astype(str).str.upper()
    df["Numero"] = df["Numero"].astype(int)
    df["Tenho"] = df["Tenho"].astype(str)

    return df


def limpar_cache():
    carregar_dados.clear()


def interpretar_consulta(texto):
    texto = texto.upper().strip()
    partes = texto.split()

    if len(partes) < 2:
        return None, None

    time = partes[0]
    numero_match = re.search(r"\d+", texto)

    if not numero_match:
        return time, None

    return time, int(numero_match.group())


def atualizar_figura(time, numero, novo_status):
    ws = conectar_google_sheets()
    df = carregar_dados()

    filtro = (
        (df["Time"].str.upper() == time.upper())
        & (df["Numero"] == numero)
    )

    if not filtro.any():
        return False, "Figurinha não encontrada."

    index = df[filtro].index[0]
    linha_google = index + 2

    status_texto = "Sim" if novo_status else "Não"

    ws.update_cell(linha_google, 4, status_texto)
    limpar_cache()

    return True, f"Figurinha {time.upper()} {numero} atualizada para {status_texto}."


def mostrar_figurinhas(df_time):
    df_time = df_time.sort_values("Numero")
    cols = st.columns(10)

    for _, row in df_time.iterrows():
        numero = int(row["Numero"])
        tenho = str(row["Tenho"]).strip().lower() == "sim"

        with cols[(numero - 1) % 10]:
            cor = "#FFD966" if tenho else "transparent"
            borda = "none" if tenho else "1px solid #666"
            texto = "black" if tenho else "#999"

            st.markdown(
                f"""
                <div style="
                background:{cor};
                border:{borda};
                color:{texto};
                text-align:center;
                padding:8px;
                border-radius:5px;
                margin:2px;
                font-weight:bold;">
                {numero}
                </div>
                """,
                unsafe_allow_html=True,
            )


def gerar_resumo(df):
    resumo = (
        df.assign(TenhoBool=df["Tenho"].str.lower().eq("sim"))
        .groupby(["Grupo", "Time"], as_index=False)
        .agg(
            Total=("Numero", "count"),
            Tenho=("TenhoBool", "sum"),
        )
    )

    resumo["Faltam"] = resumo["Total"] - resumo["Tenho"]
    resumo["%"] = (resumo["Tenho"] / resumo["Total"] * 100).round(0).astype(int)

    return resumo


def gerar_matriz_visual(df):
    matriz = df.copy()
    matriz["Status"] = matriz["Tenho"].str.lower().eq("sim").map(
        {True: "✅", False: ""}
    )

    matriz = matriz.pivot_table(
        index=["Grupo", "Time"],
        columns="Numero",
        values="Status",
        aggfunc="first",
        fill_value="",
    ).reset_index()

    matriz.columns = [str(c) for c in matriz.columns]

    return matriz


def gerar_matriz_editavel(df):
    matriz = df.copy()
    matriz["TenhoBool"] = matriz["Tenho"].str.lower().eq("sim")

    matriz = matriz.pivot_table(
        index=["Grupo", "Time"],
        columns="Numero",
        values="TenhoBool",
        aggfunc="first",
        fill_value=False,
    ).reset_index()

    matriz.columns = [str(c) for c in matriz.columns]

    return matriz


st.title("🏆 Controle Álbum Copa 2026")

aba1, aba2, aba3, aba4, aba5 = st.tabs(
    [
        "🔎 Consultar",
        "➕ Inserir",
        "➖ Remover",
        "📋 Matriz completa",
        "❌ Faltantes",
    ]
)

df = carregar_dados()

with aba1:
    consulta = st.text_input("Consulta rápida. Ex: BRA 5, FWC 2, CC 10")

    if consulta:
        time, numero = interpretar_consulta(consulta)

        if not time or not numero:
            st.warning("Digite no formato: BRA 5")
            st.stop()

        df_time = df[df["Time"].str.upper() == time.upper()]

        if df_time.empty:
            st.error(f"Sigla não encontrada: {time}")
            st.stop()

        df_fig = df_time[df_time["Numero"] == numero]

        if df_fig.empty:
            st.warning(f"Número fora do intervalo para {time}.")
            st.stop()

        tenho = str(df_fig.iloc[0]["Tenho"]).strip().lower() == "sim"

        if tenho:
            st.success(f"✅ Você JÁ TEM: {time.upper()} {numero}")
        else:
            st.error(f"❌ Você NÃO TEM: {time.upper()} {numero}")

        grupo = df_time.iloc[0]["Grupo"]

        st.subheader(f"{grupo} — {time.upper()}")

        mostrar_figurinhas(df_time)

        total = len(df_time)
        qtd_tenho = df_time["Tenho"].str.lower().eq("sim").sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Tenho", qtd_tenho)
        c2.metric("Faltam", total - qtd_tenho)
        c3.metric("%", round(qtd_tenho / total * 100))

with aba2:
    st.subheader("Adicionar figurinha")

    nova = st.text_input("Digite a nova figurinha. Ex: BRA 6")

    if st.button("Adicionar"):
        time, numero = interpretar_consulta(nova)

        if not time or not numero:
            st.warning("Digite no formato: BRA 6")
            st.stop()

        ok, msg = atualizar_figura(time, numero, True)

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with aba3:
    st.subheader("Remover figurinha")

    remover = st.text_input("Digite a figurinha para remover. Ex: BRA 6")

    if st.button("Remover"):
        time, numero = interpretar_consulta(remover)

        if not time or not numero:
            st.warning("Digite no formato: BRA 6")
            st.stop()

        ok, msg = atualizar_figura(time, numero, False)

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with aba4:
    st.subheader("Matriz completa editável")

    st.write(
        "Marque a caixa para adicionar a figurinha. Desmarque para remover. "
        "Depois clique em salvar."
    )

    matriz_original = gerar_matriz_editavel(df)

    colunas_numeros = [
        col for col in matriz_original.columns
        if col not in ["Grupo", "Time"]
    ]

    matriz_editada = st.data_editor(
        matriz_original,
        use_container_width=True,
        hide_index=True,
        disabled=["Grupo", "Time"],
        column_config={
            col: st.column_config.CheckboxColumn(col)
            for col in colunas_numeros
        },
        key="matriz_editavel",
    )

    if st.button("Salvar alterações da matriz"):
        ws = conectar_google_sheets()
        df_atual = carregar_dados()

        alteracoes = 0

        for _, linha in matriz_editada.iterrows():
            grupo = linha["Grupo"]
            time = linha["Time"]

            linha_original = matriz_original[
                (matriz_original["Grupo"] == grupo)
                & (matriz_original["Time"] == time)
            ].iloc[0]

            for col in colunas_numeros:
                numero = int(col)

                novo_valor = bool(linha[col])
                valor_antigo = bool(linha_original[col])

                if novo_valor != valor_antigo:
                    filtro = (
                        (df_atual["Grupo"] == grupo)
                        & (df_atual["Time"] == time)
                        & (df_atual["Numero"] == numero)
                    )

                    if filtro.any():
                        index = df_atual[filtro].index[0]
                        linha_google = index + 2

                        ws.update_cell(
                            linha_google,
                            4,
                            "Sim" if novo_valor else "Não",
                        )

                        alteracoes += 1

        limpar_cache()

        st.success(f"✅ {alteracoes} alteração(ões) salva(s).")
        st.rerun()

    st.divider()

    st.subheader("Matriz visual")
    matriz_visual = gerar_matriz_visual(df)

    st.dataframe(
        matriz_visual,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Baixar matriz CSV",
        data=matriz_visual.to_csv(index=False).encode("utf-8-sig"),
        file_name="matriz_album_copa_2026.csv",
        mime="text/csv",
    )

with aba5:
    st.subheader("Figurinhas faltantes")

    faltantes = df[df["Tenho"].str.lower() != "sim"]

    st.dataframe(
        faltantes[["Grupo", "Time", "Numero"]],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Baixar faltantes CSV",
        data=faltantes.to_csv(index=False).encode("utf-8-sig"),
        file_name="faltantes_album_copa_2026.csv",
        mime="text/csv",
    )

st.divider()

st.subheader("Resumo geral")

resumo = gerar_resumo(df)

st.dataframe(
    resumo,
    use_container_width=True,
    hide_index=True,
)

def salvar_figura(time, numero):
    ws = conectar_google_sheets()
    df = carregar_dados()

    filtro = (df["Time"].str.upper() == time.upper()) & (df["Numero"] == numero)

    if not filtro.any():
        return False, "Figurinha não encontrada na planilha."

    index = df[filtro].index[0]
    linha_google = index + 2

    valor_atual = str(df.loc[index, "Tenho"]).strip().lower()

    if valor_atual == "sim":
        return True, "Você já tinha essa figurinha."

    ws.update_cell(linha_google, 4, "Sim")
    st.cache_data.clear()

    return True, "Figurinha adicionada com sucesso."


def interpretar_consulta(texto):
    texto = texto.upper().strip()
    partes = texto.split()

    if len(partes) < 2:
        return None, None

    time = partes[0]

    numero_match = re.search(r"\d+", texto)

    if not numero_match:
        return time, None

    numero = int(numero_match.group())

    return time, numero


def mostrar_figurinhas(df_time):
    df_time = df_time.sort_values("Numero")

    cols = st.columns(10)

    for i, row in df_time.iterrows():
        numero = row["Numero"]
        tenho = str(row["Tenho"]).strip().lower() == "sim"

        with cols[(numero - 1) % 10]:
            cor = "#FFD966" if tenho else "transparent"
            borda = "none" if tenho else "1px solid #666"
            texto = "black" if tenho else "#999"

            st.markdown(
                f"""
                <div style="
                background:{cor};
                border:{borda};
                color:{texto};
                text-align:center;
                padding:8px;
                border-radius:5px;
                margin:2px;
                font-weight:bold;">
                {numero}
                </div>
                """,
                unsafe_allow_html=True,
            )


def gerar_resumo(df):
    resumo = (
        df.assign(TenhoBool=df["Tenho"].str.lower().eq("sim"))
        .groupby(["Grupo", "Time"], as_index=False)
        .agg(
            Total=("Numero", "count"),
            Tenho=("TenhoBool", "sum"),
        )
    )

    resumo["Faltam"] = resumo["Total"] - resumo["Tenho"]
    resumo["%"] = (resumo["Tenho"] / resumo["Total"] * 100).round(0).astype(int)

    return resumo


def gerar_matriz(df):
    matriz = df.copy()
    matriz["Status"] = matriz["Tenho"].str.lower().eq("sim").map({True: "✅", False: ""})

    matriz = matriz.pivot_table(
        index=["Grupo", "Time"],
        columns="Numero",
        values="Status",
        aggfunc="first",
        fill_value=""
    ).reset_index()

    return matriz


st.title("🏆 Controle Álbum Copa 2026")

aba1, aba2, aba3, aba4 = st.tabs([
    "🔎 Consultar",
    "➕ Inserir",
    "📋 Matriz completa",
    "❌ Faltantes"
])

df = carregar_dados()

with aba1:
    consulta = st.text_input("Consulta rápida. Ex: BRA 5, FWC 2, CC 10")

    if consulta:
        time, numero = interpretar_consulta(consulta)

        if not time or not numero:
            st.warning("Digite no formato: BRA 5")
            st.stop()

        df_time = df[df["Time"].str.upper() == time.upper()]

        if df_time.empty:
            st.error(f"Sigla não encontrada: {time}")
            st.stop()

        df_fig = df_time[df_time["Numero"] == numero]

        if df_fig.empty:
            st.warning(f"Número fora do intervalo para {time}.")
            st.stop()

        tenho = str(df_fig.iloc[0]["Tenho"]).strip().lower() == "sim"

        if tenho:
            st.success(f"✅ Você JÁ TEM: {time.upper()} {numero}")
        else:
            st.error(f"❌ Você NÃO TEM: {time.upper()} {numero}")

        grupo = df_time.iloc[0]["Grupo"]

        st.subheader(f"{grupo} — {time.upper()}")

        mostrar_figurinhas(df_time)

        total = len(df_time)
        qtd_tenho = df_time["Tenho"].str.lower().eq("sim").sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Tenho", qtd_tenho)
        c2.metric("Faltam", total - qtd_tenho)
        c3.metric("%", round(qtd_tenho / total * 100))

with aba2:
    st.subheader("Adicionar figurinha")

    nova = st.text_input("Digite a nova figurinha. Ex: BRA 6")

    if st.button("Adicionar"):
        time, numero = interpretar_consulta(nova)

        if not time or not numero:
            st.warning("Digite no formato: BRA 6")
            st.stop()

        ok, msg = salvar_figura(time, numero)

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with aba3:
    st.subheader("Matriz completa")

    matriz = gerar_matriz(df)

    st.dataframe(
        matriz,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Baixar matriz CSV",
        data=matriz.to_csv(index=False).encode("utf-8-sig"),
        file_name="matriz_album_copa_2026.csv",
        mime="text/csv"
    )

with aba4:
    st.subheader("Figurinhas faltantes")

    faltantes = df[df["Tenho"].str.lower() != "sim"]

    st.dataframe(
        faltantes[["Grupo", "Time", "Numero"]],
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Baixar faltantes CSV",
        data=faltantes.to_csv(index=False).encode("utf-8-sig"),
        file_name="faltantes_album_copa_2026.csv",
        mime="text/csv"
    )

st.divider()

st.subheader("Resumo geral")

resumo = gerar_resumo(df)

st.dataframe(
    resumo,
    use_container_width=True,
    hide_index=True
)

def interpretar_consulta(texto):
    texto = texto.upper().strip()
    partes = texto.split()

    if len(partes) < 2:
        return None, None

    sigla = partes[0]
    numero_match = re.search(r"\d+", texto)

    if not numero_match:
        return sigla, None

    return sigla, int(numero_match.group())


def mostrar_figurinhas(tenho, total):
    cols = st.columns(10)

    for i, n in enumerate(range(1, total + 1)):
        with cols[i % 10]:
            cor = "#FFD966" if n in tenho else "transparent"
            borda = "none" if n in tenho else "1px solid #666"
            texto = "black" if n in tenho else "#999"

            st.markdown(
                f"""
                <div style="
                background:{cor};
                border:{borda};
                color:{texto};
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
        st.stop()

    tenho = set(album[grupo][time])
    total = total_slots(time)

    if numero < 1 or numero > total:
        st.warning(f"⚠️ Número fora do intervalo. {time} vai de 1 a {total}.")
    elif numero in tenho:
        st.success(f"✅ Você JÁ TEM: {sigla} {numero}")
    else:
        st.error(f"❌ Você NÃO TEM: {sigla} {numero}")

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

st.dataframe(
    pd.DataFrame(resumo),
    use_container_width=True,
    hide_index=True
)
