import dash
from dash import dcc, html, dash_table, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR

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


if __name__ == "__main__":
    print("\n🛡️  Fair Play Shield Dashboard")
    print("=" * 40)
    print(f"Datos: {len(scores_df)} partidos scored")
    print(f"Europa League: {len(el_df)} partidos")
    print(f"Alertas altas: {(scores_df['alert_level'] == 'high_alert').sum()}")
    print(f"\nAbriendo en http://localhost:8050")
    print("=" * 40)
    app.run(debug=False, host="0.0.0.0", port=8050)
