# Fair Play Shield 🛡️⚽

Sistema de detección de partidos potencialmente amañados por apuestas deportivas en fútbol europeo y UEFA Europa League.

## Instalación

```bash
cd fair_play_shield
pip install -r requirements.txt
```

## Ejecución completa (3 pasos)

```bash
# 1. Descargar datos + procesar + generar features
python main.py --step all --seasons 3

# 2. Análisis exploratorio (genera gráficos en data/eda_output/)
python notebooks/01_eda.py

# 3. Entrenar modelos y generar integrity scores
python models/integrity_scorer.py

# 4. Lanzar dashboard interactivo (http://localhost:8050)
python dashboard/app.py
```

## Ejecución por pasos

```bash
python main.py --step scrape --seasons 5   # Solo descarga
python main.py --step process              # Solo procesamiento
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
├── models/
│   ├── integrity_scorer.py          # Isolation Forest + Random Forest + Logistic
│   └── trained/                     # Modelos serializados (.pkl)
├── notebooks/01_eda.py              # Análisis exploratorio + tests estadísticos
├── dashboard/app.py                 # Dashboard Dash/Plotly
├── data/
│   ├── raw/                         # Datos crudos descargados
│   ├── processed/                   # Datos procesados + integrity_scores.csv
│   └── eda_output/                  # Gráficos EDA
└── requirements.txt
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

4 pestañas interactivas:

- **Análisis General**: distribución de scores, comparativa por liga, evolución temporal, scatter cuotas vs goles
- **Alertas**: listado de partidos sospechosos con notificaciones, buscador, filtros
- **Europa League**: resultados, goleadores, partidos por país, tabla filtrable
- **Datos completos**: tabla con todos los scores, filtrable por liga
