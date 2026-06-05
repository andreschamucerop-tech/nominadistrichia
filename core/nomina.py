"""Cálculo de liquidación quincenal: real y 'como salario mínimo'."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
import holidays as holidays_lib
from sqlalchemy.orm import Session

from core.db import (
    DeduccionCadena, Empleado, Empresa, FacturaQuincena,
    HorasCalculadas, Marcacion, PrestamoQuincena,
)


@dataclass
class ResumenLiquidacion:
    # Datos base
    dias_periodo: int = 0       # días calendario del periodo (incl. descansos)
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

    # Detalle bruto
    facturas: list = field(default_factory=list)
    cadenas: list = field(default_factory=list)
    prestamos: list = field(default_factory=list)


def _festivos_col(year: int) -> set[date]:
    return set(holidays_lib.Colombia(years=year).keys())


def _contar_dominicales(
    sess: Session, empleado_id: int, ini: date, fin: date,
) -> int:
    """Cuenta dominicales asignados a la quincena.

    Se itera por cada semana (lun-dom) cuyo DOMINGO cae dentro del rango.
    "Días especiales" de la semana = domingo + festivos colombianos de ese período.

      - Sin días trabajados esa semana → no cuenta.
      - Trabajó todos los días especiales (sin descanso en festivo/dom) → 2 dom.
      - Descansó al menos 1 día especial → 1 dominical.
    """
    total = 0
    d = ini
    while d <= fin:
        if d.weekday() == 6:  # domingo
            lunes = d - timedelta(days=6)
            domingo = d

            # Festivos colombianos para los años que toca la semana
            años = {lunes.year, domingo.year}
            festivos: set[date] = set()
            for y in años:
                festivos |= _festivos_col(y)

            # Días especiales de la semana (domingo + festivos lun-sáb)
            dias_especiales: set[date] = set()
            cur = lunes
            while cur <= domingo:
                if cur.weekday() == 6 or cur in festivos:
                    dias_especiales.add(cur)
                cur += timedelta(days=1)

            # Días trabajados en esa semana
            rows = (
                sess.query(Marcacion.fecha)
                .filter(
                    Marcacion.empleado_id == empleado_id,
                    Marcacion.fecha >= lunes,
                    Marcacion.fecha <= domingo,
                )
                .all()
            )
            trabajados: set[date] = {r.fecha for r in rows}

            if not trabajados:
                d += timedelta(days=1)
                continue

            # ¿Descansó algún día especial?
            descanso_especial = dias_especiales - trabajados
            if descanso_especial:
                total += 1   # tuvo al menos 1 día de descanso especial
            else:
                total += 2   # trabajó sin descansar ningún festivo/dom

        d += timedelta(days=1)
    return total


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
    r.h_ord = round(sum(h.h_ordinarias for _, h in marcs), 2)
    r.h_ext = round(sum(h.h_extras for _, h in marcs), 2)
    r.h_noct = round(sum(h.h_nocturnas for _, h in marcs), 2)
    r.dominicales = (
        dominicales_override
        if dominicales_override is not None
        else _contar_dominicales(sess, empleado.id, periodo_inicio, periodo_fin)
    )

    # === PDF real ===
    # Salario y auxilio siempre sobre 15 días fijos (mes = 30 días, quincena = 15).
    r.salario_proporcional = round(empleado.salario_base / 2.0, 2)
    r.aux_transporte_real = round(empresa.auxilio_transporte / 2.0, 2)
    r.valor_extras = round(r.h_ext * empresa.valor_hora_extra, 2)
    r.valor_nocturnas = round(r.h_noct * empresa.valor_recargo_nocturno_hora, 2)
    r.valor_dominicales = round(
        r.dominicales * empresa.valor_recargo_dominical_dia, 2,
    )
    r.devengado_real = round(
        r.salario_proporcional + r.aux_transporte_real + r.valor_extras
        + r.valor_nocturnas + r.valor_dominicales + r.bonificacion + r.domicilios, 2,
    )

    # Deducciones sobre SMMLV × 15/30 por quincena (no sobre devengado).
    base_deduccion = round(empresa.smmlv / 2.0, 2)
    r.salud_real = round(base_deduccion * 0.04, 2)
    r.pension_real = round(base_deduccion * 0.04, 2)

    facts = (
        sess.query(FacturaQuincena)
        .filter(
            FacturaQuincena.empleado_id == empleado.id,
            FacturaQuincena.liquidacion_id.is_(None),
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
        )
        .all()
    )
    r.prestamos = list(prest)
    r.prestamos_total = round(sum(p.valor for p in prest), 2)

    r.deducciones_real = round(
        r.salud_real + r.pension_real + r.facturas_total
        + r.cadena_total + r.prestamos_total, 2,
    )
    r.neto_real = round(r.devengado_real - r.deducciones_real, 2)

    # === PDF mínimo (como si ganara solo SMMLV) ===
    r.smmlv_proporcional = round(empresa.smmlv / 2.0, 2)
    r.aux_transporte_proporcional = round(empresa.auxilio_transporte / 2.0, 2)
    r.devengado_min = round(
        r.smmlv_proporcional + r.aux_transporte_proporcional, 2,
    )
    r.salud_min = round(base_deduccion * 0.04, 2)
    r.pension_min = round(base_deduccion * 0.04, 2)
    r.deducciones_min = round(r.salud_min + r.pension_min, 2)
    r.neto_min = round(r.devengado_min - r.deducciones_min, 2)

    return r
