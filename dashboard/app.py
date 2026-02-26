import importlib.util as _ilu
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
ALERT_LABELS = {
    "normal": "Normal",
    "monitor": "Monitorear",
    "suspicious": "Sospechoso",
    "high_alert": "Alta sospecha",
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

if not el_df.empty and "league_name" not in el_df.columns:
    el_df["league_name"] = "Europa League"

_leagues = sorted(scores_df["league_name"].dropna().unique().tolist()) if "league_name" in scores_df.columns else []
_seasons = sorted(scores_df["season"].dropna().unique().tolist(), reverse=True) if "season" in scores_df.columns else []
FLAG_COLS = [c for c in scores_df.columns if c.startswith("flag_")]


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Fair Play Shield",
    suppress_callback_exceptions=True,
)


def _kpi_card(value, label, color, border):
    return dbc.Col(dbc.Card([
        dbc.CardBody([
            html.H3(str(value), className=f"text-{color} mb-0"),
            html.P(label, className="text-muted small mb-0"),
        ])
    ], className=f"bg-dark border-{border} text-center"), width=2)


def build_kpi_cards():
    total = len(scores_df)
    high_alert = int((scores_df["alert_level"] == "high_alert").sum())
    suspicious = int((scores_df["alert_level"] == "suspicious").sum())
    avg_score = scores_df["integrity_score"].mean()
    ligas = len(_leagues)
    temporadas = len(_seasons)

    return dbc.Row([
        _kpi_card(f"{total:,}", "Partidos analizados", "info", "info"),
        _kpi_card(f"{high_alert}", "🔴 Alta sospecha", "danger", "danger"),
        _kpi_card(f"{suspicious}", "🟠 Sospechosos", "warning", "warning"),
        _kpi_card(f"{avg_score:.1f}", "Score promedio", "light", "secondary"),
        _kpi_card(f"{ligas}", "Ligas cubiertas", "primary", "primary"),
        _kpi_card(f"{temporadas}", "Temporadas", "success", "success"),
    ], className="mb-4 g-2")


def build_alerts_tab():
    league_opts = [{"label": l, "value": l} for l in _leagues]
    season_opts = [{"label": s, "value": s} for s in _seasons]
    level_opts = [
        {"label": f"{ALERT_ICONS[k]} {ALERT_LABELS[k]}", "value": k}
        for k in ["high_alert", "suspicious", "monitor", "normal"]
    ]

    filter_row = dbc.Row([
        dbc.Col([
            dbc.Label("Liga", className="small text-muted"),
            dcc.Dropdown(
                id="alerts-league-filter",
                options=league_opts,
                placeholder="Todas las ligas",
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=3),
        dbc.Col([
            dbc.Label("Temporada", className="small text-muted"),
            dcc.Dropdown(
                id="alerts-season-filter",
                options=season_opts,
                placeholder="Todas",
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=2),
        dbc.Col([
            dbc.Label("Nivel de alerta", className="small text-muted"),
            dcc.Dropdown(
                id="alerts-level-filter",
                options=level_opts,
                value=["high_alert", "suspicious"],
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=3),
        dbc.Col([
            dbc.Label("Buscar equipo", className="small text-muted"),
            dbc.Input(
                id="alerts-team-search",
                placeholder="Ej: Barcelona...",
                type="text",
                size="sm",
            ),
        ], width=3),
        dbc.Col([
            dbc.Label("\u00a0", className="small d-block"),
            dbc.Button("Limpiar", id="alerts-clear-btn", color="secondary", size="sm", className="w-100"),
        ], width=1),
    ], className="mb-3 g-2 align-items-end")

    table = dash_table.DataTable(
        id="alerts-table",
        columns=[
            {"name": "Fecha", "id": "date", "type": "text"},
            {"name": "Local", "id": "home_team"},
            {"name": "Visitante", "id": "away_team"},
            {"name": "Goles", "id": "score_display"},
            {"name": "Liga", "id": "league_name"},
            {"name": "Temporada", "id": "season"},
            {"name": "Score MIS", "id": "integrity_score", "type": "numeric", "format": {"specifier": ".1f"}},
            {"name": "Nivel", "id": "alert_level"},
        ],
        data=[],
        sort_action="native",
        sort_by=[{"column_id": "date", "direction": "desc"}],
        filter_action="none",
        page_size=20,
        page_action="native",
        row_selectable="single",
        selected_rows=[],
        style_table={"overflowX": "auto"},
        style_cell={
            "backgroundColor": "#1e2a35",
            "color": "#ecf0f1",
            "textAlign": "left",
            "padding": "8px 12px",
            "fontSize": "13px",
            "border": "1px solid #2c3e50",
        },
        style_header={
            "backgroundColor": "#0d1b2a",
            "fontWeight": "bold",
            "color": "#bdc3c7",
            "border": "1px solid #2c3e50",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{alert_level} = "high_alert"'}, "backgroundColor": "#3d0c0c"},
            {"if": {"filter_query": '{alert_level} = "suspicious"'}, "backgroundColor": "#3d2008"},
            {"if": {"filter_query": '{alert_level} = "monitor"'}, "backgroundColor": "#2e2a08"},
            {"if": {"state": "selected"}, "backgroundColor": "#1a3a5c", "border": "1px solid #3498db"},
        ],
    )

    return html.Div([
        dbc.Card([
            dbc.CardBody([filter_row, html.Div(id="alerts-count", className="text-muted small mb-2"), table])
        ], className="bg-dark border-secondary"),
        html.Div(id="alerts-detail-panel", className="mt-3"),
    ], className="mt-3")


def build_score_distribution():
    fig = go.Figure()
    for level, color in ALERT_COLORS.items():
        subset = scores_df[scores_df["alert_level"] == level]
        label = ALERT_LABELS.get(level, level)
        fig.add_trace(go.Histogram(
            x=subset["integrity_score"],
            name=f"{ALERT_ICONS.get(level, '')} {label} ({len(subset)})",
            marker_color=color,
            opacity=0.8,
        ))
    fig.update_layout(
        title="Distribución de Integrity Scores",
        xaxis_title="Integrity Score",
        yaxis_title="Partidos",
        barmode="stack",
        template="plotly_dark",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
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
        height=380,
        yaxis=dict(title="Score promedio"),
        yaxis2=dict(title="Alertas altas", overlaying="y", side="right"),
        xaxis=dict(title="Mes"),
    )
    return fig


def build_scatter_odds():
    if "odds_movement_abs_max" not in leagues_df.columns:
        return go.Figure()

    filtered = leagues_df.dropna(subset=["odds_movement_abs_max", "total_goals"])
    if filtered.empty:
        return go.Figure()

    n = min(3000, len(filtered))
    sample = filtered.sample(n=n, random_state=42)
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


def build_match_detail_modal():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="modal-title", children="Detalle del Partido")),
        dbc.ModalBody(id="modal-body"),
        dbc.ModalFooter(
            dbc.Button("Cerrar", id="modal-close", className="ms-auto", n_clicks=0)
        ),
    ], id="match-modal", size="lg", is_open=False, backdrop=True)


def build_data_tab():
    league_opts = [{"label": l, "value": l} for l in _leagues]
    season_opts = [{"label": s, "value": s} for s in _seasons]
    level_opts = [
        {"label": f"{ALERT_ICONS[k]} {ALERT_LABELS[k]}", "value": k}
        for k in ["high_alert", "suspicious", "monitor", "normal"]
    ]

    filter_row = dbc.Row([
        dbc.Col([
            dbc.Label("Liga", className="small text-muted"),
            dcc.Dropdown(
                id="data-league-filter",
                options=league_opts,
                placeholder="Todas",
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=3),
        dbc.Col([
            dbc.Label("Temporada", className="small text-muted"),
            dcc.Dropdown(
                id="data-season-filter",
                options=season_opts,
                placeholder="Todas",
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=2),
        dbc.Col([
            dbc.Label("Nivel de alerta", className="small text-muted"),
            dcc.Dropdown(
                id="data-level-filter",
                options=level_opts,
                placeholder="Todos",
                multi=True,
                style={"fontSize": "13px"},
            ),
        ], width=2),
        dbc.Col([
            dbc.Label("Buscar equipo", className="small text-muted"),
            dbc.Input(
                id="data-team-search",
                placeholder="Ej: Arsenal...",
                type="text",
                size="sm",
            ),
        ], width=3),
        dbc.Col([
            dbc.Label("\u00a0", className="small d-block"),
            dbc.Button("Limpiar", id="data-clear-btn", color="secondary", size="sm", className="w-100"),
        ], width=1),
        dbc.Col([
            dbc.Label("\u00a0", className="small d-block"),
            html.Div(id="data-count", className="text-muted small pt-1"),
        ], width=1),
    ], className="mb-3 g-2 align-items-end")

    table = dash_table.DataTable(
        id="data-table",
        columns=[
            {"name": "Fecha",    "id": "date",            "type": "text"},
            {"name": "Local",    "id": "home_team"},
            {"name": "Visitante","id": "away_team"},
            {"name": "Goles",    "id": "score_display"},
            {"name": "Liga",     "id": "league_name"},
            {"name": "Temporada","id": "season"},
            {"name": "MIS",      "id": "integrity_score", "type": "numeric", "format": {"specifier": ".1f"}},
            {"name": "Nivel",    "id": "alert_level"},
        ],
        data=[],
        sort_action="native",
        sort_by=[{"column_id": "date", "direction": "desc"}],
        filter_action="none",
        page_size=20,
        page_action="native",
        row_selectable="single",
        selected_rows=[],
        style_table={"overflowX": "auto"},
        style_cell={
            "backgroundColor": "#1e2a35",
            "color": "#ecf0f1",
            "textAlign": "left",
            "padding": "8px 12px",
            "fontSize": "13px",
            "border": "1px solid #2c3e50",
        },
        style_header={
            "backgroundColor": "#0d1b2a",
            "fontWeight": "bold",
            "color": "#bdc3c7",
            "border": "1px solid #2c3e50",
        },
        style_data_conditional=[
            {"if": {"filter_query": '{alert_level} = "high_alert"'}, "backgroundColor": "#3d0c0c"},
            {"if": {"filter_query": '{alert_level} = "suspicious"'}, "backgroundColor": "#3d2008"},
            {"if": {"filter_query": '{alert_level} = "monitor"'}, "backgroundColor": "#2e2a08"},
            {"if": {"state": "selected"}, "backgroundColor": "#1a3a5c", "border": "1px solid #3498db"},
        ],
    )

    return html.Div([
        dbc.Card([
            dbc.CardBody([filter_row, html.Div(id="data-count-inline", className="text-muted small mb-2"), table])
        ], className="bg-dark border-secondary"),
        html.Div(id="data-detail-panel", className="mt-2"),
    ], className="mt-3")


def _build_prediction_form_unused():
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
    build_match_detail_modal(),

    dbc.Navbar(
        dbc.Container([
            html.Div([
                html.H4("🛡️ Fair Play Shield", className="text-light mb-0"),
                html.Small("Sistema de detección de partidos amañados — v2", className="text-muted"),
            ]),
        ]),
        color="dark",
        dark=True,
        className="mb-4",
    ),

    build_kpi_cards(),

    dbc.Tabs(id="main-tabs", children=[
        dbc.Tab(label="📊 Análisis General", tab_id="tab-analysis", children=[
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

        dbc.Tab(label="� Partidos", tab_id="tab-data", children=[
            build_data_tab(),
        ]),
    ], className="mb-4"),

    html.Footer([
        html.Hr(),
        html.P("Fair Play Shield v2.0 — Sistema de detección de partidos amañados", className="text-muted text-center small"),
    ], className="mt-4"),

], fluid=True, className="bg-dark")


_cb_path = Path(__file__).resolve().parent / "callbacks.py"
_cb_spec = _ilu.spec_from_file_location("callbacks", _cb_path)
_cb_mod = _ilu.module_from_spec(_cb_spec)
_cb_spec.loader.exec_module(_cb_mod)
_cb_mod.register_callbacks(
    app, scores_df, leagues_df, el_df,
    ALERT_COLORS, ALERT_ICONS, ALERT_LABELS, FLAG_COLS,
    MODELS_LOADED, scaler, iso_forest, rf_model, lr_model, feature_cols,
)


if __name__ == "__main__":
    print("\n🛡️  Fair Play Shield Dashboard v2")
    print("=" * 40)
    print(f"Datos: {len(scores_df)} partidos scored")
    print(f"Ligas: {len(_leagues)}")
    print(f"Temporadas: {len(_seasons)}")
    print(f"Alertas altas: {(scores_df['alert_level'] == 'high_alert').sum()}")
    print(f"\nAbriendo en http://localhost:8050")
    print("=" * 40)
    app.run(debug=False, host="0.0.0.0", port=8050)
