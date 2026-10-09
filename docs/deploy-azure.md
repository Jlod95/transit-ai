# Deploying Transit AI to Azure Container Apps

This guide deploys the Docker image from this repo to **Azure Container Apps**, a service that
runs containers for you and can scale down to zero copies when nobody is using the app.

All commands are for **PowerShell on Windows**. Nothing here has been run yet; work through it
yourself, one step at a time, and read each command's output before moving on.

## Cost summary (read first)

| Step | Costs money? |
|---|---|
| Installing the Azure CLI, logging in | Free |
| Resource group | Free (it's just a folder for resources) |
| Container registry (Basic tier) | **Costs money** — billed per day for as long as it exists, even if unused |
| Container Apps environment | Free on its own (Consumption plan) |
| Container App, scaled to zero | Mostly free: there is a monthly free allowance of CPU, memory and requests. You pay only above it |
| Log Analytics (logs) | **Can cost money** if logs are sent there; this guide turns it off |
| Budget alert | Free |

Prices change. Before you start, check:
- Container Apps pricing: https://azure.microsoft.com/pricing/details/container-apps/
- Container Registry pricing: https://azure.microsoft.com/pricing/details/container-registry/
- Pricing calculator: https://azure.microsoft.com/pricing/calculator/
- Your actual spend at any time: Azure Portal → **Cost Management**

**Set up the budget alert (section 9) before creating anything that costs money.**

## 0. Fill in your names

Pick values and set them once per PowerShell window. Every later command uses these variables.

```powershell
$RG       = "<RESOURCE_GROUP>"   # e.g. rg-transit-ai
$LOCATION = "<LOCATION>"         # e.g. canadacentral, eastus, uksouth
$ACR      = "<ACR_NAME>"         # globally unique, 5-50 lowercase letters/numbers, e.g. transitai12345
$ENV_NAME = "<ENVIRONMENT_NAME>" # e.g. cae-transit-ai
$APP      = "<APP_NAME>"         # e.g. transit-ai
$IMAGE    = "transit-ai:v1"      # image name and version tag
```

If you close PowerShell, run this block again before continuing.

## 1. Install the Azure CLI (free)

The Azure CLI is the `az` command. Install it with Windows' built-in package manager:

```powershell
winget install --exact --id Microsoft.AzureCLI
```

Close and reopen PowerShell, then check it works:

```powershell
az --version
```

## 2. Log in (free)

This opens a browser for you to sign in to your Azure account:

```powershell
az login
```

If you have more than one subscription, check which one is active:

```powershell
az account show --output table
```

Install the Container Apps extension and register the services it needs (one-off, free):

```powershell
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

## 3. Create a resource group (free)

A resource group holds everything for this project, so you can see and delete it all together.

```powershell
az group create --name $RG --location $LOCATION
```

## 4. Create a container registry (costs money)

A registry is private storage for your Docker images. Azure pulls the image from here.

```powershell
az acr create --resource-group $RG --name $ACR --sku Basic
```

## 5. Build and push the image

Build locally with Docker, then push to the registry:

```powershell
az acr login --name $ACR
docker build -t "$ACR.azurecr.io/$IMAGE" .
docker push "$ACR.azurecr.io/$IMAGE"
```

Alternative without local Docker: `az acr build --registry $ACR --image $IMAGE .` builds in Azure
instead. This uses "ACR Tasks", which is billed per build minute and may be unavailable on
free-trial subscriptions.

## 6. Create the Container Apps environment (free on its own)

The environment is the shared space your app runs in. `--logs-destination none` stops it creating
a Log Analytics workspace, which could otherwise charge for stored logs. You can turn logging on
later if you need it.

```powershell
az containerapp env create --name $ENV_NAME --resource-group $RG --location $LOCATION --logs-destination none
```

## 7. Create the app (port 8000, public, scale to zero)

```powershell
az containerapp create `
  --name $APP `
  --resource-group $RG `
  --environment $ENV_NAME `
  --image "$ACR.azurecr.io/$IMAGE" `
  --registry-server "$ACR.azurecr.io" `
  --registry-identity system `
  --target-port 8000 `
  --ingress external `
  --min-replicas 0 `
  --max-replicas 1
```

What each option means:
- `--target-port 8000`: the port uvicorn listens on inside the container.
- `--ingress external`: give the app a public HTTPS address.
- `--registry-identity system`: the app gets its own Azure identity and permission to pull from
  your registry, so no registry password is stored.
- `--min-replicas 0`: **scale to zero** — no copies run when there's no traffic. The first request
  after a quiet period is slower (a "cold start") while a copy starts up.
- `--max-replicas 1`: never run more than one copy, which caps cost.

(The backtick `` ` `` at the end of each line is PowerShell's way of continuing a command onto the
next line.)

## 8. Test it

Get the public address:

```powershell
az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn --output tsv
```

Then open `https://<that-address>/health` in a browser. You should see `{"status":"ok"}`.

Note: Azure Container Apps ignores the Dockerfile's `HEALTHCHECK`. It has its own "health
probes", which you can configure later if needed.

### Deploying a new version

Build and push with a new tag (e.g. `transit-ai:v2`), then:

```powershell
az containerapp update --name $APP --resource-group $RG --image "$ACR.azurecr.io/transit-ai:v2"
```

### Secrets

Never copy `.env` into the image (`.dockerignore` already excludes it). To give the app a secret,
store it in Container Apps and expose it as an environment variable:

```powershell
az containerapp secret set --name $APP --resource-group $RG --secrets "<secret-name>=<value>"
az containerapp update --name $APP --resource-group $RG --set-env-vars "<ENV_VAR_NAME>=secretref:<secret-name>"
```

## 9. Set a budget alert (free)

A budget sends you an email when spending reaches a threshold. It does **not** stop resources
or cap spending; it only warns you. The Azure Portal is the simplest way:

1. Go to https://portal.azure.com and search for **Cost Management**.
2. Choose **Budgets** → **+ Add**.
3. Check the **Scope** is your subscription.
4. Name it (e.g. `transit-ai-monthly`), set **Reset period** to Monthly and **Amount** to
   something small, e.g. 10 in your currency.
5. Click **Next**, add alert conditions, e.g. **Actual** at 50%, **Actual** at 100%, and
   **Forecasted** at 100%.
6. Enter your email under **Alert recipients** and click **Create**.

Cost data can lag by up to a day or so, so alerts aren't instant.

## 10. Clean up when finished

Deleting the resource group removes everything inside it, including the registry, and stops
all charges from it. This cannot be undone, so check the name first:

```powershell
az group delete --name $RG
```
