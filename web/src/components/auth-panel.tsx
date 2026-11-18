"use client";

import "@aws-amplify/ui-react/styles.css";

import { useMemo, useRef } from "react";
import { Authenticator, type AuthenticatorProps } from "@aws-amplify/ui-react";
import { signUp } from "aws-amplify/auth";
import type { SignUpInput } from "aws-amplify/auth";

import { getAppAuthConfig } from "@/lib/auth-config";

type SignUpService = NonNullable<
  NonNullable<AuthenticatorProps["services"]>["handleSignUp"]
>;

/**
 * The pool expects the Turnstile token in `validationData` (the hand-written
 * sign-up form sent it the same way). This keeps that security contract while
 * the Authenticator owns every credential screen.
 */
const createSignUp = (
  getToken: () => string | null | undefined,
): SignUpService =>
  ((first: unknown, second?: unknown) => {
    const input = (second ?? first) as SignUpInput;
    const base = input.options ?? { userAttributes: {} };
    const turnstileToken = getToken();

    return signUp({
      ...input,
      options: turnstileToken
        ? {
            ...base,
            validationData: {
              ...(base.validationData ?? {}),
              turnstileToken,
            },
          }
        : base,
    });
  }) as SignUpService;

export function AuthPanel({
  turnstileToken,
  className,
}: {
  turnstileToken?: string | null;
  className?: string;
}) {
  const tokenRef = useRef<string | null | undefined>(turnstileToken);
  tokenRef.current = turnstileToken;

  const services = useMemo(
    () => ({ handleSignUp: createSignUp(() => tokenRef.current) }),
    [],
  );

  const configured = Boolean(getAppAuthConfig()?.userPoolId);

  if (!configured) {
    return (
      <p className="text-muted-foreground text-sm">
        Authentication is not configured.
      </p>
    );
  }

  return (
    <div className={className}>
      <Authenticator services={services} />
    </div>
  );
}
