import duckdb
import uuid
import os
from reflink import reflink

def direct_connect(config, db_name):
    if not db_name in config['databases']:
        raise ValueError(f"Database {db_name} not found in config")
    return duckdb.connect(config['databases'][db_name]['path'])

def get_schema_from_db(config, db_name):
    with direct_connect(config, db_name) as db:
        return db.execute(
            "SELECT table_name, array_agg(column_name) " \
            "FROM duckdb_columns() " \
            "WHERE NOT internal " \
            "GROUP BY table_name " \
            "ORDER BY table_name ASC"
        ).fetchall()

def get_schema_from_config(config, db_name):
    if not db_name in config['databases']:
        raise ValueError(f"Database {db_name} not found in config")
    return config['databases'][db_name]['schema']

def drop_column(db, schema, table_id, column_id):
    table_name = schema[table_id][0]
    column_name = schema[table_id][1][column_id]
    db.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")

def drop_table(db, schema, table_id):
    table_name = schema[table_id][0]
    db.execute(f"DROP TABLE {table_name}")

class safe_connect:
    """
    Context manager that creates a temporary copy of the database file and
    connects to it, ensuring that the original database file is not modified.
    The temporary copy is deleted after use.
    """

    def __init__(self, config, db_name):
        if not db_name in config['databases']:
            raise ValueError(f"Database {db_name} not found in config")
        self.src_path = os.path.expanduser(config['databases'][db_name]['path'])
        self.tmp_path = os.path.expanduser(f"{config['temp_dir']}/{uuid.uuid4()}.db")
        self.db = None

    def __enter__(self):
        # os.link(self.src_path, self.tmp_path)
        reflink(self.src_path, self.tmp_path)
        self.db = duckdb.connect(self.tmp_path)
        self.db.begin()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db != None:
            try:
                self.db.rollback()
                self.db.close()
            except:
                pass
            self.db = None
        if os.path.exists(self.tmp_path):
            os.remove(self.tmp_path)
