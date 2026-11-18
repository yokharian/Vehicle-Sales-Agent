"use client";

import { useCallback, useRef, useState } from "react";
import { Turnstile, type TurnstileInstance } from "@marsidev/react-turnstile";

const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

export function useTurnstileToken(
  action: string,
  options?: { enabled?: boolean },
) {
  const enabled = options?.enabled ?? true;
  const instance = useRef<TurnstileInstance | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const element =
    siteKey && enabled ? (
      <Turnstile
        onError={() => setToken(null)}
        onExpire={() => setToken(null)}
        onSuccess={(nextToken) => setToken(nextToken)}
        options={{
          action,
          size: "flexible",
          theme: "auto",
        }}
        ref={instance}
        siteKey={siteKey}
      />
    ) : null;

  const reset = useCallback(() => {
    setToken(null);
    if (enabled) {
      instance.current?.reset();
    }
  }, [enabled]);

  return { element, reset, token };
}
