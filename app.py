from flask import Flask, render_template
from flask_socketio import SocketIO
import json
import sys
from sqlparse import format as sql_format

import db_utils
    
def load_config():
    config = json.load(open('config.json'))
    config['databases']['spider']['schema'] = db_utils.get_schema_from_db(config, 'spider')
    config['databases']['imdb']['schema'] = db_utils.get_schema_from_db(config, 'imdb')
    return config

def sql(query):
    return sql_format(query, reindent=True, keyword_case='upper', identifier_case='lower', use_space_around_operators=True, compact=True)

app = Flask(__name__)
app.jinja_env.filters['zip'] = zip
app.jinja_env.filters['sql'] = sql
socketio = SocketIO(app, cors_allowed_origins='*') #TODO: restrict to localhost
config = load_config()

sys.path.append(config['rewriter_path'])
import query_rewriting.demo_interface.demo_main as inqure # pyright: ignore[reportMissingImports]
from query_rewriting.utilities.duckdb_functions import get_result_with_column_names # pyright: ignore[reportMissingImports]
from RewriterCallback import RewriterCallback, send_query_result

@app.route('/')
def hello():
    return render_template("index.html.j2", spider=config['databases']['spider'], imdb=config['databases']['imdb'], defaults=config['rewriter_defaults'])

@socketio.on('original_query_selected')
def original_query_selected(data):
    dataset = data['dataset']
    query = data['query']
    with db_utils.safe_connect(config, dataset) as db:
        try:
            db.execute(query)
            result = get_result_with_column_names(db)
            send_query_result(query, result, 'original', 'original', config['query_preview_rows'])
        except Exception as e:
            # if the original query is not executable, we just don't show any result
            print(f"Original Query is not executable on {dataset}: {query}\nError: {e}")

@socketio.on('run_rewriter')
def run_rewriter(data):
    #TODO If we ever deploy this non-locally, we need to validate the input data!
    schema = db_utils.get_schema_from_config(config, data['dataset'])
    model = [m for m in config['rewriter_defaults']['supported_models'] if m['key'] == data['settings']['model']][0]
    inqure.run_rewriter_for_ui(
        data['query'],
        model['key'],
        data['settings']['alternativeQueries'],
        data['settings']['additionalQueries'],
        data['settings']['table_filter'],
        data['settings']['rewriter'],
        data['settings']['ranker'],
        1,
        data['settings']['intent_similarity'],
        config['databases'][data['dataset']]['has_prefixes'],
        data['settings']['embeddingThreshold'],
        data['settings']['sllmSelectivity'],
        data['settings']['cllmThreshold'],
        data['settings']['mmrLambda'],
        data['settings']['lmmsPackageSize'],
        data['settings']['correctionTries'],
        RewriterCallback(config['rewrite_preview_count'], data['id'], model, config, data['dataset'], data['deletions'])
    )

if __name__ == '__main__':
    socketio.run(app, host='localhost', port=5000)
