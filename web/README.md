# Vehicle Sales Agent — Web

Next.js 16 chat front end for the vehicle sales agent: a static-export chat UI built on assistant-ui and the LangGraph SDK, authenticating with Amazon Cognito or a Turnstile-gated guest session.

## Commands

All from this directory. pnpm 10.5.1 is pinned in `packageManager`, so `corepack pnpm ...` works without a global pnpm install.

```bash
corepack pnpm install           # deps
corepack pnpm dev               # dev server
corepack pnpm build             # writes amplify_outputs.json, then static export into out/
corepack pnpm lint              # eslint with typescript6 shim
corepack pnpm format:check      # prettier over the whole directory
corepack pnpm format            # prettier --write
```

A local `pnpm build` needs real env values, or it follows the CI pattern of dummy `NEXT_PUBLIC_*` values plus `AMPLIFY_OUTPUTS_JSON='{"auth":{}}'`.
