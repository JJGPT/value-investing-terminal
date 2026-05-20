import { LoadingPanel } from "../../components/data-status/loading-panel";
import { TerminalShell } from "../../components/shell/terminal-shell";

export default function WatchlistLoading() {
  return (
    <TerminalShell
      eyebrow="Watchlist"
      title="Research watchlist workspace."
      description="Loading the watchlist contract state."
    >
      <LoadingPanel label="Loading watchlists contract" />
    </TerminalShell>
  );
}
