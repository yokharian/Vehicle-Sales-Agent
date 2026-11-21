# WEB AGENTS

**Scope:** the `web/` directory of the Vehicle Sales Agent monorepo. Repo-wide rules live in the root `AGENTS.md`; commands live in this directory's `README.md`.

## OVERVIEW

Next.js 16 chat front end for the vehicle sales agent, built on assistant-ui primitives with React 19 and Tailwind v4. It is a fully static export (`output: "export"` in `next.config.mjs`), served by Amplify, and talks to the backend LangGraph API with the LangGraph SDK. Users sign in through Amazon Cognito (Amplify Authenticator) or continue as a guest behind a Cloudflare Turnstile check; every HTTP and SSE request carries the access token as a bearer.

## CI

`.github/workflows/ci.yml` gates the web job on `web/**` changes and runs install, `format:check`, `lint` and `build` with Node 22 and pnpm 10.5.1, using dummy `NEXT_PUBLIC_*` values and `AMPLIFY_OUTPUTS_JSON='{"auth":{}}'`. `web-deploy.yml` is the only publisher: it builds the static export and uploads it through the Amplify manual deployment API. The Amplify app has no connected repository and auto-build disabled, so GitHub Actions is the only builder and publisher.
