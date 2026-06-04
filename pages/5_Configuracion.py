"""Configuración: datos empresa, valores de recargo y cambio de contraseña."""
from __future__ import annotations

import streamlit as st

from core.auth import cambiar_password, requerir_login
from core.db import Empresa, get_session, init_db
from core.ui import peso_input

requerir_login()
init_db()
st.title("⚙️ Configuración")

tab_emp, tab_param, tab_pwd = st.tabs(
    ["Datos empresa", "Valores de nómina", "Cambiar contraseña"]
)

with get_session() as s:
    empresa = s.query(Empresa).first()

with tab_emp:
    with st.form("form_emp"):
        razon = st.text_input("Razón social", value=empresa.razon_social)
        nit = st.text_input("NIT", value=empresa.nit)
        repr_legal = st.text_input("Representante legal", value=empresa.representante_legal)
        if st.form_submit_button("Guardar", type="primary"):
            with get_session() as s:
                e = s.query(Empresa).first()
                e.razon_social = razon
                e.nit = nit
                e.representante_legal = repr_legal
                s.commit()
            st.success("Datos guardados.")
            st.rerun()

with tab_param:
    with st.form("form_param"):
        c1, c2 = st.columns(2)
        with c1:
            smmlv = peso_input(
                "Salario mínimo (SMMLV)", step=10000.0,
                value=float(empresa.smmlv),
            )
            aux = peso_input(
                "Auxilio de transporte", step=10000.0,
                value=float(empresa.auxilio_transporte),
            )
        with c2:
            v_he = peso_input(
                "Valor hora extra ordinaria ($)", step=100.0,
                value=float(empresa.valor_hora_extra),
            )
            v_rn = peso_input(
                "Valor recargo nocturno por hora ($)", step=100.0,
                value=float(empresa.valor_recargo_nocturno_hora),
            )
            v_dom = peso_input(
                "Valor recargo dominical por día ($)", step=100.0,
                value=float(empresa.valor_recargo_dominical_dia),
            )
        if st.form_submit_button("Guardar", type="primary"):
            with get_session() as s:
                e = s.query(Empresa).first()
                e.smmlv = smmlv
                e.auxilio_transporte = aux
                e.valor_hora_extra = v_he
                e.valor_recargo_nocturno_hora = v_rn
                e.valor_recargo_dominical_dia = v_dom
                s.commit()
            st.success("Valores actualizados.")
            st.rerun()

with tab_pwd:
    with st.form("form_pwd"):
        actual = st.text_input("Contraseña actual", type="password")
        nueva = st.text_input("Contraseña nueva", type="password")
        confirm = st.text_input("Confirmar contraseña nueva", type="password")
        if st.form_submit_button("Cambiar contraseña", type="primary"):
            if not nueva or nueva != confirm:
                st.error("Las contraseñas no coinciden.")
            elif len(nueva) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            else:
                ok = cambiar_password(
                    st.session_state.get("usuario", "admin"), actual, nueva,
                )
                if ok:
                    st.success("Contraseña actualizada.")
                else:
                    st.error("Contraseña actual incorrecta.")
