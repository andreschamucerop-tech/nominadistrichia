"""Liquidación quincenal con generación de PDF combinado por empleado."""
from __future__ import annotations

from calendar import monthrange
from datetime import date

import streamlit as st

from core.auth import requerir_login
from core.db import (
    Empleado, Empresa, LiquidacionQuincena, get_session, init_db,
)
from core.nomina import liquidar
from core.pdf import generar_pdf_combinado
from core.ui import peso_input

requerir_login()
init_db()
st.title("🧾 Liquidar Quincena")

with get_session() as s:
    empresa = s.query(Empresa).first()
    empleados = (
        s.query(Empleado).filter_by(activo=True).order_by(Empleado.nombres).all()
    )

if not empleados:
    st.warning("No hay empleados activos.")
    st.stop()

# Selector de periodo
c1, c2, c3 = st.columns(3)
with c1:
    anio = st.number_input(
        "Año", min_value=2020, max_value=2100,
        value=date.today().year, step=1,
    )
with c2:
    mes = st.number_input(
        "Mes", min_value=1, max_value=12,
        value=date.today().month, step=1,
    )
with c3:
    quincena = st.radio(
        "Quincena", ["1 - 15", "16 - fin"], horizontal=True,
    )

ult_dia = monthrange(int(anio), int(mes))[1]
if quincena.startswith("1"):
    periodo_inicio = date(int(anio), int(mes), 1)
    periodo_fin = date(int(anio), int(mes), 15)
else:
    periodo_inicio = date(int(anio), int(mes), 16)
    periodo_fin = date(int(anio), int(mes), ult_dia)

st.info(f"Periodo: **{periodo_inicio} → {periodo_fin}**")

tab_calc, tab_hist = st.tabs(["Calcular liquidación", "Historial"])

with tab_calc:
    sel = st.selectbox(
        "Empleado", [f"{e.id} — {e.nombres}" for e in empleados],
    )
    emp_id = int(sel.split(" — ")[0])

    c_bonif, c_dom = st.columns(2)
    with c_bonif:
        bonif = peso_input(
            "Bonificación (opcional, no constituye salario)",
            step=10000.0, value=0.0,
        )
    with c_dom:
        domicilios = peso_input(
            "Domicilios ($)",
            step=5000.0, value=0.0,
        )

    if st.button("Calcular previsualización", type="secondary"):
        # Calcular dominicales automáticamente para pre-llenar el campo
        with get_session() as s:
            emp_pre = s.get(Empleado, emp_id)
            emp_obj_pre = s.query(Empresa).first()
            r_pre = liquidar(s, emp_pre, emp_obj_pre, periodo_inicio, periodo_fin, bonif, domicilios)
        st.session_state["_liq_pendiente"] = {
            "emp_id": emp_id,
            "ini": periodo_inicio.isoformat(),
            "fin": periodo_fin.isoformat(),
            "bonif": bonif,
            "domicilios": domicilios,
            "dominicales_override": r_pre.dominicales,
        }
        st.session_state["input_dominicales"] = r_pre.dominicales
        st.rerun()

    # ── Previsualización persistente ─────────────────────────────────────────
    pend = st.session_state.get("_liq_pendiente")
    contexto_valido = (
        pend
        and pend["emp_id"] == emp_id
        and pend["ini"] == periodo_inicio.isoformat()
        and pend["fin"] == periodo_fin.isoformat()
    )

    if contexto_valido:
        with get_session() as s:
            emp = s.get(Empleado, emp_id)
            emp_obj = s.query(Empresa).first()
            r = liquidar(
                s, emp, emp_obj, periodo_inicio, periodo_fin,
                pend["bonif"], pend.get("domicilios", 0.0),
                dominicales_override=pend["dominicales_override"],
            )

        st.subheader("Resumen — Liquidación real")
        st.write({
            "Días del periodo": r.dias_periodo,
            "Días con marcación": r.dias_trabajados,
            "Horas ordinarias": r.h_ord,
            "Horas extras": r.h_ext,
            "Horas nocturnas": r.h_noct,
            "Salario": f"${r.salario_proporcional:,.0f}",
            "Auxilio de transporte": f"${r.aux_transporte_real:,.0f}",
            "Valor extras": f"${r.valor_extras:,.0f}",
            "Valor nocturnas": f"${r.valor_nocturnas:,.0f}",
            "Dominicales": r.dominicales,
            "Valor dominicales": f"${r.valor_dominicales:,.0f}",
            "Domicilios": f"${r.domicilios:,.0f}",
            "Bonificación": f"${r.bonificacion:,.0f}",
            "DEVENGADO": f"${r.devengado_real:,.0f}",
            "Salud 4%": f"${r.salud_real:,.0f}",
            "Pensión 4%": f"${r.pension_real:,.0f}",
            "Facturas": f"${r.facturas_total:,.0f}",
            "Cadena": f"${r.cadena_total:,.0f}",
            "Préstamos": f"${r.prestamos_total:,.0f}",
            "DEDUCCIONES": f"${r.deducciones_real:,.0f}",
            "NETO REAL": f"${r.neto_real:,.0f}",
        })

        st.subheader("Resumen — Base salario mínimo")
        st.write({
            "Salario mínimo": f"${r.smmlv_proporcional:,.0f}",
            "Aux. transporte": f"${r.aux_transporte_proporcional:,.0f}",
            "DEVENGADO MÍNIMO": f"${r.devengado_min:,.0f}",
            "Salud 4%": f"${r.salud_min:,.0f}",
            "Pensión 4%": f"${r.pension_min:,.0f}",
            "DEDUCCIONES MÍNIMO": f"${r.deducciones_min:,.0f}",
            "NETO MÍNIMO": f"${r.neto_min:,.0f}",
        })

        # ── Ajuste de dominicales ─────────────────────────────────────────────
        st.divider()
        ca, cb = st.columns([2, 1])
        with ca:
            st.number_input(
                "Dominicales (editable — ajusta y recalcula)",
                step=1,
                min_value=0,
                max_value=365,
                key="input_dominicales",
            )
        with cb:
            st.write("")
            st.write("")
            if st.button("Recalcular", type="secondary"):
                pend["dominicales_override"] = int(st.session_state["input_dominicales"])
                st.rerun()

        # ── Confirmar ─────────────────────────────────────────────────────────
        st.divider()
        if st.button("Confirmar liquidación y generar PDF", type="primary"):
            with get_session() as s:
                emp = s.get(Empleado, emp_id)
                emp_obj2 = s.query(Empresa).first()
                r_final = liquidar(
                    s, emp, emp_obj2, periodo_inicio, periodo_fin,
                    pend["bonif"], pend.get("domicilios", 0.0),
                    dominicales_override=pend["dominicales_override"],
                )

                liq = LiquidacionQuincena(
                    empleado_id=emp_id,
                    periodo_inicio=periodo_inicio, periodo_fin=periodo_fin,
                    dias_trabajados=r_final.dias_trabajados,
                    h_ord=r_final.h_ord, h_ext=r_final.h_ext, h_noct=r_final.h_noct,
                    dominicales=r_final.dominicales, bonificacion=r_final.bonificacion,
                    devengado_real=r_final.devengado_real,
                    deducciones_real=r_final.deducciones_real, neto_real=r_final.neto_real,
                    devengado_min=r_final.devengado_min,
                    deducciones_min=r_final.deducciones_min, neto_min=r_final.neto_min,
                )
                s.add(liq)
                s.flush()

                path_pdf = generar_pdf_combinado(
                    emp_obj2, emp, periodo_inicio, periodo_fin, r_final,
                )
                liq.pdf_real_path = path_pdf

                s.commit()
                liq_id = liq.id
                path_final = liq.pdf_real_path

            st.success(f"Liquidación #{liq_id} guardada.")
            with open(path_final, "rb") as fh:
                st.download_button(
                    "⬇️ Descargar desprendible (PDF)",
                    fh.read(),
                    file_name=path_final.split("/")[-1],
                    mime="application/pdf",
                )
            st.session_state.pop("_liq_pendiente", None)


with tab_hist:
    with get_session() as s:
        liqs = (
            s.query(LiquidacionQuincena, Empleado)
            .join(Empleado, Empleado.id == LiquidacionQuincena.empleado_id)
            .order_by(LiquidacionQuincena.periodo_inicio.desc())
            .limit(500)
            .all()
        )
    if not liqs:
        st.info("Sin liquidaciones guardadas.")
    else:
        data = [{
            "ID": l.id,
            "Empleado": e.nombres,
            "Periodo": f"{l.periodo_inicio} → {l.periodo_fin}",
            "Días": l.dias_trabajados,
            "Devengado real": f"${l.devengado_real:,.0f}",
            "Neto real": f"${l.neto_real:,.0f}",
            "Neto mínimo": f"${l.neto_min:,.0f}",
        } for (l, e) in liqs]
        st.dataframe(data, use_container_width=True, hide_index=True)

        sel_liq = st.number_input(
            "ID de liquidación para descargar PDFs",
            min_value=0, step=1, value=0,
        )
        if sel_liq > 0:
            with get_session() as s:
                liq = s.get(LiquidacionQuincena, int(sel_liq))
            if liq:
                if liq.pdf_real_path:
                    try:
                        with open(liq.pdf_real_path, "rb") as fh:
                            st.download_button(
                                "⬇️ Descargar desprendible (PDF)",
                                fh.read(),
                                file_name=liq.pdf_real_path.split("/")[-1],
                                mime="application/pdf",
                                key=f"pdf_{liq.id}",
                            )
                    except FileNotFoundError:
                        st.warning("PDF no encontrado en disco.")
                else:
                    st.info("Esta liquidación no tiene PDF guardado.")
            else:
                st.error("Liquidación no encontrada.")
