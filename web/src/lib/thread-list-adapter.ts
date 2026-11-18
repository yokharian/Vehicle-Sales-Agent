import type { AssistantStream, AssistantStreamChunk } from "assistant-stream";
import type { RemoteThreadListAdapter } from "@assistant-ui/react";
import type { Client, Thread } from "@langchain/langgraph-sdk";

type ThreadMetadata = Awaited<ReturnType<RemoteThreadListAdapter["fetch"]>>;

const TITLE_MAX_LENGTH = 60;
const UNTITLED = "Untitled";
const LOCAL_THREAD_ID_PREFIX = "__LOCALID_";

const getMessages = (values: Thread["values"]): unknown[] => {
  if (!values || Array.isArray(values)) return [];

  const messages = values.messages;
  return Array.isArray(messages) ? messages : [];
};

const getTextFromContent = (content: unknown): string => {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";

  const texts: string[] = [];
  for (const part of content) {
    if (
      typeof part === "object" &&
      part !== null &&
      "type" in part &&
      part.type === "text" &&
      "text" in part &&
      typeof part.text === "string"
    ) {
      texts.push(part.text);
    }
  }
  return texts.join(" ");
};

const getThreadTitle = (values: Thread["values"]): string => {
  const firstHuman = getMessages(values).find(
    (message) =>
      typeof message === "object" &&
      message !== null &&
      "type" in message &&
      message.type === "human",
  );

  const content =
    typeof firstHuman === "object" &&
    firstHuman !== null &&
    "content" in firstHuman
      ? firstHuman.content
      : undefined;

  const title = getTextFromContent(content).trim();
  return title ? title.slice(0, TITLE_MAX_LENGTH) : UNTITLED;
};

const toThreadMetadata = (thread: Thread): ThreadMetadata => ({
  status: "regular",
  remoteId: thread.thread_id,
  externalId: thread.thread_id,
  title: getThreadTitle(thread.values),
  lastMessageAt: thread.updated_at ? new Date(thread.updated_at) : undefined,
});

/**
 * Backs the assistant-ui thread list with LangGraph threads.
 * Memoize the result: replacing the adapter reloads the list.
 */
export function createThreadListAdapter(
  client: Client,
  assistantId: string,
): RemoteThreadListAdapter {
  return {
    list: async () => {
      const threads = await client.threads.search({
        metadata: { graph_id: assistantId },
        limit: 100,
      });

      return { threads: threads.map(toThreadMetadata) };
    },
    initialize: async (threadId) => {
      if (threadId.startsWith(LOCAL_THREAD_ID_PREFIX)) {
        const thread = await client.threads.create({ graphId: assistantId });
        return { remoteId: thread.thread_id, externalId: thread.thread_id };
      }

      await client.threads.create({
        threadId,
        graphId: assistantId,
        ifExists: "do_nothing",
      });

      return { remoteId: threadId, externalId: threadId };
    },
    delete: async (remoteId) => {
      await client.threads.delete(remoteId);
    },
    rename: async (remoteId, newTitle) => {
      await client.threads.update(remoteId, {
        metadata: { title: newTitle },
      });
    },
    fetch: async (threadId) => {
      const thread = await client.threads.get(threadId);
      return toThreadMetadata(thread);
    },
    archive: () => Promise.resolve(),
    generateTitle: (): Promise<AssistantStream> =>
      Promise.resolve(
        new ReadableStream<AssistantStreamChunk>({
          start(controller) {
            controller.close();
          },
        }),
      ),
  };
}
