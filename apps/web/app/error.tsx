"use client";

type AppErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function AppError({ error, reset }: AppErrorProps) {
  return (
    <main className="bg-obsidian text-ink min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <section className="border-line bg-graphite/80 mx-auto max-w-3xl border p-6">
        <p className="text-amber font-mono text-xs uppercase">
          Application error
        </p>
        <h1 className="mt-4 text-2xl font-semibold">
          The terminal could not render this workspace.
        </h1>
        <p className="text-muted mt-3 text-sm leading-6">
          This usually means the backend is offline, a provider response changed,
          or a local snapshot is missing. No financial data is synthesized to
          fill the gap.
        </p>
        <div className="border-line bg-graphite2/70 mt-5 border p-4">
          <p className="text-muted font-mono text-[11px] uppercase">
            Failure detail
          </p>
          <p className="mt-2 break-words text-sm leading-6">
            {error.message || "Unknown rendering error."}
          </p>
          {error.digest ? (
            <p className="text-muted mt-3 font-mono text-[11px]">
              Digest: {error.digest}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={reset}
          className="border-line hover:text-accent mt-5 border px-4 py-2 font-mono text-[11px] uppercase text-muted transition"
        >
          Retry workspace
        </button>
      </section>
    </main>
  );
}
