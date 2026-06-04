"""Cálculo simplificado de horas trabajadas.

Reglas (NO normatividad colombiana):
  - Jornada diaria = 7h 20min (7.333h). Lo que exceda es extra.
  - Recargo nocturno aplica desde las 19:00 hasta las 06:00 del día siguiente.
  - El recargo nocturno es ADICIONAL: una hora extra trabajada de 7pm a 8pm
    cuenta como 1h extra + 1h nocturna (paga ambos conceptos).
  - Las horas extras (cualquier tipo) se pagan al mismo valor de extra ordinaria.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

JORNADA_DIARIA_HORAS = 22 / 3  # 7h 20min = 7.3333…
NOCTURNO_INICIO = time(19, 0)
NOCTURNO_FIN = time(6, 0)


@dataclass
class ResultadoHoras:
    h_ordinarias: float = 0.0
    h_extras: float = 0.0
    h_nocturnas: float = 0.0  # adicional, independiente de ord/ext

    def total_trabajado(self) -> float:
        return self.h_ordinarias + self.h_extras


def _to_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def _intervalos_trabajados(
    fecha: date,
    hora_entrada: time,
    inicio_descanso: time | None,
    fin_descanso: time | None,
    hora_salida: time,
) -> list[tuple[datetime, datetime]]:
    """Construye los intervalos efectivos (descontando descanso).

    Maneja cruce de medianoche en la salida y en el fin del descanso.
    """
    entrada = _to_dt(fecha, hora_entrada)
    salida = _to_dt(fecha, hora_salida)
    if salida <= entrada:
        salida += timedelta(days=1)

    if inicio_descanso and fin_descanso:
        d1 = _to_dt(fecha, inicio_descanso)
        d2 = _to_dt(fecha, fin_descanso)
        if d1 < entrada:
            d1 += timedelta(days=1)
        if d2 < d1:
            d2 += timedelta(days=1)
        tramos = []
        if d1 > entrada:
            tramos.append((entrada, min(d1, salida)))
        if d2 < salida:
            tramos.append((max(d2, entrada), salida))
        return [t for t in tramos if t[1] > t[0]]
    return [(entrada, salida)]


def _minutos_nocturnos(ini: datetime, fin: datetime) -> float:
    """Suma de minutos del intervalo [ini, fin) que caen en franja
    nocturna (>=19:00 o <06:00)."""
    total = 0.0
    cur = ini
    while cur < fin:
        h = cur.time()
        nxt = cur + timedelta(minutes=1)
        if h >= NOCTURNO_INICIO or h < NOCTURNO_FIN:
            total += 1.0
        cur = nxt
    return total


def calcular_horas(
    fecha: date,
    hora_entrada: time,
    inicio_descanso: time | None,
    fin_descanso: time | None,
    hora_salida: time,
    jornada_diaria_horas: float = JORNADA_DIARIA_HORAS,
) -> ResultadoHoras:
    """Calcula horas ordinarias, extras y nocturnas para una marcación."""
    tramos = _intervalos_trabajados(
        fecha, hora_entrada, inicio_descanso, fin_descanso, hora_salida
    )

    total_min = 0.0
    noct_min = 0.0
    for ini, fin in tramos:
        total_min += (fin - ini).total_seconds() / 60.0
        noct_min += _minutos_nocturnos(ini, fin)

    limite_min = jornada_diaria_horas * 60.0
    ord_min = min(total_min, limite_min)
    ext_min = max(0.0, total_min - limite_min)

    return ResultadoHoras(
        h_ordinarias=round(ord_min / 60.0, 2),
        h_extras=round(ext_min / 60.0, 2),
        h_nocturnas=round(noct_min / 60.0, 2),
    )
