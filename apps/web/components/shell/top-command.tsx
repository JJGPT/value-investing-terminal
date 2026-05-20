export function TopCommand() {
  return (
    <header className="border-line bg-graphite/90 flex flex-col gap-3 border-b px-4 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between">
      <div>
        <p className="text-muted font-mono text-[11px] uppercase">
          Institutional research terminal
        </p>
        <p className="text-ink mt-1 text-sm">
          Screening, rankings, valuation, watchlists, and diagnostics with
          explicit data-state handling.
        </p>
      </div>

      <div className="border-line bg-obsidian/80 flex min-h-11 w-full items-center gap-3 border px-3 xl:max-w-xl">
        <span className="text-accent font-mono text-xs">CMD</span>
        <div className="bg-line h-5 w-px" />
        <p className="text-muted truncate text-sm">
          Search tickers, filings, screens, or research notes...
        </p>
        <span className="border-line text-muted ml-auto border px-2 py-1 font-mono text-[11px]">
          /
        </span>
      </div>
    </header>
  );
}
