import os
import argparse
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
import time
import json

# TODO works only for 6 figures right now
# TODO be able to name plants (sensors)
# TODO there is a BUG because the number of time points does not match the number of sensor points now that we are restricting the number of points!!!

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--dash_ip", default="192.168.1.38")
parser.add_argument("--rundir", default="/home/moist/moist_rundir")
parser.add_argument("--db_platform", default="mariadb")
parser.add_argument("--db_host", default="localhost")
parser.add_argument("--db_port", default=3306)
parser.add_argument("--db_user", default="moist")
parser.add_argument("--db_password", default="moisture")
parser.add_argument("--db_database", default="moist")
args = parser.parse_args()

LIMIT_HIGH = 580
LIMIT_AIR = 520
LIMIT_DRY = 360
LIMIT_WET = 277
LIMIT_LOW = 220

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log(s):
    print(f"{now()}    {s}")


if args.db_platform == "mariadb":
    from sqlalchemy import create_engine


def load_params_():
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "r") as f:
        params = json.load(f)
    return params


def save_params(params):
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "w") as f:
        json.dump(params, f, indent=4)


def db_get_measurements_mariadb(minutes):
    engine = create_engine(f"mariadb+mariadbconnector://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_database}")
    # engine = create_engine(f"mariadb:///?User={args.db_user}&;Password={args.db_password}&Database={args.db_database}&Server={args.db_host}&Port={args.db_port}")
    dt_start = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    dt_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output_data = pd.read_sql(f"SELECT * FROM moist_measurements WHERE time BETWEEN '{dt_start}' and '{dt_end}'", engine)
    return output_data


def fetch_db(minutes):
    log("retrieving up-to-date db data")
    # the real function
    output_data, sensor_columns = None, []
    if args.db_platform == "mariadb":
        output_data = db_get_measurements_mariadb(minutes=minutes)
    # format correctly
    if output_data is not None:
        output_data.time = pd.to_datetime(output_data.time)
        sensor_columns = [col for col in output_data.columns.tolist() if col[:7] == "sensor_"]
        output_data = output_data.astype({col: float for col in sensor_columns})
    else:
        print(f"unable to retrieve db data: unknown {args.db_platform}")
    return output_data, sensor_columns


def get_db_subset(db_extract: pd.DataFrame, events: list = ("entry", )):
    return db_extract[db_extract.event.isin(events)]


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


def remap_value_by_state(val, state):
    if state == "Air":
        if val > LIMIT_AIR:
            return val
        return np.nan
    if state == "Too dry":
        if (val > LIMIT_DRY) and (val <= LIMIT_AIR):
            return val
        return np.nan
    if state == "OK":
        if (val > LIMIT_WET) and (val <= LIMIT_DRY):
            return val
        return np.nan
    if state == "Too wet":
        if val <= LIMIT_WET:
            return val
        return np.nan
    return np.nan


def draw_main_grap(time, sensor_values, smooth_alpha, nvalues_value, fig_name):
    if len(time) == 0:
        return None
    if not np.isfinite(sensor_values).any():
        return None

    fig = make_subplots()

    if smooth_alpha < 1:
        # smooth using the ewm method
        sensor_values = sensor_values.ewm(alpha=smooth_alpha).mean()

    if nvalues_value < len(sensor_values):
        # to interpolate we first need to convert times to raw seconds
        time_in_seconds = (time - time.min()) / timedelta(seconds=1)
        new_time_in_seconds = np.linspace(time_in_seconds.min(), time_in_seconds.max(), num=nvalues_value)
        new_sensor_values = np.interp(
            x=new_time_in_seconds,
            xp=time_in_seconds, fp=sensor_values)
        sensor_values = pd.Series(new_sensor_values, name=sensor_values.name)
        new_time_in_seconds = [time.min() + timedelta(seconds=new_t) for new_t in new_time_in_seconds]
        time = pd.Series(new_time_in_seconds, name=time.name)

    # Sensor measures
    for state, state_color in zip(["Air", "Too dry", "OK", "Too wet"], ["#cccccc", "#ff0000", "#00ff00", "#0000ff"]):
        sensor_values_remapped = sensor_values.map(lambda val: remap_value_by_state(val, state=state))
        sensor_values_remapped[sensor_values_remapped.isna() & (~sensor_values_remapped.shift().isna())] = sensor_values[sensor_values_remapped.isna() & (~sensor_values_remapped.shift().isna())]
        fig.add_trace(
            go.Scatter(x=time, y=sensor_values_remapped, name=state, mode='lines', line=dict(width=1, color=state_color))
        )

    # Set x-axis title
    fig.update_xaxes(title_text="Time")

    # get first y axis range
    upper_y_limit = max(LIMIT_HIGH, max(sensor_values))
    lower_y_limit = min(LIMIT_LOW, min(sensor_values))

    # Set y-axes titles
    fig.update_yaxes(title_text="Humidity (raw)", range=(lower_y_limit, upper_y_limit))

    fig.update_layout(title=dict(text=fig_name), template="plotly_white", margin=dict(t=50, b=50))

    return fig


CONTENT_STYLE = {
    "margin-left": "2rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}

content = html.Div(
    [
        html.Div([
            html.Div([
                html.P("Display last (min)", style={"display": "inline-block"}),
                dcc.Input(min=1, max=21600, step=1, value=10800, id='display-length-slider', type="number",
                          style={"display": "inline-block"}),
                dcc.Slider(0, 4, 0.01,
                    id='smooth-slider',
                    marks={i: '{}'.format(10 ** (-i)) for i in range(5)},
                    value=0,
                    updatemode='drag'
                ),
                dcc.Slider(2, 4, 1,
                    id='nvaluesdisplay-slider',
                    marks={i: '{}'.format(10 ** i) for i in range(2, 5)},
                    value=4,
                    updatemode='drag'
                ),
                html.Button('Refresh', id='refresh-button', style={"display": "inline-block"}, n_clicks=0),
                html.Div(id='refresh-button-output'),
            ]),
            html.Hr(),
            html.Div([dcc.Graph(id='sensor_0')], style={'display': 'inline-block'}),
            html.Div([dcc.Graph(id='sensor_1')], style={'display': 'inline-block'}),
            html.Div([dcc.Graph(id='sensor_2')], style={'display': 'inline-block'}),
            # html.Div([dcc.Graph(id='sensor_3')], style={'display': 'inline-block'}),
            # html.Div([dcc.Graph(id='sensor_4')], style={'display': 'inline-block'}),
            # html.Div([dcc.Graph(id='sensor_5')], style={'display': 'inline-block'}),
        ], id='page-div', style={'width': '100%', 'display': 'block'}),
    ], id="page-content", style=CONTENT_STYLE
)

app.layout = html.Div(
    html.Div([
        content,
    ], id='main-div')
)


@callback(
    Output('sensor_0', 'figure'),
    Output('sensor_1', 'figure'),
    Output('sensor_2', 'figure'),
    Output('sensor_3', 'figure'),
    Output('sensor_4', 'figure'),
    Output('sensor_5', 'figure'),
    Output('refresh-button-output', 'children'),
    Input('refresh-button', 'n_clicks'),
    State ('display-length-slider', 'value'),
    State ('smooth-slider', 'value'),
    State ('nvaluesdisplay-slider', 'value'),
)
def callback_update_from_db(n_clicks, param_minutes, smooth_alpha, nvalues_value):
    # extract db
    fetch_start = time.time()

    db_extract, sensor_columns = fetch_db(param_minutes)
    db_extract_entries = get_db_subset(db_extract=db_extract, events=["entry",])
    log(f"refreshing with {db_extract_entries.shape=}")

    computes_start = time.time()

    # translate values
    smooth_alpha = 10 ** (-smooth_alpha)
    nvalues_value = 10 ** nvalues_value

    # figs
    sensor_0_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[0]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Boston Fern")
    sensor_1_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[1]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Palm tree")
    sensor_2_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[2]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Lutheria")
    # sensor_3_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[3]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Sensor 4")
    # sensor_4_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[4]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Sensor 5")
    # sensor_5_fig = draw_main_grap(time=db_extract_entries.time, sensor_values=db_extract_entries[sensor_columns[5]], smooth_alpha=smooth_alpha, nvalues_value=nvalues_value, fig_name="Sensor 6")

    end_time = time.time()

    times_output = f"fetched in {(end_time - computes_start):.3f} seconds, computed in {(computes_start - fetch_start):.3f} seconds"

    return (
        sensor_0_fig,
        sensor_1_fig,
        sensor_2_fig,
        # sensor_3_fig,
        # sensor_4_fig,
        # sensor_5_fig,
        times_output,
        )


if __name__ == '__main__':
    app.run(host=args.dash_ip)
