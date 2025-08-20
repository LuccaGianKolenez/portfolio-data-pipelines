# Portfolio Data Pipelines

Pipeline de dados **end-to-end** com Airflow + Python (Polars) + MinIO (S3 compatível) + Postgres + dbt.

Inclui um DAG que:
1) **Busca** previsão **horária** (Open-Meteo) para um par LAT/LON,
2) **Transforma** e salva como **Parquet** no container e envia para **S3/MinIO**,
3) **Carrega** os dados brutos em **Postgres** (`public.weather_hourly`),
4) **Modela** com **dbt** em duas *views*: `public_stg.stg_weather_hourly` e `public_marts.weather_daily`.

> Dentro dos containers o host do Postgres é `postgres` (porta 5432).  
> **Fora** dos containers (se usar `psql`/dbt local), use `127.0.0.1` na **porta 5433**.

---

## Estrutura

```
.
├─ airflow/
│  ├─ dags/weather_hourly_pipeline.py
│  └─ include/lib/{weather_transform.py, s3_client.py, pg.py}
├─ dbt/
│  ├─ dbt_project.yml
│  ├─ profiles/profiles.yml
│  └─ models/
│     ├─ staging/stg_weather_hourly.sql
│     └─ marts/weather_daily.sql
├─ docker-compose.yml
├─ .env.example
└─ requirements.txt
```

---

## TL;DR (rodar tudo)

1) **Crie o arquivo `.env`**:
```bash
cp .env.example .env
```

2) **Suba os serviços**:
```bash
docker compose up -d
```

3) **(Primeiro acesso) Crie um usuário no Airflow**:
```bash
docker compose exec -T airflow-webserver   airflow users create   --username admin --firstname Admin --lastname User   --role Admin --email admin@example.com --password admin
```

4) **Crie o bucket no MinIO** (uma vez):
- Acesse http://localhost:9001 (console)
- Faça login com `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` do `.env`
- Crie o bucket com o nome de `MINIO_BUCKET` do `.env`

5) **Teste o DAG completo para uma data**:
```bash
docker compose exec -T airflow-webserver   airflow dags test weather_hourly_pipeline 2025-08-20
```

6) **Rode os modelos dbt (no container)**:
```bash
docker compose exec -T airflow-webserver bash -lc 'dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt/profiles --select tag:weather'
```

7) **Cheque os dados**:
```bash
# Arquivos Parquet gravados:
docker compose exec -T airflow-webserver bash -lc 'ls -lah /opt/airflow/data/parquet_weather'

# Contagem na tabela bruta (no host, fora do Docker):
psql "host=127.0.0.1 port=5433 dbname=portfolio_data user=airflow password=airflow"   -c "SELECT COUNT(*) FROM public.weather_hourly;"
```

**UIs**
- Airflow: http://localhost:8080
- MinIO Console: http://localhost:9001

---

## Variáveis (.env)

Ajuste conforme necessário (baseado em `.env.example`):

- **Localização** (para a API de clima):
  - `LATITUDE`, `LONGITUDE`
- **Postgres**
  - `POSTGRES_DB=portfolio_data`
  - `POSTGRES_USER=airflow`
  - `POSTGRES_PASSWORD=airflow`
  - Porta interna 5432 (a externa está mapeada para 5433)
- **MinIO**
  - `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`
  - `MINIO_API_PORT=9000`, `MINIO_CONSOLE_PORT=9001`
  - `MINIO_BUCKET=portfolio-bucket`
- **Credenciais S3 usadas no Airflow**
  - O compose exporta `AWS_ACCESS_KEY_ID=${MINIO_ROOT_USER}` e `AWS_SECRET_ACCESS_KEY=${MINIO_ROOT_PASSWORD}` para os containers do Airflow.

> O endpoint S3 **dentro** dos containers é `http://minio:9000`.  
> No navegador você usa `http://localhost:9001` (console).

---

## Comandos úteis

### Rodar tarefas isoladas (debug)
```bash
# 1. Buscar dados (API)
docker compose exec -T airflow-webserver   airflow tasks test weather_hourly_pipeline fetch_weather 2025-08-20

# 2. Transformar e salvar (Parquet + upload S3)
docker compose exec -T airflow-webserver   airflow tasks test weather_hourly_pipeline transform_and_store 2025-08-20

# 3. Carregar no Postgres
docker compose exec -T airflow-webserver   airflow tasks test weather_hourly_pipeline load_postgres 2025-08-20
```

### Rodar o DAG completo (uma data)
```bash
docker compose exec -T airflow-webserver   airflow dags test weather_hourly_pipeline 2025-08-20
```

### dbt **dentro** do container
```bash
docker compose exec -T airflow-webserver bash -lc 'dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt/profiles --select tag:weather'
```

### dbt **fora** do Docker (target `local`)
```bash
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5433
export POSTGRES_DB=portfolio_data
export POSTGRES_USER=airflow
export POSTGRES_PASSWORD=airflow

dbt debug --project-dir ./dbt --profiles-dir ./dbt/profiles --target local
dbt run   --project-dir ./dbt --profiles-dir ./dbt/profiles --target local --select tag:weather
dbt test  --project-dir ./dbt --profiles-dir ./dbt/profiles --target local --select tag:weather
```

---

## Esquema & modelos

- **Base:** `public.weather_hourly` (tabela de ingestão)
- **Staging (dbt):** `public_stg.stg_weather_hourly` (view)
- **Marts (dbt):** `public_marts.weather_daily` (view)

---

## Consultas rápidas

```bash
psql "host=127.0.0.1 port=5433 dbname=portfolio_data user=airflow password=airflow"   -c "SELECT * FROM public_stg.stg_weather_hourly LIMIT 5;"

psql "host=127.0.0.1 port=5433 dbname=portfolio_data user=airflow password=airflow"   -c "SELECT * FROM public_marts.weather_daily ORDER BY day DESC LIMIT 5;"
```

---

## Troubleshooting

- **dbt local erro:** `could not translate host name "postgres"`  
  ➜ use o **target `local`** (host `127.0.0.1`, porta `5433`) e exporte as variáveis `POSTGRES_*`.

- **dbt local erro:** `Env var required but not provided: 'POSTGRES_USER'`  
  ➜ exporte todas as variáveis `POSTGRES_*` (veja bloco de dbt local).

- **Airflow/Polars:** se for extrair um escalar de um `DataFrame`, garanta shape `(1,1)` antes de chamar `.item()`.  
  (ex.: agregue com `min()`/`max()` quando quiser apenas a data do *batch*.)

- **Upload S3 falha:** confirme credenciais e se o **bucket existe** no MinIO console.

---

## Desenvolvimento

- Docker & Docker Compose
- Python 3.12+ (se for rodar dbt localmente)
- Dependências Python do Airflow estão em `requirements.txt` e são instaladas na build.

## Próximas melhorias (roadmap)

### Confiabilidade & Operação
- Backfill fácil: tarefa dedicada no DAG para reprocessar intervalos de datas (`start_date…end_date`) com idempotência.
- Retry/backoff inteligente na chamada da API (exponencial + *jitter*) e *circuit breaker* para quedas prolongadas.
- **Schedule** & **SLAs** no Airflow com alertas de atraso (*SLA miss*) e notificação no Slack/Email.

### Qualidade de Dados
- Mais testes dbt: `accepted_values` (faixas válidas), `relationships` (quando houver FK), `freshness` em *sources*.
- Regras de *sanity* na transformação (ex.: `-80°C ≤ temp ≤ 60°C`; `0–100% RH`) convertidas em *expectations* (Great Expectations ou `dbt-utils` tests).
- Observabilidade de dados: métricas de completude, duplicidade e latência publicadas (Prometheus/Grafana).

### Modelagem & Features
- Novos campos do Open-Meteo: precipitação, vento, cobertura de nuvens, pressão.
- Métricas derivadas: *feels_like*/índice de calor, *dew_point*, amplitude diária, *flags* de extremos.
- Camada *marts* incremental (`materialized='table'` + `is_incremental()` para janelas diárias).

### Armazenamento em S3/MinIO
- Particionamento Hive consistente (`weather/date=YYYY-MM-DD/...`) com *compaction* periódico.
- Regras de ciclo de vida: retenção/expiração para reduzir custo; separação **raw** vs **curated**.
- Formato com transações (Iceberg/Delta) sobre MinIO para *schema evolution* e *time travel*.

### Banco de Dados (Postgres)
- Particionamento por dia (pg_partman ou TimescaleDB) para acelerar cargas/queries.
- Índices: `time` e (opcional) `date_trunc('day', time)`; revisar `fillfactor` e `autovacuum`.
- `MERGE`/`UPSERT` mais rápido (PG ≥ 15) com *staging* + `MERGE` em vez de múltiplos `ON CONFLICT`.
- Políticas de retenção (ex.: manter 400 dias na tabela quente; histórico completo no S3).

### Orquestração & Escala
- *Task mapping* por localização: múltiplas LAT/LON vindas de **Airflow Variables/Connections**.
- Separar executores (Celery/K8s) para escalar *workers* sem travar webserver/scheduler.
- **Datasets** do Airflow para encadear DAGs *downstream* (ex.: jobs que consomem `weather_daily`).

### Segurança & Segredos
- Segredos no **Airflow Connections/Variables** (ou Docker secrets); remover credenciais do `.env` de produção.
- Usuário dedicado no MinIO com política restrita ao bucket do projeto.
- *Hardening* de rede no Compose (sub-redes, portas mínimas expostas).

### DevEx, Testes & CI/CD
- **pre-commit** (`ruff`, `black`, `isort`) + **pytest** para funções de transformação.
- CI: `dbt build` (compila/roda testes), *unit tests* e integração com Postgres de serviço no GitHub Actions.
- **dbt docs**: `dbt docs generate` e publicação automatizada (GitHub Pages) com *exposures* para dashboards.

### Experiência de Consumo
- Metabase/Lightdash apontando para `weather_daily`.
- App simples em Streamlit para explorar métricas e comparar dias/locais.