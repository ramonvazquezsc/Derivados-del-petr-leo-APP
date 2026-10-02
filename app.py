import os
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Derivados del petróleo",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Estilos responsive: en móvil reducimos márgenes, títulos, tarjetas y
# hacemos que los gráficos ocupen siempre el ancho disponible.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Menos aire lateral en pantallas pequeñas */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1500px;
    }

    h1 {
        font-size: clamp(1.65rem, 6vw, 2.4rem) !important;
        line-height: 1.1 !important;
        margin-bottom: .35rem !important;
    }

    h2, h3 {
        line-height: 1.15 !important;
    }

    /* Que los gráficos no provoquen scroll horizontal */
    .stPlotlyChart, .js-plotly-plot, .plot-container {
        width: 100% !important;
        max-width: 100% !important;
    }

    /* Métricas más compactas */
    [data-testid="stMetric"] {
        padding: .65rem .75rem;
        border: 1px solid rgba(128,128,128,.20);
        border-radius: .75rem;
        background: rgba(128,128,128,.06);
    }

    [data-testid="stMetricLabel"] {
        font-size: .78rem !important;
    }

    [data-testid="stMetricValue"] {
        font-size: clamp(1.05rem, 5vw, 1.65rem) !important;
    }

    /* Pestañas cómodas para tocar con el dedo */
    button[data-baseweb="tab"] {
        padding-left: .7rem;
        padding-right: .7rem;
    }

    /* Tabla: mantenerla dentro de la pantalla */
    [data-testid="stDataFrame"] {
        max-width: 100%;
    }

    /* En móvil las columnas se apilan */
    @media (max-width: 768px) {
        .block-container {
            padding-left: .65rem;
            padding-right: .65rem;
            padding-top: .8rem;
        }

        [data-testid="stMetric"] {
            margin-bottom: .35rem;
        }

        .stCaption {
            font-size: .78rem;
        }

        /* Evita que textos largos rompan el ancho */
        p, label, [data-testid="stMarkdownContainer"] {
            overflow-wrap: anywhere;
        }
    }
</style>
""", unsafe_allow_html=True)

BASE = "https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv/secondary/"
CACHE_DIR = "cache_jodi"

PRODUCTOS = {
    "GASDIES": "Gasóleo / diésel",
    "GASOLINE": "Gasolina",
    "LPG": "GLP (butano y propano)",
    "JETKERO": "Queroseno / jet fuel",
    "NAPHTHA": "Nafta",
    "RESFUEL": "Fueloil / búnker",
    "ONONSPEC": "Otros productos (asfalto, lubricantes, coque)",
}

CATEGORIAS = ["Transporte", "Industria y maquinaria", "Calefacción y hogar",
              "Generación eléctrica", "Petroquímica", "Construcción"]

INFO = {
    "Gasóleo / diésel": (
        ["Transporte", "Industria y maquinaria", "Calefacción y hogar", "Generación eléctrica"],
        ["Transporte por carretera", "Maquinaria agrícola y minera",
         "Transporte marítimo y ferroviario", "Calefacción", "Generación eléctrica de respaldo"]),
    "Gasolina": (
        ["Transporte", "Industria y maquinaria"],
        ["Automóviles y motos", "Pequeña maquinaria", "Aviación ligera", "Base para mezclas con etanol"]),
    "GLP (butano y propano)": (
        ["Calefacción y hogar", "Petroquímica", "Transporte", "Industria y maquinaria"],
        ["Cocina y calefacción doméstica", "Materia prima petroquímica", "Autogás",
         "Uso industrial y agrícola"]),
    "Queroseno / jet fuel": (
        ["Transporte"],
        ["Aviación comercial", "Aviación militar", "Calefacción (residual)"]),
    "Nafta": (
        ["Petroquímica"],
        ["Craqueo para etileno y plásticos", "Solventes", "Mezcla en gasolinas"]),
    "Fueloil / búnker": (
        ["Transporte", "Generación eléctrica", "Industria y maquinaria"],
        ["Combustible de buques", "Generación eléctrica", "Calderas industriales"]),
    "Otros productos (asfalto, lubricantes, coque)": (
        ["Construcción", "Industria y maquinaria", "Petroquímica"],
        ["Asfalto y betún para carreteras", "Lubricantes", "Coque de petróleo", "Parafinas y otros"]),
}

PAISES = {
    "US": "EE. UU.", "CN": "China", "IN": "India", "RU": "Rusia", "BR": "Brasil",
    "DE": "Alemania", "JP": "Japón", "CA": "Canadá", "SA": "Arabia Saudí",
    "KR": "Corea del Sur", "GB": "Reino Unido", "SG": "Singapur", "MX": "México",
    "ID": "Indonesia", "FR": "Francia", "IT": "Italia", "ES": "España", "TR": "Turquía",
    "AU": "Australia", "TH": "Tailandia", "EG": "Egipto", "AR": "Argentina",
    "ZA": "Sudáfrica", "NL": "Países Bajos", "PL": "Polonia", "MY": "Malasia",
    "VN": "Vietnam", "AE": "Emiratos Árabes", "IR": "Irán", "IQ": "Irak",
    "PK": "Pakistán", "NG": "Nigeria", "CO": "Colombia", "CL": "Chile", "PE": "Perú",
    "KW": "Kuwait", "QA": "Catar", "NO": "Noruega", "SE": "Suecia", "BE": "Bélgica",
    "GR": "Grecia", "PT": "Portugal", "CH": "Suiza", "TW": "Taiwán", "PH": "Filipinas",
    "DZ": "Argelia", "KZ": "Kazajistán", "UA": "Ucrania",
}

METRICAS = {
    "% del consumo (países que reportan)": ("cuota", "% del consumo"),
    "Millones de barriles al día": ("mbd", "mb/d"),
}


def buscar(df, *claves):
    for c in df.columns:
        if any(k in c.lower() for k in claves):
            return c
    return None


def leer_csv(anio):
    nombre = f"secondaryyear{anio}.csv" if anio == date.today().year else f"{anio}.csv"
    ruta = os.path.join(CACHE_DIR, f"secondary_{anio}.csv")
    try:
        r = requests.get(BASE + nombre, headers={"User-Agent": "Mozilla/5.0"}, timeout=90)
        r.raise_for_status()
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(ruta, "wb") as f:
            f.write(r.content)
    except Exception:
        if not os.path.exists(ruta):
            return None
    return pd.read_csv(ruta, dtype=str, encoding_errors="replace", on_bad_lines="skip")


@st.cache_data(ttl=86400, show_spinner="Descargando datos de JODI...")
def cargar():
    hoy = date.today()
    partes = [leer_csv(a) for a in (hoy.year - 1, hoy.year)]
    partes = [p for p in partes if p is not None]
    if not partes:
        return None, "No se pudo descargar ni leer ningún archivo de JODI.", {}
    raw = pd.concat(partes, ignore_index=True)

    cols = {
        "area": buscar(raw, "ref_area", "area"),
        "fecha": buscar(raw, "time_period", "time", "date"),
        "prod": buscar(raw, "energy_product", "product"),
        "flujo": buscar(raw, "flow_breakdown", "flow"),
        "unidad": buscar(raw, "unit_measure", "unit"),
        "valor": buscar(raw, "obs_value", "value"),
    }
    if None in cols.values():
        return None, "No se reconocieron las columnas del CSV.", {"columnas": list(raw.columns)}

    d = raw[[v for v in cols.values()]].copy()
    d.columns = list(cols.keys())
    for c in ["area", "prod", "flujo", "unidad"]:
        d[c] = d[c].astype(str).str.strip().str.upper()

    diag = {
        "columnas": list(raw.columns),
        "productos": sorted(d["prod"].unique())[:40],
        "flujos": sorted(d["flujo"].unique())[:40],
        "unidades": sorted(d["unidad"].unique())[:20],
    }

    d = d[d["flujo"].str.contains("DEM", na=False) & (d["unidad"] == "KBD") & d["prod"].isin(PRODUCTOS)]
    d["valor"] = pd.to_numeric(d["valor"], errors="coerce")
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce")
    d = d.dropna(subset=["valor", "fecha"])
    if d.empty:
        return None, "El CSV se descargó, pero no se encontraron filas de demanda con esos filtros.", diag

    fmax = d["fecha"].max()
    d = d[d["fecha"] >= fmax - pd.DateOffset(months=17)]
    d = d.sort_values("fecha").groupby(["area", "prod"]).tail(12)
    m = d.groupby(["area", "prod"], as_index=False).agg(kbd=("valor", "mean"))

    m["Derivado"] = m["prod"].map(PRODUCTOS)
    m["Código"] = m["area"].astype(str).str[:2].str.upper()
    m["País"] = m["area"].map(PAISES).fillna(m["area"])
    m["País con bandera"] = m.apply(
        lambda r: f"{bandera(r['Código'])} {r['País']}", axis=1
    )
    m["mbd"] = (m["kbd"] / 1000).round(3)
    m["cuota"] = (m["mbd"] / m.groupby("Derivado")["mbd"].transform("sum") * 100).round(1)
    m["puesto"] = m.groupby("Derivado")["mbd"].rank(ascending=False, method="first").astype(int)

    info = f"Último mes en la base: {fmax:%m/%Y} · descargado el {datetime.now():%d/%m/%Y %H:%M}"
    return m[["Derivado", "País", "Código", "País con bandera", "mbd", "cuota", "puesto"]], info, diag


df, info, diag = cargar()

st.title("🛢️ Derivados del petróleo")
st.caption("Consumo mundial por país y producto · Optimizado para móvil")

if df is None:
    st.error(info)
    st.write("Si tu red bloquea jodidata.org, descarga a mano los CSV secundarios de la página "
             "de descargas de JODI-Oil y guárdalos en la carpeta `cache_jodi` como "
             "`secondary_2025.csv` y `secondary_2026.csv`.")
    with st.expander("Diagnóstico"):
        st.write(diag)
    st.stop()

st.caption(f"Fuente: JODI-Oil World Database. Media de los últimos 12 meses disponibles por país. {info}")

vol = df.groupby("Derivado")["mbd"].sum().sort_values(ascending=False)
TODOS_DERIV = list(vol.index)
TODOS_PAISES = sorted(df[df["puesto"] <= 15]["País"].unique())


def reset():
    st.session_state["f_usos"] = []
    st.session_state["f_deriv"] = TODOS_DERIV
    st.session_state["f_paises"] = TODOS_PAISES
    st.session_state["f_top"] = 8
    st.session_state["f_cuota"] = 0
    st.session_state["f_metrica"] = list(METRICAS)[0]


st.session_state.setdefault("f_usos", [])
st.session_state.setdefault("f_deriv", TODOS_DERIV)
st.session_state.setdefault("f_paises", TODOS_PAISES)
st.session_state.setdefault("f_top", 8)
st.session_state.setdefault("f_cuota", 0)
st.session_state.setdefault("f_metrica", list(METRICAS)[0])
st.session_state["f_deriv"] = [x for x in st.session_state["f_deriv"] if x in TODOS_DERIV]
st.session_state["f_paises"] = [x for x in st.session_state["f_paises"] if x in TODOS_PAISES]

# ---------- Filtros ----------
st.sidebar.header("🔎 Filtros")
st.sidebar.caption("Abre este panel con la flecha ☰ cuando quieras cambiar la selección.")
st.sidebar.button("Restablecer filtros", on_click=reset)
st.sidebar.button("Actualizar datos ahora", on_click=st.cache_data.clear)

usos_sel = st.sidebar.multiselect("Uso (vacío = todos)", CATEGORIAS, key="f_usos")
deriv_sel = st.sidebar.multiselect("Derivados", TODOS_DERIV, key="f_deriv")
paises_sel = st.sidebar.multiselect("Países", TODOS_PAISES, key="f_paises")
top_n = st.sidebar.slider("Top países por derivado", 3, 15, key="f_top")
cuota_min = st.sidebar.slider("Cuota mínima (%)", 0, 30, key="f_cuota")
metrica = st.sidebar.radio("Mostrar como", list(METRICAS), key="f_metrica")
col, etiqueta = METRICAS[metrica]

derivados_activos = [
    p for p in deriv_sel
    if not usos_sel or set(INFO[p][0]) & set(usos_sel)
]

dff = df[
    df["Derivado"].isin(derivados_activos)
    & df["País"].isin(paises_sel)
    & (df["puesto"] <= top_n)
    & (df["cuota"] >= cuota_min)
]

if dff.empty:
    st.warning("Ningún dato cumple estos filtros. Amplía la selección o pulsa «Restablecer filtros».")
    st.stop()

st.sidebar.caption(f"{dff['Derivado'].nunique()} derivados · {dff['País'].nunique()} países · {len(dff)} datos")

# ---------- Indicadores ----------
total_pais = dff.groupby("País")["mbd"].sum().sort_values(ascending=False)
k1, k2, k3, k4 = st.columns(4, gap="small")
k1.metric("Derivados", dff["Derivado"].nunique())
k2.metric("Países", dff["País"].nunique())
k3.metric("Consumo filtrado", f"~{dff['mbd'].sum():.1f} mb/d")
k4.metric("País con más consumo", total_pais.index[0])

# ---------- Pestañas ----------
tab1, tab2, tab3, tab4 = st.tabs(["Resumen", "Por derivado", "Matriz", "Datos"])

with tab1:
    st.subheader("Consumo por país y derivado (mb/d)")
    orden = total_pais.sort_values().index.tolist()
    fig = px.bar(dff, x="mbd", y="País", color="Derivado", orientation="h",
                 category_orders={"País": orden})
    fig.update_layout(margin=dict(l=4, r=8, t=10, b=4), height=430,
                      xaxis_title="mb/d", yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})
    st.caption("Esta vista usa siempre mb/d, porque es la unidad que se puede sumar entre derivados.")

with tab2:
    con_datos = set(dff["Derivado"])
    presentes = [p for p in derivados_activos if p in con_datos]
    for p in presentes:
        sub = dff[dff["Derivado"] == p].sort_values(col)
        with st.container(border=True):
            st.subheader(p)
            st.caption(f"~{vol[p]:.1f} mb/d en los países que reportan · "
                       f"~{vol[p] / vol.sum() * 100:.0f}% del total de derivados")
            st.markdown("**Usos:** " + " · ".join(INFO[p][1]))
            fig = px.bar(sub, x=col, y="País con bandera", orientation="h", text=col)
            fig.update_traces(marker_color="#2a78d6", textposition="outside")
            fig.update_layout(margin=dict(l=4, r=8, t=10, b=4), height=330,
                              xaxis_title=etiqueta, yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})

with tab3:
    st.subheader(f"Derivados por país ({etiqueta})")
    pivot = dff.pivot_table(index="País con bandera", columns="Derivado", values=col, aggfunc="sum")
    fig = px.imshow(pivot, text_auto=True, aspect="auto",
                    color_continuous_scale="Blues", labels=dict(color=etiqueta))
    fig.update_layout(
        margin=dict(l=4, r=8, t=10, b=4),
        height=500,
        font=dict(size=10),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})

with tab4:
    st.subheader("Datos filtrados")
    tabla = dff.drop(columns=["Código", "País con bandera"], errors="ignore").rename(
        columns={"cuota": "% del consumo", "mbd": "mb/d", "puesto": "Puesto"}
    )
    st.dataframe(tabla, hide_index=True, use_container_width=True, height=420)
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8-sig"),
                       file_name="derivados_petroleo.csv", mime="text/csv")

with st.expander("Diagnóstico de la fuente"):
    st.write(diag)

st.caption("mb/d = millones de barriles al día. Los países que no reportan a JODI, o que aún no han "
           "enviado datos recientes, pueden faltar o aparecer con cifras de meses anteriores.")
