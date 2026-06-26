# Enterprise Branching and Promotion (Fabric)

This repository follows an enterprise-grade branch model inspired by production Fabric teams.

## Branches

- `feature/<developer-or-feature>`: long-lived personal feature branch, connected to Feature workspace via Fabric Git sync
- `dev`: integration branch, connected to shared DEV workspace via Fabric Git sync
- `uat`: deployment branch, no workspace Git sync; pipeline deploys to UAT workspace
- `main`: production branch, no workspace Git sync; pipeline deploys to PROD workspace

## Merge policy

- Always use squash merge for PR completion
- Never cherry-pick directly to `uat` or `main`
- Use short-lived promotion branches:
  - `promote/dev-to-uat/<release-id>`
  - `promote/uat-to-prod/<release-id>`

## Promotion flow

1. Feature development:
   - Build items in Feature workspace
   - Sync to `feature/*`
   - PR `feature/* -> dev` (squash)
2. DEV integration:
   - Sync DEV workspace from `dev`
   - Validate integrated behavior
3. UAT promotion:
   - Create `promote/dev-to-uat/<release-id>` from latest `uat`
   - Cherry-pick validated commit(s) from `dev`
   - PR to `uat` (squash)
   - Trigger UAT ADO pipeline
4. PROD promotion:
   - Create `promote/uat-to-prod/<release-id>` from latest `main`
   - Cherry-pick validated commit(s) from `uat`
   - PR to `main` (squash)
   - Trigger PROD ADO pipeline

## Why this pattern

- Prevents accidental full-branch promotion from `dev` to stable environments
- Creates auditable, reversible release units
- Keeps production deployments explicitly approved

## Operational notes

- `fabric-cicd` deploys item definitions (not data)
- Lakehouse deployment creates metadata containers; data loading remains pipeline/notebook responsibility
- Keep deployment scripts and pipelines outside `workspace/` to avoid being treated as deployable Fabric items
