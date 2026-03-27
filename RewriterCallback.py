from contextlib import AbstractContextManager
from duckdb import DuckDBPyConnection

from flask import render_template
from flask_socketio import emit

import db_utils

from query_rewriting.demo_interface.demo_callable import DemoCallable # pyright: ignore[reportMissingImports]
from query_rewriting.demo_interface.phase1_statistics import Phase1Statistics # pyright: ignore[reportMissingImports]
from query_rewriting.demo_interface.phase2_statistics import Phase2Statistics # pyright: ignore[reportMissingImports]
from query_rewriting.demo_interface.phase3_statistics import Phase3Statistics # pyright: ignore[reportMissingImports]
from query_rewriting.demo_interface.phase4_statistics import Phase4Statistics # pyright: ignore[reportMissingImports]

def send_query_result(query, result, rewrite_id, query_id, row_limit):
    """
    Sends the result of a query through Socket.IO.
    Parameters:
    - query: The SQL query that was executed.
    - result: The result of the query execution, expected to be a list of rows, where the first row contains column names.
    - rewrite_id: The identifier of the rewrite configuration that produced this query, used to associate the result with the correct rewrite process in the UI.
    - query_id: The identifier for the specific query within its rewrite configuration, used to associate the result with the correct query in the UI.
    - row_limit: Limits the number of rows shown in the UI to the first and last 'row_limit' rows, to prevent overwhelming the UI with too much data.
                 In other words, if the result has more than 2*row_limit rows, it will show the first 'row_limit' rows, then a placeholder row indicating that some rows are omitted, and then the last 'row_limit' rows.
    """
    if len(result) >= 1:
        header = result[0]
        rows = result[1:]
        if len(result) > 2 * row_limit + 1:
            rows = result[1:row_limit + 1] + [['...' for _ in header]] + result[-row_limit:]
        html = render_template("result_display_table.html.j2", query=query, columns=header, rows=rows, rewrite_id=rewrite_id, query_id=query_id)
        emit('query_result', {'content': html, 'rewrite_id': rewrite_id, 'query_id': query_id})

def delete_from_db(db, deletions, schema):
    for deletion in deletions['columns']:
        db_utils.drop_column(db, schema, deletion['table'], deletion['column'])
    for deletion in deletions['tables']:
        db_utils.drop_table(db, schema, deletion)

class RewriterCallback(DemoCallable):
    def __init__(self, preview_count: int, rewrite_id: int, model, config, db_name, deletions):
        super().__init__()
        self.rewrite_id = rewrite_id
        self.preview_count = preview_count
        self.model = model
        self.config = config
        self.db_name = db_name
        self.deletions = deletions

    def __calculate_token_cost(self, input_tokens, output_tokens):
        inout_cost = (self.model['input_token_cost'] * 10_000 * input_tokens) // 1_000_000
        output_cost = (self.model['output_token_cost'] * 10_000 * output_tokens) // 1_000_000
        return (inout_cost + output_cost) / 10_000
    
    def __render_success(self, template, statistics):
        statistics.token_cost = self.__calculate_token_cost(statistics.input_tokens, statistics.output_tokens)
        return render_template(template, stats=statistics, id=self.rewrite_id, preview_count=self.preview_count)

    def __render_error(self, message):
        return render_template("inqure_status_abort.html.j2", status=message)

    def first_phase_done(self, statistics1: Phase1Statistics):
        html = self.__render_success("inqure_status_filter_finished.html.j2", statistics1)
        emit('phase_done', {'phase': 'table-filter', 'rewrite_id': self.rewrite_id, 'status': html})

    def second_phase_done(self, statistics2: Phase2Statistics):
        html = self.__render_success("inqure_status_rewriter_finished.html.j2", statistics2)
        emit('phase_done', {'phase': 'rewriter', 'rewrite_id': self.rewrite_id, 'status': html})

    def third_phase_done(self, statistics3: Phase3Statistics):
        html = self.__render_success("inqure_status_ranker_finished.html.j2", statistics3)
        emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': html})

    def fourth_phase_done(self, statistics4: Phase4Statistics):
        html = self.__render_success("inqure_status_corrector_finished.html.j2", statistics4)
        emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': html})
        for query_id, (result, query) in enumerate(zip(statistics4.results_of_final_rewrites, statistics4.final_rewrites)):
            send_query_result(query, result, self.rewrite_id, query_id, self.config['query_preview_rows'])

    def first_phase_error(self, error_message: str, statistics1: Phase1Statistics):
        # render the statistics for P1 as normal
        html = self.__render_success("inqure_status_filter_finished.html.j2", statistics1)
        emit('phase_done', {'phase': 'table-filter', 'rewrite_id': self.rewrite_id, 'status': html})
        # then report this error as the P2 abort condition
        this_error = self.__render_error(error_message)
        emit('phase_done', {'phase': 'rewriter', 'rewrite_id': self.rewrite_id, 'status': this_error})
        # then report the later stages as aborted for a previosu error
        future_error = self.__render_error("Error in Previous Phase")
        emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': future_error})
        emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': future_error})

    def second_phase_error(self, error_message: str, statistics2: Phase2Statistics):
        # render the statistics for P2 as normal
        html = self.__render_success("inqure_status_rewriter_finished.html.j2", statistics2)
        emit('phase_done', {'phase': 'rewriter', 'rewrite_id': self.rewrite_id, 'status': html})
        # then report this error as the P3 abort condition
        this_error = self.__render_error(error_message)
        emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': this_error})
        # then report the later stages as aborted for a previous error
        future_error = self.__render_error("Error in Previous Phase")
        emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': future_error})

    def third_phase_error(self, error_message: str, statistics3: Phase3Statistics):
        if len(statistics3.ranked_queries) == 0:
            # Something prevented us from producing a ranking, report it as an error for this phase
            this_error = self.__render_error(error_message)
            emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': this_error})
            # then report the later stages as aborted for a previous error
            future_error = self.__render_error("Error in Previous Phase")
            emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': future_error})
        else:
            # There is a ranking for this phase, report the results as usual
            html = self.__render_success("inqure_status_ranker_finished.html.j2", statistics3)
            emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': html})
            # then report the error as the P4 abort condition
            this_error = self.__render_error(error_message)
            emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': this_error})

    def parameter_check_successful(self):
        status_info = render_template("inqure_status_panel.html.j2", id=self.rewrite_id)
        emit('rewriter_started', status_info)

    def parameter_check_failed(self, error_msg: str):
        #TODO a separate row with just one error message would be cleaner
        error = self.__render_error(error_msg)
        emit('phase_done', {'phase': 'table-filter', 'rewrite_id': self.rewrite_id, 'status': error})
        emit('phase_done', {'phase': 'rewriter', 'rewrite_id': self.rewrite_id, 'status': error})
        emit('phase_done', {'phase': 'ranker', 'rewrite_id': self.rewrite_id, 'status': error})
        emit('phase_done', {'phase': 'query-corrector', 'rewrite_id': self.rewrite_id, 'status': error})

    def get_ta_context(self) -> AbstractContextManager[DuckDBPyConnection]:
        class DeletionContextManager(db_utils.safe_connect):
            def __init__(self, config, db_name, deletions):
                super().__init__(config, db_name)
                self.deletions = deletions
                self.schema = db_utils.get_schema_from_config(config, db_name)

            def __enter__(self):
                db = super().__enter__()
                delete_from_db(db, self.deletions, self.schema)
                return db
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                super().__exit__(exc_type, exc_val, exc_tb)
        
        return DeletionContextManager(self.config, self.db_name, self.deletions)