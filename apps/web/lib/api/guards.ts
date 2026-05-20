import type { ProviderConnectionStatus } from "@value-terminal/types";

const providerStates = new Set([
  "connected",
  "not_connected",
  "degraded",
  "not_implemented",
]);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) && value.every((item) => typeof item === "string")
  );
}

export function isProviderConnectionStatus(
  value: unknown,
): value is ProviderConnectionStatus {
  if (!isRecord(value)) {
    return false;
  }

  const lastCheckedAt = value.lastCheckedAt;
  const lastSuccessfulCallAt = value.lastSuccessfulCallAt;
  const lastErrorMessage = value.lastErrorMessage;

  return (
    typeof value.provider === "string" &&
    typeof value.state === "string" &&
    providerStates.has(value.state) &&
    typeof value.message === "string" &&
    (lastCheckedAt === null || typeof lastCheckedAt === "string") &&
    (lastSuccessfulCallAt === undefined ||
      lastSuccessfulCallAt === null ||
      typeof lastSuccessfulCallAt === "string") &&
    (lastErrorMessage === undefined ||
      lastErrorMessage === null ||
      typeof lastErrorMessage === "string") &&
    (value.requiredEnvironmentVariables === undefined ||
      isStringArray(value.requiredEnvironmentVariables))
  );
}

export function hasProviderConnectionStatus(
  value: unknown,
): value is { provider: ProviderConnectionStatus } {
  return isRecord(value) && isProviderConnectionStatus(value.provider);
}
