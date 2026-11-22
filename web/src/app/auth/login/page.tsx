"use client";

import { AuthPanel } from "@/components/auth-panel";
import { useTurnstileToken } from "@/components/turnstile-widget";

export default function Page() {
  const { element: captchaElement, token: captchaToken } =
    useTurnstileToken("auth");

  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <AuthPanel turnstileToken={captchaToken} />
        {captchaElement}
      </div>
    </div>
  );
}
