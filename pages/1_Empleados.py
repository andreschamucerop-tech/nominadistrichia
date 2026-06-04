"""CRUD de empleados."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core.auth import requerir_login
from core.db import (
    DeduccionCadena, Empleado, Empresa, FacturaQuincena,
    HorasCalculadas, LiquidacionQuincena, Marcacion, get_session, init_db,
)
from core.ui import peso_input

requerir_login()
init_db()
st.title("👥 Empleados")

with get_session() as s:
    empresa = s.query(Empresa).first()

TIPOS_DOC = {
    "CC": "Cédula de ciudadanía",
    "CE": "Cédula de extranjería",
    "TI": "Tarjeta de identidad",
    "PA": "Pasaporte",
    "PPT": "Permiso de Protección Temporal",
    "PEP": "Permiso Especial de Permanencia",
}

tab_lista, tab_nuevo, tab_eliminar = st.tabs(["Lista", "Nuevo / Editar", "Eliminar"])

with tab_lista:
    with get_session() as s:
        empleados = (
            s.query(Empleado)
            .order_by(Empleado.activo.desc(), Empleado.nombres)
            .all()
        )
    if not empleados:
        st.info("No hay empleados registrados.")
    else:
        data = [
            {
                "ID": e.id,
                "Tipo doc.": e.tipo_documento or "CC",
                "Documento": e.cedula,
                "Nombres": e.nombres,
                "Cargo": e.cargo,
                "Salario": f"${e.salario_base:,.0f}",
                "Ingreso": e.fecha_ingreso,
                "Estado": "Activo" if e.activo else "Inactivo",
            }
            for e in empleados
        ]
        st.dataframe(data, use_container_width=True, hide_index=True)

with tab_nuevo:
    with get_session() as s:
        activos = (
            s.query(Empleado).filter_by(activo=True).order_by(Empleado.nombres).all()
        )
    opciones = ["(Crear nuevo)"] + [f"{e.id} — {e.nombres}" for e in activos]
    sel = st.selectbox("Empleado", opciones)
    edit_id = None if sel == "(Crear nuevo)" else int(sel.split(" — ")[0])

    datos = None
    if edit_id:
        with get_session() as s:
            datos = s.get(Empleado, edit_id)

    with st.form("form_emp"):
        c1, c2 = st.columns(2)
        with c1:
            tipos = list(TIPOS_DOC.keys())
            tipo_actual = datos.tipo_documento if datos else "CC"
            idx = tipos.index(tipo_actual) if tipo_actual in tipos else 0
            tipo_doc = st.selectbox(
                "Tipo de documento", tipos, index=idx,
                format_func=lambda k: f"{k} — {TIPOS_DOC[k]}",
            )
            cedula = st.text_input("Documento", value=datos.cedula if datos else "")
            nombres = st.text_input(
                "Nombres completos", value=datos.nombres if datos else ""
            )
            cargo = st.text_input("Cargo", value=datos.cargo if datos else "")
        with c2:
            salario = peso_input(
                "Salario base mensual", step=50000.0,
                value=float(datos.salario_base) if datos else float(empresa.smmlv),
            )
            f_ing = st.date_input(
                "Fecha de ingreso",
                value=datos.fecha_ingreso if datos else date.today(),
            )
            activo = st.checkbox(
                "Activo", value=datos.activo if datos else True,
            )
        ok = st.form_submit_button("Guardar", type="primary")

    if ok:
        if not cedula or not nombres:
            st.error("Documento y nombres son obligatorios.")
        else:
            with get_session() as s:
                if edit_id:
                    e = s.get(Empleado, edit_id)
                else:
                    e = Empleado(
                        cedula=cedula, nombres=nombres,
                        fecha_ingreso=f_ing, salario_base=salario,
                    )
                    s.add(e)
                e.tipo_documento = tipo_doc
                e.cedula = cedula
                e.nombres = nombres
                e.cargo = cargo
                e.salario_base = float(salario)
                e.fecha_ingreso = f_ing
                e.activo = activo
                s.commit()
            st.success("Empleado guardado.")
            st.rerun()

with tab_eliminar:
    with get_session() as s:
        todos = s.query(Empleado).order_by(Empleado.nombres).all()

    if not todos:
        st.info("No hay empleados registrados.")
    else:
        opciones_del = [f"{e.id} — {e.nombres} ({e.tipo_documento or 'CC'} {e.cedula})" for e in todos]
        sel_del = st.selectbox("Empleado a eliminar", opciones_del, key="del_emp_sel")
        del_id = int(sel_del.split(" — ")[0])

        with get_session() as s:
            emp_del = s.get(Empleado, del_id)
            n_marc = s.query(Marcacion).filter_by(empleado_id=del_id).count()
            n_liq = s.query(LiquidacionQuincena).filter_by(empleado_id=del_id).count()
            n_fac = s.query(FacturaQuincena).filter_by(empleado_id=del_id).count()
            n_cad = s.query(DeduccionCadena).filter_by(empleado_id=del_id).count()

        st.warning(
            f"Esta acción **elimina permanentemente** a **{emp_del.nombres}** "
            f"y todos sus datos asociados:\n\n"
            f"- {n_marc} marcaciones\n"
            f"- {n_liq} liquidaciones\n"
            f"- {n_fac} facturas\n"
            f"- {n_cad} cadenas"
        )

        confirmar = st.checkbox("Confirmo que quiero eliminar este empleado", key="del_emp_confirm")
        if st.button("Eliminar empleado", type="primary", disabled=not confirmar):
            with get_session() as s:
                e = s.get(Empleado, del_id)
                s.delete(e)
                s.commit()
            st.success(f"Empleado eliminado correctamente.")
            st.rerun()
