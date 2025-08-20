from __future__ import annotations
import os, json
from datetime import datetime

import requests
import polars as pl
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from include.lib.weather_transform import to_df
from include.lib.s3_client import get_s3
from include.lib.pg import pg_conn

DEFAULT_ARGS = {"owner": "data-eng", "retries": 1}

def _fetch_open_meteo_json() -> str:
    """Busca JSON da Open-Meteo (sem API key) e já anexa metadados."""
    base = os.getenv("OPEN_METEO_BASE", "https://api.open-meteo.com/v1/forecast")
    lat = os.getenv("OPEN_METEO_LAT", "-23.5505")
    lon = os.getenv("OPEN_METEO_LON", "-46.6333")
    params = (
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=UTC"
    )
    url = base + params
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    payload = r.json()
    payload["_meta"] = {
        "lat": lat,
        "lon": lon,
        "ingested_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    return json.dumps(payload)

@dag(
    dag_id="weather_hourly_pipeline",
    default_args=DEFAULT_ARGS,
    schedule="@hourly",
    start_date=datetime(2025, 8, 1),
    catchup=False,
    tags=["weather", "polars", "minio", "postgres", "dbt"],
)
def weather_hourly_pipeline():

    @task
    def fetch_weather() -> str:
        """Task normal de extração."""
        return _fetch_open_meteo_json()

    @task
    def transform_and_store(raw: str | None = None) -> dict:
        """
        - Quando rodada no DAG: recebe `raw` via XCom (string JSON).
        - Quando rodada isolada via `tasks test`: `raw` será None; buscamos da API.
        """
        if raw is None:
            raw = _fetch_open_meteo_json()

        payload = json.loads(raw)
        df: pl.DataFrame = to_df(payload)
        if df.is_empty():
            return {"rows": 0}

        # partição por data (YYYY-MM-DD) com base na coluna time
        date_str = df.select(pl.col("time").dt.date().min()).item().isoformat()

        # grava Parquet local
        local_dir = "/opt/airflow/data/parquet_weather"
        os.makedirs(local_dir, exist_ok=True)
        local_path = f"{local_dir}/weather_{date_str}.parquet"
        df.write_parquet(local_path, compression="zstd")

        # envia para MinIO
        s3, bucket = get_s3()
        key = f"weather/date={date_str}/weather_{date_str}.parquet"
        with open(local_path, "rb") as f:
            s3.upload_fileobj(f, bucket, key)

        return {"date": date_str, "parquet": local_path, "s3_key": key, "rows": df.height}

    @task
    def load_postgres(meta: dict):
        local_path = meta["parquet"]
        df = pl.read_parquet(local_path)

        # pega o menor dia do batch (um valor só)
        date_val = df.select(pl.col("time").dt.date().min()).item()

        with pg_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS public.weather_hourly(
                    time timestamptz,
                    temperature_2m double precision,
                    relative_humidity_2m double precision,
                    ingested_at timestamptz
                );
            """)

            # upsert simples por dia (delete + insert)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.weather_hourly WHERE time::date = %s;", (date_val,))
                rows = [tuple(r) for r in df.select(
                    ["time","temperature_2m","relative_humidity_2m","ingested_at"]
                ).iter_rows()]
                cur.executemany(
                    "INSERT INTO public.weather_hourly(time,temperature_2m,relative_humidity_2m,ingested_at) "
                    "VALUES (%s,%s,%s,%s)",
                    rows
                )
            conn.commit()
        return {"rows": len(rows)}


    # (Opcional) roda dbt após o load (se houver projeto dbt montado)
    dbt_run = BashOperator(
        task_id="dbt_run_weather",
        bash_command="dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt/profiles --exclude stg_fx_rates fx_top10_daily",
        env=os.environ.copy(),
    )

    payload = fetch_weather()
    meta = transform_and_store(payload)
    loaded = load_postgres(meta)
    loaded >> dbt_run

weather_hourly_pipeline()
