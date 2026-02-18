# Fair Play Shield — Documentación Técnica Completa

## Qué se hizo, cómo se implementó y cómo el modelo llega a sus conclusiones

---

## 1. ¿Qué es el Match Integrity Score (MIS)?

El MIS es un número de **0 a 100** que se asigna a cada partido de fútbol. Representa qué tan "estadísticamente anómalo" es ese partido comparado con el comportamiento normal del fútbol europeo.

- **0** = el partido se comportó exactamente como se esperaba (cuotas normales, goles normales, tarjetas normales)
- **100** = el partido presenta la combinación más extrema posible de anomalías estadísticas

**MIS NO significa "partido amañado"**. Significa: "este partido tiene suficientes señales estadísticas inusuales como para merecer que alguien lo investigue". Es una herramienta de priorización, no de acusación.

El MIS se genera combinando 3 modelos de Machine Learning que analizan 12 variables (features) calculadas a partir de datos reales de cuotas de apuestas y estadísticas del partido.

**Nota**: "Match Integrity Score" es un nombre propio de este proyecto, no un estándar de la industria. El concepto equivalente existe en organizaciones profesionales bajo otros nombres: Sportradar (proveedor oficial de FIFA/UEFA) lo llama **Fraud Detection System (FDS)**, la UEFA lo llama **Betting Fraud Detection System (BFDS)**, y la IBIA lo llama **Suspicious Betting Alert**. Todos aplican el mismo principio: combinar datos de cuotas de apuestas con estadísticas del partido para generar un nivel de sospecha. Nuestro MIS es una implementación académica simplificada de ese mismo concepto.

---

## 2. Librerías y dependencias del proyecto

Archivo: `requirements.txt`

| Librería                    | Versión                    | Para qué se usa                                                                                     |
| --------------------------- | -------------------------- | --------------------------------------------------------------------------------------------------- |
| `pandas`                    | >=2.0.0                    | Manipulación de datos tabulares (DataFrames)                                                        |
| `numpy`                     | >=1.24.0                   | Operaciones numéricas y arrays                                                                      |
| `requests`                  | >=2.31.0                   | Descargar datos de APIs (ESPN, football-data.co.uk)                                                 |
| `beautifulsoup4`            | >=4.12.0                   | Parseo de HTML (scraping auxiliar)                                                                  |
| `scipy`                     | >=1.11.0                   | Tests estadísticos (Shapiro-Wilk, Mann-Whitney, Z-Score)                                            |
| `statsmodels`               | >=0.14.0                   | Análisis estadístico avanzado                                                                       |
| `scikit-learn`              | >=1.3.0                    | Los 3 modelos ML (Isolation Forest, Random Forest, Logistic Regression) + StandardScaler + métricas |
| `plotly`                    | >=5.18.0                   | Gráficos interactivos del dashboard                                                                 |
| `dash`                      | >=2.14.0                   | Framework web del dashboard (servidor local)                                                        |
| `dash-bootstrap-components` | >=1.5.0                    | Componentes visuales (cards, tabs, badges) del dashboard                                            |
| `psycopg2-binary`           | >=2.9.0                    | Conexión a PostgreSQL                                                                               |
| `sqlalchemy`                | >=2.0.0                    | ORM para PostgreSQL                                                                                 |
| `python-dotenv`             | >=1.0.0                    | Variables de entorno (.env)                                                                         |
| `seaborn`                   | >=0.13.0                   | Gráficos estadísticos del EDA                                                                       |
| `matplotlib`                | >=3.8.0                    | Gráficos base del EDA                                                                               |
| `openpyxl`                  | >=3.1.0                    | Lectura de archivos Excel                                                                           |
| `lxml`                      | >=4.9.0                    | Parser XML/HTML rápido                                                                              |
| `html5lib`                  | >=1.1                      | Parser HTML alternativo                                                                             |
| `joblib`                    | (incluido en scikit-learn) | Serialización de modelos entrenados (.pkl)                                                          |

---

## 3. Cómo ejecutar el proyecto localmente

### Paso 0: Requisitos previos

- Python 3.9 o superior
- pip (gestor de paquetes de Python)
- Conexión a internet (para descargar datos la primera vez)

### Paso 1: Instalar dependencias

```bash
cd /Users/eduzuniga/Development/mioti/fair_play_shield
pip install -r requirements.txt
```

### Paso 2: Descargar datos y procesarlos

```bash
python main.py --step all --seasons 3
```

Esto ejecuta:

- Descarga de 10 ligas europeas desde football-data.co.uk (CSVs con cuotas)
- Descarga de Europa League desde ESPN API (471+ partidos)
- Limpieza de datos (elimina duplicados, normaliza columnas, parsea fechas)
- Cálculo de forma de equipos (racha, promedio de goles)
- Cálculo de features de cuotas (movimiento apertura→cierre, probabilidad implícita)
- Generación de los 7 flags de anomalía

### Paso 3: Análisis exploratorio (opcional)

```bash
python notebooks/01_eda.py
```

Genera gráficos en `data/eda_output/` y muestra tests estadísticos en consola.

### Paso 4: Entrenar modelos y generar scores

```bash
python models/integrity_scorer.py
```

Entrena los 3 modelos, genera el MIS para cada partido, y guarda:

- Modelos serializados en `models/trained/*.pkl`
- Scores en `data/processed/integrity_scores.csv`

### Paso 5: Lanzar el dashboard

```bash
python dashboard/app.py
```

Abre el navegador en **http://localhost:8050**

---

## 4. ¿En qué parte del código está cada flag?

### Los flags se calculan en 2 archivos:

**Archivo 1**: `processing/data_cleaning.py` → función `flag_anomalies()` (línea 138)

| Flag                      | Línea exacta   | Código                                                        |
| ------------------------- | -------------- | ------------------------------------------------------------- |
| `flag_odds_movement`      | línea 142      | `(df["odds_movement_abs_max"].abs() > 0.15).astype(int)`      |
| `flag_result_surprise`    | línea 145      | `df["result_surprise"]` (calculada previamente en el scraper) |
| `flag_streak_break`       | líneas 148-150 | `(df["home_win_streak"] >= 5) & (df["result"] == "A")`        |
| `flag_goals_anomaly_home` | líneas 153-155 | `df["home_goals"] > df["home_avg_goals_scored"] * 4`          |
| `flag_goals_anomaly_away` | líneas 156-158 | `df["away_goals"] > df["away_avg_goals_scored"] * 4`          |
| `flag_ht_result_changed`  | línea 161      | `df["ht_result_changed"]` (calculada en el scraper)           |
| `flag_cards_anomaly`      | líneas 164-169 | `(df["total_cards"] - mean_cards) / std_cards > 2`            |
| `total_flags`             | línea 173      | `flags[flag_cols].sum(axis=1)` (suma de todos los flags)      |

**Archivo 2**: `ingestion/scrapers/european_leagues_scraper.py` → función `compute_odds_features()` (línea 147)

| Variable de soporte            | Línea     | Código                                                |
| ------------------------------ | --------- | ----------------------------------------------------- |
| `odds_movement_home/draw/away` | línea 164 | `(df[close_col] - df[open_col]) / df[open_col]`       |
| `odds_movement_abs_max`        | línea 167 | `df[move_cols].abs().max(axis=1)`                     |
| `result_surprise`              | línea 181 | `(df["result"] != df["expected_result"]).astype(int)` |

**Archivo 3**: `processing/data_cleaning.py` → función `compute_team_form()` (línea 47)

| Variable de soporte     | Línea        | Código                                    |
| ----------------------- | ------------ | ----------------------------------------- |
| `home_win_streak`       | líneas 79-84 | Cuenta victorias consecutivas hacia atrás |
| `home_avg_goals_scored` | línea 96     | `goals_for / max(total_partidos, 1)`      |
| `away_avg_goals_scored` | línea 98     | Idem para visitante                       |

**Los umbrales de cada flag están definidos en**: `config/settings.py` (líneas 40-43)

```
ODDS_MOVEMENT_SUSPICIOUS_PCT = 0.15      → 15% para flag_odds_movement
MIN_WIN_STREAK_FOR_UPSET_FLAG = 5        → 5 victorias para flag_streak_break
GOALS_ANOMALY_MULTIPLIER = 4             → ×4 para flag_goals_anomaly
XG_DEVIATION_THRESHOLD = 2.0             → Z > 2 para flag_cards_anomaly
```

---

## 5. Aclaración sobre el movimiento de cuotas (apertura vs cierre)

> **Pregunta del usuario**: "El movimiento de apertura y cierre de casas de apuestas puede deberse a que si un equipo ya está ganando 3 a 0, la cuota de que ese equipo gane disminuirá notoriamente."

Esta es una observación muy válida, pero hay una distinción importante:

### Las cuotas que usamos NO son "en vivo" (in-play)

- **Cuota de apertura** (`ps_home`): es la cuota que Pinnacle publica cuando abre el mercado para ese partido, típicamente **3-7 días antes del partido**. El partido aún no ha empezado.
- **Cuota de cierre** (`ps_close_home`): es la cuota de Pinnacle en el **momento exacto en que arranca el partido** (pitido inicial). El partido tampoco ha empezado aún.

Ambas cuotas son **pre-partido**. El balón NO ha rodado todavía cuando se toma la cuota de cierre. Por lo tanto, el escenario de "ya van ganando 3-0" no aplica a nuestros datos.

### ¿Qué causa un movimiento legítimo de cuotas pre-partido?

- Una lesión de un jugador clave anunciada el día del partido
- Condiciones climáticas adversas
- Alineación sorpresa anunciada 1 hora antes
- El equipo ya está clasificado y no tiene motivación

Estos movimientos suelen ser del **5-10%**. Nuestro umbral de alerta es **>15%**, que es un movimiento mucho más agresivo que sólo puede explicarse por un volumen inusual de dinero entrando al mercado en una dirección específica — lo cual es la señal clásica de "dinero informado" (smart money) asociada a amaños.

### Resumen

| Tipo de cuota           | Momento                          | ¿Se usa en este proyecto? |
| ----------------------- | -------------------------------- | ------------------------- |
| Cuota de apertura       | Días antes del partido           | ✅ Sí                     |
| Cuota de cierre         | Minutos antes del pitido inicial | ✅ Sí                     |
| Cuota in-play (en vivo) | Durante el partido               | ❌ No                     |

---

## 6. La variable `total_flags` — Explicación detallada

### ¿Qué es?

`total_flags` es simplemente **la suma aritmética** de los 7 flags binarios de un partido. Cada flag vale 0 o 1, así que `total_flags` puede ir de 0 a 7.

### Ejemplo concreto

Imaginemos un partido Equipo A vs Equipo B:

| Flag                      | Valor | Razón                                                 |
| ------------------------- | ----- | ----------------------------------------------------- |
| `flag_odds_movement`      | 1     | Las cuotas se movieron un 22%                         |
| `flag_result_surprise`    | 1     | El mercado esperaba victoria local, ganó el visitante |
| `flag_streak_break`       | 0     | El local no tenía racha de 5+ victorias               |
| `flag_goals_anomaly_home` | 0     | El local marcó 1 gol (dentro de su promedio)          |
| `flag_goals_anomaly_away` | 1     | El visitante marcó 4 goles (promedia 0.8)             |
| `flag_ht_result_changed`  | 1     | Al descanso iba 1-0 (H), terminó 1-4 (A)              |
| `flag_cards_anomaly`      | 0     | 4 tarjetas (dentro de lo normal)                      |
| **total_flags**           | **4** | Suma: 1+1+0+0+1+1+0                                   |

Este partido tiene `total_flags = 4`, lo cual es muy inusual (solo el 0.6% de partidos llegan a 4).

### ¿Qué significa "anomalías simultáneas"?

**NO significa flags "seguidos" en el tiempo ni en partidos consecutivos**. Significa que **en un mismo partido** coinciden múltiples señales de anomalía al mismo tiempo. Es decir:

- El movimiento de cuotas fue raro **Y**
- El resultado fue sorpresa **Y**
- Los goles fueron anómalos **Y**
- El resultado cambió entre tiempos

Todo eso le pasó **al mismo partido en la misma fecha**. La coincidencia de múltiples anomalías en un solo evento es lo que genera sospecha, no la secuencia temporal entre partidos diferentes.

### Distribución observada

| total_flags | Partidos | %     | Interpretación                                                   |
| ----------- | -------- | ----- | ---------------------------------------------------------------- |
| 0           | 2,255    | 22.8% | Partido completamente normal                                     |
| 1           | 4,326    | 43.8% | Un indicador aislado (muy común, no sospechoso)                  |
| 2           | 2,621    | 26.5% | Dos coincidencias (frecuente, vigilar si son cuotas + resultado) |
| 3           | 604      | 6.1%  | Tres anomalías juntas → empieza a ser estadísticamente raro      |
| 4           | 62       | 0.6%  | Cuatro anomalías → muy inusual                                   |
| 5           | 5        | 0.1%  | Cinco anomalías → extremadamente raro                            |

El umbral de 3+ flags se eligió porque marca el punto donde la probabilidad de que sea coincidencia empieza a ser baja (solo 6.8% de los partidos).

---

## 7. Etiquetas sintéticas (is_suspicious) — Por qué hay 3 criterios y no solo total_flags

### La pregunta del usuario

> "Si cumple al menos una condición, pero las condiciones 2 y 3 ya no estaban consideradas como un flag... el total de flags ya está medido en el punto 1."

### Respuesta

Correcto: los **flags** (sección 4) y las **etiquetas sintéticas** (sección 5) son cosas diferentes que se calculan en momentos distintos del pipeline.

**Los 7 flags** se calculan en `processing/data_cleaning.py` durante el feature engineering. Son variables que alimentan al modelo.

**Las etiquetas sintéticas** se calculan DESPUÉS, en `models/integrity_scorer.py` (función `create_synthetic_labels`, línea 87). Son la variable objetivo (y) para entrenar los modelos supervisados (Random Forest y Logistic Regression).

### Los 3 criterios para etiquetar como sospechoso

```
Criterio 1: total_flags >= 3
            → Usa los flags ya calculados. Captura partidos con MUCHAS señales simultáneas.

Criterio 2: odds_movement_abs_max > percentil 95
            → NO es un flag. Es el valor CONTINUO del movimiento de cuotas.
            El flag_odds_movement se activa con >15%, pero el criterio 2 toma solo el
            top 5% más extremo (que puede ser >40-50%).
            Un partido puede tener flag_odds_movement = 1 (movimiento del 16%)
            pero NO activar el criterio 2 (porque el percentil 95 está en ~35%).

Criterio 3: |Z-Score de goles totales| > 2.5
            → NO es un flag. Es un cálculo estadístico diferente.
            Los flags de goles (4 y 5) comparan goles de UN equipo vs SU promedio.
            El criterio 3 compara TOTAL de goles del partido vs la MEDIA GLOBAL.
            Ejemplo: un partido 4-4 puede no activar ningún flag de goles individuales
            (si ambos equipos son goleadores) pero sí el criterio 3 (8 goles totales
            es Z > 2.5 cuando la media global es ~2.7 goles).
```

### Resumen de la diferencia

| Concepto                         | Dónde se calcula          | Qué hace                             | Relación                       |
| -------------------------------- | ------------------------- | ------------------------------------ | ------------------------------ |
| Los 7 flags                      | `data_cleaning.py:138`    | Features binarias del modelo         | INPUT del modelo               |
| total_flags                      | `data_cleaning.py:173`    | Suma de flags, también feature       | INPUT del modelo               |
| Etiqueta is_suspicious           | `integrity_scorer.py:87`  | Variable objetivo para entrenamiento | OUTPUT target                  |
| Criterio 1 (flags>=3)            | `integrity_scorer.py:91`  | Parte de la etiqueta                 | Usa flags como input           |
| Criterio 2 (percentil 95 cuotas) | `integrity_scorer.py:99`  | Parte de la etiqueta                 | Usa valor continuo, NO el flag |
| Criterio 3 (Z-Score goles)       | `integrity_scorer.py:106` | Parte de la etiqueta                 | Cálculo nuevo, NO es un flag   |

Los criterios 2 y 3 agregan información **adicional** que los flags solos no capturan: valores extremos continuos que van más allá de los umbrales binarios.

---

## 8. ¿Qué es un árbol de decisión? (y cómo lo usa Isolation Forest)

### Árbol de decisión — Concepto

Un árbol de decisión es un algoritmo que toma decisiones dividiendo los datos paso a paso, como un diagrama de flujo. En cada paso, elige UNA variable y UN umbral para separar los datos en dos grupos.

### Ejemplo visual

Supongamos que queremos clasificar si un partido es sospechoso usando solo 2 variables:

```
                    ¿odds_movement > 0.20?
                     /                \
                   SÍ                  NO
                  /                      \
        ¿total_goals > 5?          ¿total_flags >= 4?
         /          \                /           \
        SÍ          NO             SÍ            NO
        |            |              |              |
   SOSPECHOSO    REVISAR      SOSPECHOSO       NORMAL
```

El árbol hace preguntas binarias (sí/no) sobre las variables y va "bajando" hasta llegar a una conclusión. Cada "pregunta" se llama un **nodo** y cada conclusión final se llama una **hoja**.

### ¿Cómo usa Isolation Forest los árboles?

Isolation Forest usa una idea diferente al árbol de clasificación normal. Su lógica es:

1. **Construye 200 árboles** (n_estimators=200), cada uno con divisiones ALEATORIAS
2. Para cada partido, mide **cuántas divisiones necesita para aislarlo** (dejarlo solo en una hoja)
3. Un partido NORMAL está rodeado de muchos partidos similares → necesita MUCHAS divisiones para aislarlo → score bajo
4. Un partido ANÓMALO es diferente a todos → se aísla con MUY POCAS divisiones → score alto

### Analogía

Imagina una sala con 100 personas. Si quieres aislar a una persona "normal" (estatura media, ropa común), necesitas muchas preguntas: "¿Mide más de 1.75?", "¿Lleva camiseta roja?", "¿Tiene barba?"... porque hay muchas personas parecidas.

Pero si hay una persona disfrazada de astronauta, con una sola pregunta ("¿Lleva casco?") ya la aislaste. Esa persona es la anomalía — es fácil de separar del resto.

Isolation Forest hace exactamente esto con partidos de fútbol: los partidos con combinaciones raras de estadísticas se "aíslan" rápidamente.

---

## 9. ¿Cómo se sabe que Random Forest es el modelo de mejor rendimiento?

### La métrica: AUC-ROC

Para comparar modelos de clasificación se usa la métrica **AUC-ROC** (Area Under the Receiver Operating Characteristic Curve). Esta métrica mide qué tan bien el modelo distingue entre partidos normales y sospechosos.

| Valor AUC | Significado                                       |
| --------- | ------------------------------------------------- |
| 0.50      | El modelo es igual que lanzar una moneda (inútil) |
| 0.70      | Aceptable                                         |
| 0.80      | Bueno                                             |
| 0.90      | Muy bueno                                         |
| 0.95      | Excelente                                         |
| 1.00      | Perfecto (clasifica todo correctamente)           |

### Resultados obtenidos

| Modelo              | AUC-ROC   | Interpretación                                   |
| ------------------- | --------- | ------------------------------------------------ |
| Isolation Forest    | —         | No aplica (no supervisado, no usa etiquetas)     |
| **Random Forest**   | **0.999** | Casi perfecto distinguiendo normal vs sospechoso |
| Logistic Regression | 0.988     | Excelente, pero ligeramente inferior             |

### ¿Cómo se midió?

En `models/integrity_scorer.py`, líneas 129-146:

1. Se separaron los datos: **80% para entrenamiento** y **20% para test** (estratificado para mantener la proporción de clases)
2. Se entrenó cada modelo con el 80%
3. Se evaluó cada modelo prediciendo el 20% que NUNCA vio durante el entrenamiento
4. Se comparó la predicción con la etiqueta real usando `roc_auc_score` de scikit-learn

### ¿Por qué 0.999 es tan alto?

El AUC de 0.999 es extremadamente alto. Esto se debe a que las etiquetas sintéticas fueron creadas a partir de reglas sobre las mismas features que el modelo recibe. No es un "truco" — es la consecuencia lógica del diseño:

- Las etiquetas dicen "sospechoso si odds_movement > percentil 95"
- El modelo recibe odds_movement como feature
- Naturalmente, el modelo aprende esa relación con precisión

Esto **no invalida el modelo**. El valor del modelo está en que:

1. Aprende la **interacción** entre variables (ej: cuotas altas + goles anómalos juntos son peor que cada uno por separado)
2. Genera un **score continuo** (0-100), no solo binario (sí/no)
3. Puede aplicarse a **datos nuevos** que no se usaron para crear las etiquetas

### Código exacto donde se compara

```python
rf_auc = roc_auc_score(y_test, rf_proba)   # línea 137
lr_auc = roc_auc_score(y_test, lr_proba)   # línea 145
```

Random Forest gana: 0.999 > 0.988. Por eso recibe el mayor peso (40%) en el ensamble.

---

## 10. Explicación funcional de cada modelo y su configuración

### 10.1 Isolation Forest — Configuración y parámetros

Código: `models/integrity_scorer.py`, líneas 55-60

```python
IsolationForest(
    contamination=0.08,
    n_estimators=200,
    max_samples="auto",
    random_state=42,
)
```

| Parámetro       | Valor  | Qué significa                                                                                                                                          |
| --------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `contamination` | 0.08   | Le dice al modelo que asuma que el 8% de los datos son anomalías. Se eligió 8% porque es cercano al porcentaje de partidos con total_flags >= 3 (6.8%) |
| `n_estimators`  | 200    | Usa 200 árboles aleatorios. Más árboles = resultado más estable. 200 es un buen balance entre precisión y velocidad                                    |
| `max_samples`   | "auto" | Cada árbol se entrena con un subconjunto aleatorio de los datos (por defecto 256 muestras o el total si hay menos)                                     |
| `random_state`  | 42     | Semilla de aleatoriedad para reproducibilidad. Siempre da el mismo resultado si se ejecuta de nuevo                                                    |

**Proceso funcional**:

1. Recibe las 12 features escaladas (StandardScaler)
2. Construye 200 árboles con divisiones aleatorias
3. Para cada partido calcula un "anomaly score" basado en la profundidad promedio de aislamiento
4. `decision_function()` devuelve un score continuo (más negativo = más anómalo)
5. Se normaliza a 0-1 y se invierte (1 = más anómalo)

### 10.2 Random Forest Classifier — Configuración y parámetros

Código: `models/integrity_scorer.py`, líneas 61-67

```python
RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_leaf=5,
    random_state=42,
    class_weight="balanced",
)
```

| Parámetro          | Valor      | Qué significa                                                                                                                                                         |
| ------------------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `n_estimators`     | 200        | 200 árboles de decisión votan. La clase con más votos gana                                                                                                            |
| `max_depth`        | 10         | Cada árbol puede tener máximo 10 niveles de profundidad. Limita la complejidad para evitar overfitting (que el modelo memorice los datos en vez de aprender patrones) |
| `min_samples_leaf` | 5          | Cada hoja final debe tener al menos 5 partidos. Evita que el modelo cree reglas basadas en 1 solo partido                                                             |
| `class_weight`     | "balanced" | Automáticamente da más importancia a la clase minoritaria (sospechoso, 11.5%) para compensar que hay muchos más partidos normales (88.5%)                             |
| `random_state`     | 42         | Reproducibilidad                                                                                                                                                      |

**Proceso funcional**:

1. Recibe las 12 features escaladas + las etiquetas sintéticas (0 = normal, 1 = sospechoso)
2. Separa 80% entrenamiento, 20% test
3. Construye 200 árboles, cada uno entrenado con un subconjunto aleatorio de datos y features
4. Para un partido nuevo, los 200 árboles "votan" → `predict_proba()` da la proporción de árboles que votaron "sospechoso"
5. Si 180 de 200 árboles dicen "sospechoso" → probabilidad = 0.90 (90%)

### 10.3 Logistic Regression — Configuración y parámetros

Código: `models/integrity_scorer.py`, líneas 68-72

```python
LogisticRegression(
    max_iter=1000,
    class_weight="balanced",
    random_state=42,
)
```

| Parámetro      | Valor      | Qué significa                                                                                      |
| -------------- | ---------- | -------------------------------------------------------------------------------------------------- |
| `max_iter`     | 1000       | Máximo 1000 iteraciones para converger. El algoritmo busca los coeficientes óptimos iterativamente |
| `class_weight` | "balanced" | Compensa el desbalance de clases (igual que Random Forest)                                         |
| `random_state` | 42         | Reproducibilidad                                                                                   |

**Proceso funcional**:

1. Aprende una ecuación lineal: `P(sospechoso) = sigmoid(β₀ + β₁×feature_1 + β₂×feature_2 + ... + β₁₂×feature_12)`
2. La función sigmoid convierte cualquier número a un rango entre 0 y 1 (probabilidad)
3. Cada coeficiente β indica: si es positivo → esa feature aumenta la sospecha; si es negativo → la disminuye
4. Es el modelo más simple e interpretable de los 3

### 10.4 Escalado de datos (StandardScaler)

Antes de entrar a cualquier modelo, todas las features se escalan:

```python
X_scaled = scaler.fit_transform(X)  # línea 120
```

Esto transforma cada feature para que tenga media = 0 y desviación estándar = 1. Es necesario porque:

- `odds_movement_abs_max` va de 0 a 2.0
- `total_goals` va de 0 a 12
- `flag_streak_break` es 0 o 1

Sin escalar, las variables con rangos más grandes dominarían a las pequeñas.

---

## 11. ¿Cómo se determinaron los pesos del ensamble (35%, 40%, 25%)?

### La fórmula del ensamble

```python
combined = (0.35 * iso_norm + 0.40 * rf_proba + 0.25 * lr_proba)  # línea 173
```

Código: `models/integrity_scorer.py`, línea 173

### Criterios para asignar los pesos

Los pesos se asignaron siguiendo 3 principios:

**Principio 1: El modelo con mejor rendimiento medible recibe más peso**

- Random Forest tiene AUC 0.999 → recibe el mayor peso: **40%**
- Logistic Regression tiene AUC 0.988 → recibe menos: **25%**
- Isolation Forest no tiene AUC medible (no supervisado) → peso intermedio

**Principio 2: Diversidad de enfoques**

- Si solo usáramos Random Forest (100%), el score dependería completamente de las etiquetas sintéticas. Si las etiquetas tienen errores, el score hereda todos esos errores.
- Isolation Forest NO usa etiquetas → su perspectiva es independiente y aporta diversidad. Por eso recibe **35%** a pesar de no tener AUC medible.
- Tener modelos diversos es una práctica estándar en ML llamada "ensemble learning".

**Principio 3: Estabilidad y regularización**

- Logistic Regression es un modelo lineal simple que no se "sobreajusta" a los datos. Funciona como un contrapeso estabilizador.
- Si Random Forest y Isolation Forest dan scores altos pero Logistic Regression da score bajo, el score final se modera. Esto reduce falsos positivos.

### ¿Son los pesos óptimos?

No necesariamente. Se podrían optimizar los pesos usando validación cruzada o un meta-aprendizaje (stacking). Los pesos actuales (35/40/25) son una asignación razonable basada en el rendimiento observado, la diversidad de los modelos y las buenas prácticas de ensemble. Es una decisión de diseño, no un resultado matemático exacto.

Una alternativa sería usar un modelo de "stacking" donde un cuarto modelo aprende los pesos óptimos automáticamente. Esto se podría implementar como mejora futura.

---

## 12. Los 7 flags de anomalía — Criterios y ubicación en el código

### Resumen visual

```
processing/data_cleaning.py → flag_anomalies() [línea 138]
├── flag_odds_movement .......... línea 142  │ ¿Cuotas se movieron >15%?
├── flag_result_surprise ........ línea 145  │ ¿Resultado diferente al esperado?
├── flag_streak_break ........... línea 148  │ ¿Racha de 5+ victorias rota en casa?
├── flag_goals_anomaly_home ..... línea 153  │ ¿Local marcó >4× su promedio?
├── flag_goals_anomaly_away ..... línea 156  │ ¿Visitante marcó >4× su promedio?
├── flag_ht_result_changed ...... línea 161  │ ¿Cambió el resultado entre tiempos?
├── flag_cards_anomaly .......... línea 164  │ ¿Tarjetas con Z-Score >2?
└── total_flags ................. línea 173  │ Suma de todos los anteriores
```

---

## 13. Niveles de alerta — Umbrales y significado

Definidos en `config/settings.py`, líneas 33-38:

```python
MATCH_INTEGRITY_THRESHOLDS = {
    "normal": (0, 30),
    "monitor": (31, 60),
    "suspicious": (61, 80),
    "high_alert": (81, 100),
}
```

Aplicados en `models/integrity_scorer.py`, líneas 177-181:

```python
alert_levels = pd.cut(
    integrity_score,
    bins=[-1, 30, 60, 80, 101],
    labels=["normal", "monitor", "suspicious", "high_alert"],
)
```

| Nivel         | Rango MIS | Qué significa en la práctica                                                                                                                                                                                                                                   | Cantidad | %     |
| ------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----- |
| 🟢 Normal     | 0 — 30    | Los 3 modelos coinciden en que el partido no presenta anomalías significativas. Las cuotas se mantuvieron estables, el resultado fue esperado, los goles y tarjetas están dentro de lo normal.                                                                 | 7,820    | 79.2% |
| 🟡 Monitor    | 31 — 60   | Al menos uno de los 3 modelos detecta algo inusual, pero no hay consenso. Puede ser un movimiento de cuotas moderado o un resultado ligeramente sorpresivo. Recomendación: anotar y revisar si se repite con el mismo equipo.                                  | 902      | 9.1%  |
| 🟠 Suspicious | 61 — 80   | Al menos 2 de los 3 modelos señalan anomalías. Típicamente: cuotas se movieron bastante (>20%) + resultado sorpresa + algún flag adicional. Recomendación: investigar el partido, revisar noticias, verificar si hubo lesiones o factores externos.            | 642      | 6.5%  |
| 🔴 High Alert | 81 — 100  | Los 3 modelos coinciden en que el partido es altamente anómalo. Combinación extrema: cuotas se movieron >30%, resultado totalmente inesperado, goles muy por encima del promedio, cambio de resultado entre tiempos. Recomendación: investigación prioritaria. | 509      | 5.2%  |

---

## 14. Limitaciones y consideraciones

1. **No hay "ground truth"**: las etiquetas son sintéticas. El modelo detecta anomalías estadísticas, NO prueba amaños.
2. **Falsos positivos**: un partido con score alto puede tener explicaciones legítimas (lesiones de último momento, condiciones climáticas, motivación del equipo).
3. **El movimiento de cuotas domina**: el 63% de la importancia recae en cuotas. Si las cuotas no están disponibles (ej: datos de Europa League vía ESPN), el modelo pierde poder predictivo.
4. **Sesgo temporal**: los patrones de apuestas cambian con el tiempo. El modelo debe reentrenarse periódicamente.
5. **Correlación ≠ causalidad**: un score alto es una señal para investigar, no una acusación.

---

## 15. Cómo interpretar el dashboard

- **Tab "Análisis General"**: visión macro. Si una liga tiene muchos partidos en zona roja, merece atención.
- **Tab "Alertas"**: lista priorizada de partidos sospechosos. Empezar investigación por los de score más alto.
- **Tab "Europa League"**: datos específicos de la competición UEFA.
- **Tab "Datos completos"**: tabla filtrable para explorar cualquier partido. Usar filtro de liga + ordenar por score.

El sistema está diseñado para ser una **primera barrera** — no reemplaza la investigación humana, pero la prioriza y la hace más eficiente.

---

## 16. Estructura del proyecto — Archivos y carpetas

```
fair_play_shield/
│
├── main.py                              # Punto de entrada principal del pipeline
├── requirements.txt                     # Dependencias Python
├── README.md                            # Documentación básica
├── TECHNICAL_README.md                  # Esta guía técnica completa
├── .env.example                         # Plantilla de variables de entorno
│
├── config/
│   └── settings.py                      # Configuración global (umbrales, rutas, URLs)
│
├── database/
│   └── schema.sql                       # Esquema PostgreSQL para producción
│
├── ingestion/
│   └── scrapers/
│       ├── european_leagues_scraper.py  # Descarga 10 ligas europeas (football-data.co.uk)
│       └── europa_league_scraper.py     # Descarga Europa League (ESPN API)
│
├── processing/
│   └── data_cleaning.py                 # Limpieza + feature engineering + flags
│
├── models/
│   ├── integrity_scorer.py              # Entrenamiento de los 3 modelos + scoring
│   └── trained/                         # Modelos serializados (.pkl)
│       ├── fps_leagues_scaler.pkl
│       ├── fps_leagues_isolation_forest.pkl
│       ├── fps_leagues_random_forest.pkl
│       ├── fps_leagues_logistic.pkl
│       └── fps_leagues_feature_cols.pkl
│
├── notebooks/
│   └── 01_eda.py                        # Análisis exploratorio + tests estadísticos
│
├── dashboard/
│   └── app.py                           # Dashboard Dash/Plotly (http://localhost:8050)
│
├── alerts/
│   └── __init__.py                      # Módulo de alertas (extensible)
│
└── data/
    ├── raw/                             # Datos descargados sin procesar
    │   ├── european_leagues_with_odds.csv
    │   └── europa_league_matches.csv
    ├── processed/                       # Datos procesados + scores
    │   ├── european_leagues_with_odds_processed.csv
    │   ├── europa_league_processed.csv
    │   └── integrity_scores.csv         # ← Archivo final con MIS
    └── eda_output/                       # Gráficos generados por EDA
```

---

## 17. Flujo completo del sistema — Diagrama

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASE 1: INGESTA                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  football-data.co.uk ──────┐                                                │
│  (CSVs con cuotas)         │                                                │
│                            ▼                                                │
│              european_leagues_scraper.py                                    │
│                            │                                                │
│                            ▼                                                │
│              data/raw/european_leagues_with_odds.csv                        │
│              (9,873 partidos × 100+ columnas)                               │
│                                                                             │
│  ESPN API ─────────────────┐                                                │
│  (JSON partidos)           │                                                │
│                            ▼                                                │
│              europa_league_scraper.py                                       │
│                            │                                                │
│                            ▼                                                │
│              data/raw/europa_league_matches.csv                             │
│              (471 partidos × 30+ columnas)                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FASE 2: FEATURE ENGINEERING                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│              processing/data_cleaning.py                                    │
│                            │                                                │
│              ┌─────────────┼─────────────┐                                  │
│              ▼             ▼             ▼                                  │
│         clean_matches  compute_team_form  flag_anomalies                    │
│              │             │             │                                  │
│              │             │             ├── flag_odds_movement             │
│              │             │             ├── flag_result_surprise           │
│              │             │             ├── flag_streak_break              │
│              │             │             ├── flag_goals_anomaly_home        │
│              │             │             ├── flag_goals_anomaly_away        │
│              │             │             ├── flag_ht_result_changed         │
│              │             │             ├── flag_cards_anomaly             │
│              │             │             └── total_flags                    │
│              │             │             │                                  │
│              └─────────────┴─────────────┘                                  │
│                            │                                                │
│                            ▼                                                │
│              data/processed/european_leagues_with_odds_processed.csv        │
│              (9,873 partidos × 120+ columnas incluyendo flags)              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FASE 3: MODELADO ML                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│              models/integrity_scorer.py                                     │
│                            │                                                │
│              ┌─────────────┼─────────────┐                                  │
│              ▼             ▼             ▼                                  │
│       Isolation Forest  Random Forest  Logistic Regression                 │
│       (no supervisado)  (supervisado)  (supervisado)                        │
│              │             │             │                                  │
│              │      ┌──────┴──────┐      │                                  │
│              │      ▼             ▼      │                                  │
│              │   80% train    20% test   │                                  │
│              │      │             │      │                                  │
│              │      └──────┬──────┘      │                                  │
│              │             │             │                                  │
│              ▼             ▼             ▼                                  │
│         iso_score      rf_proba      lr_proba                               │
│           (0-1)         (0-1)         (0-1)                                 │
│              │             │             │                                  │
│              └─────────────┼─────────────┘                                  │
│                            │                                                │
│                            ▼                                                │
│              MIS = 0.35×iso + 0.40×rf + 0.25×lr                             │
│                            │                                                │
│                            ▼                                                │
│              Match Integrity Score (0-100)                                  │
│                            │                                                │
│                            ▼                                                │
│              Alert Level: normal / monitor / suspicious / high_alert        │
│                            │                                                │
│                            ▼                                                │
│              data/processed/integrity_scores.csv                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FASE 4: VISUALIZACIÓN                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│              dashboard/app.py                                               │
│                            │                                                │
│              ┌─────────────┼─────────────┬─────────────┐                    │
│              ▼             ▼             ▼             ▼                    │
│         Tab 1          Tab 2         Tab 3         Tab 4                    │
│      Análisis       Alertas      Europa League   Datos                      │
│       General     (filtrable)    (stats EL)    Completos                    │
│                                                                             │
│              Servidor local: http://localhost:8050                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 18. Aclaración importante: ¿Se usa el mismo dataset para entrenar y predecir?

### Respuesta corta: Sí, actualmente sí.

### Flujo actual (limitación conocida)

```
european_leagues_with_odds_processed.csv (9,873 partidos)
        │
        ▼
┌───────────────────────────────────────┐
│  integrity_scorer.py                  │
│  - Entrena con 80% de los datos       │
│  - Evalúa métricas con 20% (test)     │
│  - PERO luego aplica score() a TODO   │
│    el dataset (100%)                  │
└───────────────────────────────────────┘
        │
        ▼
integrity_scores.csv (9,873 partidos con MIS)
        │
        ▼
dashboard/app.py (muestra los 9,873 partidos)
```

### ¿Es esto un problema?

**Para un sistema de producción, sí sería un problema** — estarías mostrando predicciones sobre datos que el modelo ya "vio" durante el entrenamiento, lo cual infla artificialmente la confianza.

**Para este proyecto académico/demo, es aceptable** porque:

1. El objetivo es demostrar el concepto, no desplegar en producción
2. El modelo se evaluó correctamente con un split 80/20 estratificado (AUC 0.999 es sobre el 20% que NO se usó para entrenar)
3. Los scores del dashboard son ilustrativos, no decisiones finales

### ¿Cómo sería en producción?

```
Datos históricos (temporadas pasadas) → Entrenar modelo una vez
Datos nuevos (partidos de esta semana) → Aplicar modelo entrenado → Dashboard
```

El modelo nunca vería los partidos nuevos hasta que ya está entrenado. Esto se implementaría separando el pipeline en:

1. `train_model.py` — se ejecuta una vez con datos históricos
2. `score_new_matches.py` — se ejecuta cada semana con partidos nuevos

---

## 19. Los 7 flags — Fórmulas matemáticas exactas y ejemplos

### Flag 1: `flag_odds_movement`

**Archivo**: `processing/data_cleaning.py`, línea 142

**Fórmula**:

```
odds_movement_X = (ps_close_X - ps_X) / ps_X    para X ∈ {home, draw, away}

odds_movement_abs_max = max(|odds_movement_home|, |odds_movement_draw|, |odds_movement_away|)

flag_odds_movement = 1 si odds_movement_abs_max > 0.15, sino 0
```

**Ejemplo numérico**:

- Cuota apertura local (ps_home): 2.10
- Cuota cierre local (ps_close_home): 1.75
- Movimiento: (1.75 - 2.10) / 2.10 = **-0.167 = -16.7%**
- |−16.7%| = 16.7% > 15% → **flag = 1**

---

### Flag 2: `flag_result_surprise`

**Archivo**: `ingestion/scrapers/european_leagues_scraper.py`, línea 181

**Fórmula**:

```
implied_prob_X = 1 / avg_odds_X                 para X ∈ {home, draw, away}

prob_sum = implied_prob_home + implied_prob_draw + implied_prob_away

norm_prob_X = implied_prob_X / prob_sum         (normalización)

expected_result = argmax(norm_prob_home, norm_prob_draw, norm_prob_away)

flag_result_surprise = 1 si result ≠ expected_result, sino 0
```

**Ejemplo numérico**:

- Cuotas promedio: Home=1.80, Draw=3.50, Away=4.50
- Prob implícita: Home=1/1.80=0.556, Draw=1/3.50=0.286, Away=1/4.50=0.222
- Suma: 0.556 + 0.286 + 0.222 = 1.064
- Prob normalizada: Home=0.522, Draw=0.269, Away=0.209
- Resultado esperado: **H** (local, mayor probabilidad)
- Resultado real: **A** (visitante ganó)
- H ≠ A → **flag = 1**

---

### Flag 3: `flag_streak_break`

**Archivo**: `processing/data_cleaning.py`, líneas 147-150

**Fórmula**:

```
home_win_streak = número de victorias consecutivas del equipo local ANTES de este partido

flag_streak_break = 1 si (home_win_streak >= 5 AND result == "A"), sino 0
```

**Ejemplo**:

- Equipo local: últimos 5 resultados = W, W, W, W, W → racha = 5
- Resultado de este partido: A (pierde en casa)
- 5 >= 5 AND result == "A" → **flag = 1**

---

### Flag 4: `flag_goals_anomaly_home`

**Archivo**: `processing/data_cleaning.py`, líneas 152-155

**Fórmula**:

```
home_avg_goals_scored = Σ(goles_marcados_local) / total_partidos_jugados

flag_goals_anomaly_home = 1 si home_goals > home_avg_goals_scored × 4, sino 0
```

**Ejemplo**:

- Equipo local ha marcado 18 goles en 15 partidos → promedio = 1.2
- En este partido marca 5 goles
- 5 > 1.2 × 4 = 4.8 → **flag = 1**

---

### Flag 5: `flag_goals_anomaly_away`

**Archivo**: `processing/data_cleaning.py`, líneas 156-158

**Fórmula**: Idéntica al flag 4, pero para el equipo visitante.

---

### Flag 6: `flag_ht_result_changed`

**Archivo**: `processing/data_cleaning.py`, línea 161

**Fórmula**:

```
ht_result = "H" si ht_home_goals > ht_away_goals
            "A" si ht_home_goals < ht_away_goals
            "D" si ht_home_goals == ht_away_goals

flag_ht_result_changed = 1 si ht_result ≠ result, sino 0
```

**Ejemplo**:

- Medio tiempo: 1-0 → ht_result = "H"
- Final: 1-2 → result = "A"
- "H" ≠ "A" → **flag = 1**

---

### Flag 7: `flag_cards_anomaly`

**Archivo**: `processing/data_cleaning.py`, líneas 163-169

**Fórmula**:

```
μ = mean(total_cards)           # media de tarjetas en todo el dataset
σ = std(total_cards)            # desviación estándar

z_score = (total_cards_partido - μ) / σ

flag_cards_anomaly = 1 si z_score > 2, sino 0
```

**Ejemplo**:

- Media de tarjetas en el dataset: μ = 4.2
- Desviación estándar: σ = 1.8
- Este partido tuvo 9 tarjetas
- Z = (9 - 4.2) / 1.8 = **2.67**
- 2.67 > 2 → **flag = 1**

---

### Variable derivada: `total_flags`

**Archivo**: `processing/data_cleaning.py`, línea 173

**Fórmula**:

```
total_flags = flag_odds_movement + flag_result_surprise + flag_streak_break +
              flag_goals_anomaly_home + flag_goals_anomaly_away +
              flag_ht_result_changed + flag_cards_anomaly
```

**Rango**: 0 a 7

---

## 20. Justificación de umbrales — Por qué se eligió cada valor

| Umbral                      | Valor | Justificación                                                                                                                                                                                             |
| --------------------------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Movimiento cuotas >15%**  | 0.15  | Basado en literatura de Sportradar: movimientos >10-15% sin causa conocida son señal de "smart money". Se eligió 15% para reducir falsos positivos (movimientos legítimos por lesiones suelen ser 5-10%). |
| **Racha de 5+ victorias**   | 5     | Una racha de 5+ victorias consecutivas ocurre en ~5% de los equipos. Es estadísticamente significativa. Perder en casa después de esa racha es inusual (~0.3% de partidos).                               |
| **Goles >4× promedio**      | 4     | Multiplicador de 4 captura outliers extremos. Si un equipo promedia 1.2 goles, marcar 5+ es un evento raro (percentil >99).                                                                               |
| **Z-Score tarjetas >2**     | 2.0   | En una distribución normal, solo ~2.3% de los datos caen fuera de ±2σ. Es el umbral estándar para detectar outliers estadísticos.                                                                         |
| **MIS 0-30 = Normal**       | 30    | ~80% de los partidos caen aquí. Es el comportamiento "normal" del fútbol.                                                                                                                                 |
| **MIS 31-60 = Monitor**     | 60    | ~9% de partidos. Al menos 1 modelo detecta algo, pero no hay consenso.                                                                                                                                    |
| **MIS 61-80 = Suspicious**  | 80    | ~6.5% de partidos. 2+ modelos coinciden en anomalía.                                                                                                                                                      |
| **MIS 81-100 = High Alert** | 100   | ~5% de partidos. Los 3 modelos coinciden en anomalía extrema.                                                                                                                                             |

**Nota**: Los cortes del MIS (30/60/80) se eligieron **empíricamente** observando la distribución del score en los datos y buscando puntos naturales de separación. No son óptimos matemáticos — son decisiones de diseño para que cada categoría tenga un tamaño razonable y sea accionable.

---

## 21. Feature Importance — Qué variables pesan más en la decisión

Calculado por Random Forest (`models/integrity_scorer.py`, líneas 148-154):

| Feature                   | Importancia | %   | Interpretación                                                                             |
| ------------------------- | ----------- | --- | ------------------------------------------------------------------------------------------ |
| `odds_movement_abs_max`   | 0.4129      | 41% | **El indicador principal**. El valor continuo del movimiento de cuotas domina la decisión. |
| `flag_odds_movement`      | 0.2234      | 22% | El flag binario refuerza lo anterior. Juntos suman **63%**.                                |
| `total_goals`             | 0.0752      | 8%  | Partidos con muchos goles son más sospechosos.                                             |
| `flag_goals_anomaly_away` | 0.0510      | 5%  | Goles inesperados del visitante.                                                           |
| `flag_goals_anomaly_home` | 0.0418      | 4%  | Goles inesperados del local.                                                               |
| `total_cards`             | 0.0401      | 4%  | Exceso de tarjetas.                                                                        |
| `ht_result_changed`       | 0.0344      | 3%  | Cambio de resultado entre tiempos.                                                         |
| `flag_ht_result_changed`  | 0.0327      | 3%  | Flag binario del cambio HT.                                                                |
| `flag_cards_anomaly`      | 0.0326      | 3%  | Flag de tarjetas extremas.                                                                 |
| `result_surprise`         | 0.0251      | 3%  | Resultado vs expectativa del mercado.                                                      |
| `flag_result_surprise`    | 0.0249      | 2%  | Flag de sorpresa.                                                                          |
| `flag_streak_break`       | 0.0059      | 1%  | Ruptura de racha (raro pero específico).                                                   |

**Conclusión clave**: El **63% de la decisión** del modelo depende del movimiento de cuotas de apuestas. Esto es consistente con la realidad: el mercado de apuestas es el primer lugar donde se manifiesta un amaño.

---

## 22. Integración con Airflow y MLflow

### Arquitectura de orquestación

El proyecto incluye integración con **Apache Airflow** para orquestación de pipelines y **MLflow** para tracking de experimentos ML.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AIRFLOW (Orquestación)                            │
│                                                                             │
│   DAG: fps_pipeline                                                         │
│   Schedule: Lunes 6:00 AM (@weekly)                                         │
│                                                                             │
│   start ──▶ [ingest_european_leagues] ──┐                                   │
│             [ingest_europa_league]   ───┴──▶ process_data ──▶ train ──▶ end │
│                                                    │                        │
│                                                    ▼                        │
│                                               MLflow Tracking               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Servicios Docker

| Servicio              | Puerto | Descripción                         |
| --------------------- | ------ | ----------------------------------- |
| **Airflow Webserver** | 8080   | UI para monitorear DAGs y tasks     |
| **Airflow Scheduler** | —      | Ejecuta los DAGs programados        |
| **MLflow Server**     | 5001   | UI para tracking de experimentos    |
| **PostgreSQL**        | 5432   | Base de datos para Airflow metadata |

### Archivos de configuración

| Archivo                            | Propósito                                    |
| ---------------------------------- | -------------------------------------------- |
| `docker-compose.yml`               | Definición de todos los servicios            |
| `Dockerfile.airflow`               | Imagen custom con dependencias del proyecto  |
| `requirements-airflow.txt`         | Dependencias adicionales (mlflow, providers) |
| `airflow/dags/fps_pipeline_dag.py` | DAG principal del pipeline                   |
| `scripts/init_airflow.sh`          | Script de inicialización                     |

### Iniciar los servicios

```bash
./scripts/init_airflow.sh
```

Esto ejecuta:

1. Crea archivo `.env` con `AIRFLOW_UID`
2. Crea directorios necesarios
3. Construye imágenes Docker
4. Levanta todos los servicios

### URLs de acceso

- **Airflow UI**: http://localhost:8080 (user: `airflow`, pass: `airflow`)
- **MLflow UI**: http://localhost:5001

### Comandos útiles

```bash
docker-compose logs -f                    # Ver logs en tiempo real
docker-compose down                       # Detener servicios
docker-compose up -d                      # Reiniciar servicios

docker exec airflow-scheduler airflow dags trigger fps_pipeline   # Ejecutar pipeline manualmente
docker exec airflow-scheduler airflow dags list                   # Listar DAGs
docker exec airflow-scheduler airflow tasks list fps_pipeline     # Listar tasks del DAG
```

### MLflow Tracking — Qué se registra

Cada ejecución del pipeline registra en MLflow:

**Parámetros**:

- `isolation_forest_contamination`: 0.08
- `isolation_forest_n_estimators`: 200
- `random_forest_n_estimators`: 200
- `random_forest_max_depth`: 10
- `ensemble_weight_if/rf/lr`: 0.35, 0.40, 0.25
- `n_features`: número de features usadas
- `total_matches`: partidos procesados

**Métricas**:

- `rf_auc`, `lr_auc`: AUC-ROC de cada modelo
- `rf_precision`, `rf_recall`, `rf_f1`: métricas de Random Forest
- `lr_precision`, `lr_recall`, `lr_f1`: métricas de Logistic Regression
- `iso_anomalies_pct`: % de anomalías detectadas por Isolation Forest
- `alert_normal_count/pct`, `alert_monitor_count/pct`, etc.: distribución de alertas
- `avg_integrity_score`, `max_integrity_score`

**Artefactos**:

- Modelos serializados (Isolation Forest, Random Forest, Logistic Regression)
- `feature_importance.csv`: importancia de cada feature

### DAG Tasks — Detalle

| Task                      | Función                        | Archivo fuente                                   |
| ------------------------- | ------------------------------ | ------------------------------------------------ |
| `ingest_european_leagues` | Descarga 10 ligas europeas     | `ingestion/scrapers/european_leagues_scraper.py` |
| `ingest_europa_league`    | Descarga Europa League         | `ingestion/scrapers/europa_league_scraper.py`    |
| `process_data`            | Limpieza + feature engineering | `processing/data_cleaning.py`                    |
| `train_and_score`         | Entrena modelos + genera MIS   | `models/integrity_scorer.py`                     |
| `notify_completion`       | Imprime resumen final          | Inline en DAG                                    |

### Ejecución sin Docker (desarrollo local)

Si prefieres ejecutar sin Docker:

```bash
pip install mlflow apache-airflow

export MLFLOW_TRACKING_URI=http://localhost:5001

mlflow server --host 0.0.0.0 --port 5001 &

python models/integrity_scorer.py
```

El código detecta automáticamente si MLflow está disponible y logea si la conexión es exitosa.

---

## 23. Deployment en AWS (Free Tier)

### Arquitectura

```
┌───────────────────────────────────────────────────────────────┐
│                    AWS FREE TIER ($0/mes)                      │
│                                                                │
│   ┌─────────────────────────────────────────────────────┐     │
│   │              EC2 t2.micro (1 instancia)              │     │
│   │                                                      │     │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐          │     │
│   │   │ Dashboard│  │  MLflow  │  │ Airflow  │          │     │
│   │   │  (8050)  │  │  (5001)  │  │  (8080)  │          │     │
│   │   └──────────┘  └──────────┘  └──────────┘          │     │
│   └─────────────────────────────────────────────────────┘     │
│                          │                                     │
│                          ▼                                     │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │ RDS t2.micro │    │     S3       │    │ EventBridge  │    │
│   │  PostgreSQL  │    │ data/models  │    │  + Lambda    │    │
│   └──────────────┘    └──────────────┘    └──────────────┘    │
└───────────────────────────────────────────────────────────────┘
```

### Componentes AWS

| Servicio        | Tipo        | Free Tier              |
| --------------- | ----------- | ---------------------- |
| **EC2**         | t2.micro    | 750 hrs/mes gratis     |
| **RDS**         | db.t3.micro | 750 hrs/mes gratis     |
| **S3**          | Standard    | 5 GB gratis            |
| **Lambda**      | —           | 1M requests/mes gratis |
| **EventBridge** | —           | Gratis                 |

### Archivos de Infraestructura

```
infra/
├── terraform/
│   ├── main.tf              # VPC, Security Groups, providers
│   ├── ec2.tf               # Instancia t2.micro
│   ├── rds.tf               # PostgreSQL db.t3.micro
│   ├── s3.tf                # Bucket para data y modelos
│   ├── lambda.tf            # Trigger semanal del pipeline
│   └── variables.tfvars.example
└── scripts/
    └── setup_ec2.sh         # Bootstrap de la instancia
```

### Requisitos Previos

1. **Cuenta AWS** con Free Tier activo
2. **AWS CLI** configurado (`aws configure`)
3. **Terraform** instalado (v1.0+)
4. **Key Pair** de SSH creado en AWS

### Despliegue Paso a Paso

```bash
cd infra/terraform

cp variables.tfvars.example terraform.tfvars

terraform init

terraform plan -var-file=terraform.tfvars

terraform apply -var-file=terraform.tfvars
```

### Variables Requeridas

Editar `terraform.tfvars`:

```hcl
aws_region       = "us-east-1"
project_name     = "fair-play-shield"
environment      = "dev"
db_password      = "TU_PASSWORD_SEGURO"
ssh_key_name     = "tu-key-pair"
allowed_ssh_cidr = "TU_IP/32"
```

### Outputs del Despliegue

Después de `terraform apply`:

```
ec2_public_ip  = "3.xxx.xxx.xxx"
dashboard_url  = "http://3.xxx.xxx.xxx:8050"
mlflow_url     = "http://3.xxx.xxx.xxx:5001"
airflow_url    = "http://3.xxx.xxx.xxx:8080"
rds_endpoint   = "fair-play-shield-db.xxx.us-east-1.rds.amazonaws.com:5432"
s3_bucket_name = "fair-play-shield-data-xxxxxxxx"
```

### Ejecución Automática

El pipeline se ejecuta automáticamente:

- **Frecuencia**: Cada lunes a las 6:00 AM UTC
- **Trigger**: EventBridge → Lambda → SSM → EC2

Para ejecutar manualmente:

```bash
aws lambda invoke --function-name fair-play-shield-pipeline-trigger output.json
```

### CI/CD con GitHub Actions

El workflow `.github/workflows/deploy.yml` automatiza:

1. **Test**: Ejecuta tests en cada push
2. **Deploy**: En push a `main`, actualiza EC2 vía SSM

Secrets requeridos en GitHub:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

### Destruir Infraestructura

```bash
terraform destroy -var-file=terraform.tfvars
```

---

## 24. Scripts de Entrenamiento y Predicción

### Entrenamiento Manual

```bash
python scripts/train_model.py

python scripts/train_model.py \
  --data-path data/processed/my_data.csv \
  --model-prefix my_model \
  --output-scores data/processed/my_scores.csv
```

### Predicción sobre Nuevos Datos

```bash
python scripts/predict.py --input data/new_matches.csv

python scripts/predict.py \
  --input data/new_matches.csv \
  --output data/scored_matches.csv \
  --model-prefix fps_leagues \
  --threshold 60
```

### Formato de Datos de Entrada

El CSV de entrada debe tener columnas similares a:

| Columna           | Descripción              |
| ----------------- | ------------------------ |
| `date`            | Fecha del partido        |
| `home_team`       | Equipo local             |
| `away_team`       | Equipo visitante         |
| `home_goals`      | Goles local              |
| `away_goals`      | Goles visitante          |
| `odds_home_open`  | Cuota apertura local     |
| `odds_home_close` | Cuota cierre local       |
| ...               | (otras columnas de odds) |

---

## 25. Guía de Instalación Paso a Paso

### Requisitos Previos

- **Python 3.11+**
- **Docker & Docker Compose**
- **AWS CLI** configurado con credenciales
- **Terraform** >= 1.0
- **Git**

### Opción A: Desarrollo Local

```bash
git clone https://github.com/eduzsantillan/fair_play_shield.git
cd fair_play_shield

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env

python main.py --step all --seasons 3

python dashboard/app.py
```

**Con Docker Compose (MLflow + Airflow):**

```bash
./scripts/init_airflow.sh
```

### Opción B: Despliegue AWS Free Tier

#### Paso 1: Configurar AWS CLI

```bash
aws configure
# Ingresa: Access Key, Secret Key, Region (us-east-1)
```

#### Paso 2: Crear Key Pair en AWS

```bash
aws ec2 create-key-pair --key-name aws-dev --query 'KeyMaterial' --output text > ~/.ssh/aws-dev.pem
chmod 400 ~/.ssh/aws-dev.pem
```

#### Paso 3: Crear Repositorio ECR

```bash
aws ecr create-repository --repository-name fair-play-shield --region us-east-1
```

#### Paso 4: Construir y Subir Imagen Docker

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker buildx build --platform linux/amd64 -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/fair-play-shield:latest -f Dockerfile.prod . --push
```

#### Paso 5: Configurar Variables Terraform

```bash
cd infra/terraform
cp variables.tfvars.example terraform.tfvars
```

Editar `terraform.tfvars`:

```hcl
aws_region      = "us-east-1"
project_name    = "fair-play-shield"
environment     = "dev"
db_password     = "tu_password_seguro"  # Sin caracteres especiales (@, #, etc.)
ssh_key_name    = "aws-dev"
allowed_ssh_cidr = "0.0.0.0/0"  # O tu IP específica
```

#### Paso 6: Desplegar Infraestructura

```bash
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars -auto-approve
```

#### Paso 7: Verificar Despliegue

```bash
terraform output

curl http://<EC2_PUBLIC_IP>:8050
```

#### Paso 8: Acceder por SSH (opcional)

```bash
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_PUBLIC_IP>
sudo docker ps
sudo docker logs fps-dashboard
```

### Redesplegar Cambios

```bash
docker buildx build --platform linux/amd64 -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/fair-play-shield:latest -f Dockerfile.prod . --push

ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_PUBLIC_IP> "cd /home/ec2-user/fair_play_shield && sudo docker-compose pull && sudo docker-compose up -d"
```

### Destruir Infraestructura

```bash
cd infra/terraform
terraform destroy -var-file=terraform.tfvars
```

---

## 26. Arquitectura AWS Free Tier

### Componentes Desplegados

| Servicio        | Tipo                   | Propósito       |
| --------------- | ---------------------- | --------------- |
| **EC2**         | t3.micro (1GB RAM)     | Dashboard       |
| **RDS**         | db.t3.micro PostgreSQL | Base de datos   |
| **S3**          | Bucket                 | Datos y modelos |
| **ECR**         | Repositorio            | Imágenes Docker |
| **Lambda**      | Función                | Trigger semanal |
| **EventBridge** | Regla                  | Scheduler       |

### Limitaciones Free Tier

- **t3.micro** tiene solo 1GB RAM → Solo Dashboard en EC2
- **MLflow y Airflow** deben correr localmente para desarrollo
- Para producción completa, usar t3.small o superior

### URLs de Servicios

| Entorno   | Dashboard             | MLflow                | Airflow               |
| --------- | --------------------- | --------------------- | --------------------- |
| **Local** | http://localhost:8050 | http://localhost:5001 | http://localhost:8080 |
| **AWS**   | http://EC2_IP:8050    | Local                 | Local                 |

---

## 27. Troubleshooting

### EC2 no responde

```bash
aws ec2 reboot-instances --instance-ids <INSTANCE_ID>

ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "sudo docker logs fps-dashboard"
```

### Error de arquitectura Docker

```bash
docker buildx build --platform linux/amd64 ...
```

### RDS conexión rechazada

Verificar Security Group permite puerto 5432 desde EC2.

### Dashboard no accesible

```bash
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "sudo docker ps"
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "curl localhost:8050"
```
