import Link from "next/link";

import { TerminalShell } from "../components/shell/terminal-shell";
import { PlaceholderCard } from "../components/ui/placeholder-card";

export default function NotFoundPage() {
  return (
    <TerminalShell
      eyebrow="Not found"
      title="Workspace route unavailable."
      description="The requested terminal view does not exist, or the route parameters were incomplete."
    >
      <PlaceholderCard
        label="Navigation"
        title="Return to an active workspace"
        description="Use an existing research route instead of relying on incomplete URLs."
      >
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <Link className="border-line hover:text-accent border p-3" href="/">
            Overview
          </Link>
          <Link
            className="border-line hover:text-accent border p-3"
            href="/screener"
          >
            Screener
          </Link>
          <Link
            className="border-line hover:text-accent border p-3"
            href="/rankings"
          >
            Rankings
          </Link>
          <Link
            className="border-line hover:text-accent border p-3"
            href="/diagnostics"
          >
            Diagnostics
          </Link>
        </div>
      </PlaceholderCard>
    </TerminalShell>
  );
}
