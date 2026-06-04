"""Registro de deducciones por empleado: facturas, cadena y préstamos."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core.auth import requerir_login
from core.db import (
    DeduccionCadena, Empleado, FacturaQuincena, PrestamoQuincena,
    get_session, init_db,
)
from core.ui import peso_input

requerir_login()
init_db()
st.title("💸 Deducciones")

with get_session() as s:
    empleados = (
        s.query(Empleado).filter_by(activo=True).order_by(Empleado.nombres).all()
    )

if not empleados:
    st.warning("Primero registra empleados activos.")
    st.stop()

emp_id = int(
    st.selectbox("Empleado", [f"{e.id} — {e.nombres}" for e in empleados])
    .split(" — ")[0]
)

# ── Formulario de registro ────────────────────────────────────────────────────
st.subheader("Registrar deducción")
concepto = st.selectbox(
    "Concepto",
    ["Factura (fiado, 10% descuento)", "Cadena", "Préstamo"],
)

with st.form("form_deduccion"):
    if concepto == "Factura (fiado, 10% descuento)":
        c1, c2, c3 = st.columns(3)
        with c1:
            valor_fac = peso_input("Valor factura", step=10000.0)
        with c2:
            fecha_fac = st.date_input("Fecha", value=date.today())
        with c3:
            desc_fac = st.text_input("Descripción")
        if st.form_submit_button("Registrar", type="primary"):
            if valor_fac <= 0:
                st.error("El valor debe ser mayor a cero.")
            else:
                valor_deducir = round(valor_fac * 0.90, 2)
                with get_session() as s:
                    s.add(FacturaQuincena(
                        empleado_id=emp_id, valor_factura=valor_fac,
                        descuento_pct=10.0, valor_deducir=valor_deducir,
                        descripcion=desc_fac, fecha=fecha_fac,
                    ))
                    s.commit()
                st.success(
                    f"Factura ${valor_fac:,.0f} registrada. "
                    f"A deducir: ${valor_deducir:,.0f} (con 10% descuento empleado)."
                )
                st.rerun()

    elif concepto == "Cadena":
        c1, c2 = st.columns(2)
        with c1:
            fecha_cad = st.date_input("Fecha", value=date.today())
        with c2:
            valor_cad = peso_input("Valor cadena", step=5000.0)
        if st.form_submit_button("Registrar", type="primary"):
            if valor_cad <= 0:
                st.error("El valor debe ser mayor a cero.")
            else:
                with get_session() as s:
                    s.add(DeduccionCadena(
                        empleado_id=emp_id, fecha=fecha_cad, valor=valor_cad,
                    ))
                    s.commit()
                st.success(
                    f"Cadena {fecha_cad.strftime('%d/%m/%Y')}: ${valor_cad:,.0f} registrada."
                )
                st.rerun()

    else:  # Préstamo
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_prest = st.date_input("Fecha", value=date.today())
        with c2:
            valor_prest = peso_input("Valor a deducir", step=10000.0)
        with c3:
            desc_prest = st.text_input("Descripción (opcional)")
        if st.form_submit_button("Registrar", type="primary"):
            if valor_prest <= 0:
                st.error("El valor debe ser mayor a cero.")
            else:
                with get_session() as s:
                    s.add(PrestamoQuincena(
                        empleado_id=emp_id, fecha=fecha_prest,
                        valor=valor_prest, descripcion=desc_prest,
                    ))
                    s.commit()
                st.success(
                    f"Préstamo ${valor_prest:,.0f} registrado para "
                    f"{fecha_prest.strftime('%d/%m/%Y')}."
                )
                st.rerun()

# ── Lista de pendientes con acciones ─────────────────────────────────────────
st.divider()
st.subheader("Deducciones pendientes")

with get_session() as s:
    facts = (
        s.query(FacturaQuincena)
        .filter(FacturaQuincena.empleado_id == emp_id,
                FacturaQuincena.liquidacion_id.is_(None))
        .order_by(FacturaQuincena.fecha.desc())
        .all()
    )
    cads = (
        s.query(DeduccionCadena)
        .filter(DeduccionCadena.empleado_id == emp_id,
                DeduccionCadena.liquidacion_id.is_(None))
        .order_by(DeduccionCadena.fecha.desc())
        .all()
    )
    prests = (
        s.query(PrestamoQuincena)
        .filter(PrestamoQuincena.empleado_id == emp_id,
                PrestamoQuincena.liquidacion_id.is_(None))
        .order_by(PrestamoQuincena.fecha.desc())
        .all()
    )

registros = []
for f in facts:
    registros.append({
        "_tipo": "factura", "_id": f.id,
        "Tipo": "Factura",
        "Ref.": f.fecha.strftime("%d/%m/%Y"),
        "Valor": f.valor_factura,
        "Dcto 10%": round(f.valor_factura * 0.10, 2),
        "A deducir": f.valor_deducir,
        "Descripción": f.descripcion or "",
    })
for c in cads:
    registros.append({
        "_tipo": "cadena", "_id": c.id,
        "Tipo": "Cadena",
        "Ref.": c.fecha.strftime("%d/%m/%Y") if c.fecha else "—",
        "Valor": c.valor,
        "Dcto 10%": 0.0,
        "A deducir": c.valor,
        "Descripción": "",
    })
for p in prests:
    registros.append({
        "_tipo": "prestamo", "_id": p.id,
        "Tipo": "Préstamo",
        "Ref.": p.fecha.strftime("%d/%m/%Y"),
        "Valor": p.valor,
        "Dcto 10%": 0.0,
        "A deducir": p.valor,
        "Descripción": p.descripcion or "",
    })

if not registros:
    st.info("Sin deducciones pendientes para este empleado.")
else:
    h = st.columns([1.2, 1.8, 2, 1.8, 2, 2.5, 0.6, 0.6])
    for col, label in zip(h, ["Tipo", "Ref.", "Valor", "Dcto 10%", "A deducir", "Descripción", "", ""]):
        col.markdown(f"**{label}**")
    st.divider()

    for reg in registros:
        cols = st.columns([1.2, 1.8, 2, 1.8, 2, 2.5, 0.6, 0.6])
        cols[0].write(reg["Tipo"])
        cols[1].write(reg["Ref."])
        cols[2].write(f"${reg['Valor']:,.0f}")
        cols[3].write(f"${reg['Dcto 10%']:,.0f}" if reg["Dcto 10%"] > 0 else "—")
        cols[4].write(f"${reg['A deducir']:,.0f}")
        cols[5].write(reg["Descripción"] or "—")

        key_edit = f"edit_{reg['_tipo']}_{reg['_id']}"
        key_del  = f"del_{reg['_tipo']}_{reg['_id']}"

        if cols[6].button("✏️", key=key_edit, help="Editar"):
            st.session_state["_ded_edit"] = (reg["_tipo"], reg["_id"])

        if cols[7].button("🗑️", key=key_del, help="Eliminar"):
            with get_session() as s:
                if reg["_tipo"] == "factura":
                    obj = s.get(FacturaQuincena, reg["_id"])
                elif reg["_tipo"] == "cadena":
                    obj = s.get(DeduccionCadena, reg["_id"])
                else:
                    obj = s.get(PrestamoQuincena, reg["_id"])
                if obj:
                    s.delete(obj)
                    s.commit()
            st.session_state.pop("_ded_edit", None)
            st.rerun()

    # ── Formulario de edición en línea ────────────────────────────────────────
    edit_state = st.session_state.get("_ded_edit")
    if edit_state:
        tipo_ed, id_ed = edit_state
        with get_session() as s:
            if tipo_ed == "factura":
                obj_ed = s.get(FacturaQuincena, id_ed)
            elif tipo_ed == "cadena":
                obj_ed = s.get(DeduccionCadena, id_ed)
            else:
                obj_ed = s.get(PrestamoQuincena, id_ed)

        if obj_ed and getattr(obj_ed, "empleado_id", None) == emp_id:
            st.divider()
            tipo_label = {"factura": "Factura", "cadena": "Cadena", "prestamo": "Préstamo"}
            st.markdown(f"**Editando {tipo_label[tipo_ed]} #{id_ed}**")
            with st.form("form_edit_ded"):
                if tipo_ed == "factura":
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nv = peso_input("Valor factura",
                                        step=10000.0, value=float(obj_ed.valor_factura))
                    with c2:
                        nf = st.date_input("Fecha", value=obj_ed.fecha)
                    with c3:
                        nd = st.text_input("Descripción", value=obj_ed.descripcion or "")
                    c_save, c_cancel = st.columns(2)
                    if c_save.form_submit_button("Guardar cambios", type="primary"):
                        with get_session() as s:
                            o = s.get(FacturaQuincena, id_ed)
                            o.valor_factura = nv
                            o.valor_deducir = round(nv * 0.90, 2)
                            o.fecha = nf
                            o.descripcion = nd
                            s.commit()
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()
                    if c_cancel.form_submit_button("Cancelar"):
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()

                elif tipo_ed == "cadena":
                    c1, c2 = st.columns(2)
                    with c1:
                        nf_cad = st.date_input("Fecha", value=obj_ed.fecha or date.today())
                    with c2:
                        nvc = peso_input("Valor cadena",
                                         step=5000.0, value=float(obj_ed.valor))
                    c_save, c_cancel = st.columns(2)
                    if c_save.form_submit_button("Guardar cambios", type="primary"):
                        with get_session() as s:
                            o = s.get(DeduccionCadena, id_ed)
                            o.fecha = nf_cad
                            o.valor = nvc
                            s.commit()
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()
                    if c_cancel.form_submit_button("Cancelar"):
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()

                else:  # prestamo
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nf_p = st.date_input("Fecha", value=obj_ed.fecha)
                    with c2:
                        nvp = peso_input("Valor a deducir",
                                         step=10000.0, value=float(obj_ed.valor))
                    with c3:
                        ndp = st.text_input("Descripción", value=obj_ed.descripcion or "")
                    c_save, c_cancel = st.columns(2)
                    if c_save.form_submit_button("Guardar cambios", type="primary"):
                        with get_session() as s:
                            o = s.get(PrestamoQuincena, id_ed)
                            o.fecha = nf_p
                            o.valor = nvp
                            o.descripcion = ndp
                            s.commit()
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()
                    if c_cancel.form_submit_button("Cancelar"):
                        st.session_state.pop("_ded_edit", None)
                        st.rerun()
        else:
            st.session_state.pop("_ded_edit", None)
