import Link from "next/link";

import { navigationItems } from "./navigation";

export function Sidebar() {
  return (
    <aside className="border-line bg-obsidian/95 flex w-full flex-col border-b px-4 py-4 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r">
      <Link href="/" className="flex items-center gap-3">
        <span className="border-accent/40 bg-accent/10 text-accent flex h-10 w-10 items-center justify-center border font-mono text-sm font-semibold">
          VIT
        </span>
        <span>
          <span className="text-ink block text-sm font-semibold">
            Value Terminal
          </span>
          <span className="text-muted block font-mono text-[11px] uppercase">
            Research OS
          </span>
        </span>
      </Link>

      <nav className="mt-5 flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
        {navigationItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="border-line bg-panel hover:border-accent/45 hover:text-accent flex min-w-max items-center justify-between border px-3 py-3 text-sm text-zinc-200 transition"
          >
            <span>{item.label}</span>
            <span className="text-muted ml-5 font-mono text-[11px]">
              {item.code}
            </span>
          </Link>
        ))}
      </nav>

      <div className="border-line mt-auto hidden border-t pt-4 lg:block">
        <p className="text-muted font-mono text-[11px] uppercase">
          Phase status
        </p>
        <p className="text-ink mt-2 text-sm">Stabilization pass</p>
        <p className="text-muted mt-1 text-xs leading-5">
          Provider keys stay backend-only. AI, trading, notifications, and
          portfolio optimization remain disabled.
        </p>
      </div>
    </aside>
  );
}
