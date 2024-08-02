from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import sqlite3
import pandas as pd
import json
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
CORS(app, resources={r"/*": {"origins": "*"}})

def query_db(query, params=()):
    conn = sqlite3.connect('messages.db')
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def df_to_json(df):
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    return json.loads(df.to_json(orient='records', default_handler=str))

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('fetch_data')
def handle_fetch_data():
    try:
        messages_df = query_db('SELECT * FROM messages')
        telemetry_df = query_db('SELECT * FROM telemetry')
        positions_df = query_db('SELECT * FROM positions')
        environment_df = query_db('''
            SELECT e.*, n.long_name
            FROM environment e
            JOIN nodes n ON e.node_id = n.node_id
        ''')

        data = {
            'messages': df_to_json(messages_df),
            'telemetry': df_to_json(telemetry_df),
            'positions': df_to_json(positions_df),
            'environment': df_to_json(environment_df)
        }

        emit('update_data', json.dumps(data))
    except Exception as e:
        print(f"Error fetching data: {e}")
        emit('update_data', json.dumps({'error': 'Failed to fetch data'}))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
