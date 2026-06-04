"""Entrada principal de la aplicación de nómina DISTRICHIA SAS."""
from __future__ import annotations
from pathlib import Path

import streamlit as st

from core.auth import cerrar_sesion, requerir_login
from core.db import Empresa, get_session
from core.seed import seed_inicial

LOGO_PATH = Path(__file__).parent / "data" / "logo.png"

st.set_page_config(
    page_title="Nómina DISTRICHIA SAS",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "💼",
    layout="wide",
)

if LOGO_PATH.exists():
    st.logo(str(LOGO_PATH))

st.markdown("""
<style>
/* ── Tipografía base ── */
html, body, [class*="css"] {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1C3A1C 0%, #2A6B2A 60%, #5B9B2A 100%);
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] .stButton > button {
    background-color: #E87020 !important;
    color: #FFFFFF !important;
    border: none;
    border-radius: 6px;
    font-weight: 600;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #F5B000 !important;
    color: #1C3A1C !important;
}

/* ── Encabezados ── */
h1 { color: #2A6B2A !important; font-weight: 700; }
h2 { color: #2A6B2A !important; font-weight: 600; }
h3 { color: #5B9B2A !important; font-weight: 600; }

/* ── Botón primario ── */
[data-testid="baseButton-primary"] {
    background-color: #E87020 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
[data-testid="baseButton-primary"]:hover {
    background-color: #F5B000 !important;
    color: #1C3A1C !important;
}

/* ── Botón secundario ── */
[data-testid="baseButton-secondary"] {
    border: 2px solid #2A6B2A !important;
    color: #2A6B2A !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
}
[data-testid="baseButton-secondary"]:hover {
    background-color: #F2F7EE !important;
    border-color: #5B9B2A !important;
}

/* ── Tabs ── */
[data-testid="stTab"] button[aria-selected="true"] {
    color: #E87020 !important;
    border-bottom: 3px solid #E87020 !important;
    font-weight: 600;
}

/* ── Métricas / info boxes ── */
[data-testid="stMetric"] { background-color: #F2F7EE; border-radius: 8px; padding: 8px; }

/* ── Dataframe header ── */
[data-testid="stDataFrame"] thead tr th {
    background-color: #2A6B2A !important;
    color: #FFFFFF !important;
}

/* ── Divider ── */
hr { border-color: #5B9B2A !important; opacity: 0.3; }
</style>
""", unsafe_allow_html=True)

# Seed silencioso. Si genera password, la muestra en consola.
pwd = seed_inicial()
if pwd:
    print("\n" + "=" * 60)
    print(" Usuario admin creado en la base de datos.")
    print(f" Usuario:    admin")
    print(f" Contraseña: {pwd}")
    print(" (Cámbiala desde la página de Configuración tras iniciar sesión.)")
    print("=" * 60 + "\n")

requerir_login()

with get_session() as s:
    empresa = s.query(Empresa).first()

col_logo, col_title = st.columns([1, 5])
with col_logo:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=140)
with col_title:
    st.title("Nómina DISTRICHIA SAS")
    st.caption(f"NIT: {empresa.nit} — Representante legal: {empresa.representante_legal}")

st.markdown(
    """
    Bienvenido al sistema de nómina. Navega por las páginas en el menú lateral:

    1. **Empleados** — Crear, editar y desactivar empleados.
    2. **Cargar Marcaciones** — Subir el Excel con las horas trabajadas.
    3. **Deducciones** — Registrar facturas (fiado) y cadena por empleado.
    4. **Liquidar Quincena** — Generar la liquidación y los dos PDFs por empleado.
    5. **Configuración** — Valores de SMMLV, auxilio, recargos y cambio de contraseña.
    """
)

with st.sidebar:
    st.divider()
    if st.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()
