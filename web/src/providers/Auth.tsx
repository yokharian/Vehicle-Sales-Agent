"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { fetchAuthSession, getCurrentUser, signOut } from "aws-amplify/auth";
import { Hub } from "aws-amplify/utils";
import {
  configureRegisteredAuth,
  guestAuthConfigAvailable,
} from "@/lib/auth-config";
import {
  clearGuestTokens,
  createGuestSession,
  currentGuestAccessToken,
  isGuestAccessToken,
  onGuestSessionLost,
  readGuestTokens,
} from "@/lib/guest-session";

interface CognitoUser {
  username: string;
  email?: string;
  attributes?: Record<string, string>;
}

interface AuthSession {
  user: CognitoUser | null;
  accessToken?: string;
  idToken?: string;
}

type AuthContextValue = {
  session: AuthSession | null;
  loading: boolean;
  isGuest: boolean;
  signInAnonymously: (captchaToken?: string) => Promise<{
    error: string | null;
  }>;
  signOut: () => Promise<void>;
  guestExpired: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const GUEST_USER: CognitoUser = {
  username: "guest",
  attributes: { "custom:is_guest": "true" },
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const [guestExpired, setGuestExpired] = useState(false);

  const adoptGuestTokens = useCallback(
    (accessToken: string, idToken: string) => {
      setSession({
        user: GUEST_USER,
        accessToken,
        idToken,
      });
      setIsGuest(true);
      setGuestExpired(false);
    },
    [],
  );

  useEffect(() => {
    return onGuestSessionLost(() => {
      setSession(null);
      setIsGuest(false);
      setGuestExpired(true);
    });
  }, []);

  useEffect(() => {
    let mounted = true;

    configureRegisteredAuth();

    const loadSession = async () => {
      try {
        const authSession = await fetchAuthSession();
        const currentUser = await getCurrentUser();

        if (mounted) {
          setSession({
            user: currentUser
              ? {
                  username: currentUser.username,
                  email: currentUser.signInDetails?.loginId,
                  attributes: (
                    currentUser as { attributes?: Record<string, string> }
                  ).attributes,
                }
              : null,
            accessToken: authSession.tokens?.accessToken?.toString(),
            idToken: authSession.tokens?.idToken?.toString(),
          });
          setIsGuest(false);
        }
        return;
      } catch {
        // No registered session.
      }

      const guestTokens = readGuestTokens();
      if (!guestTokens) {
        if (mounted) {
          setSession(null);
          setIsGuest(false);
        }
        return;
      }

      const accessToken = await currentGuestAccessToken();
      if (mounted) {
        if (accessToken && isGuestAccessToken(accessToken)) {
          adoptGuestTokens(accessToken, guestTokens.idToken);
        } else {
          clearGuestTokens();
          setSession(null);
          setIsGuest(false);
          setGuestExpired(true);
        }
      }
    };

    loadSession().finally(() => {
      if (mounted) setLoading(false);
    });

    const hubListener = (data: {
      payload: { event: string; data?: unknown };
    }) => {
      const { event } = data.payload;
      if (
        event === "signedIn" ||
        event === "signedOut" ||
        event === "tokenRefresh"
      ) {
        loadSession();
      }
    };

    const unsubscribe = Hub.listen("auth", hubListener);

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [adoptGuestTokens]);

  /**
   * Guests are minted by the backend (`createGuest`): the pool password is
   * burned server-side, so this is the only way in — there is no sign-in
   * afterwards, and the session lives in the returned tokens alone.
   */
  const signInAnonymouslyFn = useCallback(
    async (captchaToken?: string): Promise<{ error: string | null }> => {
      if (!guestAuthConfigAvailable()) {
        return {
          error: "Guest sign-in is unavailable. Please try again later.",
        };
      }
      if (!captchaToken) {
        return { error: "Complete the captcha to continue as guest." };
      }

      try {
        const tokens = await createGuestSession(captchaToken);
        adoptGuestTokens(tokens.accessToken, tokens.idToken);
        return { error: null };
      } catch (error: unknown) {
        return {
          error:
            error instanceof Error ? error.message : "Guest sign in failed",
        };
      }
    },
    [adoptGuestTokens],
  );

  const signOutFn = useCallback(async () => {
    try {
      if (!isGuest) {
        configureRegisteredAuth();
        await signOut({ global: true });
      }
    } catch (error) {
      console.error("Sign out error:", error);
    } finally {
      clearGuestTokens();
      setSession(null);
      setIsGuest(false);
      setGuestExpired(false);
    }
  }, [isGuest]);

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        isGuest,
        signInAnonymously: signInAnonymouslyFn,
        signOut: signOutFn,
        guestExpired,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export { useAuth };
