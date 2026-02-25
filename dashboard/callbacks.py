from dash import Input, Output, html
import dash_bootstrap_components as dbc
import pandas as pd


def register_callbacks(
    app, scores_df, leagues_df, el_df,
    ALERT_COLORS, ALERT_ICONS, ALERT_LABELS, FLAG_COLS,
    MODELS_LOADED, scaler, iso_forest, rf_model, lr_model, feature_cols,
):

    def _apply_filters(df, leagues, seasons, levels, team_search):
        if leagues:
            df = df[df["league_name"].isin(leagues)]
        if seasons:
            df = df[df["season"].isin(seasons)]
        if levels:
            df = df[df["alert_level"].isin(levels)]
        if team_search and len(team_search) >= 2:
            q = team_search.lower()
            mask = (
                df["home_team"].str.lower().str.contains(q, na=False)
                | df["away_team"].str.lower().str.contains(q, na=False)
            )
            df = df[mask]
        return df

    def _prep_table_df(df):
        out = df.copy()
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        if "home_goals" in out.columns and "away_goals" in out.columns:
            out["score_display"] = (
                out["home_goals"].fillna("?").astype(str)
                + " - "
                + out["away_goals"].fillna("?").astype(str)
            )
        return out

    @app.callback(
        Output("data-table", "data"),
        Output("data-count", "children"),
        Input("data-league-filter", "value"),
        Input("data-season-filter", "value"),
        Input("data-level-filter", "value"),
        Input("data-team-search", "value"),
    )
    def update_data_table(leagues, seasons, levels, team_search):
        df = _apply_filters(scores_df.copy(), leagues, seasons, levels, team_search)
        df = df.sort_values("date", ascending=False)
        out = _prep_table_df(df)
        return out.to_dict("records"), f"{len(out):,} partidos"

    @app.callback(
        Output("data-league-filter", "value"),
        Output("data-season-filter", "value"),
        Output("data-level-filter", "value"),
        Output("data-team-search", "value"),
        Input("data-clear-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_data_filters(_):
        return None, None, None, ""

    @app.callback(
        Output("data-detail-panel", "children"),
        Input("data-table", "selected_rows"),
        Input("data-table", "data"),
    )
    def show_match_detail(selected_rows, data):
        if not selected_rows or not data:
            return html.Div(
                html.P("Selecciona un partido en la tabla para ver el detalle.", className="text-muted small"),
                className="text-center py-3",
            )

        row = data[selected_rows[0]]
        level = row.get("alert_level", "normal")
        color = ALERT_COLORS.get(level, "#95a5a6")
        icon = ALERT_ICONS.get(level, "⚪")
        label = ALERT_LABELS.get(level, level)

        home = row.get("home_team", "?")
        away = row.get("away_team", "?")
        date_str = row.get("date", "?")
        mis = float(row.get("integrity_score", 0))

        scores_date_col = pd.to_datetime(scores_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        leagues_date_col = pd.to_datetime(leagues_df["date"], errors="coerce").dt.strftime("%Y-%m-%d")

        orig = scores_df[
            (scores_date_col == date_str)
            & (scores_df["home_team"] == home)
            & (scores_df["away_team"] == away)
        ]
        orig_league = leagues_df[
            (leagues_date_col == date_str)
            & (leagues_df["home_team"] == home)
            & (leagues_df["away_team"] == away)
        ]

        iso_score = rf_score = lr_score = None
        result = home_goals = away_goals = None
        ht_result = None
        if not orig.empty:
            r = orig.iloc[0]
            iso_score = r.get("iso_score", None)
            rf_score = r.get("rf_score", None)
            lr_score = r.get("lr_score", None)
            result = r.get("result", None)
            home_goals = r.get("home_goals", None)
            away_goals = r.get("away_goals", None)
            ht_result = r.get("ht_result", None)

        _FLAG_LABELS = {
            "flag_odds_movement": ("Movimiento de cuotas >15%", "Las cuotas se movieron significativamente antes del partido"),
            "flag_result_surprise": ("Resultado sorpresa", "El favorito según cuotas NO ganó (empate o victoria del no-favorito)"),
            "flag_streak_break": ("Ruptura de racha", "Se rompió una racha de 5+ victorias consecutivas"),
            "flag_goals_anomaly_home": ("Goles local anómalos", "Los goles del local están fuera del rango estadístico normal"),
            "flag_goals_anomaly_away": ("Goles visitante anómalos", "Los goles del visitante están fuera del rango estadístico normal"),
            "flag_ht_result_changed": ("Cambio de resultado HT→FT", "El resultado del descanso cambió en la segunda parte"),
            "flag_cards_anomaly": ("Tarjetas anómalas", "Número inusualmente alto de tarjetas"),
        }

        active_flags = []
        match_features = {}
        if not orig_league.empty:
            lr = orig_league.iloc[0]
            for col, (flag_label, flag_desc) in _FLAG_LABELS.items():
                val = lr.get(col, None)
                if val is not None and pd.notna(val) and int(val) == 1:
                    active_flags.append((flag_label, flag_desc))

            for fld in [
                "odds_movement_abs_max", "total_goals", "total_cards",
                "result_surprise", "ht_result_changed", "total_flags",
                "home_shots", "away_shots", "home_corners", "away_corners",
                "home_yellow_cards", "away_yellow_cards", "home_red_cards", "away_red_cards",
                "home_win_streak", "away_loss_streak",
            ]:
                v = lr.get(fld, None)
                if v is not None and pd.notna(v):
                    match_features[fld] = v

        def _row(lbl, val, highlight=False):
            cls = "text-warning fw-bold" if highlight else "text-light"
            return dbc.Row([
                dbc.Col(html.Small(lbl, className="text-muted"), width=8),
                dbc.Col(html.Small(str(val), className=cls), width=4),
            ], className="mb-1")

        def _bar(lbl, val, weight):
            if val is None:
                return html.Div()
            v = float(val)
            bc = "#e74c3c" if v >= 70 else "#e67e22" if v >= 50 else "#f39c12" if v >= 30 else "#27ae60"
            progress = dbc.Progress(
                children=[dbc.Progress(value=v, bar=True, style={"backgroundColor": bc})],
                value=v, max=100, style={"height": "16px"},
            )
            return dbc.Row([
                dbc.Col(html.Small(lbl, className="text-muted"), width=5),
                dbc.Col(progress, width=5),
                dbc.Col(html.Small(f"{v:.0f}", className="text-light"), width=2),
            ], className="align-items-center mb-1")

        score_col = [
            html.H6("🧠 Scores por modelo", className="text-info mb-2"),
            _bar("Isolation Forest (×0.35)", iso_score, 0.35),
            _bar("Random Forest (×0.40)", rf_score, 0.40),
            _bar("Logistic Regression (×0.25)", lr_score, 0.25),
            html.Hr(className="my-2"),
            dbc.Row([
                dbc.Col(html.Small("MIS Final", className="text-muted"), width=5),
                dbc.Col(
                    dbc.Progress(
                        children=[dbc.Progress(value=mis, bar=True, style={"backgroundColor": color})],
                        value=mis, max=100, style={"height": "20px"},
                    ),
                    width=5,
                ),
                dbc.Col(html.Small(f"{mis:.1f}", className="fw-bold", style={"color": color}), width=2),
            ], className="align-items-center"),
        ]

        flags_col = [html.H6("🚩 Flags activados", className="text-warning mb-2")]
        if active_flags:
            for fl, desc in active_flags:
                flags_col.append(html.Div([
                    dbc.Badge(f"🚩 {fl}", color="warning", className="text-dark mb-1"),
                    html.P(desc, className="text-muted small mb-2 ms-1"),
                ]))
        else:
            flags_col.append(html.Div([
                html.P("Ningún flag binario activado.", className="text-success small mb-1"),
                html.P(
                    "El MIS alto proviene de patrones numéricos que los modelos aprendieron. "
                    "Revisa las métricas del partido →",
                    className="text-muted small",
                ),
            ]))

        mf = match_features
        stats_col = [html.H6("� Datos del partido", className="text-primary mb-2")]
        if home_goals is not None and away_goals is not None:
            ht_str = f"  (HT: {ht_result})" if ht_result else ""
            stats_col.append(_row("Resultado", f"{int(home_goals)}-{int(away_goals)} {result or ''}{ht_str}", False))
        if "total_goals" in mf:
            stats_col.append(_row("Goles totales", int(mf["total_goals"]), int(mf["total_goals"]) >= 5))
        if "odds_movement_abs_max" in mf:
            pct = float(mf["odds_movement_abs_max"])
            stats_col.append(_row("Mov. cuotas (abs max)", f"{pct:.1%}", pct > 0.15))
        if "result_surprise" in mf:
            stats_col.append(_row("Favorito no ganó", "Sí" if int(mf["result_surprise"]) else "No", int(mf["result_surprise"]) == 1))
        if "ht_result_changed" in mf:
            stats_col.append(_row("Cambio resultado HT→FT", "Sí" if int(mf["ht_result_changed"]) else "No", int(mf["ht_result_changed"]) == 1))
        if "total_cards" in mf:
            stats_col.append(_row("Tarjetas totales", int(mf["total_cards"]), int(mf["total_cards"]) >= 7))
        if "home_shots" in mf and "away_shots" in mf:
            stats_col.append(_row("Tiros (local/visit.)", f"{int(mf['home_shots'])}/{int(mf['away_shots'])}", False))
        if "home_corners" in mf and "away_corners" in mf:
            stats_col.append(_row("Córners (local/visit.)", f"{int(mf['home_corners'])}/{int(mf['away_corners'])}", False))
        if "home_win_streak" in mf:
            stats_col.append(_row("Racha local (victorias)", int(mf["home_win_streak"]), int(mf["home_win_streak"]) >= 5))
        if "total_flags" in mf:
            stats_col.append(_row("Total flags activados", int(mf["total_flags"]), int(mf["total_flags"]) >= 2))
        if len(stats_col) == 1:
            stats_col.append(html.P("Sin datos numéricos disponibles", className="text-muted small"))

        return dbc.Card([
            dbc.CardHeader([
                html.Span(f"{icon} ", style={"fontSize": "1.3rem"}),
                html.Strong(f"{home} vs {away}"),
                html.Span(f"  —  {date_str}", className="text-muted ms-2 small"),
                dbc.Badge(f"{label}  |  MIS: {mis:.1f}", className="ms-3", style={"backgroundColor": color}),
                html.Span(f"  {row.get('league_name', '')}  {row.get('season', '')}", className="text-muted ms-3 small"),
            ]),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(flags_col, width=4),
                    dbc.Col(stats_col, width=4),
                    dbc.Col(score_col, width=4),
                ]),
            ]),
        ], className="border mt-2", style={"borderColor": color, "borderWidth": "2px"})

