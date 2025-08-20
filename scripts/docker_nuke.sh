
#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-targeted}" # targeted | nuke

if [ "$MODE" = "targeted" ]; then
  echo "[targeted] docker compose down -v --remove-orphans"
  docker compose down -v --remove-orphans || true
  echo "[targeted] docker system prune -f"
  docker system prune -f || true
  echo "[targeted] docker builder prune -f"
  docker builder prune -f || true
  echo "OK. Limpeza direcionada concluída."
  exit 0
fi

if [ "$MODE" = "nuke" ]; then
  read -p "Isso vai APAGAR TUDO do Docker (containers/imagens/volumes). Continuar? (yes/NO): " ans
  if [ "$ans" != "yes" ]; then
    echo "Abortado."
    exit 1
  fi

  docker stop $(docker ps -aq) 2>/dev/null || true
  docker rm -f $(docker ps -aq) 2>/dev/null || true
  docker rmi -f $(docker images -q) 2>/dev/null || true
  docker volume rm $(docker volume ls -q) -f 2>/dev/null || true
  docker network rm $(docker network ls -q | grep -vE '(^ID|bridge|host|none)') 2>/dev/null || true
  docker system prune -af --volumes || true
  docker builder prune -af || true
  echo "OK. Docker zerado completamente."
  exit 0
fi

echo "Uso: $0 [targeted|nuke]"

