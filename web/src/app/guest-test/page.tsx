"use client";

import Link from "next/link";
import { useState } from "react";

import { useTurnstileToken } from "@/components/turnstile-widget";
import { createGuestSession } from "@/lib/guest-session";

export default function GuestTestPage() {
  const { element, token, reset } = useTurnstileToken("guest_test");
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!token) return;
    setPending(true);
    setError(null);
    setResult(null);
    try {
      const session = await createGuestSession(token);
      setResult(
        `OK - access ${session.accessToken.slice(0, 16)}... expires ${new Date(session.expiresAt).toISOString()}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      reset();
      setPending(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 p-8">
      <h1 className="text-xl font-semibold">Guest session MVP</h1>
      <p className="text-muted-foreground text-sm">
        Isolated test of the Turnstile widget + AppSync createGuest call. No
        chat API is involved, so a failure here is a guest-session problem and a
        success here points at the backend.
      </p>
      <div>
        {element ?? (
          <p className="text-destructive text-sm">
            Turnstile widget not configured (NEXT_PUBLIC_TURNSTILE_SITE_KEY
            missing).
          </p>
        )}
      </div>
      <button
        className="bg-primary text-primary-foreground rounded-md px-4 py-2 text-sm disabled:opacity-50"
        disabled={!token || pending}
        onClick={run}
        type="button"
      >
        {pending
          ? "Creating guest session..."
          : token
            ? "Create guest session"
            : "Waiting for Turnstile..."}
      </button>
      {result ? (
        <pre className="bg-muted overflow-x-auto rounded-md p-3 text-xs">
          {result}
        </pre>
      ) : null}
      {error ? (
        <pre className="bg-destructive/10 text-destructive overflow-x-auto rounded-md p-3 text-xs">
          {error}
        </pre>
      ) : null}
      <Link
        className="text-sm underline"
        href="/"
      >
        Back to chat
      </Link>
    </main>
  );
}
