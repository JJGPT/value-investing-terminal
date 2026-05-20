import type { ReactNode } from "react";

import { Sidebar } from "./sidebar";
import { TopCommand } from "./top-command";

type TerminalShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function TerminalShell({
  eyebrow,
  title,
  description,
  children
}: TerminalShellProps) {
  return (
    <main className="terminal-grid bg-obsidian text-ink min-h-screen">
      <div className="terminal-scanline pointer-events-none fixed inset-0 opacity-20" />
      <div className="relative flex min-h-screen flex-col lg:flex-row">
        <Sidebar />
        <section className="flex min-w-0 flex-1 flex-col">
          <TopCommand />
          <div className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <section className="mb-6 max-w-4xl">
              <p className="text-accent font-mono text-xs uppercase">
                {eyebrow}
              </p>
              <h1 className="text-ink mt-3 text-3xl font-semibold leading-tight sm:text-4xl">
                {title}
              </h1>
              <p className="text-muted mt-3 max-w-2xl text-sm leading-6 sm:text-base">
                {description}
              </p>
            </section>
            {children}
          </div>
        </section>
      </div>
    </main>
  );
}
