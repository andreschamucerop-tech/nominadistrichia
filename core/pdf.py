"""Generación de PDFs de desprendibles (real + mínimo)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from core.db import PDF_DIR, Empleado, Empresa
from core.nomina import ResumenLiquidacion

LOGO_PATH = Path(__file__).resolve().parent.parent / "data" / "logo.png"

# Relación de aspecto aproximada del logo DistriChia (ancho:alto ≈ 1.56:1)
_LOGO_ASPECT = 1.56


class _WatermarkCanvas(rl_canvas.Canvas):
    """Canvas que estampa el logo como marca de agua centrada en cada página."""

    def showPage(self):
        self._stamp_watermark()
        super().showPage()

    def _stamp_watermark(self):
        if not LOGO_PATH.exists():
            return
        self.saveState()
        self.setFillAlpha(0.07)      # 7% opacidad — sutil pero visible
        self.setStrokeAlpha(0.07)
        page_w, page_h = letter
        img_w = 13 * cm
        img_h = img_w / _LOGO_ASPECT
        x = (page_w - img_w) / 2
        y = (page_h - img_h) / 2
        self.drawImage(
            str(LOGO_PATH),
            x, y,
            width=img_w,
            height=img_h,
            mask="auto",
            preserveAspectRatio=True,
        )
        self.restoreState()


def _fmt(v: float) -> str:
    return f"${v:,.0f}"


def _estilos():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        name="H1", parent=s["Title"], fontSize=14, alignment=1, spaceAfter=4,
    ))
    s.add(ParagraphStyle(
        name="H2", parent=s["Heading2"], fontSize=11, spaceAfter=2,
    ))
    s.add(ParagraphStyle(
        name="Center", parent=s["Normal"], alignment=1,
    ))
    return s


def _encabezado(empresa: Empresa, empleado: Empleado,
                periodo_ini: date, periodo_fin: date,
                titulo: str, styles) -> list:
    el = []
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=4 * cm, height=4 * cm / _LOGO_ASPECT)
        logo.hAlign = "CENTER"
        el.append(logo)
        el.append(Spacer(1, 0.15 * cm))
    el.append(Paragraph(empresa.razon_social, styles["H1"]))
    el.append(Paragraph(f"NIT: {empresa.nit}", styles["Center"]))
    el.append(Spacer(1, 0.2 * cm))
    el.append(Paragraph(titulo, styles["H2"]))
    el.append(Paragraph(
        f"Periodo: {periodo_ini.strftime('%d/%m/%Y')} "
        f"al {periodo_fin.strftime('%d/%m/%Y')}",
        styles["Normal"],
    ))
    el.append(Spacer(1, 0.2 * cm))

    data = [
        ["Empleado:", empleado.nombres],
        ["Documento:", f"{empleado.tipo_documento or 'CC'} {empleado.cedula}"],
        ["Cargo:", empleado.cargo or "—"],
        ["Salario base:", _fmt(empleado.salario_base)],
    ]
    t = Table(data, colWidths=[3.5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    el.append(t)
    el.append(Spacer(1, 0.3 * cm))
    return el


def _tabla_concepto_valor(rows: list, _styles, total_destacado: bool = True) -> Table:
    cmds = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde7ff")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if total_destacado:
        cmds.extend([
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0f0f0")),
        ])
    t = Table(rows, colWidths=[10 * cm, 5 * cm])
    t.setStyle(TableStyle(cmds))
    return t


def _firmas(empresa: Empresa, empleado: Empleado) -> list:
    tipo_doc = empleado.tipo_documento or "CC"
    return [
        Spacer(1, 1.5 * cm),
        Table(
            [["_________________________", "_________________________"],
             ["Firma empleado", "Firma empleador"],
             [empleado.nombres, empresa.representante_legal],
             [f"{tipo_doc} {empleado.cedula}", "Representante legal"]],
            colWidths=[8 * cm, 8 * cm],
            style=TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]),
        ),
    ]


def _flowables_real(
    empresa: Empresa, empleado: Empleado, periodo_ini: date,
    periodo_fin: date, r: ResumenLiquidacion, styles,
) -> list:
    el = _encabezado(
        empresa, empleado, periodo_ini, periodo_fin,
        "Desprendible de nómina", styles,
    )

    deveng = [["Devengado", "Valor"]]
    deveng.append([f"Salario ({r.dias_periodo} días)", _fmt(r.salario_proporcional)])
    deveng.append([f"Auxilio de transporte ({r.dias_periodo} días)", _fmt(r.aux_transporte_real)])
    if r.h_ext > 0:
        deveng.append([
            f"Horas extras ({r.h_ext:.2f} h × {_fmt(empresa.valor_hora_extra)})",
            _fmt(r.valor_extras),
        ])
    if r.h_noct > 0:
        deveng.append([
            f"Recargo nocturno ({r.h_noct:.2f} h × "
            f"{_fmt(empresa.valor_recargo_nocturno_hora)})",
            _fmt(r.valor_nocturnas),
        ])
    if r.dominicales > 0:
        deveng.append([
            f"Dominicales ({r.dominicales} × "
            f"{_fmt(empresa.valor_recargo_dominical_dia)})",
            _fmt(r.valor_dominicales),
        ])
    if r.domicilios > 0:
        deveng.append(["Domicilios", _fmt(r.domicilios)])
    if r.bonificacion > 0:
        deveng.append(["Bonificación", _fmt(r.bonificacion)])
    deveng.append(["Total devengado", _fmt(r.devengado_real)])
    el.append(_tabla_concepto_valor(deveng, styles))
    el.append(Spacer(1, 0.3 * cm))

    dedu = [["Deducciones", "Valor"]]
    base_q = round(empresa.smmlv / 2, 0)
    dedu.append([f"Salud 4% (base quincena {_fmt(base_q)})", _fmt(r.salud_real)])
    dedu.append([f"Pensión 4% (base quincena {_fmt(base_q)})", _fmt(r.pension_real)])
    if r.facturas_total > 0:
        dedu.append([
            f"Facturas (fiado, {len(r.facturas)} ítems con 10% dcto)",
            _fmt(r.facturas_total),
        ])
    if r.cadena_total > 0:
        dedu.append([f"Cadena ({len(r.cadenas)} aporte/s)", _fmt(r.cadena_total)])
    if r.prestamos_total > 0:
        dedu.append([f"Préstamos ({len(r.prestamos)} cuota/s)", _fmt(r.prestamos_total)])
    dedu.append(["Total deducciones", _fmt(r.deducciones_real)])
    el.append(_tabla_concepto_valor(dedu, styles))
    el.append(Spacer(1, 0.3 * cm))

    neto = Table(
        [["NETO A PAGAR", _fmt(r.neto_real)]],
        colWidths=[10 * cm, 5 * cm],
        style=TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#c8e6c9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    el.append(neto)
    el.extend(_firmas(empresa, empleado))
    return el


def _flowables_minimo(
    empresa: Empresa, empleado: Empleado, periodo_ini: date,
    periodo_fin: date, r: ResumenLiquidacion, styles,
) -> list:
    el = _encabezado(
        empresa, empleado, periodo_ini, periodo_fin,
        "Desprendible de nómina", styles,
    )

    deveng = [["Devengado", "Valor"]]
    deveng.append([f"Salario mínimo ({r.dias_periodo} días)", _fmt(r.smmlv_proporcional)])
    deveng.append([f"Auxilio de transporte ({r.dias_periodo} días)", _fmt(r.aux_transporte_proporcional)])
    deveng.append(["Total devengado", _fmt(r.devengado_min)])
    el.append(_tabla_concepto_valor(deveng, styles))
    el.append(Spacer(1, 0.3 * cm))

    dedu = [["Deducciones de ley", "Valor"]]
    dedu.append(["Salud 4%", _fmt(r.salud_min)])
    dedu.append(["Pensión 4%", _fmt(r.pension_min)])
    dedu.append(["Total deducciones", _fmt(r.deducciones_min)])
    el.append(_tabla_concepto_valor(dedu, styles))
    el.append(Spacer(1, 0.3 * cm))

    neto = Table(
        [["NETO A PAGAR (base mínimo)", _fmt(r.neto_min)]],
        colWidths=[10 * cm, 5 * cm],
        style=TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#c8e6c9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    el.append(neto)
    el.extend(_firmas(empresa, empleado))
    return el


def _nombre(nombres: str, periodo_ini: date, periodo_fin: date) -> str:
    ini = periodo_ini.strftime("%d-%m-%Y")
    fin = periodo_fin.strftime("%d-%m-%Y")
    # Elimina caracteres no permitidos en nombres de archivo
    nombre_seguro = "".join(c for c in nombres if c not in r'\/:*?"<>|')
    return f"{nombre_seguro} - {ini} al {fin}.pdf"


def generar_pdf_combinado(
    empresa: Empresa, empleado: Empleado,
    periodo_ini: date, periodo_fin: date,
    resumen: ResumenLiquidacion,
) -> str:
    """PDF de 2 páginas: real + mínimo, con marca de agua del logo."""
    styles = _estilos()
    path = Path(PDF_DIR) / _nombre(empleado.nombres, periodo_ini, periodo_fin)
    doc = SimpleDocTemplate(
        str(path), pagesize=letter,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    flow = _flowables_real(empresa, empleado, periodo_ini, periodo_fin, resumen, styles)
    flow.append(PageBreak())
    flow.extend(_flowables_minimo(empresa, empleado, periodo_ini, periodo_fin, resumen, styles))
    doc.build(flow, canvasmaker=_WatermarkCanvas)
    return str(path)
