import dash
from dash import dcc, html, dash_table, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "trained"

SCORES_PATH = PROCESSED_DATA_DIR / "integrity_scores.csv"
LEAGUES_PATH = PROCESSED_DATA_DIR / "european_leagues_with_odds_processed.csv"
EL_PATH = RAW_DATA_DIR / "europa_league_matches.csv"

ALERT_COLORS = {
    "normal": "#27ae60",
    "monitor": "#f39c12",
    "suspicious": "#e67e22",
    "high_alert": "#e74c3c",
}
ALERT_ICONS = {
    "normal": "🟢",
    "monitor": "🟡",
    "suspicious": "🟠",
    "high_alert": "🔴",
}


def load_trained_models():
    try:
        scaler = joblib.load(MODEL_DIR / "fps_leagues_scaler.pkl")
        iso_forest = joblib.load(MODEL_DIR / "fps_leagues_isolation_forest.pkl")
        rf_model = joblib.load(MODEL_DIR / "fps_leagues_random_forest.pkl")
        lr_model = joblib.load(MODEL_DIR / "fps_leagues_logistic.pkl")
        feature_cols = joblib.load(MODEL_DIR / "fps_leagues_feature_cols.pkl")
        return scaler, iso_forest, rf_model, lr_model, feature_cols
    except Exception as e:
        print(f"Error loading models: {e}")
        return None, None, None, None, None


scaler, iso_forest, rf_model, lr_model, feature_cols = load_trained_models()
MODELS_LOADED = scaler is not None


def load_data():
    scores = pd.read_csv(SCORES_PATH, parse_dates=["date"])
    leagues = pd.read_csv(LEAGUES_PATH, parse_dates=["date"], low_memory=False)
    el = pd.read_csv(EL_PATH, parse_dates=["date"]) if EL_PATH.exists() else pd.DataFrame()
    return scores, leagues, el


scores_df, leagues_df, el_df = load_data()

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Fair Play Shield",
    suppress_callback_exceptions=True,
)


def build_kpi_cards():
    total = len(scores_df)
    high_alert = (scores_df["alert_level"] == "high_alert").sum()
    suspicious = (scores_df["alert_level"] == "suspicious").sum()
    avg_score = scores_df["integrity_score"].mean()
    max_score = scores_df["integrity_score"].max()

    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{total:,}", className="text-info"),
                html.P("Partidos analizados"),
            ])
        ], className="bg-dark border-info"), width=2),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{high_alert}", className="text-danger"),
                html.P("🔴 Alta sospecha"),
            ])
        ], className="bg-dark border-danger"), width=2),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{suspicious}", className="text-warning"),
                html.P("🟠 Sospechosos"),
            ])
        ], className="bg-dark border-warning"), width=2),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{avg_score:.1f}", className="text-light"),
                html.P("Score promedio"),
            ])
        ], className="bg-dark border-secondary"), width=2),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{max_score:.1f}", className="text-danger"),
                html.P("Score máximo"),
            ])
        ], className="bg-dark border-danger"), width=2),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4(f"{len(el_df)}", className="text-primary"),
                html.P("Europa League"),
            ])
        ], className="bg-dark border-primary"), width=2),
    ], className="mb-4")


def build_alerts_panel():
    alerts = scores_df[scores_df["alert_level"].isin(["high_alert", "suspicious"])].sort_values(
        "integrity_score", ascending=False
    ).head(30)

    alert_items = []
    for _, row in alerts.iterrows():
        level = row["alert_level"]
        icon = ALERT_ICONS.get(level, "⚪")
        color = ALERT_COLORS.get(level, "#95a5a6")
        date_str = pd.to_datetime(row["date"]).strftime("%Y-%m-%d") if pd.notna(row["date"]) else "?"
        score = row["integrity_score"]

        alert_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Span(f"{icon} ", style={"fontSize": "1.2rem"}),
                    html.Strong(f"{row.get('home_team','?')} vs {row.get('away_team','?')}"),
                    html.Span(f"  ({date_str})", className="text-muted ms-2"),
                ]),
                html.Div([
                    html.Span(
                        f"Score: {score:.1f}",
                        className="badge",
                        style={"backgroundColor": color, "fontSize": "0.85rem"},
                    ),
                    html.Span(
                        f"  {row.get('home_goals','')} - {row.get('away_goals','')}",
                        className="text-light ms-2",
                    ),
                    html.Span(
                        f"  {row.get('league_name','')}" if "league_name" in row.index else "",
                        className="text-muted ms-2",
                    ),
                ], className="mt-1"),
            ], className="bg-dark", style={"borderLeft": f"4px solid {color}"})
        )

    return dbc.Card([
        dbc.CardHeader(html.H5("🚨 Alertas — Partidos sospechosos", className="text-danger")),
        dbc.CardBody([
            dbc.ListGroup(alert_items, flush=True, style={"maxHeight": "500px", "overflowY": "auto"})
        ])
    ], className="bg-dark border-danger mb-4")


def build_score_distribution():
    fig = go.Figure()
    for level, color in ALERT_COLORS.items():
        subset = scores_df[scores_df["alert_level"] == level]
        fig.add_trace(go.Histogram(
            x=subset["integrity_score"],
            name=f"{ALERT_ICONS.get(level,'')} {level} ({len(subset)})",
            marker_color=color,
            opacity=0.8,
        ))
    fig.update_layout(
        title="Distribución de Integrity Scores",
        xaxis_title="Integrity Score",
        yaxis_title="Partidos",
        barmode="stack",
        template="plotly_dark",
        height=400,
    )
    return fig


def build_league_comparison():
    if "league_name" not in scores_df.columns:
        return go.Figure()

    league_stats = scores_df.groupby("league_name").agg(
        mean_score=("integrity_score", "mean"),
        max_score=("integrity_score", "max"),
        high_alerts=("alert_level", lambda x: (x == "high_alert").sum()),
        total=("integrity_score", "count"),
    ).reset_index()
    league_stats["pct_high"] = league_stats["high_alerts"] / league_stats["total"] * 100
    league_stats = league_stats.sort_values("mean_score", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=league_stats["league_name"],
        x=league_stats["mean_score"],
        orientation="h",
        name="Score promedio",
        marker_color="#3498db",
    ))
    fig.add_trace(go.Bar(
        y=league_stats["league_name"],
        x=league_stats["pct_high"],
        orientation="h",
        name="% Alta sospecha",
        marker_color="#e74c3c",
    ))
    fig.update_layout(
        title="Comparativa por Liga",
        barmode="group",
        template="plotly_dark",
        height=400,
        xaxis_title="Valor",
    )
    return fig


def build_time_series():
    ts = scores_df.copy()
    ts["month"] = ts["date"].dt.to_period("M").astype(str)
    monthly = ts.groupby("month").agg(
        mean_score=("integrity_score", "mean"),
        high_alerts=("alert_level", lambda x: (x == "high_alert").sum()),
        total=("integrity_score", "count"),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=monthly["mean_score"],
        mode="lines+markers", name="Score promedio",
        line=dict(color="#3498db", width=2),
    ))
    fig.add_trace(go.Bar(
        x=monthly["month"], y=monthly["high_alerts"],
        name="Alertas altas", marker_color="#e74c3c", opacity=0.6,
        yaxis="y2",
    ))
    fig.update_layout(
        title="Evolución temporal de sospecha",
        template="plotly_dark",
        height=400,
        yaxis=dict(title="Score promedio"),
        yaxis2=dict(title="Alertas altas", overlaying="y", side="right"),
        xaxis=dict(title="Mes"),
    )
    return fig


def build_scatter_odds():
    if "odds_movement_abs_max" not in leagues_df.columns:
        return go.Figure()

    sample = leagues_df.dropna(subset=["odds_movement_abs_max", "total_goals"]).sample(
        min(3000, len(leagues_df)), random_state=42
    )
    merged = sample.merge(
        scores_df[["date", "home_team", "away_team", "integrity_score", "alert_level"]],
        on=["date", "home_team", "away_team"],
        how="left",
    )
    merged = merged.dropna(subset=["integrity_score"])

    fig = px.scatter(
        merged,
        x="odds_movement_abs_max",
        y="total_goals",
        color="alert_level",
        color_discrete_map=ALERT_COLORS,
        hover_data=["home_team", "away_team", "integrity_score", "date"],
        title="Movimiento de cuotas vs Goles (color = nivel alerta)",
        template="plotly_dark",
        height=400,
        opacity=0.6,
    )
    fig.add_vline(x=0.15, line_dash="dash", line_color="white", annotation_text="Umbral 15%")
    return fig


def build_europa_league_panel():
    if el_df.empty:
        return html.P("No hay datos de Europa League disponibles", className="text-muted")

    fig_results = px.pie(
        el_df, names="result",
        color="result",
        color_discrete_map={"H": "#27ae60", "D": "#f39c12", "A": "#e74c3c"},
        title="Resultados Europa League",
        template="plotly_dark",
        height=350,
    )

    top_scorers = el_df.groupby("home_team")["home_goals"].sum().add(
        el_df.groupby("away_team")["away_goals"].sum(), fill_value=0
    ).sort_values(ascending=False).head(15)

    fig_goals = go.Figure(go.Bar(
        x=top_scorers.values,
        y=top_scorers.index,
        orientation="h",
        marker_color="#1abc9c",
    ))
    fig_goals.update_layout(
        title="Top 15 equipos goleadores (Europa League)",
        template="plotly_dark",
        height=350,
        yaxis=dict(autorange="reversed"),
    )

    country_matches = el_df["country"].value_counts().head(15)
    fig_countries = go.Figure(go.Bar(
        x=country_matches.values,
        y=country_matches.index,
        orientation="h",
        marker_color="#9b59b6",
    ))
    fig_countries.update_layout(
        title="Partidos por país (Europa League)",
        template="plotly_dark",
        height=350,
        yaxis=dict(autorange="reversed"),
    )

    return html.Div([
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_results), width=4),
            dbc.Col(dcc.Graph(figure=fig_goals), width=4),
            dbc.Col(dcc.Graph(figure=fig_countries), width=4),
        ]),
    ])


def build_prediction_form():
    if not MODELS_LOADED:
        return dbc.Alert("⚠️ Modelos no cargados. Ejecuta primero el entrenamiento.", color="warning")
    
    return html.Div([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎯 Predicción de Integridad de Partido")),
                    dbc.CardBody([
                        html.P("Ingresa los datos del partido para predecir si presenta anomalías sospechosas.", className="text-muted mb-4"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Equipo Local"),
                                dbc.Input(id="input-home-team", type="text", placeholder="Ej: Real Madrid"),
                            ], width=6),
                            dbc.Col([
                                dbc.Label("Equipo Visitante"),
                                dbc.Input(id="input-away-team", type="text", placeholder="Ej: Barcelona"),
                            ], width=6),
                        ], className="mb-3"),
                        
                        html.Hr(),
                        html.H6("📊 Estadísticas del Partido", className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Goles Local"),
                                dbc.Input(id="input-home-goals", type="number", value=1, min=0, max=15),
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Goles Visitante"),
                                dbc.Input(id="input-away-goals", type="number", value=0, min=0, max=15),
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Tarjetas Totales"),
                                dbc.Input(id="input-cards", type="number", value=3, min=0, max=20),
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Resultado HT cambió"),
                                dbc.Select(id="input-ht-changed", options=[
                                    {"label": "No", "value": "0"},
                                    {"label": "Sí", "value": "1"},
                                ], value="0"),
                            ], width=3),
                        ], className="mb-3"),
                        
                        html.Hr(),
                        html.H6("💰 Datos de Cuotas (Apuestas)", className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Movimiento de cuotas (%)"),
                                dbc.Input(id="input-odds-movement", type="number", value=5, min=0, max=100, step=0.1),
                                dbc.FormText("Cambio % entre cuota apertura y cierre"),
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Resultado sorpresa"),
                                dbc.Select(id="input-result-surprise", options=[
                                    {"label": "No (favorito ganó)", "value": "0"},
                                    {"label": "Sí (no favorito ganó)", "value": "1"},
                                ], value="0"),
                                dbc.FormText("¿Ganó el equipo menos favorecido?"),
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Ruptura de racha"),
                                dbc.Select(id="input-streak-break", options=[
                                    {"label": "No", "value": "0"},
                                    {"label": "Sí", "value": "1"},
                                ], value="0"),
                                dbc.FormText("¿Se rompió racha de 5+ victorias?"),
                            ], width=4),
                        ], className="mb-4"),
                        
                        dbc.Button("🔍 Analizar Partido", id="btn-predict", color="primary", size="lg", className="w-100"),
                    ])
                ], className="bg-dark border-primary"),
            ], width=6),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📋 Resultado del Análisis")),
                    dbc.CardBody(id="prediction-result", children=[
                        html.Div([
                            html.I(className="fas fa-arrow-left me-2"),
                            html.P("Completa el formulario y haz clic en 'Analizar Partido'", className="text-muted text-center mt-5"),
                        ], className="text-center", style={"minHeight": "400px", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
                    ])
                ], className="bg-dark border-secondary h-100"),
            ], width=6),
        ]),
        
        html.Hr(className="my-4"),
        
        dbc.Card([
            dbc.CardHeader(html.H6("ℹ️ Cómo interpretar los resultados")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.P([html.Strong("🟢 Normal (0-30): "), "El partido no presenta anomalías significativas."]),
                        html.P([html.Strong("🟡 Monitor (31-60): "), "Algunas señales menores, seguimiento recomendado."]),
                    ], width=6),
                    dbc.Col([
                        html.P([html.Strong("🟠 Sospechoso (61-80): "), "Múltiples anomalías detectadas, investigar."]),
                        html.P([html.Strong("🔴 Alta Sospecha (81-100): "), "Patrón altamente anómalo, requiere revisión urgente."]),
                    ], width=6),
                ]),
            ])
        ], className="bg-dark border-info"),
    ])


app.layout = dbc.Container([
    dbc.Navbar(
        dbc.Container([
            html.Div([
                html.H3("🛡️ Fair Play Shield", className="text-light mb-0"),
                html.Small("Sistema de detección de partidos amañados", className="text-muted"),
            ]),
        ]),
        color="dark",
        dark=True,
        className="mb-4",
    ),

    build_kpi_cards(),

    dbc.Tabs([
        dbc.Tab(label="📊 Análisis General", children=[
            html.Div([
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=build_score_distribution()), width=6),
                    dbc.Col(dcc.Graph(figure=build_league_comparison()), width=6),
                ], className="mb-4"),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=build_time_series()), width=6),
                    dbc.Col(dcc.Graph(figure=build_scatter_odds()), width=6),
                ]),
            ], className="mt-3")
        ]),

        dbc.Tab(label="🚨 Alertas", children=[
            html.Div([
                dbc.Row([
                    dbc.Col(build_alerts_panel(), width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H5("🔍 Buscar partido")),
                            dbc.CardBody([
                                dbc.Input(id="search-input", placeholder="Buscar equipo...", type="text", className="mb-3"),
                                html.Div(id="search-results"),
                            ])
                        ], className="bg-dark border-info mb-4"),
                        dbc.Card([
                            dbc.CardHeader(html.H5("📈 Filtrar por nivel")),
                            dbc.CardBody([
                                dcc.Dropdown(
                                    id="alert-filter",
                                    options=[
                                        {"label": "🔴 Alta sospecha", "value": "high_alert"},
                                        {"label": "🟠 Sospechoso", "value": "suspicious"},
                                        {"label": "🟡 Monitorear", "value": "monitor"},
                                        {"label": "🟢 Normal", "value": "normal"},
                                    ],
                                    value=["high_alert", "suspicious"],
                                    multi=True,
                                    className="mb-3",
                                ),
                                html.Div(id="filtered-count"),
                            ])
                        ], className="bg-dark border-warning"),
                    ], width=6),
                ]),
            ], className="mt-3")
        ]),

        dbc.Tab(label="⚽ Europa League", children=[
            html.Div([
                build_europa_league_panel(),
                html.Hr(),
                html.H5("Últimos partidos Europa League"),
                dash_table.DataTable(
                    data=el_df.sort_values("date", ascending=False).head(50).to_dict("records") if not el_df.empty else [],
                    columns=[
                        {"name": "Fecha", "id": "date"},
                        {"name": "Local", "id": "home_team"},
                        {"name": "Goles L", "id": "home_goals"},
                        {"name": "Goles V", "id": "away_goals"},
                        {"name": "Visitante", "id": "away_team"},
                        {"name": "Resultado", "id": "result"},
                        {"name": "Estadio", "id": "stadium"},
                        {"name": "País", "id": "country"},
                        {"name": "Ronda", "id": "round"},
                    ],
                    style_table={"overflowX": "auto"},
                    style_cell={"backgroundColor": "#2c3e50", "color": "white", "textAlign": "left", "padding": "8px"},
                    style_header={"backgroundColor": "#1a252f", "fontWeight": "bold"},
                    page_size=20,
                    filter_action="native",
                    sort_action="native",
                ),
            ], className="mt-3")
        ]),

        dbc.Tab(label="📋 Datos completos", children=[
            html.Div([
                html.H5("Integrity Scores — Todos los partidos", className="mt-3 mb-3"),
                dcc.Dropdown(
                    id="league-filter",
                    options=[{"label": l, "value": l} for l in sorted(scores_df["league_name"].dropna().unique())] if "league_name" in scores_df.columns else [],
                    placeholder="Filtrar por liga...",
                    multi=True,
                    className="mb-3",
                ),
                dash_table.DataTable(
                    id="scores-table",
                    data=scores_df.sort_values("integrity_score", ascending=False).head(200).to_dict("records"),
                    columns=[
                        {"name": "Fecha", "id": "date"},
                        {"name": "Local", "id": "home_team"},
                        {"name": "Visitante", "id": "away_team"},
                        {"name": "Goles L", "id": "home_goals"},
                        {"name": "Goles V", "id": "away_goals"},
                        {"name": "Score", "id": "integrity_score"},
                        {"name": "Alerta", "id": "alert_level"},
                        {"name": "Liga", "id": "league_name"},
                        {"name": "Temporada", "id": "season"},
                    ],
                    style_table={"overflowX": "auto"},
                    style_cell={"backgroundColor": "#2c3e50", "color": "white", "textAlign": "left", "padding": "8px"},
                    style_header={"backgroundColor": "#1a252f", "fontWeight": "bold"},
                    style_data_conditional=[
                        {"if": {"filter_query": '{alert_level} = "high_alert"'}, "backgroundColor": "#5b1a1a"},
                        {"if": {"filter_query": '{alert_level} = "suspicious"'}, "backgroundColor": "#5b3a1a"},
                        {"if": {"filter_query": '{alert_level} = "monitor"'}, "backgroundColor": "#5b5b1a"},
                    ],
                    page_size=25,
                    filter_action="native",
                    sort_action="native",
                ),
            ], className="mt-3")
        ]),

        dbc.Tab(label="🎯 Predicción", children=[
            html.Div([
                build_prediction_form(),
            ], className="mt-3")
        ]),
    ]),

    html.Footer([
        html.Hr(),
        html.P("Fair Play Shield v1.0 — Sistema de detección de partidos amañados", className="text-muted text-center"),
    ], className="mt-4"),

], fluid=True, className="bg-dark")


@callback(
    Output("search-results", "children"),
    Input("search-input", "value"),
)
def search_matches(query):
    if not query or len(query) < 2:
        return html.P("Escribe al menos 2 caracteres...", className="text-muted")

    query_lower = query.lower()
    mask = (
        scores_df["home_team"].str.lower().str.contains(query_lower, na=False)
        | scores_df["away_team"].str.lower().str.contains(query_lower, na=False)
    )
    results = scores_df[mask].sort_values("integrity_score", ascending=False).head(10)

    if results.empty:
        return html.P("Sin resultados", className="text-muted")

    items = []
    for _, row in results.iterrows():
        level = row["alert_level"]
        icon = ALERT_ICONS.get(level, "⚪")
        items.append(html.Div([
            html.Span(f"{icon} "),
            html.Strong(f"{row['home_team']} vs {row['away_team']}"),
            html.Span(f" — Score: {row['integrity_score']:.1f}", className="text-warning"),
        ], className="mb-2"))

    return html.Div(items)


@callback(
    Output("filtered-count", "children"),
    Input("alert-filter", "value"),
)
def filter_count(levels):
    if not levels:
        return html.P("Selecciona un nivel", className="text-muted")
    count = scores_df[scores_df["alert_level"].isin(levels)].shape[0]
    return html.P(f"{count:,} partidos encontrados", className="text-info")


@callback(
    Output("scores-table", "data"),
    Input("league-filter", "value"),
)
def filter_league(leagues):
    df = scores_df.sort_values("integrity_score", ascending=False)
    if leagues:
        df = df[df["league_name"].isin(leagues)]
    return df.head(200).to_dict("records")


@callback(
    Output("prediction-result", "children"),
    Input("btn-predict", "n_clicks"),
    State("input-home-team", "value"),
    State("input-away-team", "value"),
    State("input-home-goals", "value"),
    State("input-away-goals", "value"),
    State("input-cards", "value"),
    State("input-ht-changed", "value"),
    State("input-odds-movement", "value"),
    State("input-result-surprise", "value"),
    State("input-streak-break", "value"),
    prevent_initial_call=True,
)
def predict_match(n_clicks, home_team, away_team, home_goals, away_goals, cards, ht_changed, odds_movement, result_surprise, streak_break):
    if not MODELS_LOADED:
        return dbc.Alert("Modelos no disponibles", color="danger")
    
    if not home_team or not away_team:
        return dbc.Alert("Ingresa los nombres de los equipos", color="warning")
    
    try:
        home_goals = int(home_goals or 0)
        away_goals = int(away_goals or 0)
        cards = int(cards or 0)
        ht_changed = int(ht_changed or 0)
        odds_movement = float(odds_movement or 0) / 100
        result_surprise = int(result_surprise or 0)
        streak_break = int(streak_break or 0)
        
        total_goals = home_goals + away_goals
        
        goals_mean = leagues_df["total_goals"].mean() if "total_goals" in leagues_df.columns else 2.5
        goals_std = leagues_df["total_goals"].std() if "total_goals" in leagues_df.columns else 1.5
        goals_anomaly = 1 if goals_std > 0 and abs(total_goals - goals_mean) / goals_std > 2 else 0
        
        cards_mean = leagues_df["total_cards"].mean() if "total_cards" in leagues_df.columns else 4
        cards_anomaly = 1 if cards > cards_mean * 1.5 else 0
        
        flag_odds = 1 if odds_movement > 0.15 else 0
        
        input_data = {
            "odds_movement_abs_max": odds_movement,
            "result_surprise": result_surprise,
            "ht_result_changed": ht_changed,
            "total_goals": total_goals,
            "total_cards": cards,
            "flag_odds_movement": flag_odds,
            "flag_result_surprise": result_surprise,
            "flag_streak_break": streak_break,
            "flag_goals_anomaly_home": goals_anomaly,
            "flag_goals_anomaly_away": goals_anomaly,
            "flag_ht_result_changed": ht_changed,
            "flag_cards_anomaly": cards_anomaly,
        }
        
        df_input = pd.DataFrame([input_data])
        
        available_features = [f for f in feature_cols if f in df_input.columns]
        for f in feature_cols:
            if f not in df_input.columns:
                df_input[f] = 0
        
        X = df_input[feature_cols].fillna(0)
        X_scaled = scaler.transform(X)
        
        iso_raw = iso_forest.decision_function(X_scaled)[0]
        iso_norm = 1 - (iso_raw - (-0.5)) / (0.5 - (-0.5) + 1e-8)
        iso_norm = max(0, min(1, iso_norm))
        
        rf_proba = rf_model.predict_proba(X_scaled)[0][1]
        lr_proba = lr_model.predict_proba(X_scaled)[0][1]
        
        integrity_score = (0.35 * iso_norm + 0.40 * rf_proba + 0.25 * lr_proba) * 100
        integrity_score = max(0, min(100, integrity_score))
        
        if integrity_score <= 30:
            alert_level, alert_color, alert_icon = "Normal", "success", "🟢"
        elif integrity_score <= 60:
            alert_level, alert_color, alert_icon = "Monitor", "warning", "🟡"
        elif integrity_score <= 80:
            alert_level, alert_color, alert_icon = "Sospechoso", "orange", "🟠"
        else:
            alert_level, alert_color, alert_icon = "Alta Sospecha", "danger", "🔴"
        
        flags_detected = []
        if flag_odds > 0:
            flags_detected.append("Movimiento de cuotas >15%")
        if result_surprise > 0:
            flags_detected.append("Resultado sorpresa")
        if streak_break > 0:
            flags_detected.append("Ruptura de racha")
        if goals_anomaly > 0:
            flags_detected.append("Goles anómalos")
        if ht_changed > 0:
            flags_detected.append("Cambio resultado HT")
        if cards_anomaly > 0:
            flags_detected.append("Tarjetas anómalas")
        
        return html.Div([
            html.Div([
                html.H1(f"{alert_icon}", style={"fontSize": "4rem"}),
                html.H2(f"{integrity_score:.1f}", className=f"text-{alert_color}" if alert_color != "orange" else "text-warning"),
                html.P("Match Integrity Score", className="text-muted"),
            ], className="text-center mb-4"),
            
            dbc.Alert([
                html.H5(f"{alert_icon} {alert_level}", className="alert-heading"),
                html.P(f"{home_team} vs {away_team}"),
            ], color=alert_color if alert_color != "orange" else "warning"),
            
            html.Hr(),
            
            html.H6("📊 Desglose de Scores"),
            dbc.Progress([
                dbc.Progress(value=iso_norm*100, color="info", bar=True, label=f"IF: {iso_norm*100:.0f}"),
            ], className="mb-2", style={"height": "25px"}),
            dbc.Progress([
                dbc.Progress(value=rf_proba*100, color="primary", bar=True, label=f"RF: {rf_proba*100:.0f}"),
            ], className="mb-2", style={"height": "25px"}),
            dbc.Progress([
                dbc.Progress(value=lr_proba*100, color="secondary", bar=True, label=f"LR: {lr_proba*100:.0f}"),
            ], className="mb-3", style={"height": "25px"}),
            
            html.Small("IF=Isolation Forest, RF=Random Forest, LR=Logistic Regression", className="text-muted"),
            
            html.Hr(),
            
            html.H6(f"🚩 Flags Detectados ({len(flags_detected)})"),
            html.Ul([html.Li(f, className="text-warning") for f in flags_detected]) if flags_detected else html.P("Ninguno", className="text-success"),
            
            html.Hr(),
            
            html.H6("📋 Datos de Entrada"),
            html.Small([
                html.Div(f"Goles: {home_goals}-{away_goals} | Tarjetas: {cards} | Mov. cuotas: {odds_movement*100:.1f}%"),
            ], className="text-muted"),
        ])
        
    except Exception as e:
        return dbc.Alert(f"Error en predicción: {str(e)}", color="danger")


if __name__ == "__main__":
    print("\n🛡️  Fair Play Shield Dashboard")
    print("=" * 40)
    print(f"Datos: {len(scores_df)} partidos scored")
    print(f"Europa League: {len(el_df)} partidos")
    print(f"Alertas altas: {(scores_df['alert_level'] == 'high_alert').sum()}")
    print(f"\nAbriendo en http://localhost:8050")
    print("=" * 40)
    app.run(debug=False, host="0.0.0.0", port=8050)
