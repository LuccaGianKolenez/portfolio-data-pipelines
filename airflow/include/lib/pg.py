import os
import psycopg
from contextlib import contextmanager

@contextmanager
def pg_conn():
    host = os.getenv("POSTGRES_HOST", "postgres")
    db = os.getenv("POSTGRES_DB", "portfolio_data")
    user = os.getenv("POSTGRES_USER", "airflow")
    pwd = os.getenv("POSTGRES_PASSWORD", "airflow")
    port = int(os.getenv("POSTGRES_PORT_IN", "5432"))
    dsn = f"host={host} dbname={db} user={user} password={pwd} port={port}"
    with psycopg.connect(dsn) as conn:
        yield conn
