import { LoadingPanel } from "../../components/data-status/loading-panel";
import { TerminalShell } from "../../components/shell/terminal-shell";

export default function DiagnosticsLoading() {
  return (
    <TerminalShell
      eyebrow="Diagnostics"
      title="Data reliability workspace."
      description="Loading API connectivity, provider health, cache settings, and repository diagnostics."
    >
      <LoadingPanel label="Loading diagnostics" />
    </TerminalShell>
  );
}
