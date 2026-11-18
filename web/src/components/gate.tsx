"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Ghost } from "lucide-react";

import type { ReactNode } from "react";
import { AuthPanel } from "@/components/auth-panel";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/Auth";
import { useTurnstileToken } from "@/components/turnstile-widget";

export function Gate({ children }: { children: ReactNode }) {
  const { session, loading, guestExpired, signInAnonymously } = useAuth();
  const [guestPending, setGuestPending] = useState(false);
  const [guestError, setGuestError] = useState<string | null>(null);
  const {
    element: captchaElement,
    reset: resetCaptcha,
    token: captchaToken,
  } = useTurnstileToken("auth");

  const enterAsGuest = useCallback(
    async (token: string) => {
      setGuestPending(true);
      setGuestError(null);
      const { error } = await signInAnonymously(token);
      if (error) {
        setGuestError(error);
      }
      resetCaptcha();
      setGuestPending(false);
    },
    [resetCaptcha, signInAnonymously],
  );

  const autoRestoreStarted = useRef(false);
  useEffect(() => {
    if (session) {
      autoRestoreStarted.current = false;
      return;
    }
    if (guestExpired && captchaToken && !autoRestoreStarted.current) {
      autoRestoreStarted.current = true;
      enterAsGuest(captchaToken);
    }
  }, [session, guestExpired, captchaToken, enterAsGuest]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        Loading...
      </div>
    );
  }

  if (!session) {
    if (guestExpired) {
      return (
        <div className="flex min-h-svh w-full flex-col items-center justify-center gap-3 p-6 md:p-10">
          <p className="text-muted-foreground text-sm">
            {guestPending
              ? "Restoring your guest session..."
              : "Your guest session ended. Starting a new one..."}
          </p>
          {captchaElement}
          {guestError ? (
            <p className="text-destructive text-sm">{guestError}</p>
          ) : null}
          <Button
            disabled={guestPending || !captchaToken}
            onClick={() => captchaToken && enterAsGuest(captchaToken)}
            type="button"
            variant="outline"
          >
            <Ghost className="size-4" />
            Continue as guest
          </Button>
        </div>
      );
    }

    return (
      <div className="flex min-h-svh w-full flex-col items-center justify-center p-6 md:p-10">
        <div className="w-full max-w-sm">
          <AuthPanel turnstileToken={captchaToken} />
          <div className="mt-3 flex flex-col items-center gap-2">
            {captchaElement}
            <Button
              className="w-full"
              disabled={guestPending || !captchaToken}
              onClick={() => captchaToken && enterAsGuest(captchaToken)}
              type="button"
              variant="outline"
            >
              <Ghost className="size-4" />
              {guestPending ? "Entering as guest..." : "Continue as guest"}
            </Button>
            {guestError ? (
              <p className="text-destructive text-sm">{guestError}</p>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col">
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
