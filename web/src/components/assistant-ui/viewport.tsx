"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { ArrowDown } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { authFetch } from "@/lib/auth-fetch";

// `autoScroll` lets the primitive own stick-to-bottom tracking; no direct
// use-stick-to-bottom wiring.
export function ThreadViewport({ children }: { children: ReactNode }) {
  return (
    <ThreadPrimitive.Viewport
      autoScroll
      className="relative flex h-full flex-col overflow-y-auto scroll-smooth bg-white"
    >
      {children}
    </ThreadPrimitive.Viewport>
  );
}

// Renders nothing while the viewport is already at the bottom.
export function ScrollToBottomButton() {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <Button
        variant="outline"
        size="icon"
        className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full shadow-lg"
      >
        <ArrowDown className="size-4" />
        <span className="sr-only">Scroll to bottom</span>
      </Button>
    </ThreadPrimitive.ScrollToBottom>
  );
}

const EMPTY_STATE_HINT =
  "Ask about a vehicle, request a financing plan, or ask anything about the company.";

export function ThreadViewportEmpty() {
  return (
    <ThreadPrimitive.Empty>
      <div className="flex w-full flex-col items-center gap-2 py-24 text-center">
        <p className="text-lg font-semibold tracking-tight">
          Start a conversation
        </p>
        <p className="text-muted-foreground max-w-md text-sm">
          {EMPTY_STATE_HINT}
        </p>
      </div>
    </ThreadPrimitive.Empty>
  );
}

const HEALTH_CHECK_TOAST_ID = "info-health-check";

const readApiUrl = (): string | undefined =>
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "") || undefined;

const isAbortError = (error: unknown): boolean =>
  error instanceof DOMException && error.name === "AbortError";

const describeError = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const toastUnreachable = (description: string) =>
  toast.error("Cannot reach the assistant server.", {
    // Stable id: StrictMode's double-invoked effect (and repeated failures)
    // update this single toast instead of stacking duplicates.
    id: HEALTH_CHECK_TOAST_ID,
    description,
    richColors: true,
    closeButton: true,
  });

// Aborts never toast, so StrictMode's cleanup-aborted first request is silent.
export function InfoHealthCheck() {
  useEffect(() => {
    const apiUrl = readApiUrl();
    if (!apiUrl) return; // RuntimeProvider already fails loudly when unset.

    const controller = new AbortController();

    const checkHealth = async () => {
      try {
        const response = await authFetch(`${apiUrl}/info`, {
          signal: controller.signal,
        });
        if (response.ok) return;

        toastUnreachable(`GET /info responded with ${response.status}.`);
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) return;

        toastUnreachable(`GET /info failed: ${describeError(error)}`);
      }
    };

    void checkHealth();

    return () => controller.abort();
  }, []);

  return null;
}
