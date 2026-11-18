"use client";

import "@assistant-ui/react-markdown/styles/dot.css";
import "katex/dist/katex.min.css";

import {
  MarkdownTextPrimitive,
  normalizeMathDelimiters,
} from "@assistant-ui/react-markdown";
import { memo } from "react";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

const MarkdownTextImpl = () => (
  <div className="prose prose-neutral dark:prose-invert prose-code:before:content-none prose-code:after:content-none max-w-none">
    <MarkdownTextPrimitive
      preprocess={normalizeMathDelimiters}
      rehypePlugins={[rehypeKatex]}
      remarkPlugins={[remarkGfm, remarkMath]}
    />
  </div>
);

export const MarkdownText = memo(MarkdownTextImpl);
