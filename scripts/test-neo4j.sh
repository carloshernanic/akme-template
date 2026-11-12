#!/usr/bin/env bash
# Roda tests/test_neo4j_integration.py contra um Neo4j descartavel, criado e removido por este script.
#
# Sobe um neo4j:2026.10.1 em 127.0.0.1 (portas livres, 37687/37474 se puder), com senha aleatoria guardada num
# arquivo chmod 600 (nunca impressa), exporta AKME_NEO4J_TEST_*, roda os testes e, ao sair (sucesso, falha ou
# Ctrl+C), remove o container e o volume. Nunca toca em outro banco: os testes APAGAM o banco que recebem.
#
# Uso: scripts/test-neo4j.sh [argumentos extras do pytest]
# Variaveis opcionais: AKME_NEO4J_TEST_IMAGE (padrao neo4j:2026.10.1), AKME_NEO4J_TEST_TMPDIR (pasta do arquivo
# de senha; padrao uma pasta temporaria nova, removida no fim), AKME_NEO4J_TEST_HEAP (padrao 1G).
set -euo pipefail

cd "$(dirname "$0")/.."
IMAGE="${AKME_NEO4J_TEST_IMAGE:-neo4j:2026.10.1}"
HEAP="${AKME_NEO4J_TEST_HEAP:-1G}"
NAME="akme-neo4j-it-$$-$RANDOM"
if [ -n "${AKME_NEO4J_TEST_TMPDIR:-}" ]; then
  TMP="$AKME_NEO4J_TEST_TMPDIR"
  OWN_TMP=""
else
  TMP="$(mktemp -d)"
  OWN_TMP="$TMP"  # pasta criada aqui: removida no fim
fi
mkdir -p "$TMP"
ENV_FILE="$TMP/$NAME.env"

cleanup() {
  docker rm -f -v "$NAME" >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
  if [ -n "$OWN_TMP" ]; then rm -rf "$OWN_TMP"; fi
}
# EXIT limpa em sucesso ou falha; Ctrl+C e TERM limpam e saem (sem o exit, o script seguiria para o proximo comando)
trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

free_port() {  # porta preferida se estiver livre; senao, uma que o sistema der
  python3 - "$1" <<'PY'
import socket, sys
def free(port):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return s.getsockname()[1]
        except OSError:
            return None
print(free(int(sys.argv[1])) or free(0))
PY
}
BOLT="$(free_port 37687)"
HTTP="$(free_port 37474)"

umask 077
PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
printf 'NEO4J_AUTH=neo4j/%s\n' "$PASSWORD" > "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "subindo $IMAGE descartavel ($NAME) em bolt://127.0.0.1:$BOLT"
docker run -d --name "$NAME" --env-file "$ENV_FILE" \
  -e NEO4J_server_memory_heap_max__size="$HEAP" -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_pagecache_size=256m \
  -p "127.0.0.1:$BOLT:7687" -p "127.0.0.1:$HTTP:7474" "$IMAGE" >/dev/null

export AKME_NEO4J_TEST_URI="bolt://127.0.0.1:$BOLT"
export AKME_NEO4J_TEST_USER="neo4j"
export AKME_NEO4J_TEST_PASSWORD="$PASSWORD"
unset AKME_NEO4J_DATABASE

echo "esperando o Neo4j aceitar conexoes..."
for _ in $(seq 1 90); do
  if uv run --extra neo4j python -c '
import os, neo4j
with neo4j.GraphDatabase.driver(os.environ["AKME_NEO4J_TEST_URI"],
        auth=(os.environ["AKME_NEO4J_TEST_USER"], os.environ["AKME_NEO4J_TEST_PASSWORD"])) as d:
    d.verify_connectivity()
' >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 2
done
if [ -z "${READY:-}" ]; then
  echo "o Neo4j nao subiu; ultimas linhas do log:" >&2
  docker logs --tail 30 "$NAME" >&2 || true
  exit 1
fi

docker exec "$NAME" neo4j --version 2>/dev/null | sed 's/^/versao: /' || true
uv run --extra dev --extra neo4j pytest -q -rs tests/test_neo4j_integration.py "$@"
