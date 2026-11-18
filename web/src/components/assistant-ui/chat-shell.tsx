"use client";

import { ThreadPrimitive } from "@assistant-ui/react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";
import { useMemo } from "react";

import { Composer } from "@/components/assistant-ui/composer";
import {
  AssistantMessage,
  UserMessage,
} from "@/components/assistant-ui/message";
import { ThreadList } from "@/components/assistant-ui/thread-list";
import {
  InfoHealthCheck,
  ScrollToBottomButton,
  ThreadViewport,
  ThreadViewportEmpty,
} from "@/components/assistant-ui/viewport";
import { CurrentUserAvatar } from "@/components/current-user-avatar";
import { GuestBanner } from "@/components/guest-banner";
import { LogoutButton } from "@/components/logout-button";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useAuth } from "@/providers/Auth";

const readApiUrl = (): string | undefined =>
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "") || undefined;

function ConnectedHost({ apiUrl }: { apiUrl: string }) {
  let host: string;
  try {
    host = new URL(apiUrl).host;
  } catch {
    host = apiUrl;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="text-muted-foreground hidden max-w-40 truncate text-xs sm:inline">
            {host}
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          <p>Connected to {apiUrl}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function ChatShell() {
  const { isGuest } = useAuth();
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(true),
  );
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const apiUrl = readApiUrl();

  const messageComponents = useMemo(
    () => ({
      UserMessage,
      AssistantMessage: () => <AssistantMessage hideTools={hideToolCalls} />,
    }),
    [hideToolCalls],
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      <ThreadList />
      <main className="flex min-w-0 flex-1 flex-col">
        {isGuest ? <GuestBanner /> : null}
        <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
          <header className="relative z-10 flex shrink-0 items-center justify-between gap-3 p-2">
            <div className="flex min-w-0 items-center gap-2">
              {(!chatHistoryOpen || !isLargeScreen) && (
                <Button
                  className="hover:bg-gray-100"
                  variant="ghost"
                  onClick={() => setChatHistoryOpen((open) => !open)}
                >
                  {chatHistoryOpen ? (
                    <PanelRightOpen className="size-5" />
                  ) : (
                    <PanelRightClose className="size-5" />
                  )}
                </Button>
              )}
              <h1 className="text-xl font-semibold tracking-tight">
                Agent Chat
              </h1>
              {apiUrl ? <ConnectedHost apiUrl={apiUrl} /> : null}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="flex items-center gap-2">
                <Switch
                  checked={hideToolCalls}
                  id="hide-tool-calls"
                  onCheckedChange={setHideToolCalls}
                />
                <label
                  className="text-muted-foreground hidden text-sm md:inline"
                  htmlFor="hide-tool-calls"
                >
                  Hide Tool Calls
                </label>
              </div>
              <CurrentUserAvatar />
              <LogoutButton />
            </div>
          </header>
          <div className="relative flex min-h-0 flex-1 flex-col">
            <ThreadViewport>
              <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pt-8">
                <ThreadPrimitive.Messages components={messageComponents} />
                <ThreadViewportEmpty />
              </div>
            </ThreadViewport>
            <ScrollToBottomButton />
          </div>
          <Composer />
          <InfoHealthCheck />
        </ThreadPrimitive.Root>
      </main>
    </div>
  );
}
