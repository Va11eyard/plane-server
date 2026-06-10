/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface CustomComponentProps {
  href: string;
  children: React.ReactNode;
}

type CustomComponent = React.ComponentType<CustomComponentProps>;

interface Props {
  markdown: string;
  className?: string;
  components?: {
    a?: CustomComponent;
    blockquote?: CustomComponent;
    code?: CustomComponent;
    del?: CustomComponent;
    em?: CustomComponent;
    heading?: CustomComponent;
    hr?: CustomComponent;
    image?: CustomComponent;
    inlineCode?: CustomComponent;
    link?: CustomComponent;
    list?: CustomComponent;
    listItem?: CustomComponent;
    paragraph?: CustomComponent;
    strong?: CustomComponent;
    table?: CustomComponent;
    tableCell?: CustomComponent;
    tableHead?: CustomComponent;
    tableRow?: CustomComponent;
  };
  options?: Record<string, unknown>;
}

function HeadingPrimary({ children }: { children: React.ReactNode }) {
  return <h1 className="mb-3 mt-5 text-18 font-semibold text-primary first:mt-0">{children}</h1>;
}

function HeadingSecondary({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-2 mt-4 text-16 font-semibold text-primary first:mt-0">{children}</h2>;
}

function HeadingTertiary({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 mt-3 text-14 font-semibold text-primary first:mt-0">{children}</h3>;
}

function Paragraph({ children }: { children: React.ReactNode }) {
  return <p className="mb-3 text-13 leading-relaxed text-primary last:mb-0">{children}</p>;
}

function HorizontalRule() {
  return <hr className="my-4 border-subtle" />;
}

function Blockquote({ children }: { children: React.ReactNode }) {
  return (
    <blockquote className="mb-3 border-l-2 border-subtle pl-3 text-13 italic text-secondary">{children}</blockquote>
  );
}

function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full border-collapse text-13 text-primary">{children}</table>
    </div>
  );
}

function TableHead({ children }: { children: React.ReactNode }) {
  return <thead className="bg-surface-2">{children}</thead>;
}

function TableRow({ children }: { children: React.ReactNode }) {
  return <tr className="border-b border-subtle">{children}</tr>;
}

function TableHeaderCell({ children }: { children: React.ReactNode }) {
  return <th className="px-3 py-2 text-left font-semibold">{children}</th>;
}

function TableCell({ children }: { children: React.ReactNode }) {
  return <td className="px-3 py-2 align-top">{children}</td>;
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-12">{children}</code>;
}

function CodeBlock({ children }: { children: React.ReactNode }) {
  return (
    <pre className="mb-4 overflow-x-auto rounded-md bg-surface-2 p-3 font-mono text-12 leading-relaxed text-primary">
      <code>{children}</code>
    </pre>
  );
}

function Strong({ children }: { children: React.ReactNode }) {
  return <strong className="font-semibold text-primary">{children}</strong>;
}

function OrderedList({ children }: { children: React.ReactNode }) {
  return <ol className="mb-4 ml-6 list-decimal space-y-1 text-13 text-primary">{children}</ol>;
}

function UnorderedList({ children }: { children: React.ReactNode }) {
  return <ul className="mb-4 ml-6 list-disc space-y-1 text-13 text-primary">{children}</ul>;
}

function ListItem({ children }: { children: React.ReactNode }) {
  return <li className="leading-relaxed">{children}</li>;
}

function Link({ href, children }: CustomComponentProps) {
  return (
    <a href={href} className="underline hover:no-underline" target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

export function MarkdownRenderer({ markdown, className, options = {} }: Props) {
  const customComponents = {
    h1: HeadingPrimary,
    h2: HeadingSecondary,
    h3: HeadingTertiary,
    p: Paragraph,
    ol: OrderedList,
    ul: UnorderedList,
    li: ListItem,
    a: Link,
    hr: HorizontalRule,
    blockquote: Blockquote,
    table: Table,
    thead: TableHead,
    tr: TableRow,
    th: TableHeaderCell,
    td: TableCell,
    code: ({ inline, children }: { inline?: boolean; children: React.ReactNode }) =>
      inline ? <InlineCode>{children}</InlineCode> : <CodeBlock>{children}</CodeBlock>,
    strong: Strong,
  };

  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={customComponents} {...options}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
