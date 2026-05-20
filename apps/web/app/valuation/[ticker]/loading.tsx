import { LoadingPanel } from "../../../components/data-status/loading-panel";
import { TerminalShell } from "../../../components/shell/terminal-shell";

export default function ValuationLoading() {
  return (
    <TerminalShell
      eyebrow="Valuation"
      title="DCF valuation workbench."
      description="Loading the valuation scenario, normalized inputs, and sensitivity contracts."
    >
      <LoadingPanel label="Loading valuation workbench" />
    </TerminalShell>
  );
}
