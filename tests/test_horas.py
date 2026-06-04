"""Tests del cálculo simplificado de horas."""
from __future__ import annotations

import sys
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.horas import calcular_horas  # noqa: E402


def _aprox(a: float, b: float, tol: float = 0.05) -> bool:
    return abs(a - b) <= tol


def test_turno_diurno_simple():
    """8am-12, 1pm-5pm = 8h. Jornada 7.33h → 7.33 ord + 0.67 ext, 0 noct."""
    r = calcular_horas(
        date(2026, 6, 1), time(8, 0), time(12, 0), time(13, 0), time(17, 0),
    )
    assert _aprox(r.h_ordinarias, 7.33), r
    assert _aprox(r.h_extras, 0.67), r
    assert r.h_nocturnas == 0


def test_turno_sin_descanso():
    """9am-1pm sin descanso = 4h. Todo ordinario."""
    r = calcular_horas(
        date(2026, 6, 1), time(9, 0), None, None, time(13, 0),
    )
    assert _aprox(r.h_ordinarias, 4.0), r
    assert r.h_extras == 0
    assert r.h_nocturnas == 0


def test_turno_largo_con_nocturna():
    """11am-1pm, 2pm-11pm = 2 + 9 = 11h. Jornada 7.33 → 7.33 ord + 3.67 ext.
    Nocturna desde 7pm: 4h (7pm-11pm).
    """
    r = calcular_horas(
        date(2026, 6, 2), time(11, 0), time(13, 0), time(14, 0), time(23, 0),
    )
    assert _aprox(r.h_ordinarias, 7.33), r
    assert _aprox(r.h_extras, 3.67), r
    assert _aprox(r.h_nocturnas, 4.0), r


def test_turno_nocturno_cruza_medianoche():
    """6pm-2am sin descanso = 8h. 7.33 ord + 0.67 ext.
    Nocturna: 7pm-2am = 7h.
    """
    r = calcular_horas(
        date(2026, 6, 1), time(18, 0), None, None, time(2, 0),
    )
    assert _aprox(r.h_ordinarias, 7.33), r
    assert _aprox(r.h_extras, 0.67), r
    assert _aprox(r.h_nocturnas, 7.0), r


def test_jornada_exacta():
    """7h 20min exactos → todo ordinario, sin extras."""
    r = calcular_horas(
        date(2026, 6, 1), time(8, 0), None, None, time(15, 20),
    )
    assert _aprox(r.h_ordinarias, 7.33), r
    assert r.h_extras == 0


def test_dia_completo_sin_almuerzo():
    """8am-9pm sin descanso = 13h. 7.33 ord + 5.67 ext.
    Nocturna: 7pm-9pm = 2h.
    """
    r = calcular_horas(
        date(2026, 6, 1), time(8, 0), None, None, time(21, 0),
    )
    assert _aprox(r.h_ordinarias, 7.33), r
    assert _aprox(r.h_extras, 5.67), r
    assert _aprox(r.h_nocturnas, 2.0), r


def test_turno_corto_nocturno():
    """7pm-10pm = 3h. Todo ordinario, 3h nocturnas."""
    r = calcular_horas(
        date(2026, 6, 1), time(19, 0), None, None, time(22, 0),
    )
    assert _aprox(r.h_ordinarias, 3.0), r
    assert r.h_extras == 0
    assert _aprox(r.h_nocturnas, 3.0), r


def test_madrugada():
    """3am-7am sin descanso = 4h. Nocturna 3am-6am = 3h."""
    r = calcular_horas(
        date(2026, 6, 1), time(3, 0), None, None, time(7, 0),
    )
    assert _aprox(r.h_ordinarias, 4.0), r
    assert _aprox(r.h_nocturnas, 3.0), r


if __name__ == "__main__":
    import traceback

    funcs = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    fallidos = 0
    for f in funcs:
        try:
            f()
            print(f"✓ {f.__name__}")
        except AssertionError as e:
            fallidos += 1
            print(f"✗ {f.__name__}: {e}")
        except Exception:
            fallidos += 1
            traceback.print_exc()
    print(f"\n{len(funcs) - fallidos}/{len(funcs)} OK")
    sys.exit(1 if fallidos else 0)
