import { generateClient } from "aws-amplify/data";
import {
  configureGuestDataAuth,
  configureRegisteredAuth,
  getAppAuthConfig,
} from "./auth-config";

const STORAGE_KEY = "vsa.guest.tokens";
const EXPIRY_SKEW_MS = 60_000;

export interface GuestTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresAt: number;
}

export type GuestTokenResponse = {
  accessToken: string;
  idToken: string;
  refreshToken: string;
  expiresIn: number;
};

type CognitoAuthResult = {
  AccessToken?: string;
  IdToken?: string;
  RefreshToken?: string;
  ExpiresIn?: number;
};

let memoryTokens: GuestTokens | null = null;
const sessionLostListeners = new Set<() => void>();

/**
 * Fires when the guest session cannot be renewed any more, so the UI can mint
 * a replacement instead of leaving stale tokens on screen.
 */
export function onGuestSessionLost(listener: () => void): () => void {
  sessionLostListeners.add(listener);
  return () => {
    sessionLostListeners.delete(listener);
  };
}

function notifyGuestSessionLost(): void {
  for (const listener of sessionLostListeners) listener();
}

function toTokens(response: GuestTokenResponse): GuestTokens {
  return {
    accessToken: response.accessToken,
    idToken: response.idToken,
    refreshToken: response.refreshToken,
    expiresAt: Date.now() + response.expiresIn * 1000,
  };
}

function isGuestTokenResponse(value: unknown): value is GuestTokenResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Partial<GuestTokenResponse>;
  return (
    typeof v.accessToken === "string" &&
    typeof v.idToken === "string" &&
    typeof v.refreshToken === "string" &&
    typeof v.expiresIn === "number"
  );
}

function parseResponseBody(data: unknown): GuestTokenResponse {
  const payload =
    typeof data === "string" ? (JSON.parse(data) as unknown) : data;
  if (!isGuestTokenResponse(payload)) {
    throw new Error("createGuest returned an unexpected payload");
  }
  return payload;
}

/**
 * Guest tokens live in sessionStorage (never localStorage) so a closed tab
 * ends the session; memory is the primary copy and storage the reload mirror.
 */
export function saveGuestTokens(response: GuestTokenResponse): GuestTokens {
  const tokens = toTokens(response);
  memoryTokens = tokens;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
  } catch (error) {
    console.warn("guest session storage write failed", error);
  }
  return tokens;
}

export function readGuestTokens(): GuestTokens | null {
  if (memoryTokens) return memoryTokens;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GuestTokens>;
    if (
      typeof parsed.accessToken !== "string" ||
      typeof parsed.idToken !== "string" ||
      typeof parsed.refreshToken !== "string" ||
      typeof parsed.expiresAt !== "number"
    ) {
      return null;
    }
    memoryTokens = parsed as GuestTokens;
    return memoryTokens;
  } catch {
    return null;
  }
}

export function clearGuestTokens(): void {
  memoryTokens = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (error) {
    console.warn("guest session storage clear failed", error);
  }
}

const GUEST_GROUP = "guest";

/**
 * Guest marker: the create-guest lambda adds the user to the `guest` group
 * before minting tokens, so `cognito:groups` carries the flag regardless of
 * which app client issued the token.
 */
export function isGuestAccessToken(accessToken: string): boolean {
  const claims = decodeJwtPayload(accessToken);
  const groups = claims?.["cognito:groups"];
  return Array.isArray(groups) && groups.includes(GUEST_GROUP);
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const segment = token.split(".")[1];
  if (!segment) return null;
  try {
    const padded = segment.replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(padded.padEnd(Math.ceil(padded.length / 4) * 4, "="));
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Mints a brand-new guest (AppSync `createGuest`, IAM guest authorization). */
export async function createGuestSession(
  turnstileToken: string,
  email?: string,
): Promise<GuestTokens> {
  // The query runs before the caller holds a token, so it must execute
  // against the guest identity pool's unauthenticated role. Restore the
  // registered pool afterwards so credential resolution keeps working.
  configureGuestDataAuth();
  try {
    const client = generateClient();
    const queries = client.queries as unknown as {
      createGuest: (args: {
        turnstileToken: string;
        email?: string;
      }) => Promise<{ data?: unknown; errors?: unknown[] }>;
    };

    const { data, errors } = await queries.createGuest({
      turnstileToken,
      ...(email ? { email } : {}),
    });

    if (errors?.length) {
      const first = errors[0] as { message?: string };
      throw new Error(first?.message ?? "createGuest failed");
    }
    return saveGuestTokens(parseResponseBody(data));
  } finally {
    configureRegisteredAuth();
  }
}

async function refreshGuestTokens(
  tokens: GuestTokens,
): Promise<GuestTokens | null> {
  const config = getAppAuthConfig();
  const clientId = config?.appClientIds.guest;
  const region = config?.userPoolId?.split("_")[0];
  if (!clientId || !region) return null;

  try {
    const response = await fetch(
      `https://cognito-idp.${region}.amazonaws.com/`,
      {
        method: "POST",
        headers: {
          "content-type": "application/x-amz-json-1.1",
          "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
        },
        body: JSON.stringify({
          AuthFlow: "REFRESH_TOKEN_AUTH",
          ClientId: clientId,
          AuthParameters: { REFRESH_TOKEN: tokens.refreshToken },
        }),
      },
    );

    if (!response.ok) {
      clearGuestTokens();
      notifyGuestSessionLost();
      return null;
    }

    const body = (await response.json()) as {
      AuthenticationResult?: CognitoAuthResult;
    };
    const result = body.AuthenticationResult;
    if (!result?.AccessToken || !result.IdToken) {
      clearGuestTokens();
      notifyGuestSessionLost();
      return null;
    }

    return saveGuestTokens({
      accessToken: result.AccessToken,
      idToken: result.IdToken,
      refreshToken: result.RefreshToken ?? tokens.refreshToken,
      expiresIn: result.ExpiresIn ?? 3600,
    });
  } catch {
    return null;
  }
}

/**
 * Valid guest access token, renewing with the refresh token before expiry.
 * Returns null when the guest is gone and only a fresh createGuest can help.
 */
export async function currentGuestAccessToken(): Promise<string | null> {
  const tokens = readGuestTokens();
  if (!tokens) return null;
  if (tokens.expiresAt - EXPIRY_SKEW_MS > Date.now()) return tokens.accessToken;

  const renewed = await refreshGuestTokens(tokens);
  if (renewed) return renewed.accessToken;
  notifyGuestSessionLost();
  return null;
}
