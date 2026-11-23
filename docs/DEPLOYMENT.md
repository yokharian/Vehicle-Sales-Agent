# Deployment

How both deployables ship. CI provisions nothing; the AWS resources and
secrets below must exist before the workflows that use them can succeed.

## Backend container image

`.github/workflows/deploy.yml` builds `backend/Dockerfile` with the
`./backend` build context, pushes the image to GitHub Container Registry on
pushes to `master`, on `v*.*.*` tags and on manual dispatch, and signs the
digest with cosign. The image is the LangGraph API server: it exposes the
agent graph (`src/agent.py:agent`) and the Cognito-authenticated API, with
the catalog, document and financing tools reading PostgreSQL.

## Deploying to Vercel (Fluid Compute)

Vercel builds `backend/Dockerfile` and serves it with Fluid Compute enabled.
The public hostname is terminated by a Kong reverse proxy, so no domain has
to be attached to the Vercel project: Kong upstreams to the production
deployment URL (`https://<project>.vercel.app`). Kong is also the place to
attach the Twilio webhook path, because this image serves the LangGraph API,
not the WhatsApp server.

`vercel.json` pins the Container framework preset and `fluid: true`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "container",
  "fluid": true
}
```

The project must use the Container preset — Vercel keeps a detected
framework otherwise, and `backend/Dockerfile` is only built when no other
framework is selected. The project settings also need:

| Setting | Value |
|---|---|
| Framework preset | Container |
| Install command | empty (the image installs its own dependencies) |

Environment variables: `DATABASE_URI` resolves the database URL (with
`PGVECTOR_URI` defaulting to it), so a single-database setup needs one URL.
`LANGGRAPH_RUNTIME_EDITION=inmem` keeps the LangGraph run queue in memory
and needs no runtime database, and `REDIS_URI=fake` satisfies the queue's
configuration. `PORT` must match the port the image listens on (`8000`).

## Web hosting (Amplify)

`.github/workflows/web-deploy.yml` builds the static export and publishes it
to Amplify Hosting through the manual deployment API: checkout, write
`web/amplify_outputs.json` from `secrets.AMPLIFY_OUTPUTS_JSON`, `pnpm
install`, `pnpm build`, zip `web/out`, upload the artifact, authenticate
with the OIDC role, then `amplify create-deployment`, upload,
`start-deployment` and poll `get-job`. It runs on pushes to `master` that
touch `web/**` or the workflow file, and on manual dispatch; it never runs
on pull requests. The Amplify app has no connected repository and auto-build
disabled, so GitHub Actions is the only builder and publisher.

## AWS provisioning precondition

The web app talks to AWS-hosted resources. Provision them once before the
first `web-deploy.yml` run; the workflow fails at the AWS steps until they
exist.

- **Amazon Cognito user pool** (us-east-1) with a registered app client and
  a guest app client. The registered client backs sign-in and sign-up, the
  guest client backs the "Continue as guest" flow. The backend validates
  access tokens against the pool JWKS once `COGNITO_REGION` and
  `COGNITO_USER_POOL_ID` are set, and runs open while they are unset; list
  both app clients in `COGNITO_APP_CLIENT_IDS` so guest tokens pass the
  `client_id` check.

  The backend's pool and client ids must be the ones the deployed web build
  ships in `amplify_outputs.json`, and the pool must still exist. A deleted
  pool leaves the JWKS endpoint returning 404, so every token fails
  validation and the API answers 401 on every authenticated route while
  `/ok` stays green. Replacing a pool means updating the Dokploy compose env
  (`COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_IDS`) and the Amplify bundle
  together, then redeploying both.
- **Amplify app** for hosting the static export, created with no connected
  repository, no auto branch creation and `enableAutoBuild: false` on its
  branch.
- **GitHub secrets and variables**: secrets `NEXT_PUBLIC_API_URL`,
  `NEXT_PUBLIC_ASSISTANT_ID`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`,
  `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`,
  `AMPLIFY_OUTPUTS_JSON` and `AWS_DEPLOY_ROLE_ARN`; variables
  `AMPLIFY_APP_ID`, `AMPLIFY_BRANCH` and `AWS_REGION`. The deploy role must
  trust the GitHub Actions OIDC provider and be allowed to call the Amplify
  hosting deployment APIs on that app.

The PostgreSQL database needs the `pgvector` extension enabled before the
document search works.
