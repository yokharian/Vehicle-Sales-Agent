"use client";

import type { ToolCallMessagePartProps } from "@assistant-ui/react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { parseAsBoolean, useQueryState } from "nuqs";
import { useState } from "react";

import { cn } from "@/lib/utils";

const STATUS_BADGE_CLASSES: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  complete: "bg-green-100 text-green-700",
  "requires-action": "bg-amber-100 text-amber-700",
  incomplete: "bg-red-100 text-red-700",
};

function isComplexValue(value: unknown): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

function ToolValue({ value }: { value: unknown }) {
  return isComplexValue(value) ? (
    <code className="rounded bg-gray-50 px-2 py-1 font-mono text-sm break-all">
      {JSON.stringify(value, null, 2)}
    </code>
  ) : (
    <>{String(value)}</>
  );
}

function ArgsTable({ args }: { args: Record<string, unknown> }) {
  const entries = Object.entries(args);

  if (entries.length === 0) {
    return <code className="block p-3 text-sm">{"{}"}</code>;
  }

  return (
    <table className="min-w-full divide-y divide-gray-200">
      <tbody className="divide-y divide-gray-200">
        {entries.map(([key, value]) => (
          <tr key={key}>
            <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-gray-900">
              {key}
            </td>
            <td className="px-4 py-2 text-sm text-gray-500">
              <ToolValue value={value} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function StatusBadge({
  status,
}: {
  status: ToolCallMessagePartProps["status"];
}) {
  return (
    <span
      className={cn(
        "rounded px-2 py-1 text-sm",
        STATUS_BADGE_CLASSES[status.type] ?? "bg-gray-100 text-gray-700",
      )}
    >
      {status.type === "requires-action" || status.type === "incomplete"
        ? `${status.type} (${status.reason})`
        : status.type}
    </span>
  );
}

function ToolResultContent({ result }: { result: unknown }) {
  const [isExpanded, setIsExpanded] = useState(false);

  let parsedContent: unknown;
  let isJsonContent = false;

  if (typeof result === "string") {
    try {
      parsedContent = JSON.parse(result);
      isJsonContent = isComplexValue(parsedContent);
    } catch {
      // Content is not JSON, use as is
      parsedContent = result;
    }
  } else if (isComplexValue(result)) {
    parsedContent = result;
    isJsonContent = true;
  } else {
    parsedContent = result;
  }

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(result);
  const contentLines = contentStr.split("\n");
  const shouldTruncate = contentLines.length > 4 || contentStr.length > 500;
  const displayedContent =
    shouldTruncate && !isExpanded
      ? contentStr.length > 500
        ? contentStr.slice(0, 500) + "..."
        : contentLines.slice(0, 4).join("\n") + "\n..."
      : contentStr;

  const arrayContent =
    isJsonContent && Array.isArray(parsedContent)
      ? (parsedContent as unknown[])
      : [];
  const objectEntries = Array.isArray(parsedContent)
    ? []
    : Object.entries((parsedContent ?? {}) as Record<string, unknown>);

  const rows: [number | string, unknown][] = Array.isArray(parsedContent)
    ? (isExpanded ? arrayContent : arrayContent.slice(0, 5)).map(
        (item, idx) => [idx, item],
      )
    : objectEntries;

  const canExpand =
    (shouldTruncate && !isJsonContent) || arrayContent.length > 5;

  return (
    <div className="min-w-full border-t-[1px] border-gray-200 bg-gray-100">
      <div className="p-3">
        {isJsonContent ? (
          <table className="min-w-full divide-y divide-gray-200">
            <tbody className="divide-y divide-gray-200">
              {rows.map(([key, value], idx) => (
                <tr key={idx}>
                  <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-gray-900">
                    {key}
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">
                    <ToolValue value={value} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <code className="block text-sm">{displayedContent}</code>
        )}
      </div>
      {canExpand && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex w-full cursor-pointer items-center justify-center border-t-[1px] border-gray-200 py-2 text-gray-500 transition-all duration-200 ease-in-out hover:bg-gray-50 hover:text-gray-600"
        >
          {isExpanded ? <ChevronUp /> : <ChevronDown />}
        </button>
      )}
    </div>
  );
}

export function ToolFallback({
  toolName,
  toolCallId,
  args,
  result,
  status,
}: ToolCallMessagePartProps) {
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );

  if (hideToolCalls) return null;

  return (
    <div className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
      <div className="overflow-hidden rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-medium text-gray-900">
              {toolName}
              {toolCallId && (
                <code className="ml-2 rounded bg-gray-100 px-2 py-1 text-sm">
                  {toolCallId}
                </code>
              )}
            </h3>
            <StatusBadge status={status} />
          </div>
        </div>
        <ArgsTable args={args} />
        {result !== undefined && <ToolResultContent result={result} />}
      </div>
    </div>
  );
}
