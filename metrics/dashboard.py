import argparse
import sqlite3
from pathlib import Path

import dash
import pandas as pd
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output


def load_data(db_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    conn = sqlite3.connect(db_path)
    df_basecalled_ = pd.read_sql("SELECT * FROM basecalled_reads", conn)
    df_classified_ = pd.read_sql("SELECT * FROM classified_reads", conn)
    conn.close()
    return df_basecalled_, df_classified_


def create_app(db_path):
    app = dash.Dash(__name__)
    app.title = "Real-Time Monitoring"

    app.layout = html.Div([
        html.H1("Real-Time Monitoring"),

        dcc.Interval(id='interval-component', interval=5 * 1000, n_intervals=0),

        dcc.Graph(id='area-chart'),

        html.H2("Total Basecalled Reads by Final Class"),
        dash_table.DataTable(
            id='basecalled-table',
            columns=[
                {'name': 'Final Class', 'id': 'final_class'},
                {'name': 'Total Bases', 'id': 'total_bases'},
                {'name': 'Number of Reads', 'id': 'read_count'}
            ],
            style_cell={'textAlign': 'center'},
            style_header={'fontWeight': 'bold'},
        ),

        html.H2("Real-Time Read Fragments"),
        dash_table.DataTable(
            id='classified-table',
            columns=[
                {'name': 'Inferred Class', 'id': 'inferred_class'},
                {'name': 'Count', 'id': 'count'},
            ],
            style_cell={'textAlign': 'center'},
            style_header={'fontWeight': 'bold'},
        ),
        dash_table.DataTable(
            id='classified-total-table',
            columns=[
                {'name': 'Status', 'id': 'status'},
                {'name': 'Count', 'id': 'count'},
            ],
            style_cell={'textAlign': 'center'},
            style_header={'fontWeight': 'bold'},
        ),
    ], style={'width': '90%', 'margin': 'auto'})

    @app.callback(
        Output('area-chart','figure'),
        Output('basecalled-table','data'),
        Output('classified-table','data'),
        Output('classified-total-table', 'data'),
        Input('interval-component','n_intervals')
    )
    def update_dashboard(n_intervals: int):
        df_basecalled, df_classified = load_data(db_path)
        df_classified['timestamp'] = pd.to_datetime(df_classified['timestamp'], format='mixed')
        df_basecalled['timestamp'] = pd.to_datetime(df_basecalled['timestamp'], format='mixed')

        df_filtered = df_basecalled[df_basecalled['final_class'].notna()]
        pivot = df_filtered.pivot_table(
            index=df_filtered.index,
            columns='final_class',
            values='length',
            aggfunc='sum',
            fill_value=0
        )
        cum  = pivot.cumsum(axis=0)
        prop = cum.div(cum.sum(axis=1), axis=0)
        area_fig = {
            'data': [
                {
                  'x': prop.index,
                  'y': prop[col],
                  'type': 'scatter',
                  'mode': 'none',
                  'stackgroup': 'one',
                  'name': str(col)
                }
                for col in prop.columns
            ],
            'layout': {
                'title': 'Proportion of Basecalled Bases Over Time',
                'xaxis': {'title': 'Record Index'},
                'yaxis': {'title': 'Proportion'}
            }
        }

        df_basecalled_filled = df_basecalled.assign(final_class=df_basecalled["final_class"].fillna("unclassified"))
        final_class_stats = (
            df_basecalled_filled
            .groupby("final_class", as_index=False)
            .agg(
                total_bases=("length", "sum"),
                read_count=("read_id", "count")
            )
        )
        base_data = final_class_stats.to_dict("records")

        df_latest = (
            df_classified
            .sort_values(by=['read_id', 'timestamp'])
            .groupby('read_id', as_index=False)
            .last()
        )

        df_final_classified = df_latest[df_latest['inferred_class'].notna()]
        class_breakdown = (
            df_final_classified
            .groupby("inferred_class", as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .to_dict("records")
        )

        classified = int(df_latest['inferred_class'].notna().sum())
        unclassified = int(df_latest['inferred_class'].isna().sum())
        status_breakdown = [
            {'status': 'Classified', 'count': classified},
            {'status': 'Unclassified', 'count': unclassified},
        ]

        return area_fig, base_data, class_breakdown, status_breakdown

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="minster frontend")
    parser.add_argument('--db-path', type=Path, required=True)
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8050)
    args = parser.parse_args()

    app_ = create_app(str(args.db_path))
    app_.run(debug=True, host=args.host, port=args.port)
