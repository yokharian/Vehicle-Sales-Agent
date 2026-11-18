import { fetchAuthSession } from "aws-amplify/auth";
import {
  configureRegisteredAuth,
  guestAuthConfigAvailable,
} from "./auth-config";
import { currentGuestAccessToken } from "./guest-session";

/**
 * `fetch` wrapper that injects the current Cognito access token as an
 * `Authorization: Bearer` header on every request.
 *
 * Pass it to the LangGraph SDK via `callerOptions.fetch` (HTTP client)
 * and `fetch` (SSE/WS transport) so all traffic is authenticated.
 *
 * The token is resolved from the registered session first, then from the
 * guest token store (renewed with its refresh token when close to expiry);
 * sessions without any token pass through unauthenticated and the backend
 * decides.
 */
export const authFetch = async (
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> => {
  const accessToken = await currentAccessToken();

  if (accessToken) {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);

    return fetch(input, {
      ...init,
      headers,
    });
  }

  return fetch(input, init);
};

const currentAccessToken = async (): Promise<string | undefined> => {
  configureRegisteredAuth();

  const registered = await sessionToken();
  if (registered) return registered;

  if (guestAuthConfigAvailable()) {
    const guest = await currentGuestAccessToken();
    if (guest) return guest;
  }

  return undefined;
};

const sessionToken = async (): Promise<string | undefined> => {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.accessToken?.toString();
  } catch {
    return undefined;
  }
};
