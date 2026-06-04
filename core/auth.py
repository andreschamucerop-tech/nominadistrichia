"""Autenticación del único administrador."""
from __future__ import annotations

import bcrypt
import streamlit as st

from core.db import Admin, get_session


def _verificar(usuario: str, password: str) -> bool:
    with get_session() as s:
        a = s.query(Admin).filter_by(usuario=usuario).first()
        if not a:
            return False
        return bcrypt.checkpw(password.encode(), a.password_hash.encode())


def cambiar_password(usuario: str, password_actual: str, password_nuevo: str) -> bool:
    if not _verificar(usuario, password_actual):
        return False
    with get_session() as s:
        a = s.query(Admin).filter_by(usuario=usuario).first()
        a.password_hash = bcrypt.hashpw(
            password_nuevo.encode(), bcrypt.gensalt()
        ).decode()
        s.commit()
    return True


def requerir_login():
    """Renderiza login si no hay sesión; detiene la página si no autenticado."""
    if st.session_state.get("auth_ok"):
        return

    st.title("🔐 Acceso administrador")
    with st.form("login"):
        u = st.text_input("Usuario", value="admin")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Entrar", type="primary")
    if ok:
        if _verificar(u, p):
            st.session_state["auth_ok"] = True
            st.session_state["usuario"] = u
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


def cerrar_sesion():
    for k in ("auth_ok", "usuario"):
        st.session_state.pop(k, None)
