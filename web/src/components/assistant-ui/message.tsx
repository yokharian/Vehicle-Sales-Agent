"use client";

import {
  ActionBarPrimitive,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react";
import { Copy, CopyCheck, RefreshCcw } from "lucide-react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { MarkdownText } from "./markdown-text";
import { ToolFallback } from "./tool-fallback";

function CopyButton() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <ActionBarPrimitive.Copy
          copiedDuration={2000}
          asChild
        >
          <Button
            variant="ghost"
            size="icon"
            className="group/copy size-6 p-1"
          >
            <Copy className="block group-data-[copied=true]/copy:hidden" />
            <CopyCheck className="hidden text-green-500 group-data-[copied=true]/copy:block" />
            <span className="sr-only">Copy content</span>
          </Button>
        </ActionBarPrimitive.Copy>
      </TooltipTrigger>
      <TooltipContent>Copy content</TooltipContent>
    </Tooltip>
  );
}

function ReloadButton() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <ActionBarPrimitive.Reload asChild>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 p-1"
          >
            <RefreshCcw />
            <span className="sr-only">Refresh</span>
          </Button>
        </ActionBarPrimitive.Reload>
      </TooltipTrigger>
      <TooltipContent>Refresh</TooltipContent>
    </Tooltip>
  );
}

export function AssistantMessage({
  hideTools = false,
}: {
  hideTools?: boolean;
} = {}) {
  return (
    <MessagePrimitive.Root className="flex w-full flex-col gap-2 py-4">
      <MessagePrimitive.Parts
        components={{
          Text: MarkdownText,
          tools: { Fallback: hideTools ? () => null : ToolFallback },
        }}
      />
      <ActionBarPrimitive.Root
        hideWhenRunning
        className="flex items-center gap-2"
      >
        <CopyButton />
        <ReloadButton />
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  );
}

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex w-full flex-col items-end gap-2 py-4">
      <MessagePrimitive.Parts />
      <ActionBarPrimitive.Root className="flex items-center gap-2">
        <CopyButton />
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  );
}

export function AssistantMessageLoading() {
  const isRunning = useAuiState((s) => s.thread.isRunning);

  if (!isRunning) return null;

  return (
    <div className="mr-auto flex items-start gap-2">
      <div className="bg-muted flex h-8 items-center gap-1 rounded-2xl px-4 py-2">
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_0.5s_infinite] rounded-full"></div>
        <div className="bg-foreground/50 h-1.5 w-1.5 animate-[pulse_1.5s_ease-in-out_1s_infinite] rounded-full"></div>
      </div>
    </div>
  );
}

const describeError = (error: unknown): string => {
  if (typeof error === "string" && error.length > 0) return error;
  try {
    const serialized = JSON.stringify(error);
    if (serialized && serialized !== "null" && serialized !== "undefined") {
      return serialized;
    }
  } catch {
    // no-op
  }
  return "Unknown stream error";
};

// The LangGraph runtime reports a stream failure by setting the last assistant
// message's status to { type: "incomplete", reason: "error", error }; the thread
// scope's state has no error field, so this selector derives it from the message.
export function ThreadErrorToaster() {
  const errorMessage = useAuiState((s) => {
    const messages = s.thread.messages;
    const last = messages[messages.length - 1];

    if (!last || last.role !== "assistant") return undefined;

    const { status } = last;
    if (status.type !== "incomplete" || status.reason !== "error") {
      return undefined;
    }

    return describeError(status.error);
  });
  const lastError = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (errorMessage === undefined) {
      lastError.current = undefined;
      return;
    }

    // Message has already been toasted. Do not modify ref, return early.
    if (lastError.current === errorMessage) return;

    // Message is defined and has not been toasted yet. Save it, then toast.
    lastError.current = errorMessage;
    toast.error("An error occurred. Please try again.", {
      description: (
        <p>
          <strong>Error:</strong> <code>{errorMessage}</code>
        </p>
      ),
      richColors: true,
      closeButton: true,
    });
  }, [errorMessage]);

  return null;
}
