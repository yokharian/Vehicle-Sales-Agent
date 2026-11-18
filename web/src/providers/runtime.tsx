"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  type LangChainMessage,
  unstable_createLangGraphStream,
  useLangGraphRuntime,
} from "@assistant-ui/react-langgraph";
import { Client } from "@langchain/langgraph-sdk";
import { parseAsString, useQueryState } from "nuqs";
import { useCallback, useMemo, type ReactNode } from "react";

import { authFetch } from "@/lib/auth-fetch";
import { resolveCheckpointId } from "@/lib/checkpoint-history";
import { createThreadListAdapter } from "@/lib/thread-list-adapter";

type GraphState = {
  messages: LangChainMessage[];
};

const readApiUrl = (): string => {
  const value = process.env.NEXT_PUBLIC_API_URL?.trim();

  if (!value) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not set. Point it at the LangGraph API server.",
    );
  }

  return value.replace(/\/+$/, "");
};

const readAssistantId = (): string => {
  const value = process.env.NEXT_PUBLIC_ASSISTANT_ID?.trim();

  if (!value) {
    throw new Error(
      "NEXT_PUBLIC_ASSISTANT_ID is not set. Point it at the LangGraph assistant.",
    );
  }

  return value;
};

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const [threadId, setThreadId] = useQueryState("threadId", parseAsString);
  const apiUrl = useMemo(() => readApiUrl(), []);
  const assistantId = useMemo(() => readAssistantId(), []);

  const client = useMemo(
    () =>
      new Client<GraphState>({
        apiUrl,
        callerOptions: { fetch: authFetch },
      }),
    [apiUrl],
  );

  const stream = useMemo(
    () => unstable_createLangGraphStream({ client, assistantId }),
    [client, assistantId],
  );

  const threadListAdapter = useMemo(
    () => createThreadListAdapter(client, assistantId),
    [client, assistantId],
  );

  const getCheckpointId = useCallback(
    (externalId: string, parentMessages: LangChainMessage[]) =>
      resolveCheckpointId(client, externalId, parentMessages),
    [client],
  );

  const runtime = useLangGraphRuntime({
    unstable_threadListAdapter: threadListAdapter,
    stream,
    load: async (externalId) => {
      const state = await client.threads.getState<GraphState>(externalId);
      return { messages: state.values.messages };
    },
    threadId: threadId ?? undefined,
    onThreadIdChange: (id) => setThreadId(id ?? null),
    getCheckpointId,
    unstable_allowCancellation: true,
    autoCancelPendingToolCalls: false,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
