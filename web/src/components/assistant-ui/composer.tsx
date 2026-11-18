"use client";

import { ComposerPrimitive, useAuiState } from "@assistant-ui/react";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

// Mirror the source composer styling (agent-chat-ui thread/index.tsx:452-522).
const COMPOSER_INPUT_CLASSES =
  "resize-none border-none bg-transparent p-3.5 pb-0 shadow-none outline-none focus:outline-none focus:ring-0 focus-visible:ring-0 focus-visible:border-none min-h-0";

export function Composer() {
  const isRunning = useAuiState((s) => s.thread.isRunning);

  return (
    <div className="bg-muted relative z-10 mx-auto mb-8 w-full max-w-3xl rounded-2xl shadow-xs transition-all">
      <ComposerPrimitive.Root className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
        <ComposerPrimitive.Input asChild rows={1}>
          <Textarea
            placeholder="Type your message..."
            className={COMPOSER_INPUT_CLASSES}
          />
        </ComposerPrimitive.Input>

        <div className="flex items-center gap-6 p-2 pt-4">
          {isRunning ? (
            <ComposerPrimitive.Cancel asChild>
              <Button className="ml-auto">
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Cancel
              </Button>
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send asChild>
              <Button
                type="submit"
                className="ml-auto shadow-md transition-all"
              >
                Send
              </Button>
            </ComposerPrimitive.Send>
          )}
        </div>
      </ComposerPrimitive.Root>
    </div>
  );
}
