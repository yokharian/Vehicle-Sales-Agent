import type { LangChainMessage } from "@assistant-ui/react-langgraph";
import type { Client, Config } from "@langchain/langgraph-sdk";

type GraphState = {
  messages: LangChainMessage[];
};

/** Checkpoints fetched per history page. */
const HISTORY_PAGE_SIZE = 50;

/**
 * True when the server state messages end with exactly the same message ids
 * as the client transcript being regenerated. Ids are the only stable key
 * shared by both sides, so a missing id on either side is a mismatch.
 */
export const endsWithParentIds = (
  stateMessages: readonly LangChainMessage[] | undefined,
  parentMessages: readonly LangChainMessage[],
): boolean => {
  if (!stateMessages || parentMessages.length === 0) return false;
  if (stateMessages.length < parentMessages.length) return false;

  const offset = stateMessages.length - parentMessages.length;
  return parentMessages.every((parent, index) => {
    const stateMessage = stateMessages[offset + index];
    return (
      typeof parent.id === "string" &&
      typeof stateMessage?.id === "string" &&
      parent.id === stateMessage.id
    );
  });
};

/**
 * Resolves the LangGraph checkpoint the runtime should fork from when it
 * regenerates the transcript ending at `parentMessages`.
 *
 * `getHistory` returns states newest first. The first state whose
 * `values.messages` ends with the parent ids is the state from which the
 * regenerated turn starts; pages are followed with a `before` cursor so older
 * messages still find their checkpoint instead of forking from the thread
 * head. Returns null when no state matches (empty parent, changed ids, or a
 * history that ends before the parent).
 */
export const resolveCheckpointId = async (
  client: Client<GraphState>,
  threadId: string,
  parentMessages: LangChainMessage[],
): Promise<string | null> => {
  if (parentMessages.length === 0) return null;

  let before: Config | undefined;

  for (;;) {
    const states = await client.threads.getHistory(threadId, {
      limit: HISTORY_PAGE_SIZE,
      ...(before ? { before } : {}),
    });

    for (const state of states) {
      if (endsWithParentIds(state.values.messages, parentMessages)) {
        return state.checkpoint.checkpoint_id ?? null;
      }
    }

    const oldestCheckpointId = states.at(-1)?.checkpoint.checkpoint_id;
    if (states.length < HISTORY_PAGE_SIZE || !oldestCheckpointId) return null;
    before = { configurable: { checkpoint_id: oldestCheckpointId } };
  }
};
