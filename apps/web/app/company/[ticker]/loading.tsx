import { LoadingPanel } from "../../../components/data-status/loading-panel";
import { TerminalShell } from "../../../components/shell/terminal-shell";

export default function CompanyLoading() {
  return (
    <TerminalShell
      eyebrow="Company"
      title="Company research dashboard."
      description="Loading the company overview and market snapshot contracts."
    >
      <LoadingPanel label="Loading company contracts" />
    </TerminalShell>
  );
}
