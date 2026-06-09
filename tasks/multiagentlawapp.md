<GRAFANA_ADMIN_PASSWORD>  admin --grafana admin



kubectl -n hermes-prod delete secret ghcr-pull-secret --ignore-not-found

export GHCR_PAT="<YOUR_GITHUB_PAT>"

kubectl -n hermes-prod create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=serverax \
  --docker-password="$GHCR_PAT"

export GHCR_PAT='<YOUR_GITHUB_PAT>'   # set from your secret store, never commit a real token
echo ${#GHCR_PAT}


cd /mnt/f/hermes

read -s <YOUR_GITHUB_PAT>
kubectl -n ns-agent-admin-bot create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username=serverax \
  --docker-password="$GHCR_PAT" \
  --docker-email="serverax@example.com" \
  --dry-run=client -o yaml | kubectl apply -f -

unset GHCR_PAT



cd /mnt/f/hermes

read -rsp "<YOUR_GITHUB_PAT>: " GHCR_PAT
echo
echo "Token length: ${#GHCR_PAT}"