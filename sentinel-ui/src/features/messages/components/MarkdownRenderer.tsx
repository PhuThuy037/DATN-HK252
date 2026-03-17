import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

type MarkdownRendererProps = {
  content: string;
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="space-y-2 break-words text-sm text-foreground [&_li]:ml-4 [&_li]:list-disc [&_ol>li]:list-decimal [&_pre]:overflow-auto [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:p-1.5 [&_th]:border [&_th]:bg-muted [&_th]:p-1.5">
      <ReactMarkdown
        components={{
          a: ({ node: _node, ...props }) => (
            <a
              {...props}
              className="underline underline-offset-4"
              rel="noreferrer"
              target="_blank"
            />
          ),
          code({ inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const code = String(children).replace(/\n$/, "");

            if (!inline && match) {
              return (
                <SyntaxHighlighter
                  customStyle={{ borderRadius: 8, margin: 0 }}
                  language={match[1]}
                  style={oneLight}
                  {...props}
                >
                  {code}
                </SyntaxHighlighter>
              );
            }

            return (
              <code
                className="rounded bg-muted px-1 py-0.5 font-mono text-xs"
                {...props}
              >
                {children}
              </code>
            );
          },
          p: ({ node: _node, ...props }) => (
            <p className="whitespace-pre-wrap break-words" {...props} />
          ),
        }}
        remarkPlugins={[remarkGfm]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
