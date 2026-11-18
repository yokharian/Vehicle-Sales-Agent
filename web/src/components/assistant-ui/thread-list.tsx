"use client";

import {
  ThreadListItemPrimitive,
  ThreadListPrimitive,
} from "@assistant-ui/react";
import { PanelRightClose, PanelRightOpen, Plus } from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/useMediaQuery";

const THREAD_HISTORY_TITLE = "Thread History";

const LIST_CLASSES =
  "flex h-full w-full flex-col items-start justify-start gap-2 overflow-y-scroll [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent";

function ThreadListItem() {
  return (
    <div className="w-full px-1">
      <ThreadListItemPrimitive.Root className="w-full">
        <ThreadListItemPrimitive.Trigger asChild>
          <Button
            variant="ghost"
            className="w-[280px] items-start justify-start text-left font-normal data-[active=true]:bg-gray-100"
          >
            <p className="w-full truncate text-ellipsis">
              <ThreadListItemPrimitive.Title />
            </p>
          </Button>
        </ThreadListItemPrimitive.Trigger>
      </ThreadListItemPrimitive.Root>
    </div>
  );
}

function NewThreadButton() {
  return (
    <div className="w-full px-1">
      <ThreadListPrimitive.New asChild>
        <Button
          variant="ghost"
          className="w-[280px] items-start justify-start gap-2 text-left font-normal"
        >
          <Plus className="size-4 shrink-0" />
          <span className="truncate text-ellipsis">New Thread</span>
        </Button>
      </ThreadListPrimitive.New>
    </div>
  );
}

function ThreadListBody() {
  return (
    <div className={LIST_CLASSES}>
      <NewThreadButton />
      <ThreadListPrimitive.Items components={{ ThreadListItem }} />
    </div>
  );
}

export function ThreadList() {
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(true),
  );

  const toggleChatHistory = () => setChatHistoryOpen((open) => !open);

  return (
    <>
      {chatHistoryOpen ? (
        <aside className="shadow-inner-right hidden h-full w-[300px] shrink-0 flex-col items-start justify-start gap-6 border-r-[1px] border-slate-300 lg:flex">
          <div className="flex w-full items-center justify-between px-4 pt-1.5">
            <Button
              className="hover:bg-gray-100"
              variant="ghost"
              onClick={toggleChatHistory}
            >
              <PanelRightOpen className="size-5" />
            </Button>
            <h1 className="text-xl font-semibold tracking-tight">
              {THREAD_HISTORY_TITLE}
            </h1>
          </div>
          <ThreadListBody />
        </aside>
      ) : (
        <div className="hidden h-full items-start p-2 lg:flex">
          <Button
            className="hover:bg-gray-100"
            variant="ghost"
            onClick={toggleChatHistory}
          >
            <PanelRightClose className="size-5" />
          </Button>
        </div>
      )}
      <div className="lg:hidden">
        {!chatHistoryOpen && (
          <Button
            className="hover:bg-gray-100"
            variant="ghost"
            onClick={() => setChatHistoryOpen(true)}
          >
            <PanelRightClose className="size-5" />
          </Button>
        )}
        <Sheet
          open={!!chatHistoryOpen && !isLargeScreen}
          onOpenChange={(open) => {
            if (isLargeScreen) return;
            setChatHistoryOpen(open);
          }}
        >
          <SheetContent
            side="left"
            className="flex w-[300px] flex-col gap-6 lg:hidden"
          >
            <SheetHeader>
              <SheetTitle>{THREAD_HISTORY_TITLE}</SheetTitle>
            </SheetHeader>
            <div
              className="flex h-full w-full flex-col"
              onClickCapture={() => setChatHistoryOpen(false)}
            >
              <ThreadListBody />
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
