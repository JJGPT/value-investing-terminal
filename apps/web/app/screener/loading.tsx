import { LoadingPanel } from "../../components/data-status/loading-panel";
import { TerminalShell } from "../../components/shell/terminal-shell";

export default function ScreenerLoading() {
  return (
    <TerminalShell
      eyebrow="Screener"
      title="Global stock screening workspace."
      description="Loading the securities contract state."
    >
      <LoadingPanel label="Loading screener contract" />
    </TerminalShell>
  );
}
