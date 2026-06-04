"""Modelos SQLAlchemy y utilidades de base de datos.

Soporta dos backends:
  - PostgreSQL (Supabase): cuando [supabase] db_url está en .streamlit/secrets.toml.
  - SQLite local (fallback): data/nomina.db cuando no hay secrets configurados.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
    String, Time, create_engine, text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
DATA_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "nomina.db"


def _crear_engine():
    """Devuelve el engine correcto según los secrets disponibles.

    Prioridad:
    1. PostgreSQL (Supabase) si secrets.toml contiene [supabase] db_url válida.
    2. SQLite local como fallback (desarrollo / sin conexión).
    """
    db_url: str | None = None
    try:
        import streamlit as st
        raw = st.secrets.get("supabase", {}).get("db_url", "")
        # Ignorar si el placeholder no fue reemplazado
        if raw and "[TU-PASSWORD]" not in raw and raw.startswith("postgresql"):
            db_url = raw
    except Exception:
        pass

    if db_url:
        return create_engine(
            db_url,
            echo=False,
            future=True,
            pool_pre_ping=True,   # detecta conexiones caídas
            pool_size=5,
            max_overflow=10,
            connect_args={"sslmode": "require"},
        )

    # ── Fallback: SQLite local ────────────────────────────────────────────────
    return create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)


engine = _crear_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Admin(Base):
    __tablename__ = "admin"
    id = Column(Integer, primary_key=True)
    usuario = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)


class Empresa(Base):
    __tablename__ = "empresa"
    id = Column(Integer, primary_key=True)
    razon_social = Column(String(200), nullable=False, default="DISTRICHIA SAS")
    nit = Column(String(30), nullable=False, default="901.114.577-6")
    representante_legal = Column(String(150), nullable=False, default="ARMANDO ZAMORA TRIANA")
    smmlv = Column(Float, default=1750905.0)
    auxilio_transporte = Column(Float, default=249095.0)
    valor_hora_extra = Column(Float, default=9949.0)
    valor_recargo_nocturno_hora = Column(Float, default=2785.0)
    valor_recargo_dominical_dia = Column(Float, default=46690.0)


class Empleado(Base):
    __tablename__ = "empleado"
    id = Column(Integer, primary_key=True)
    tipo_documento = Column(String(10), default="CC")
    cedula = Column(String(20), unique=True, nullable=False)
    nombres = Column(String(150), nullable=False)
    cargo = Column(String(100), default="")
    salario_base = Column(Float, nullable=False)
    fecha_ingreso = Column(Date, nullable=False)
    fecha_retiro = Column(Date, nullable=True)
    activo = Column(Boolean, default=True)

    marcaciones = relationship(
        "Marcacion", back_populates="empleado", cascade="all, delete-orphan"
    )


class Marcacion(Base):
    __tablename__ = "marcacion"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleado.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    hora_entrada = Column(Time, nullable=False)
    inicio_descanso = Column(Time, nullable=True)
    fin_descanso = Column(Time, nullable=True)
    hora_salida = Column(Time, nullable=False)
    archivo_origen = Column(String(200), default="")
    fecha_carga = Column(DateTime, default=datetime.utcnow)

    empleado = relationship("Empleado", back_populates="marcaciones")
    horas = relationship(
        "HorasCalculadas",
        back_populates="marcacion",
        uselist=False,
        cascade="all, delete-orphan",
    )


class HorasCalculadas(Base):
    __tablename__ = "horas_calculadas"
    id = Column(Integer, primary_key=True)
    marcacion_id = Column(Integer, ForeignKey("marcacion.id"), nullable=False)
    h_ordinarias = Column(Float, default=0.0)
    h_extras = Column(Float, default=0.0)
    h_nocturnas = Column(Float, default=0.0)

    marcacion = relationship("Marcacion", back_populates="horas")


class FacturaQuincena(Base):
    __tablename__ = "factura_quincena"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleado.id"), nullable=False)
    liquidacion_id = Column(Integer, ForeignKey("liquidacion_quincena.id"), nullable=True)
    valor_factura = Column(Float, nullable=False)
    descuento_pct = Column(Float, default=10.0)
    valor_deducir = Column(Float, nullable=False)
    descripcion = Column(String(200), default="")
    fecha = Column(Date, default=date.today)


class DeduccionCadena(Base):
    __tablename__ = "deduccion_cadena"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleado.id"), nullable=False)
    liquidacion_id = Column(Integer, ForeignKey("liquidacion_quincena.id"), nullable=True)
    fecha = Column(Date, nullable=False, default=date.today)
    valor = Column(Float, nullable=False)


class PrestamoQuincena(Base):
    __tablename__ = "prestamo_quincena"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleado.id"), nullable=False)
    liquidacion_id = Column(Integer, ForeignKey("liquidacion_quincena.id"), nullable=True)
    fecha = Column(Date, nullable=False, default=date.today)
    valor = Column(Float, nullable=False)
    descripcion = Column(String(200), default="")


class LiquidacionQuincena(Base):
    __tablename__ = "liquidacion_quincena"
    id = Column(Integer, primary_key=True)
    empleado_id = Column(Integer, ForeignKey("empleado.id"), nullable=False)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fin = Column(Date, nullable=False)
    dias_trabajados = Column(Integer, default=0)
    h_ord = Column(Float, default=0.0)
    h_ext = Column(Float, default=0.0)
    h_noct = Column(Float, default=0.0)
    dominicales = Column(Integer, default=0)
    bonificacion = Column(Float, default=0.0)
    devengado_real = Column(Float, default=0.0)
    deducciones_real = Column(Float, default=0.0)
    neto_real = Column(Float, default=0.0)
    devengado_min = Column(Float, default=0.0)
    deducciones_min = Column(Float, default=0.0)
    neto_min = Column(Float, default=0.0)
    pdf_real_path = Column(String(300), default="")
    pdf_minimo_path = Column(String(300), default="")
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)
    _migrate()


def _migrate():
    """Migraciones incrementales.

    En PostgreSQL (Supabase) las tablas se crean siempre limpias mediante
    create_all(), por lo que no se requieren migraciones manuales.
    Solo se ejecuta la migración de SQLite cuando el backend es local.
    """
    if engine.dialect.name != "sqlite":
        return  # PostgreSQL: esquema gestionado por create_all()

    with engine.connect() as conn:
        cols_cadena = {r[1] for r in conn.execute(text("PRAGMA table_info(deduccion_cadena)"))}
        if "fecha" not in cols_cadena:
            conn.execute(text("ALTER TABLE deduccion_cadena ADD COLUMN fecha DATE"))
            # Convierte registros viejos "YYYY-MM" → "YYYY-MM-01"
            conn.execute(text(
                "UPDATE deduccion_cadena SET fecha = mes || '-01' "
                "WHERE mes IS NOT NULL AND fecha IS NULL"
            ))
            conn.commit()


def get_session():
    return SessionLocal()
