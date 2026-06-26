# Fabric-CICD

Code-first starter for Microsoft Fabric CI/CD using Python and GitHub Actions.

## What this gives you

- Environment-driven deployment config (`dev`, `test`, `prod`)
- Service principal auth to Microsoft Fabric API
- Export step for workspace item metadata
- Artifact-type specific deployment orchestration (`Notebook`, `Pipeline`, `SemanticModel`, `Report`)
- Validation gates (source existence, dependency wiring, target compatibility checks)
- Automatic rollback manifest generation before overwrite operations
- PR checks + environment-gated deployment + explicit rollback workflow
- Enterprise policy checks (artifact allowlist, required types, naming rules, freeze/deployment window)
- Release evidence manifest per deployment for auditability

## Choose one delivery path

This repository contains two deployment implementations:

- GitHub Actions path (`.github/workflows/*`) based on the local `fabric_cicd` Python package.
- Azure DevOps path (`.pipelines/*` + `.deploy/deploy_fabric_workspace.py`) based on the external `fabric-cicd` package.

To reduce operational complexity, choose one path as primary for production and keep the other for reference or migration.

## Project structure

- `fabric_cicd/`: Python package and CLI
- `.deploy/deploy_fabric_workspace.py`: `fabric-cicd` deployment entry script (ADO)
- `.pipelines/deploy_workspace_uat.yml`: Azure DevOps UAT deployment pipeline
- `.pipelines/deploy_workspace_prod.yml`: Azure DevOps PROD deployment pipeline
- `configs/environments/`: environment YAMLs
- `scripts/`: local PowerShell helper scripts
- `.github/workflows/fabric-cicd.yml`: GitHub Actions pipeline
- `.github/workflows/pr-checks.yml`: pull request validation checks
- `.github/workflows/rollback.yml`: manual rollback pipeline
- `workspace/engineering/project_one/`: engineering Fabric items + `parameter.yml`
- `workspace/presentation/project_one/`: presentation Fabric items
- `docs/enterprise-branching-and-promotion.md`: enterprise branch and promotion guidance
- `configs/enterprise-policy.yaml`: enterprise governance policy file
- `artifacts/exported/`: generated exports
- `artifacts/rollback/`: generated rollback manifests
- `artifacts/releases/`: generated release evidence manifests

## Prerequisites

1. Python 3.11+
2. Azure AD app registration (service principal) with Fabric permissions
3. Fabric workspaces for each stage
4. GitHub repository secrets:
   - `FABRIC_TENANT_ID`
   - `FABRIC_CLIENT_ID`
   - `FABRIC_CLIENT_SECRET`

## Setup

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Update environment files:

- `configs/environments/dev.yaml`
- `configs/environments/test.yaml`
- `configs/environments/prod.yaml`

Set:
- `workspace_id`
- `capacity_id`
- `backup_workspace_id`
- `items` map using this schema:

```yaml
items:
   variablelib_runtime:
      name: "RuntimeVariables"
      type: "VariableLibrary"
   environment_spark:
      name: "SparkRuntimeEnvironment"
      type: "Environment"
      depends_on: ["variablelib_runtime"]
   lakehouse_sales:
      name: "SalesLakehouse"
      type: "Lakehouse"
      depends_on: ["environment_spark"]
   notebook_ingest:
      name: "NotebookIngest"
      type: "Notebook"
      depends_on: ["lakehouse_sales", "environment_spark"]
   dataflow_curated_sales:
      name: "CuratedSalesDataflow"
      type: "Dataflow"
      depends_on: ["lakehouse_sales"]
   pipeline_ingestion:
      name: "IngestionPipeline"
      type: "Pipeline"
      depends_on: ["notebook_ingest", "dataflow_curated_sales"]
   copyjob_ops_snapshot:
      name: "OpsSnapshotCopyJob"
      type: "CopyJob"
      depends_on: ["pipeline_ingestion"]
   semantic_sales:
      name: "SalesSemanticModel"
      type: "SemanticModel"
      depends_on: ["pipeline_ingestion", "copyjob_ops_snapshot"]
   report_sales:
      name: "SalesReport"
      type: "Report"
      depends_on: ["semantic_sales"]
```

Supported `type` values in this starter:
- `Notebook`
- `Pipeline`
- `Lakehouse`
- `Environment`
- `CopyJob`
- `Dataflow`
- `VariableLibrary`
- `SemanticModel`
- `Report`

## Second sample scenario: Core ingestion (lighter starter)

Use this profile when you only want the ingestion path and not semantic/reporting artifacts yet.

```yaml
items:
   lakehouse_sales:
      name: "SalesLakehouse"
      type: "Lakehouse"

   notebook_ingest:
      name: "NotebookIngest"
      type: "Notebook"
      depends_on: ["lakehouse_sales"]

   pipeline_ingestion:
      name: "IngestionPipeline"
      type: "Pipeline"
      depends_on: ["notebook_ingest"]

   copyjob_raw_to_curated:
      name: "RawToCuratedCopyJob"
      type: "CopyJob"
      depends_on: ["pipeline_ingestion"]
```

Suggested rollout path for this lighter profile:
- Start with only these four items in `dev`.
- Validate and promote to `test`.
- Add `Dataflow`, `SemanticModel`, and `Report` later when ingestion is stable.

3. Set local auth env vars (for local runs):

```powershell
$env:FABRIC_TENANT_ID = "<tenant-guid>"
$env:FABRIC_CLIENT_ID = "<app-guid>"
$env:FABRIC_CLIENT_SECRET = "<client-secret>"
```

## Local usage

Export dev metadata:

```powershell
python -m fabric_cicd.cli export --env-config configs/environments/dev.yaml
```

Promote dev to test:

```powershell
python -m fabric_cicd.cli promote --source-config configs/environments/dev.yaml --target-config configs/environments/test.yaml
```

Run only validation gates:

```powershell
python -m fabric_cicd.cli validate --source-config configs/environments/dev.yaml --target-config configs/environments/test.yaml
```

Run config linting only:

```powershell
python -m fabric_cicd.cli lint-config --env-config configs/environments/dev.yaml
```

Run full preflight (lint + remote source/target checks):

```powershell
python -m fabric_cicd.cli preflight --source-config configs/environments/dev.yaml --target-config configs/environments/test.yaml
```

Run enterprise preflight (includes policy checks):

```powershell
python -m fabric_cicd.cli enterprise-preflight --source-config configs/environments/dev.yaml --target-config configs/environments/test.yaml --policy-file configs/enterprise-policy.yaml
```

Render dependency graph (Mermaid):

```powershell
python -m fabric_cicd.cli graph --env-config configs/environments/dev.yaml --format mermaid
```

Selective deploy by changed artifacts (dependencies included automatically):

```powershell
python -m fabric_cicd.cli promote --source-config configs/environments/dev.yaml --target-config configs/environments/test.yaml --only notebook_ingest pipeline_ingestion
```

Run rollback using generated manifest:

```powershell
python -m fabric_cicd.cli rollback --target-config configs/environments/test.yaml --manifest artifacts/rollback/dev-to-test-rollback.json
```

Or use helper scripts:

```powershell
./scripts/export_dev.ps1
./scripts/promote_dev_to_test.ps1
```

## GitHub Actions usage

1. Push repository to GitHub.
2. Configure the three repository secrets.
3. Protect environments `test` and `prod` in GitHub with required reviewers (Settings -> Environments).
4. Run workflow `Fabric CI-CD` via `workflow_dispatch`.
5. Choose `source_env` and `target_env`.

## Azure DevOps enterprise deployment (article-aligned)

This repo now also includes an Azure DevOps + `fabric-cicd` deployment path, similar to the referenced enterprise pattern.

- UAT pipeline: `.pipelines/deploy_workspace_uat.yml`
- PROD pipeline: `.pipelines/deploy_workspace_prod.yml`
- Shared pipeline template: `.pipelines/deploy_workspace_template.yml`
- Deployment script: `.deploy/deploy_fabric_workspace.py`
- Project-level parameterization: `workspace/engineering/project_one/parameter.yml`

Expected ADO variable group variables:
- `workspace_guid`
- `fabric_vl_vset_active` (for example: `UAT`, `PROD`)
- `repo_project_directory` (for example: `project_one`)
- `fabric_item_type_inscope` (for example: `VariableLibrary,Environment,Notebook,DataPipeline,Lakehouse,CopyJob,Dataflow,SemanticModel,Report`)
- `azure_service_connection`

The script uses `AzureCliCredential`, so deployment auth comes from the `AzureCLI@2` task service connection rather than hardcoded secrets.

Branching/promotion reference:
- See `docs/enterprise-branching-and-promotion.md` for feature/dev/uat/main, squash-merge rule, and cherry-pick promotion branches.

## Pipeline controls included

- `PR Checks` workflow validates Python syntax + dev->test compatibility on pull requests to `main`.
- `Fabric CI-CD` workflow enforces enterprise preflight before promote and binds jobs to GitHub environments for approvals.
- `Fabric Rollback` workflow allows manual restore by applying a rollback manifest.
- Promote job uploads release evidence JSON for audit/compliance trails.

## Advanced deployment features

- Selective deploy: deploy only specified logical artifacts with automatic dependency expansion.
- Dependency graph output: print artifact dependency graph as `json` or `mermaid`.
- Config linter: validates schema, supported artifact types, unknown dependencies, and cycle detection.
- Preflight command: runs lint + remote source/target compatibility checks before promote.
- Enterprise preflight: adds policy-based guardrails (naming, required/allowed types, freeze, deployment window).
- Release evidence output: records deployed artifacts and timestamp to `artifacts/releases/`.

## Important notes

- Fabric API operations evolve quickly. Verify the item copy/export endpoints against your tenant capabilities and API version before production usage.
- This starter resolves artifacts by display name + type and applies dependency-aware deploy order.
- Rollback reliability depends on `backup_workspace_id` availability and copy API behavior in your tenant.

## Recommended next enhancements

- Add artifact-type specific deployment logic (Notebooks, Data Pipelines, Semantic Models, Reports)
- Add pull request validation and drift checks
- Add test suite with mocked Fabric API responses
- Add release tags and environment approvals
