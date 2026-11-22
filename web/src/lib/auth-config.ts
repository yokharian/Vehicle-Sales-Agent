import { Amplify } from "aws-amplify";
import outputs from "../../amplify_outputs.json";

Amplify.configure(outputs);

/**
 * Contract of the backend's `amplify_outputs.json` custom payload: one user
 * pool for both flows, the Amplify-managed identity pool for registered
 * sessions, and a dedicated unauthenticated-only identity pool for the
 * `createGuest` bootstrap call. `guest` names the client the create-guest
 * lambda mints guest tokens from.
 */
export interface AppAuthConfig {
  userPoolId?: string;
  identityPoolId?: string;
  guestIdentityPoolId?: string;
  appClientIds: {
    default?: string;
    guest?: string;
  };
}

export function getAppAuthConfig(): AppAuthConfig | null {
  const payload = (outputs as { custom?: { payload?: string } }).custom
    ?.payload;
  if (!payload) return null;
  try {
    const parsed = JSON.parse(payload) as Partial<AppAuthConfig>;
    return {
      userPoolId: parsed.userPoolId,
      identityPoolId: parsed.identityPoolId,
      guestIdentityPoolId: parsed.guestIdentityPoolId,
      appClientIds: parsed.appClientIds ?? {},
    };
  } catch {
    return null;
  }
}

export function guestAppClientId(): string | undefined {
  return getAppAuthConfig()?.appClientIds.guest;
}

export function guestAuthConfigAvailable(): boolean {
  return Boolean(guestAppClientId());
}

function applyIdentityPool(identityPoolId: string | undefined): void {
  if (!identityPoolId) {
    Amplify.configure(outputs);
    return;
  }
  Amplify.configure({
    ...outputs,
    auth: { ...outputs.auth, identity_pool_id: identityPoolId },
  });
}

export function configureRegisteredAuth(): void {
  applyIdentityPool(getAppAuthConfig()?.identityPoolId);
}

export function configureGuestAuth(): void {
  applyIdentityPool(getAppAuthConfig()?.guestIdentityPoolId);
}
