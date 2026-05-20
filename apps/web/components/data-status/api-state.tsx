import type { ProviderConnectionStatus } from "@value-terminal/types";

import { isProviderConnectionStatus } from "../../lib/api/guards";

type ApiStateProps = {
  title: string;
  message: string;
  provider?: ProviderConnectionStatus;
  endpoint?: string;
  asOf?: string | null;
};

function guidanceForProvider(provider: ProviderConnectionStatus | null) {
  if (!provider) {
    return null;
  }

  if (provider.state === "not_connected") {
    return "Provider credentials are not configured on the backend. The UI will keep rendering unavailable states instead of synthetic data.";
  }

  if (provider.state === "degraded") {
    return "The provider is reachable but reported an operational issue. Existing snapshots may still render, but fresh data can be incomplete.";
  }

  if (provider.state === "not_implemented") {
    return "The contract is reserved, but this capability is intentionally unavailable in the current phase.";
  }

  return null;
}

export function ApiState({
  title,
  message,
  provider,
  endpoint,
  asOf,
}: ApiStateProps) {
  const validProvider = isProviderConnectionStatus(provider) ? provider : null;
  const guidance = guidanceForProvider(validProvider);
  const statusTone =
    validProvider?.state === "connected"
      ? "text-signal"
      : validProvider?.state === "degraded" ||
          validProvider?.state === "not_implemented"
        ? "text-amber"
        : "text-muted";

  return (
    <div className="border-line bg-graphite2/70 border px-4 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`font-mono text-[11px] uppercase ${statusTone}`}>
            {title}
          </p>
          <p className="text-muted mt-2 text-sm leading-6">{message}</p>
          {guidance ? (
            <p className="text-muted mt-2 text-xs leading-5">{guidance}</p>
          ) : null}
        </div>
        {validProvider ? (
          <span
            className={`border-line border px-2 py-1 font-mono text-[11px] uppercase ${statusTone}`}
          >
            {validProvider.provider}: {validProvider.state}
          </span>
        ) : null}
      </div>
      {asOf ? (
        <p className="text-muted mt-3 font-mono text-[11px]">As of: {asOf}</p>
      ) : null}
      {validProvider?.lastSuccessfulCallAt ? (
        <p className="text-muted mt-3 font-mono text-[11px]">
          Last provider success: {validProvider.lastSuccessfulCallAt}
        </p>
      ) : null}
      {validProvider?.lastErrorMessage ? (
        <p className="text-muted mt-3 font-mono text-[11px]">
          Last provider error: {validProvider.lastErrorMessage}
        </p>
      ) : null}
      {endpoint ? (
        <p className="text-muted mt-3 font-mono text-[11px]">{endpoint}</p>
      ) : null}
      {validProvider?.requiredEnvironmentVariables?.length ? (
        <p className="text-muted mt-3 font-mono text-[11px]">
          Provider env vars:{" "}
          {validProvider.requiredEnvironmentVariables.join(", ")}
        </p>
      ) : null}
    </div>
  );
}
