# Fair Play Shield 🛡️⚽

Sistema de detección de partidos potencialmente amañados por apuestas deportivas en fútbol europeo y UEFA Europa League.

## Instalación

```bash
cd fair_play_shield
pip install -r requirements.txt
```

## Ejecución completa (manual)

```bash
# 1. Descargar datos + procesar + generar features
python main.py --step all --seasons 3

# 2. Entrenar modelos y generar integrity scores
python models/integrity_scorer.py

# 3. Lanzar dashboard interactivo
python dashboard/app.py
# Abre http://localhost:8050
```

## Ejecución por pasos

```bash
python main.py --step scrape --seasons 5   # Solo descarga
python main.py --step process              # Solo procesamiento
```

## Ejecución con Airflow (automática)

Airflow orquesta el pipeline completo de forma automática cada lunes a las 6:00 AM,
sin necesidad de ejecutar `main.py` ni `integrity_scorer.py` manualmente.

```bash
# Arrancar todo (Airflow + MLflow + Dashboard)
bash scripts/start.sh
```

Esto levanta:

- **Airflow** en http://localhost:8080 (user: `airflow`, pass: `airflow`)
- **MLflow** en http://localhost:5001
- **Dashboard** en http://localhost:8050

El pipeline se ejecuta automáticamente cada lunes. Para dispararlo manualmente:

```bash
docker exec airflow-scheduler airflow dags trigger fps_pipeline
```

> **Nota:** Airflow no está desplegado en AWS EC2 por limitaciones de RAM del t3.micro (1GB).
> Para producción en AWS se recomienda una instancia t3.small o superior.

```bash
# Detener todos los servicios
bash scripts/stop_services.sh
```

## Estructura del proyecto

```
fair_play_shield/
├── main.py                          # Pipeline principal
├── config/settings.py               # Configuración global
├── database/schema.sql              # Esquema PostgreSQL
├── ingestion/scrapers/
│   ├── europa_league_scraper.py     # UEFA Europa League (ESPN API)
│   └── european_leagues_scraper.py  # 10 ligas europeas (football-data.co.uk)
├── processing/data_cleaning.py      # Limpieza + feature engineering
├── models/integrity_scorer.py       # IF + RF + LR → MIS
├── dashboard/app.py                 # Dashboard Dash/Plotly
├── airflow/dags/                    # DAGs de Airflow
├── scripts/                         # Scripts de utilidad
├── infra/terraform/                 # Infraestructura AWS
├── docker-compose.yml               # Desarrollo local
├── docker-compose.prod.yml          # Producción AWS
└── Dockerfile.prod                  # Imagen Docker para producción
```

## Fuentes de datos

- **ESPN API** (pública, sin API key): 471+ partidos UEFA Europa League con stats, estadio, ciudad, país, asistencia, posesión, tiros, tarjetas, córners, faltas, forma del equipo
- **football-data.co.uk**: 9,873+ partidos de 10 ligas europeas (3 temporadas) con cuotas de 6+ casas de apuestas (apertura y cierre)

## Modelos de detección

| Modelo              | Tipo           | AUC-ROC |
| ------------------- | -------------- | ------- |
| Isolation Forest    | No supervisado | —       |
| Random Forest       | Supervisado    | 0.999   |
| Logistic Regression | Supervisado    | 0.988   |

Los 3 modelos se combinan en un **Match Integrity Score (MIS)** ponderado: 0-100.

## Niveles de alerta

| Nivel         | Rango  | Significado   |
| ------------- | ------ | ------------- |
| 🟢 Normal     | 0-30   | Sin indicios  |
| 🟡 Monitor    | 31-60  | Vigilar       |
| 🟠 Suspicious | 61-80  | Sospechoso    |
| 🔴 High Alert | 81-100 | Alta sospecha |

## Indicadores de anomalía (features)

- Movimiento sospechoso de cuotas apertura→cierre (>15%)
- Resultado sorpresa vs probabilidad implícita de casas de apuestas
- Ruptura de racha de victorias (5+ victorias → derrota)
- Goles anómalos vs promedio histórico del equipo
- Cambio de resultado entre primer y segundo tiempo
- Exceso de tarjetas vs media del árbitro/partido
- Z-Score en volumen de goles, faltas, córners

## Dashboard

5 pestañas interactivas:

- **Análisis General**: distribución de scores, comparativa por liga, evolución temporal, scatter cuotas vs goles
- **Alertas**: listado de partidos sospechosos con notificaciones, buscador, filtros
- **Europa League**: resultados, goleadores, partidos por país, tabla filtrable
- **Datos completos**: tabla con todos los scores, filtrable por liga
- **Predicción**: formulario para ingresar datos de un partido y predecir su MIS en tiempo real
