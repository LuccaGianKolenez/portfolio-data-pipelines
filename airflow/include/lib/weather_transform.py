from __future__ import annotations
import polars as pl

def to_df(payload: dict) -> pl.DataFrame:
    """
    Converte o payload do Open-Meteo em DF longo com:
      time (Datetime), temperature_2m, relative_humidity_2m, lat, lon, ingested_at
    """
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    rhs   = hourly.get("relative_humidity_2m") or []

    lat = (payload.get("_meta") or {}).get("lat")
    lon = (payload.get("_meta") or {}).get("lon")
    ing = (payload.get("_meta") or {}).get("ingested_at")

    if not times:
        return pl.DataFrame(schema={
            "time": pl.Datetime, "temperature_2m": pl.Float64,
            "relative_humidity_2m": pl.Float64, "lat": pl.Utf8,
            "lon": pl.Utf8, "ingested_at": pl.Datetime
        })

    df = pl.DataFrame(
        {
            "time": times,
            "temperature_2m": temps,
            "relative_humidity_2m": rhs,
        }
    ).with_columns(
        pl.col("time").str.strptime(pl.Datetime, strict=False),
        pl.lit(lat).alias("lat"),
        pl.lit(lon).alias("lon"),
        pl.lit(ing).str.strptime(pl.Datetime, strict=False).alias("ingested_at"),
    )
    return df
