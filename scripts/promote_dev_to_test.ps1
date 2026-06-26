param(
    [string]$TenantId = $env:FABRIC_TENANT_ID,
    [string]$ClientId = $env:FABRIC_CLIENT_ID,
    [string]$ClientSecret = $env:FABRIC_CLIENT_SECRET
)

python -m fabric_cicd.cli promote `
  --source-config configs/environments/dev.yaml `
  --target-config configs/environments/test.yaml `
  --tenant-id $TenantId `
  --client-id $ClientId `
  --client-secret $ClientSecret
