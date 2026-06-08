import re
from io import BytesIO

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

try:
    from rapidocr_onnxruntime import RapidOCR
    OCR_DISPONIVEL = True
except Exception:
    OCR_DISPONIVEL = False


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

    if "Quantidade" not in df.columns:
        df["Quantidade"] = df["Tenho"].astype(str).str.lower().eq("sim").map(
            {True: 1, False: 0}
        )

    df["Grupo"] = df["Grupo"].astype(str)
    df["Time"] = df["Time"].astype(str).str.upper()
    df["Numero"] = df["Numero"].astype(int)
    df["Tenho"] = df["Tenho"].astype(str)
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0).astype(int)

    return df


def garantir_coluna_quantidade():
    ws = conectar_google_sheets()
    cabecalho = ws.row_values(1)

    if "Quantidade" not in cabecalho:
        proxima_coluna = len(cabecalho) + 1
        ws.update_cell(1, proxima_coluna, "Quantidade")

        df = carregar_dados()
        for i, row in df.iterrows():
            qtd = 1 if str(row["Tenho"]).lower() == "sim" else 0
            ws.update_cell(i + 2, proxima_coluna, qtd)


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


def extrair_figurinhas_do_texto(texto):
    texto = texto.upper()
    encontrados = re.findall(r"\b([A-Z]{2,6})\s*[- ]?\s*(\d{1,2})[A-Z]?\b", texto)
    return [(time, int(numero)) for time, numero in encontrados]


def localizar_linha(df, time, numero):
    filtro = (
        (df["Time"].str.upper() == time.upper())
        & (df["Numero"] == numero)
    )

    if not filtro.any():
        return None

    return df[filtro].index[0]


def atualizar_quantidade(time, numero, nova_quantidade):
    garantir_coluna_quantidade()

    ws = conectar_google_sheets()
    df = carregar_dados()

    index = localizar_linha(df, time, numero)

    if index is None:
        return False, f"Figurinha não encontrada: {time.upper()} {numero}"

    linha_google = index + 2
    nova_quantidade = max(0, int(nova_quantidade))
    novo_status = "Sim" if nova_quantidade > 0 else "Não"

    ws.update_cell(linha_google, 4, novo_status)
    ws.update_cell(linha_google, 5, nova_quantidade)

    limpar_cache()

    return True, f"{time.upper()} {numero} atualizada para quantidade {nova_quantidade}."


def adicionar_figura(time, numero):
    df = carregar_dados()
    index = localizar_linha(df, time, numero)

    if index is None:
        return False, f"Figurinha não encontrada: {time.upper()} {numero}"

    qtd_atual = int(df.loc[index, "Quantidade"])
    return atualizar_quantidade(time, numero, qtd_atual + 1)


def remover_figura(time, numero):
    df = carregar_dados()
    index = localizar_linha(df, time, numero)

    if index is None:
        return False, f"Figurinha não encontrada: {time.upper()} {numero}"

    qtd_atual = int(df.loc[index, "Quantidade"])
    return atualizar_quantidade(time, numero, qtd_atual - 1)


def mostrar_figurinhas(df_time):
    df_time = df_time.sort_values("Numero")
    cols = st.columns(10)

    for _, row in df_time.iterrows():
        numero = int(row["Numero"])
        qtd = int(row["Quantidade"])
        tenho = qtd > 0

        with cols[(numero - 1) % 10]:
            cor = "#FFD966" if tenho else "transparent"
            borda = "none" if tenho else "1px solid #666"
            texto = "black" if tenho else "#999"
            extra = f"<br><small>x{qtd}</small>" if qtd > 1 else ""

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
                {numero}{extra}
                </div>
                """,
                unsafe_allow_html=True,
            )


def gerar_resumo(df):
    resumo = (
        df.assign(TenhoBool=df["Quantidade"] > 0)
        .groupby(["Grupo", "Time"], as_index=False)
        .agg(
            Total=("Numero", "count"),
            Tenho=("TenhoBool", "sum"),
            Quantidade_Total=("Quantidade", "sum"),
        )
    )

    resumo["Faltam"] = resumo["Total"] - resumo["Tenho"]
    resumo["Repetidas"] = resumo["Quantidade_Total"] - resumo["Tenho"]
    resumo["%"] = (resumo["Tenho"] / resumo["Total"] * 100).round(0).astype(int)

    return resumo


def gerar_matriz_aggrid(df):
    base = df.copy()
    base["TenhoBool"] = base["Quantidade"] > 0

    matriz = base.pivot_table(
        index=["Grupo", "Time"],
        columns="Numero",
        values="TenhoBool",
        aggfunc="first",
    ).reset_index()

    matriz.columns = [str(c) for c in matriz.columns]
    return matriz


def gerar_matriz_visual(df):
    matriz = df.copy()
    matriz["Status"] = matriz["Quantidade"].apply(
        lambda x: "" if x == 0 else ("✅" if x == 1 else f"✅ x{x}")
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


def processar_lote(texto, acao):
    itens = extrair_figurinhas_do_texto(texto)

    if not itens:
        return 0, ["Nenhuma figurinha encontrada no texto."]

    mensagens = []
    sucesso = 0

    for time, numero in itens:
        if acao == "adicionar":
            ok, msg = adicionar_figura(time, numero)
        else:
            ok, msg = remover_figura(time, numero)

        mensagens.append(msg)

        if ok:
            sucesso += 1

    return sucesso, mensagens


st.title("🏆 Controle Álbum Copa 2026")

garantir_coluna_quantidade()
df = carregar_dados()

aba1, aba2, aba3, aba4, aba5, aba6, aba7 = st.tabs(
    [
        "🔎 Consultar",
        "➕ Inserir",
        "➖ Remover",
        "📦 Lote",
        "📷 OCR",
        "📋 Matriz",
        "❌ Faltantes/Repetidas",
    ]
)

with aba1:
    consulta = st.text_input(
        "Consulta rápida. Ex: BRA 5, FWC 2, CC 10",
        key="consulta_rapida",
    )

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

        qtd = int(df_fig.iloc[0]["Quantidade"])

        if qtd > 0:
            st.success(f"✅ Você JÁ TEM: {time.upper()} {numero} — quantidade {qtd}")
        else:
            st.error(f"❌ Você NÃO TEM: {time.upper()} {numero}")

        grupo = df_time.iloc[0]["Grupo"]
        st.subheader(f"{grupo} — {time.upper()}")

        mostrar_figurinhas(df_time)

        total = len(df_time)
        qtd_tenho = (df_time["Quantidade"] > 0).sum()
        qtd_repetidas = df_time["Quantidade"].sum() - qtd_tenho

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tenho", qtd_tenho)
        c2.metric("Faltam", total - qtd_tenho)
        c3.metric("Repetidas", qtd_repetidas)
        c4.metric("%", round(qtd_tenho / total * 100))

with aba2:
    st.subheader("Adicionar figurinha")

    nova = st.text_input(
        "Digite a nova figurinha. Ex: BRA 6",
        key="inserir_figurinha",
    )

    if st.button("Adicionar", key="botao_adicionar"):
        time, numero = interpretar_consulta(nova)

        if not time or not numero:
            st.warning("Digite no formato: BRA 6")
            st.stop()

        ok, msg = adicionar_figura(time, numero)

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with aba3:
    st.subheader("Remover figurinha")

    remover = st.text_input(
        "Digite a figurinha para remover. Ex: BRA 6",
        key="remover_figurinha",
    )

    if st.button("Remover", key="botao_remover"):
        time, numero = interpretar_consulta(remover)

        if not time or not numero:
            st.warning("Digite no formato: BRA 6")
            st.stop()

        ok, msg = remover_figura(time, numero)

        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

with aba4:
    st.subheader("Adicionar ou remover em lote")

    texto_lote = st.text_area(
        "Cole várias figurinhas. Ex: BRA 1, BRA 2, MAR 5 ou uma por linha.",
        height=160,
        key="texto_lote",
    )

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Adicionar lote", key="adicionar_lote"):
            qtd, mensagens = processar_lote(texto_lote, "adicionar")
            st.success(f"{qtd} operação(ões) processada(s).")
            with st.expander("Ver detalhes"):
                st.write("\n".join(mensagens))
            st.rerun()

    with col_b:
        if st.button("Remover lote", key="remover_lote"):
            qtd, mensagens = processar_lote(texto_lote, "remover")
            st.success(f"{qtd} operação(ões) processada(s).")
            with st.expander("Ver detalhes"):
                st.write("\n".join(mensagens))
            st.rerun()

with aba5:
    st.subheader("Leitor OCR")

    st.write("Tire uma foto ou envie imagem com códigos como BRA 5, MAR 8, FWC 2.")

    imagem = st.camera_input("Tirar foto", key="camera_ocr")

    if imagem is None:
        imagem = st.file_uploader(
            "Ou envie uma imagem",
            type=["png", "jpg", "jpeg"],
            key="upload_ocr",
        )

    if imagem is not None:
        img = Image.open(imagem)
        st.image(img, caption="Imagem capturada", use_container_width=True)

        if OCR_DISPONIVEL:
            if st.button("Ler imagem com OCR", key="botao_ocr"):
                ocr = RapidOCR()
                resultado, _ = ocr(img)

                texto_extraido = ""

                if resultado:
                    texto_extraido = "\n".join([linha[1] for linha in resultado])

                st.text_area(
                    "Texto encontrado",
                    value=texto_extraido,
                    height=160,
                    key="texto_ocr_resultado",
                )

                figurinhas = extrair_figurinhas_do_texto(texto_extraido)

                if figurinhas:
                    st.success(f"Encontrei {len(figurinhas)} possível(is) figurinha(s).")
                    st.write(figurinhas)

                    texto_para_lote = "\n".join(
                        [f"{time} {numero}" for time, numero in figurinhas]
                    )

                    st.text_area(
                        "Revise antes de adicionar",
                        value=texto_para_lote,
                        height=120,
                        key="ocr_revisado",
                    )
                else:
                    st.warning("Não encontrei códigos no padrão BRA 5, MAR 8 etc.")
        else:
            st.error(
                "OCR não disponível. Confirme se `rapidocr-onnxruntime` está no requirements.txt."
            )

    texto_manual_ocr = st.text_area(
        "Correção manual / texto do OCR para processar",
        height=120,
        key="texto_manual_ocr",
    )

    if st.button("Adicionar texto OCR revisado", key="adicionar_ocr_revisado"):
        qtd, mensagens = processar_lote(texto_manual_ocr, "adicionar")
        st.success(f"{qtd} figurinha(s) processada(s).")
        with st.expander("Ver detalhes"):
            st.write("\n".join(mensagens))
        st.rerun()

with aba6:
    st.subheader("Matriz completa editável")

    st.write(
        "Grupo e Time ficam fixos. As colunas não podem ser arrastadas. "
        "Marque para adicionar. Desmarque para remover. Depois clique em salvar."
    )

    matriz_original = gerar_matriz_aggrid(df)

    colunas_numeros = [
        col for col in matriz_original.columns
        if col not in ["Grupo", "Time"]
    ]

    gb = GridOptionsBuilder.from_dataframe(matriz_original)

    gb.configure_default_column(
        editable=True,
        resizable=True,
        sortable=True,
        filter=True,
        suppressMovable=True,
        wrapHeaderText=True,
        autoHeaderHeight=True,
    )

    gb.configure_column(
        "Grupo",
        pinned="left",
        editable=False,
        width=150,
        minWidth=150,
        suppressMovable=True,
    )

    gb.configure_column(
        "Time",
        pinned="left",
        editable=False,
        width=115,
        minWidth=115,
        suppressMovable=True,
    )

    for col in colunas_numeros:
        gb.configure_column(
            col,
            editable=True,
            width=90,
            minWidth=90,
            suppressMovable=True,
            wrapHeaderText=True,
            autoHeaderHeight=True,
            cellRenderer="agCheckboxCellRenderer",
            cellEditor="agCheckboxCellEditor",
        )

    grid_options = gb.build()

    grid_options["suppressMovableColumns"] = True
    grid_options["suppressDragLeaveHidesColumns"] = True
    grid_options["ensureDomOrder"] = True

    grid_response = AgGrid(
        matriz_original,
        gridOptions=grid_options,
        height=650,
        fit_columns_on_grid_load=False,
        data_return_mode=DataReturnMode.AS_INPUT,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        theme="streamlit",
        key="aggrid_matriz_album",
    )

    matriz_editada = pd.DataFrame(grid_response["data"])

    if st.button("Salvar alterações da matriz", key="salvar_matriz_aggrid"):
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

                novo_bruto = linha.get(col)
                antigo_bruto = linha_original.get(col)

                if pd.isna(novo_bruto) and pd.isna(antigo_bruto):
                    continue

                novo_valor = False if pd.isna(novo_bruto) else bool(novo_bruto)
                valor_antigo = False if pd.isna(antigo_bruto) else bool(antigo_bruto)

                if novo_valor != valor_antigo:
                    filtro = (
                        (df_atual["Grupo"] == grupo)
                        & (df_atual["Time"] == time)
                        & (df_atual["Numero"] == numero)
                    )

                    if filtro.any():
                        index = df_atual[filtro].index[0]
                        linha_google = index + 2

                        qtd_atual = int(df_atual.loc[index, "Quantidade"])

                        if novo_valor:
                            nova_qtd = max(1, qtd_atual)
                        else:
                            nova_qtd = 0

                        ws.update_cell(linha_google, 4, "Sim" if nova_qtd > 0 else "Não")
                        ws.update_cell(linha_google, 5, nova_qtd)

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
        key="baixar_matriz_csv",
    )

with aba7:
    st.subheader("Figurinhas faltantes")

    faltantes = df[df["Quantidade"] == 0]

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
        key="baixar_faltantes_csv",
    )

    st.divider()

    st.subheader("Figurinhas repetidas")

    repetidas = df[df["Quantidade"] > 1].copy()
    repetidas["Repetidas"] = repetidas["Quantidade"] - 1

    st.dataframe(
        repetidas[["Grupo", "Time", "Numero", "Quantidade", "Repetidas"]],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "Baixar repetidas CSV",
        data=repetidas.to_csv(index=False).encode("utf-8-sig"),
        file_name="repetidas_album_copa_2026.csv",
        mime="text/csv",
        key="baixar_repetidas_csv",
    )

st.divider()

total_figurinhas = len(df)
total_tenho = (df["Quantidade"] > 0).sum()
total_quantidade = df["Quantidade"].sum()
total_repetidas = total_quantidade - total_tenho
total_faltam = total_figurinhas - total_tenho
percentual = round(total_tenho / total_figurinhas * 100, 1)

st.subheader("📊 Progresso do Álbum")

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric("Total", total_figurinhas)
c2.metric("Tenho", total_tenho)
c3.metric("Faltam", total_faltam)
c4.metric("Repetidas", total_repetidas)
c5.metric("% Completo", f"{percentual}%")

st.subheader("Resumo geral")

resumo = gerar_resumo(df)

st.dataframe(
    resumo,
    use_container_width=True,
    hide_index=True,
)
