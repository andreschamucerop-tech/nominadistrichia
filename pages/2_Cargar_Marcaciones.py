"""Carga del Excel con marcaciones y cálculo de horas."""
from __future__ import annotations

from datetime import datetime, time
from io import BytesIO

import pandas as pd
import streamlit as st

from core.auth import requerir_login
from core.db import (
    Empleado, HorasCalculadas, Marcacion, get_session, init_db,
)
from core.horas import calcular_horas

requerir_login()
init_db()
st.title("📥 Cargar Marcaciones (Excel)")

st.markdown(
    """
    El Excel debe tener estas columnas (insensible a mayúsculas/espacios):

    | cedula | nombre | fecha | hora_entrada | inicio_descanso | fin_descanso | hora_salida |

    - **fecha**: `AAAA-MM-DD` o formato fecha de Excel.
    - **horas**: `HH:MM` (24 h). Si la salida cruza medianoche, pon la hora del día siguiente.
    - Si no hay almuerzo, deja vacíos `inicio_descanso` y `fin_descanso`.
    - Se identifica el empleado por **cedula** (si está) o por **nombre**.
    """
)


def _generar_plantilla() -> bytes:
    plantilla = pd.DataFrame([
        {"cedula": "1010101010", "nombre": "Juan Pérez",
         "fecha": "2026-05-01", "hora_entrada": "08:00",
         "inicio_descanso": "12:00", "fin_descanso": "13:00",
         "hora_salida": "17:00"},
        {"cedula": "1020202020", "nombre": "María Gómez",
         "fecha": "2026-05-01", "hora_entrada": "18:00",
         "inicio_descanso": "", "fin_descanso": "",
         "hora_salida": "02:00"},
    ])
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        plantilla.to_excel(w, sheet_name="Marcaciones", index=False)
    return buf.getvalue()


st.download_button(
    "⬇️ Descargar plantilla Excel",
    data=_generar_plantilla(),
    file_name="plantilla_marcaciones.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


def _norm(c: str) -> str:
    return str(c).strip().lower().replace(" ", "_")


def _to_time(v) -> time | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    try:
        f = float(s)
        total_min = round(f * 24 * 60)
        return time(total_min // 60 % 24, total_min % 60)
    except Exception:
        return None


def _to_date(v):
    if isinstance(v, datetime):
        return v.date()
    return pd.to_datetime(v).date()


archivo = st.file_uploader("Archivo Excel", type=["xlsx", "xls"])

if archivo:
    try:
        df = pd.read_excel(archivo)
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        st.stop()

    df.columns = [_norm(c) for c in df.columns]
    requeridas = {"fecha", "hora_entrada", "hora_salida"}
    faltan = requeridas - set(df.columns)
    if faltan or ("nombre" not in df.columns and "cedula" not in df.columns):
        st.error(
            "Faltan columnas. Requeridas: fecha, hora_entrada, hora_salida "
            "y al menos una de (cedula, nombre)."
        )
        st.stop()

    st.write(f"Filas leídas: **{len(df)}**")
    st.dataframe(df.head(10), use_container_width=True)

    if st.button("Procesar y calcular horas", type="primary"):
        with get_session() as s:
            por_nombre = {e.nombres.strip().lower(): e for e in s.query(Empleado).all()}
            por_cedula = {e.cedula: e for e in s.query(Empleado).all()}

            errores = []
            insertados = 0
            for idx, row in df.iterrows():
                emp = None
                if "cedula" in df.columns and pd.notna(row.get("cedula")):
                    emp = por_cedula.get(str(row["cedula"]).strip())
                if emp is None and "nombre" in df.columns and pd.notna(row.get("nombre")):
                    emp = por_nombre.get(str(row["nombre"]).strip().lower())
                if emp is None:
                    errores.append(f"Fila {idx + 2}: empleado no encontrado.")
                    continue

                try:
                    f = _to_date(row["fecha"])
                    h_in = _to_time(row["hora_entrada"])
                    h_out = _to_time(row.get("hora_salida"))
                    h_id = _to_time(row.get("inicio_descanso"))
                    h_fd = _to_time(row.get("fin_descanso"))

                    if h_in and h_id and not h_fd and not h_out:
                        # Turno corrido (solo entrada + salida en columna descanso)
                        h_out = h_id
                        h_id = None

                    if not h_in or not h_out:
                        raise ValueError("hora_entrada/hora_salida inválidas")
                except Exception as e:
                    errores.append(f"Fila {idx + 2}: {e}")
                    continue

                existente = (
                    s.query(Marcacion)
                    .filter_by(empleado_id=emp.id, fecha=f)
                    .first()
                )
                if existente:
                    s.delete(existente)
                    s.flush()

                m = Marcacion(
                    empleado_id=emp.id, fecha=f,
                    hora_entrada=h_in, inicio_descanso=h_id,
                    fin_descanso=h_fd, hora_salida=h_out,
                    archivo_origen=archivo.name,
                )
                s.add(m)
                s.flush()

                horas = calcular_horas(f, h_in, h_id, h_fd, h_out)
                s.add(HorasCalculadas(
                    marcacion_id=m.id,
                    h_ordinarias=horas.h_ordinarias,
                    h_extras=horas.h_extras,
                    h_nocturnas=horas.h_nocturnas,
                ))
                insertados += 1

            s.commit()

        st.success(f"Procesadas {insertados} marcaciones.")
        if errores:
            with st.expander(f"⚠️ {len(errores)} errores"):
                for e in errores:
                    st.text(e)


# Vista de marcaciones existentes
st.divider()
st.subheader("Marcaciones registradas")

with get_session() as s:
    rows = (
        s.query(Marcacion, HorasCalculadas, Empleado)
        .join(HorasCalculadas, HorasCalculadas.marcacion_id == Marcacion.id)
        .join(Empleado, Empleado.id == Marcacion.empleado_id)
        .order_by(Marcacion.fecha.desc())
        .limit(2000)
        .all()
    )

if rows:
    data = [{
        "Fecha": m.fecha,
        "Empleado": e.nombres,
        "Entrada": str(m.hora_entrada),
        "Descanso": f"{m.inicio_descanso}-{m.fin_descanso}" if m.inicio_descanso else "—",
        "Salida": str(m.hora_salida),
        "Ord": h.h_ordinarias,
        "Ext": h.h_extras,
        "Noct": h.h_nocturnas,
    } for (m, h, e) in rows]
    df_marc = pd.DataFrame(data)

    with st.expander("🔎 Filtros", expanded=False):
        f1, f2, f3 = st.columns(3)
        with f1:
            emp_opt = sorted(df_marc["Empleado"].unique().tolist())
            sel_emp = st.multiselect("Empleado", emp_opt, default=[])
        with f2:
            f_desde = st.date_input(
                "Desde", value=df_marc["Fecha"].min(), key="filt_desde",
            )
        with f3:
            f_hasta = st.date_input(
                "Hasta", value=df_marc["Fecha"].max(), key="filt_hasta",
            )

    df_filt = df_marc.copy()
    if sel_emp:
        df_filt = df_filt[df_filt["Empleado"].isin(sel_emp)]
    if f_desde:
        df_filt = df_filt[df_filt["Fecha"] >= f_desde]
    if f_hasta:
        df_filt = df_filt[df_filt["Fecha"] <= f_hasta]

    st.caption(f"Mostrando {len(df_filt)} de {len(df_marc)} marcaciones")
    st.dataframe(df_filt, use_container_width=True, hide_index=True)
else:
    st.info("Aún no hay marcaciones registradas.")


# === Borrar marcaciones ===
st.divider()
st.subheader("🗑️ Borrar marcaciones")

with get_session() as s:
    todos_emp = s.query(Empleado).order_by(Empleado.nombres).all()

if todos_emp:
    opc = ["(Todos los empleados)"] + [
        f"{e.nombres} ({e.tipo_documento or 'CC'} {e.cedula})" for e in todos_emp
    ]
    emp_filtro = st.selectbox("Empleado", opc, key="del_emp")
    c1, c2 = st.columns(2)
    with c1:
        f_d = st.date_input("Desde", value=None, key="del_desde", format="YYYY-MM-DD")
    with c2:
        f_h = st.date_input("Hasta", value=None, key="del_hasta", format="YYYY-MM-DD")

    with get_session() as s:
        q = s.query(Marcacion)
        if emp_filtro != "(Todos los empleados)":
            emp_obj = next(
                e for e in todos_emp
                if f"{e.nombres} ({e.tipo_documento or 'CC'} {e.cedula})" == emp_filtro
            )
            q = q.filter(Marcacion.empleado_id == emp_obj.id)
        if f_d:
            q = q.filter(Marcacion.fecha >= f_d)
        if f_h:
            q = q.filter(Marcacion.fecha <= f_h)
        cantidad = q.count()

    st.info(f"Se eliminarán **{cantidad}** marcaciones.")
    confirmar = st.checkbox("Confirmo la eliminación", key="del_confirm")
    if st.button(
        "Eliminar", type="primary",
        disabled=(cantidad == 0 or not confirmar),
    ):
        with get_session() as s:
            q = s.query(Marcacion)
            if emp_filtro != "(Todos los empleados)":
                emp_obj = next(
                    e for e in todos_emp
                    if f"{e.nombres} ({e.tipo_documento or 'CC'} {e.cedula})" == emp_filtro
                )
                q = q.filter(Marcacion.empleado_id == emp_obj.id)
            if f_d:
                q = q.filter(Marcacion.fecha >= f_d)
            if f_h:
                q = q.filter(Marcacion.fecha <= f_h)
            marcs = q.all()
            for m in marcs:
                s.delete(m)
            s.commit()
        st.success(f"Eliminadas {len(marcs)} marcaciones.")
        st.rerun()
