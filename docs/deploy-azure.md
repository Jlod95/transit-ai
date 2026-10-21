# Deploying Transit AI to Azure Container Apps

This is how the live demo was deployed on 20 Oct 2026, with the exact commands used. It runs
the Docker image from this repo on **Azure Container Apps**, a service that runs containers for
you and scales down to zero copies when nobody is using the app.

Live app: https://transit-ai.wittypebble-5d89ce05.canadacentral.azurecontainerapps.io

All commands are for **PowerShell on Windows**, run from the project folder. Read each
command's output before moving on.

## What gets created, and why

Everything lives in **one resource group**, so the whole project can be deleted in one step.

| Resource | Name | What it is for |
|---|---|---|
| Resource group | `rg-transit-ai` | A folder holding everything below; delete it to delete the project |
| Container registry (Basic) | `transitaijlod95` | Private storage for the Docker image; Azure pulls the image from here. Password login is off |
| Log Analytics workspace | `log-transit-ai` | Keeps the app's log output for 30 days, so logs survive after the app scales to zero |
| Container Apps environment | `cae-transit-ai` | The shared space the app runs in: networking, the public HTTPS front door, the link to logs |
| Container app | `transit-ai` | The running service: 0 to 1 copies, 0.25 CPU, 0.5 GiB memory, HTTPS on port 8000 |
| Managed identity + AcrPull role | (on the app) | The app's own Azure identity, allowed only to read images from the registry, so no registry password is stored |
| Secret | `anthropic-api-key` | The Anthropic API key, stored encrypted in the app and given to the code as `ANTHROPIC_API_KEY` |

**Why max 1 replica:** the `/ask` rate limiter keeps its counters in memory. Two copies would
each count separately and double the daily cap, so there must only ever be one copy.
**Why min 0:** no copies run while nobody is visiting, so there is nothing to pay for. The
first visit after a quiet period takes 10-30 seconds longer while a copy starts ("cold start").

## Cost (Canada Central, checked 20 Oct 2026)

| Resource | Price | Expected per month at very low traffic |
|---|---|---|
| Resource group, environment, identity, secret | Free | $0 |
| Container registry, Basic | CA$0.236/day, charged even when idle; 10 GB storage included | **about CA$7.20** |
| Container app | Free monthly allowance per subscription: 180,000 vCPU-seconds, 360,000 GiB-seconds, 2 million requests. At 0.25 vCPU / 0.5 GiB that is 200 hours of running time | about $0 |
| Log Analytics | First 5 GB/month free per billing account, then CA$3.91/GB | about $0 (a few KB/day) |
| **Total** | | **about CA$7-8/month**, almost all of it the registry |

The Anthropic API is billed separately; `DAILY_QUESTION_CAP=100` limits it to 100 questions a day.

Prices change. Check before relying on them:
- https://azure.microsoft.com/pricing/details/container-apps/
- https://azure.microsoft.com/pricing/details/container-registry/
- https://azure.microsoft.com/pricing/details/log-analytics/
- https://azure.microsoft.com/pricing/calculator/
- Your actual spend: Azure Portal → **Cost Management**

**Set up the budget alert (section 10) before creating anything that costs money.**

## 0. Names used

Set these once per PowerShell window; later commands use them. The registry name must be
unique across all of Azure (check with `az acr check-name -n <name>`).

```powershell
$RG       = "rg-transit-ai"
$LOCATION = "canadacentral"
$ACR      = "transitaijlod95"
$LOGS     = "log-transit-ai"
$ENV_NAME = "cae-transit-ai"
$APP      = "transit-ai"
```

## 1. Install the Azure CLI and sign in (free)

```powershell
winget install --exact --id Microsoft.AzureCLI
```

Close and reopen PowerShell, then sign in (this opens a browser) and check the subscription:

```powershell
az login
az account show --output table
```

## 2. One-off setup (free)

Add the Container Apps and Log Analytics extensions to the CLI, and register the Azure
services this project uses on your subscription. `--wait` returns once registration is done
(a few minutes).

```powershell
az extension add --name containerapp --upgrade
az extension add --name log-analytics
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.OperationalInsights --wait
```

## 3. Resource group (free)

```powershell
az group create --name $RG --location $LOCATION --tags project=transit-ai
```

## 4. Container registry (costs money from now on)

```powershell
az acr create --resource-group $RG --name $ACR --sku Basic --location $LOCATION
```

## 5. Log Analytics workspace

```powershell
az monitor log-analytics workspace create --resource-group $RG --workspace-name $LOGS --location $LOCATION
```

## 6. Build and push the image

Commit your changes first, then tag the image with the commit ID so you can always tell which
code is live. The image holds no raw GTFS feed: it copies the committed summary
`data/summaries/halifax.json`, which every tool answers from (see section 12 for updating it).

```powershell
$TAG = git rev-parse --short HEAD
az acr login --name $ACR
docker build -t "$ACR.azurecr.io/transit-ai:$TAG" .
docker push "$ACR.azurecr.io/transit-ai:$TAG"
```

## 7. Container Apps environment (free on its own)

The workspace ID and key are read into variables and passed straight to the next command,
so the key is never printed.

```powershell
$WS_ID  = az monitor log-analytics workspace show -g $RG -n $LOGS --query customerId -o tsv
$WS_KEY = az monitor log-analytics workspace get-shared-keys -g $RG -n $LOGS --query primarySharedKey -o tsv
az containerapp env create `
  --name $ENV_NAME `
  --resource-group $RG `
  --location $LOCATION `
  --logs-destination log-analytics `
  --logs-workspace-id $WS_ID `
  --logs-workspace-key $WS_KEY
```

(The backtick `` ` `` at the end of a line continues the command on the next line.)

## 8. Container app

```powershell
az containerapp create `
  --name $APP `
  --resource-group $RG `
  --environment $ENV_NAME `
  --image "$ACR.azurecr.io/transit-ai:$TAG" `
  --registry-server "$ACR.azurecr.io" `
  --registry-identity system `
  --target-port 8000 `
  --ingress external `
  --min-replicas 0 `
  --max-replicas 1 `
  --cpu 0.25 `
  --memory 0.5Gi `
  --env-vars DAILY_QUESTION_CAP=100
```

What the options mean:
- `--registry-identity system`: give the app its own Azure identity with read-only (AcrPull)
  access to the registry, instead of storing a registry password.
- `--target-port 8000`: the port uvicorn listens on inside the container.
- `--ingress external`: a public HTTPS address. Plain `http://` is redirected to `https://`.
- `--min-replicas 0` / `--max-replicas 1`: scale to zero when idle, never more than one copy.
- `--cpu 0.25 --memory 0.5Gi`: the smallest size; plenty for this app.

The app starts without the API key: `/health` and the page work, `/ask` does not yet.

## 9. Add the API key as a secret

The key must never be in the image, a file, or a command (commands are kept in your terminal
history). So it is pasted directly into the Azure Portal:

1. Go to https://portal.azure.com, search for **transit-ai** and open the **Container App**.
2. Open **Settings → Secrets → + Add**.
3. **Key:** `anthropic-api-key`. **Type:** Container Apps Secret. **Value:** paste the key.
4. Click **Add**.

Then point the app's `ANTHROPIC_API_KEY` at the secret. This command contains only the
secret's name, never its value. It creates a new revision (version) of the app.

```powershell
az containerapp secret list -n $APP -g $RG --query "[].name" -o tsv
az containerapp update --name $APP --resource-group $RG --set-env-vars ANTHROPIC_API_KEY=secretref:anthropic-api-key
```

To replace the key later, edit the secret's value in the Portal, then restart the app so
it picks up the new value:

```powershell
az containerapp revision restart -n $APP -g $RG --revision (az containerapp show -n $APP -g $RG --query properties.latestRevisionName -o tsv)
```

## 10. Check it works

```powershell
$URL = "https://" + (az containerapp show -n $APP -g $RG --query properties.configuration.ingress.fqdn -o tsv)
$URL
curl.exe -s "$URL/health"
```

You should see `{"status":"ok"}`. Open `$URL` in a browser for the demo page.

Azure Container Apps ignores the Dockerfile's `HEALTHCHECK`; it has its own health probes.

## 11. Viewing logs

**Live**, while a copy is running (it streams until you press Ctrl+C). If the app has scaled to
zero there is nothing to stream; open the page first to wake it.

```powershell
az containerapp logs show -n $APP -g $RG --type console --follow
```

**Past logs** (kept 30 days), even when the app is scaled to zero. New lines take a few
minutes to arrive.

- In the Portal: open the container app → **Monitoring → Logs**, close the query picker, and
  run:

  ```kusto
  ContainerAppConsoleLogs_CL
  | where ContainerAppName_s == "transit-ai"
  | project TimeGenerated, RevisionName_s, Log_s
  | order by TimeGenerated desc
  ```

  Add `| where Log_s has "/ask"` before `project` to see only the one-line-per-question log
  (`/ask status=200 rounds=2 rate_limited=no`).

- From PowerShell:

  ```powershell
  $WS_ID = az monitor log-analytics workspace show -g $RG -n $LOGS --query customerId -o tsv
  az monitor log-analytics query --workspace $WS_ID -o table --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == 'transit-ai' and Log_s has '/ask' | project TimeGenerated, Log_s | order by TimeGenerated desc | take 20"
  ```

## 12. Deploying a new version

Commit, then build and push with the new commit ID as the tag, and point the app at it:

```powershell
$TAG = git rev-parse --short HEAD
az acr login --name $ACR
docker build -t "$ACR.azurecr.io/transit-ai:$TAG" .
docker push "$ACR.azurecr.io/transit-ai:$TAG"
az containerapp update --name $APP --resource-group $RG --image "$ACR.azurecr.io/transit-ai:$TAG"
```

### Updating the timetable data

The current feed is valid to 29 Nov 2026. To move to a newer one, download it, rebuild the
summary locally, check it, and commit it; then deploy as above. The summary's stamp records
the new feed's SHA-256 hash and the code commit that built it.

```powershell
curl.exe -L -o data/raw/halifax.zip http://gtfs.halifax.ca/static/google_transit.zip
.venv\Scripts\python.exe scripts/build_summaries.py halifax
.venv\Scripts\python.exe -m pytest
git add data/summaries/
git commit -m "Rebuild Halifax summary from new feed"
```

Commit any code changes before rebuilding, so the stamp names a clean commit rather than
one marked "-dirty".

## 13. Budget alert (free)

A budget emails you when spending reaches a threshold. It does **not** stop resources or cap
spending; it only warns you.

1. Go to https://portal.azure.com and search for **Cost Management**.
2. Choose **Budgets** → **+ Add**, and check the **Scope** is your subscription.
3. Name it (e.g. `transit-ai-monthly`), set **Reset period** to Monthly and **Amount** to
   e.g. 10 (CAD).
4. Click **Next**, add alert conditions, e.g. **Actual** at 50%, **Actual** at 100%, and
   **Forecasted** at 100%.
5. Enter your email under **Alert recipients** and click **Create**.

Cost data can lag by a day or so, so alerts aren't instant.

## 14. Deleting everything

Deleting the resource group removes every resource above (registry, logs, environment, app,
secret) and stops all charges from them. This cannot be undone, so check the name first:

```powershell
az group delete --name $RG
```
