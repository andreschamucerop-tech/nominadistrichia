# Nómina DISTRICHIA SAS

Sistema de nómina quincenal desarrollado con **Streamlit** + **SQLite** para la empresa DISTRICHIA SAS.

## Funcionalidades

| Módulo | Descripción |
|---|---|
| 👥 Empleados | CRUD completo con tipos de documento colombianos |
| 📥 Cargar Marcaciones | Importación desde Excel, cálculo automático de horas ordinarias, extras y nocturnas |
| 💸 Deducciones | Registro de facturas (fiado), cadena y préstamos por empleado |
| 🧾 Liquidar Quincena | Liquidación real + base salario mínimo, ajuste de dominicales, historial |
| 📄 PDF | Desprendible de 2 páginas (real + mínimo) con logo como marca de agua |
| ⚙️ Configuración | Datos empresa, SMMLV, recargos y cambio de contraseña |

## Stack

- **Python 3.9+**
- **Streamlit ≥ 1.32**
- **SQLAlchemy 2.0** con SQLite
- **ReportLab** para PDFs
- **Pandas / openpyxl** para importación de Excel
- **bcrypt** para autenticación

## Instalación

```bash
git clone <url-del-repo>
cd Nomina

# Crear entorno virtual (recomendado)
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

Al iniciar por primera vez se crea automáticamente:
- La base de datos en `data/nomina.db`
- El usuario **admin** con una contraseña aleatoria impresa en consola

> ⚠️ Cambia la contraseña desde **Configuración → Cambiar contraseña** tras el primer inicio.

## Estructura

```
Nomina/
├── app.py                    # Entrada principal + login + estilos
├── requirements.txt
├── .streamlit/
│   └── config.toml           # Tema visual (colores corporativos)
├── core/
│   ├── auth.py               # Autenticación bcrypt
│   ├── db.py                 # Modelos SQLAlchemy + migraciones
│   ├── horas.py              # Cálculo de horas (ord/ext/noct)
│   ├── nomina.py             # Liquidación quincenal
│   ├── pdf.py                # Generación de desprendibles PDF
│   ├── seed.py               # Inicialización de BD
│   └── ui.py                 # Helpers de UI (peso_input)
├── data/
│   └── pdfs/                 # PDFs generados (excluidos del repo)
├── pages/
│   ├── 1_Empleados.py
│   ├── 2_Cargar_Marcaciones.py
│   ├── 3_Deducciones.py
│   ├── 4_Liquidar_Quincena.py
│   └── 5_Configuracion.py
└── tests/
    └── test_horas.py
```

## Tests

```bash
python3 tests/test_horas.py
# o con pytest:
pytest tests/
```

## Notas de seguridad

- La base de datos (`data/nomina.db`) está excluida del repositorio — contiene datos personales y la contraseña hasheada.
- Los PDFs generados (`data/pdfs/`) también están excluidos.
- No subas `data/nomina.db` a repositorios públicos.
