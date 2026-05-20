import { NeuralSphere } from "../components/landing/neural-sphere";
import { TerminalShell } from "../components/shell/terminal-shell";
import { PlaceholderCard } from "../components/ui/placeholder-card";
import { StatusList } from "../components/ui/status-list";

export default function HomePage() {
  return (
    <TerminalShell
      eyebrow="Stabilized research terminal"
      title="Institutional value investing research, ready for local workflows."
      description="A premium workspace for provider-backed screening, company research, deterministic rankings, valuation scenarios, watchlists, and diagnostics. AI workflows and trading remain intentionally disabled."
    >
      <section className="relative min-h-[620px] overflow-hidden border border-line bg-graphite/80">
        <div className="absolute inset-0 opacity-95">
          <NeuralSphere />
        </div>
        <div className="relative z-10 flex min-h-[620px] items-end p-5 sm:p-8">
          <div className="max-w-3xl pb-5">
            <p className="font-mono text-xs uppercase text-accent">
              Neural research interface
            </p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight text-ink sm:text-5xl">
              Designed for investors who need evidence, structure, and speed.
            </h2>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-300 sm:text-base">
              The terminal now prioritizes traceable data, saved snapshots,
              reproducible valuation scenarios, and explicit provider states so
              analysts can see what is real, stale, degraded, or unavailable.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <PlaceholderCard
          label="Workspace"
          title="Navigation foundation"
          description="Sidebar, command surface, responsive panels, and research routes are in place for repeated analyst workflows."
        >
          <StatusList
            items={[
              { label: "Terminal shell", status: "ready" },
              { label: "Company research", status: "ready" },
              { label: "Watchlist workspace", status: "ready" },
            ]}
          />
        </PlaceholderCard>
        <PlaceholderCard
          label="Data boundary"
          title="Backend-only provider access"
          description="Alpaca and FMP keys stay server-side. Missing providers render explicit not-connected states instead of invented data."
        >
          <StatusList
            items={[
              { label: "Market data", status: "Alpaca optional" },
              { label: "Fundamentals", status: "FMP optional" },
              { label: "Diagnostics", status: "ready" },
            ]}
          />
        </PlaceholderCard>
        <PlaceholderCard
          label="Scope control"
          title="No synthetic analysis"
          description="The application remains deterministic: no AI research, no trading, no portfolio optimization, and no buy/sell recommendations."
        >
          <StatusList
            items={[
              { label: "Valuation", status: "auditable" },
              { label: "Rankings", status: "deterministic" },
              { label: "AI workflows", status: "disabled" },
            ]}
          />
        </PlaceholderCard>
      </section>
    </TerminalShell>
  );
}
