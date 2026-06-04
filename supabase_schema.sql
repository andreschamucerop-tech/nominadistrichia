-- ============================================================
-- SCHEMA - Nómina DISTRICHIA SAS
-- Ejecutar en: Supabase Dashboard → SQL Editor → New query
-- ============================================================

-- 1. Usuario administrador
CREATE TABLE IF NOT EXISTS admin (
    id               SERIAL PRIMARY KEY,
    usuario          VARCHAR(50)  UNIQUE NOT NULL,
    password_hash    VARCHAR(200) NOT NULL
);

-- 2. Datos de la empresa
CREATE TABLE IF NOT EXISTS empresa (
    id                          SERIAL PRIMARY KEY,
    razon_social                VARCHAR(200) NOT NULL DEFAULT 'DISTRICHIA SAS',
    nit                         VARCHAR(30)  NOT NULL DEFAULT '901.114.577-6',
    representante_legal         VARCHAR(150) NOT NULL DEFAULT 'ARMANDO ZAMORA TRIANA',
    smmlv                       FLOAT        DEFAULT 1750905.0,
    auxilio_transporte          FLOAT        DEFAULT 249095.0,
    valor_hora_extra            FLOAT        DEFAULT 9949.0,
    valor_recargo_nocturno_hora FLOAT        DEFAULT 2785.0,
    valor_recargo_dominical_dia FLOAT        DEFAULT 46690.0
);

-- 3. Empleados
CREATE TABLE IF NOT EXISTS empleado (
    id              SERIAL PRIMARY KEY,
    tipo_documento  VARCHAR(10)  DEFAULT 'CC',
    cedula          VARCHAR(20)  UNIQUE NOT NULL,
    nombres         VARCHAR(150) NOT NULL,
    cargo           VARCHAR(100) DEFAULT '',
    salario_base    FLOAT        NOT NULL,
    fecha_ingreso   DATE         NOT NULL,
    fecha_retiro    DATE,
    activo          BOOLEAN      DEFAULT TRUE
);

-- 4. Marcaciones (registros de entrada/salida)
CREATE TABLE IF NOT EXISTS marcacion (
    id               SERIAL PRIMARY KEY,
    empleado_id      INTEGER NOT NULL REFERENCES empleado(id) ON DELETE CASCADE,
    fecha            DATE    NOT NULL,
    hora_entrada     TIME    NOT NULL,
    inicio_descanso  TIME,
    fin_descanso     TIME,
    hora_salida      TIME    NOT NULL,
    archivo_origen   VARCHAR(200) DEFAULT '',
    fecha_carga      TIMESTAMP    DEFAULT NOW()
);

-- 5. Horas calculadas por marcación
CREATE TABLE IF NOT EXISTS horas_calculadas (
    id            SERIAL PRIMARY KEY,
    marcacion_id  INTEGER NOT NULL REFERENCES marcacion(id) ON DELETE CASCADE,
    h_ordinarias  FLOAT DEFAULT 0.0,
    h_extras      FLOAT DEFAULT 0.0,
    h_nocturnas   FLOAT DEFAULT 0.0
);

-- 6. Liquidaciones quincenales
CREATE TABLE IF NOT EXISTS liquidacion_quincena (
    id               SERIAL PRIMARY KEY,
    empleado_id      INTEGER NOT NULL REFERENCES empleado(id),
    periodo_inicio   DATE    NOT NULL,
    periodo_fin      DATE    NOT NULL,
    dias_trabajados  INTEGER DEFAULT 0,
    h_ord            FLOAT   DEFAULT 0.0,
    h_ext            FLOAT   DEFAULT 0.0,
    h_noct           FLOAT   DEFAULT 0.0,
    dominicales      INTEGER DEFAULT 0,
    bonificacion     FLOAT   DEFAULT 0.0,
    devengado_real   FLOAT   DEFAULT 0.0,
    deducciones_real FLOAT   DEFAULT 0.0,
    neto_real        FLOAT   DEFAULT 0.0,
    devengado_min    FLOAT   DEFAULT 0.0,
    deducciones_min  FLOAT   DEFAULT 0.0,
    neto_min         FLOAT   DEFAULT 0.0,
    pdf_real_path    VARCHAR(300) DEFAULT '',
    pdf_minimo_path  VARCHAR(300) DEFAULT '',
    fecha_creacion   TIMESTAMP    DEFAULT NOW()
);

-- 7. Facturas / fiado (deducción con 10% descuento al empleado)
CREATE TABLE IF NOT EXISTS factura_quincena (
    id              SERIAL PRIMARY KEY,
    empleado_id     INTEGER NOT NULL REFERENCES empleado(id),
    liquidacion_id  INTEGER REFERENCES liquidacion_quincena(id),
    valor_factura   FLOAT   NOT NULL,
    descuento_pct   FLOAT   DEFAULT 10.0,
    valor_deducir   FLOAT   NOT NULL,
    descripcion     VARCHAR(200) DEFAULT '',
    fecha           DATE         DEFAULT CURRENT_DATE
);

-- 8. Deducciones de cadena
CREATE TABLE IF NOT EXISTS deduccion_cadena (
    id              SERIAL PRIMARY KEY,
    empleado_id     INTEGER NOT NULL REFERENCES empleado(id),
    liquidacion_id  INTEGER REFERENCES liquidacion_quincena(id),
    fecha           DATE    DEFAULT CURRENT_DATE,
    valor           FLOAT   NOT NULL
);

-- 9. Préstamos
CREATE TABLE IF NOT EXISTS prestamo_quincena (
    id              SERIAL PRIMARY KEY,
    empleado_id     INTEGER NOT NULL REFERENCES empleado(id),
    liquidacion_id  INTEGER REFERENCES liquidacion_quincena(id),
    fecha           DATE    DEFAULT CURRENT_DATE,
    valor           FLOAT   NOT NULL,
    descripcion     VARCHAR(200) DEFAULT ''
);

-- ============================================================
-- ÍNDICES para mejorar rendimiento de consultas frecuentes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_marcacion_empleado_fecha
    ON marcacion(empleado_id, fecha);

CREATE INDEX IF NOT EXISTS idx_horas_marcacion
    ON horas_calculadas(marcacion_id);

CREATE INDEX IF NOT EXISTS idx_factura_empleado_liq
    ON factura_quincena(empleado_id, liquidacion_id);

CREATE INDEX IF NOT EXISTS idx_cadena_empleado_liq
    ON deduccion_cadena(empleado_id, liquidacion_id);

CREATE INDEX IF NOT EXISTS idx_prestamo_empleado_liq
    ON prestamo_quincena(empleado_id, liquidacion_id);

CREATE INDEX IF NOT EXISTS idx_liq_empleado_periodo
    ON liquidacion_quincena(empleado_id, periodo_inicio);
