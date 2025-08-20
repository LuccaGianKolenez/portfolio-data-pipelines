#!/usr/bin/env bash
set -euo pipefail

# (1) Pré-checagens básicas
command -v docker >/dev/null || { echo "Docker não encontrado"; exit 1; }
command -v docker compose >/dev/null || { echo "Docker Compose V2 não encontrado"; exit 1; }

# (2) .env e AIRFLOW_UID
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi
grep -q '^AIRFLOW_UID=' .env 2>/dev/null || echo "AIRFLOW_UID=$(id -u)" >> .env

echo "[0/4] Conferindo _PIP_ADDITIONAL_REQUIREMENTS no .env:"
grep _PIP_ADDITIONAL_REQUIREMENTS .env || echo "(não definido no .env)"

# (3) Sobe dependências e espera saúde
echo "[1/4] Subindo Postgres e MinIO..."
docker compose up -d postgres minio

# Use 'docker compose wait' se disponível; senão, faça polling de health
if docker compose help | grep -q " wait"; then
  echo "[2/4] Aguardando healthchecks (compose wait)..."
  docker compose wait postgres minio
else
  echo "[2/4] Aguardando healthchecks (poll)..."
  for svc in postgres minio; do
    cid="$(docker compose ps -q "$svc")"
    [ -n "$cid" ] || { echo "Serviço $svc não encontrado"; exit 1; }
    until [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" = "healthy" ]; do
      echo " - $svc ainda não healthy; aguardando..."
      sleep 2
    done
  done
fi

# (4) Cria bucket do MinIO (separado, para falhas ficarem claras)
echo "[3/4] Inicializando bucket do MinIO..."
docker compose up --no-deps --abort-on-container-exit --exit-code-from createbucket createbucket || {
  echo "Falha ao criar/configurar bucket no MinIO"; exit 1;
}

# (5) Roda airflow-init (instala deps + migra DB + cria usuário)
echo "[4/4] Executando airflow-init (instala deps, migra DB, cria admin)..."
# Dica: 'run --rm' usa o mesmo service mas como job efêmero (não fica preso a logs)
docker compose run --rm airflow-init

# (6) Sobe webserver e scheduler
echo ">> Subindo Airflow Webserver e Scheduler em background..."
docker compose up -d airflow-webserver airflow-scheduler

echo
echo "✅ Pronto!"
echo "Airflow UI: http://localhost:8080  (admin / admin)"
echo "MinIO Console: http://localhost:9001  | S3 API: http://localhost:9000"
