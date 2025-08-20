{{ config(materialized='view', tags=['weather']) }}

with s as (select * from {{ ref('stg_weather_hourly') }})
select
  date_utc,
  avg(temperature_2m)      as avg_temp_c,
  max(temperature_2m)      as max_temp_c,
  min(temperature_2m)      as min_temp_c,
  avg(relative_humidity_2m) as avg_rh
from s
group by 1
order by 1
