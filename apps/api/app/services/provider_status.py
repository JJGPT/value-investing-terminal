from typing import Optional


def provider_not_connected(
    provider: str,
    required_environment_variables: list[str],
) -> dict:
    return {
        "provider": provider,
        "state": "not_connected",
        "message": (
            "Provider credentials and ingestion jobs are not configured."
        ),
        "requiredEnvironmentVariables": required_environment_variables,
        "lastCheckedAt": None,
        "lastSuccessfulCallAt": None,
        "lastErrorMessage": None,
    }


def provider_connected(
    provider: str,
    message: str,
    last_successful_call_at: Optional[str] = None,
) -> dict:
    return {
        "provider": provider,
        "state": "connected",
        "message": message,
        "requiredEnvironmentVariables": [],
        "lastCheckedAt": None,
        "lastSuccessfulCallAt": last_successful_call_at,
        "lastErrorMessage": None,
    }


def provider_degraded(
    provider: str,
    message: str,
    required_environment_variables: list[str],
    last_successful_call_at: Optional[str] = None,
    last_error_message: Optional[str] = None,
) -> dict:
    return {
        "provider": provider,
        "state": "degraded",
        "message": message,
        "requiredEnvironmentVariables": required_environment_variables,
        "lastCheckedAt": None,
        "lastSuccessfulCallAt": last_successful_call_at,
        "lastErrorMessage": last_error_message or message,
    }


def provider_not_implemented(
    provider: str,
    message: str,
    required_environment_variables: list[str],
    last_successful_call_at: Optional[str] = None,
) -> dict:
    return {
        "provider": provider,
        "state": "not_implemented",
        "message": message,
        "requiredEnvironmentVariables": required_environment_variables,
        "lastCheckedAt": None,
        "lastSuccessfulCallAt": last_successful_call_at,
        "lastErrorMessage": None,
    }
