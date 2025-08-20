{{ config(materialized='view', tags=['weather']) }}

select
  time                          as time_utc,
  date(time)                    as date_utc,
  temperature_2m,
  relative_humidity_2m
from {{ source('public', 'weather_hourly') }}
