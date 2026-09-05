"""Cálculo de liquidación quincenal: real y 'como salario mínimo'."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
import holidays as holidays_lib
from sqlalchemy.orm import Session

from core.db import (
    DeduccionCadena, Empleado, Empresa, FacturaQuincena,
    HorasCalculadas, Marcacion, PermisoNoRemunerado, PrestamoQuincena,
)
from core.horas import JORNADA_SEMANAL_HORAS


@dataclass
class ResumenLiquidacion:
    # Datos base
    dias_periodo: int = 0       # días calendario del periodo (incl. descansos)
    dias_laborados: int = 0     # días del periodo cubiertos por el contrato (según fecha_ingreso/retiro)
    dias_trabajados: int = 0    # días con marcación (informativo)
    h_ord: float = 0.0
    h_ext: float = 0.0
    h_noct: float = 0.0
    dominicales: int = 0

    # PDF real
    salario_proporcional: float = 0.0
    aux_transporte_real: float = 0.0
    valor_extras: float = 0.0
    valor_nocturnas: float = 0.0
    valor_dominicales: float = 0.0
    bonificacion: float = 0.0
    domicilios: float = 0.0
    devengado_real: float = 0.0

    salud_real: float = 0.0
    pension_real: float = 0.0
    facturas_total: float = 0.0
    cadena_total: float = 0.0
    prestamos_total: float = 0.0
    deducciones_real: float = 0.0
    neto_real: float = 0.0

    # PDF mínimo
    smmlv_proporcional: float = 0.0
    aux_transporte_proporcional: float = 0.0
    devengado_min: float = 0.0
    salud_min: float = 0.0
    pension_min: float = 0.0
    deducciones_min: float = 0.0
    neto_min: float = 0.0

    permisos_dias: int = 0
    permisos_descuento: float = 0.0

    # Detalle bruto
    facturas: list = field(default_factory=list)
    cadenas: list = field(default_factory=list)
    prestamos: list = field(default_factory=list)
    permisos: list = field(default_factory=list)


def _festivos_col(year: int) -> set[date]:
    return set(holidays_lib.Colombia(years=year).keys())


def _contar_dominicales(
    sess: Session, empleado_id: int, ini: date, fin: date,
) -> int:
    """Cuenta dominicales asignados a la quincena.

    Se itera por cada domingo dentro del rango [ini, fin]. Los "días
    especiales" (domingo + festivos colombianos) y los días trabajados se
    restringen estrictamente a la quincena que se está liquidando — no se
    consulta ni se tiene en cuenta información de días fuera del periodo,
    aunque pertenezcan a la misma semana calendario.

      - Sin días trabajados esa semana (dentro del periodo) → no cuenta.
      - Trabajó todos los días especiales del periodo (sin descanso) → 2 dom.
      - Descansó al menos 1 día especial del periodo → 1 dominical.
    """
    total = 0
    d = ini
    while d <= fin:
        if d.weekday() == 6:  # domingo
            lunes = d - timedelta(days=6)
            domingo = d
            lunes_periodo = max(lunes, ini)
            domingo_periodo = min(domingo, fin)

            # Festivos colombianos para los años que toca la semana
            años = {lunes.year, domingo.year}
            festivos: set[date] = set()
            for y in años:
                festivos |= _festivos_col(y)

            # Días especiales de la semana (domingo + festivos lun-sáb),
            # restringidos a los que caen dentro de la quincena.
            dias_especiales: set[date] = set()
            cur = lunes_periodo
            while cur <= domingo_periodo:
                if cur.weekday() == 6 or cur in festivos:
                    dias_especiales.add(cur)
                cur += timedelta(days=1)

            # Días trabajados dentro de la quincena, en esa semana
            rows = (
                sess.query(Marcacion.fecha)
                .filter(
                    Marcacion.empleado_id == empleado_id,
                    Marcacion.fecha >= lunes_periodo,
                    Marcacion.fecha <= domingo_periodo,
                )
                .all()
            )
            trabajados: set[date] = {r.fecha for r in rows}

            if not trabajados:
                d += timedelta(days=1)
                continue

            # ¿Descansó algún día especial (dentro del periodo)?
            descanso_especial = dias_especiales - trabajados
            if descanso_especial:
                total += 1   # tuvo al menos 1 día de descanso especial
            else:
                total += 2   # trabajó sin descansar ningún festivo/dom

        d += timedelta(days=1)
    return total


def _horas_semana_ajustadas(
    sess: Session, empleado_id: int, periodo_inicio: date, periodo_fin: date,
) -> tuple[float, float]:
    """Recalcula ordinarias/extras del periodo aplicando también el tope
    semanal de 42h (además del tope diario de 7h ya aplicado en
    HorasCalculadas).

    Se recorre cada semana completa (lun-dom) que toca el periodo, aunque
    se salga de él, para que el corte de quincena no altere el resultado
    semanal real (igual criterio que _contar_dominicales). Las horas
    "ordinarias" diarias (ya topadas a 7h/día) se acumulan por semana; lo
    que exceda de 42h se reclasifica como extra.
    """
    ini_semana = periodo_inicio - timedelta(days=periodo_inicio.weekday())
    fin_semana = periodo_fin + timedelta(days=6 - periodo_fin.weekday())

    filas = (
        sess.query(
            Marcacion.fecha, HorasCalculadas.h_ordinarias, HorasCalculadas.h_extras,
        )
        .join(HorasCalculadas, HorasCalculadas.marcacion_id == Marcacion.id)
        .filter(
            Marcacion.empleado_id == empleado_id,
            Marcacion.fecha >= ini_semana,
            Marcacion.fecha <= fin_semana,
        )
        .order_by(Marcacion.fecha)
        .all()
    )

    h_ord_total = 0.0
    h_ext_total = 0.0
    acumulado_ord = 0.0
    semana_actual: date | None = None
    for fecha, ord_dia, ext_dia in filas:
        inicio_semana_fecha = fecha - timedelta(days=fecha.weekday())
        if inicio_semana_fecha != semana_actual:
            semana_actual = inicio_semana_fecha
            acumulado_ord = 0.0

        ord_dia = ord_dia or 0.0
        ext_dia = ext_dia or 0.0
        ord_permitida = max(0.0, min(ord_dia, JORNADA_SEMANAL_HORAS - acumulado_ord))
        excedente = ord_dia - ord_permitida
        acumulado_ord += ord_permitida

        if periodo_inicio <= fecha <= periodo_fin:
            h_ord_total += ord_permitida
            h_ext_total += ext_dia + excedente

    return round(h_ord_total, 2), round(h_ext_total, 2)


def liquidar(
    sess: Session,
    empleado: Empleado,
    empresa: Empresa,
    periodo_inicio: date,
    periodo_fin: date,
    bonificacion: float = 0.0,
    domicilios: float = 0.0,
    dominicales_override: int | None = None,
) -> ResumenLiquidacion:
    """Calcula todos los conceptos de la quincena (sin persistir).

    Los días sin marcación se tratan como descanso remunerado: el salario
    se calcula sobre todos los días del periodo, no sólo los con marcación.
    """
    r = ResumenLiquidacion(bonificacion=bonificacion, domicilios=domicilios)
    r.dias_periodo = (periodo_fin - periodo_inicio).days + 1

    # Días del periodo efectivamente cubiertos por el contrato del empleado,
    # según su fecha de ingreso y (si aplica) fecha de retiro. Se usa el
    # criterio comercial de mes de 30 días (el día 31 no cuenta aparte),
    # consistente con que cada quincena siempre equivale a 15/30 días.
    inicio_efectivo = max(periodo_inicio, empleado.fecha_ingreso)
    fin_efectivo = (
        min(periodo_fin, empleado.fecha_retiro)
        if empleado.fecha_retiro
        else periodo_fin
    )
    if fin_efectivo >= inicio_efectivo:
        dia_ini = inicio_efectivo.day
        dia_fin = 30 if fin_efectivo.day > 30 else fin_efectivo.day
        r.dias_laborados = max(0, dia_fin - dia_ini + 1)
    else:
        r.dias_laborados = 0

    marcs = (
        sess.query(Marcacion, HorasCalculadas)
        .join(HorasCalculadas, HorasCalculadas.marcacion_id == Marcacion.id)
        .filter(
            Marcacion.empleado_id == empleado.id,
            Marcacion.fecha >= periodo_inicio,
            Marcacion.fecha <= periodo_fin,
        )
        .all()
    )
    r.dias_trabajados = len({m.fecha for m, _ in marcs})
    r.h_ord, r.h_ext = _horas_semana_ajustadas(
        sess, empleado.id, periodo_inicio, periodo_fin,
    )
    r.h_noct = round(sum(h.h_nocturnas for _, h in marcs), 2)
    r.dominicales = (
        dominicales_override
        if dominicales_override is not None
        else _contar_dominicales(sess, empleado.id, periodo_inicio, periodo_fin)
    )

    # === PDF real ===
    # Salario y auxilio proporcionales a los días realmente cubiertos por el
    # contrato dentro del periodo (mes = 30 días), no siempre 15 días fijos.
    r.salario_proporcional = round(
        empleado.salario_base / 30.0 * r.dias_laborados, 2,
    )
    r.aux_transporte_real = round(
        empresa.auxilio_transporte / 30.0 * r.dias_laborados, 2,
    )
    r.valor_extras = round(r.h_ext * empresa.valor_hora_extra, 2)
    r.valor_nocturnas = round(r.h_noct * empresa.valor_recargo_nocturno_hora, 2)
    r.valor_dominicales = round(
        r.dominicales * empresa.valor_recargo_dominical_dia, 2,
    )
    r.devengado_real = round(
        r.salario_proporcional + r.aux_transporte_real + r.valor_extras
        + r.valor_nocturnas + r.valor_dominicales + r.bonificacion + r.domicilios, 2,
    )

    # Deducciones sobre SMMLV proporcional a los días laborados (no sobre devengado).
    base_deduccion = round(empresa.smmlv / 30.0 * r.dias_laborados, 2)
    r.salud_real = round(base_deduccion * 0.04, 2)
    r.pension_real = round(base_deduccion * 0.04, 2)

    facts = (
        sess.query(FacturaQuincena)
        .filter(
            FacturaQuincena.empleado_id == empleado.id,
            FacturaQuincena.liquidacion_id.is_(None),
            FacturaQuincena.fecha >= periodo_inicio,
            FacturaQuincena.fecha <= periodo_fin,
        )
        .all()
    )
    r.facturas = list(facts)
    r.facturas_total = round(sum(f.valor_deducir for f in facts), 2)

    ult_dia_mes = monthrange(periodo_inicio.year, periodo_inicio.month)[1]
    mes_inicio = date(periodo_inicio.year, periodo_inicio.month, 1)
    mes_fin = date(periodo_inicio.year, periodo_inicio.month, ult_dia_mes)
    cads = (
        sess.query(DeduccionCadena)
        .filter(
            DeduccionCadena.empleado_id == empleado.id,
            DeduccionCadena.liquidacion_id.is_(None),
            DeduccionCadena.fecha >= mes_inicio,
            DeduccionCadena.fecha <= mes_fin,
        )
        .all()
    )
    r.cadenas = list(cads)
    r.cadena_total = round(sum(c.valor for c in cads), 2)

    prest = (
        sess.query(PrestamoQuincena)
        .filter(
            PrestamoQuincena.empleado_id == empleado.id,
            PrestamoQuincena.liquidacion_id.is_(None),
            PrestamoQuincena.fecha >= periodo_inicio,
            PrestamoQuincena.fecha <= periodo_fin,
        )
        .all()
    )
    r.prestamos = list(prest)
    r.prestamos_total = round(sum(p.valor for p in prest), 2)

    perms = (
        sess.query(PermisoNoRemunerado)
        .filter(
            PermisoNoRemunerado.empleado_id == empleado.id,
            PermisoNoRemunerado.liquidacion_id.is_(None),
            PermisoNoRemunerado.fecha >= periodo_inicio,
            PermisoNoRemunerado.fecha <= periodo_fin,
        )
        .all()
    )
    r.permisos = list(perms)
    r.permisos_dias = len(perms)
    r.permisos_descuento = round(
        (empleado.salario_base / 30 + empresa.auxilio_transporte / 30) * r.permisos_dias, 2,
    )

    r.deducciones_real = round(
        r.salud_real + r.pension_real + r.facturas_total
        + r.cadena_total + r.prestamos_total + r.permisos_descuento, 2,
    )
    r.neto_real = round(r.devengado_real - r.deducciones_real, 2)

    # === PDF mínimo (como si ganara solo SMMLV) ===
    r.smmlv_proporcional = round(empresa.smmlv / 30.0 * r.dias_laborados, 2)
    r.aux_transporte_proporcional = round(
        empresa.auxilio_transporte / 30.0 * r.dias_laborados, 2,
    )
    r.devengado_min = round(
        r.smmlv_proporcional + r.aux_transporte_proporcional, 2,
    )
    r.salud_min = round(base_deduccion * 0.04, 2)
    r.pension_min = round(base_deduccion * 0.04, 2)
    r.deducciones_min = round(r.salud_min + r.pension_min, 2)
    r.neto_min = round(r.devengado_min - r.deducciones_min, 2)

    return r
