from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.services.fundamentals.computed_metrics import build_computed_metrics_response
from app.services.fundamentals.provider import FundamentalsProvider
from app.services.market_data.provider import MarketDataProvider
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SCHEMA_VERSION
from app.services.provider_status import (
    provider_connected,
    provider_degraded,
    provider_not_connected,
)

DCF_ENGINE_VERSION = "platform-fcff-dcf-v1"
VALUATION_METHODOLOGY_VERSION = "fcff-methodology-v1"
LONG_TERM_GDP_GROWTH_PROXY = 0.035
DEFAULT_PROJECTION_YEARS = 5
ASSUMPTION_LIMITS = {
    ("discountRate", "riskFreeRate"): (-0.02, 0.15),
    ("discountRate", "equityRiskPremium"): (0.0, 0.2),
    ("discountRate", "beta"): (0.0, 5.0),
    ("discountRate", "preTaxCostOfDebt"): (0.0, 0.25),
    ("discountRate", "taxRate"): (0.0, 0.5),
    ("discountRate", "debtWeight"): (0.0, 1.0),
    ("discountRate", "equityWeight"): (0.0, 1.0),
    ("discountRate", "wacc"): (-0.5, 0.5),
    ("growth", "projectionYears"): (1, 10),
    ("growth", "revenueGrowthRate"): (-0.5, 0.5),
    ("margin", "operatingMargin"): (-0.5, 0.8),
    ("reinvestment", "reinvestmentRate"): (0.0, 2.0),
    ("shareCount", "dilutedShareGrowthRate"): (-0.2, 0.2),
    ("shareCount", "stockBasedCompensationDilutionRate"): (0.0, 0.15),
    ("shareCount", "buybackRate"): (0.0, 0.25),
    ("netDebt", "operatingCashPercentOfRevenue"): (0.0, 0.2),
    ("terminalValue", "terminalGrowthRate"): (-0.05, 0.06),
}


def build_dcf_result(
    ticker: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    overrides: Optional[dict] = None,
    persist: bool = False,
    repository: Optional[SnapshotRepository] = None,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    now = utc_now()
    materials = load_valuation_materials(
        normalized_ticker,
        fundamentals_provider,
        market_data_provider,
    )
    normalized_overrides = overrides or {}
    assumptions = build_assumptions(materials, normalized_overrides)
    scenario = build_scenario(
        normalized_ticker,
        assumptions,
        now,
        scenario_name_from_overrides(normalized_overrides),
        scenario_id=normalized_overrides.get("scenarioId"),
        parent_scenario_id=normalized_overrides.get("parentScenarioId"),
        prior_version_id=normalized_overrides.get("priorVersionId"),
    )
    result = calculate_dcf_result(
        normalized_ticker,
        scenario,
        assumptions,
        materials,
        now,
    )

    if persist and repository is not None:
        repository.upsert_valuation_scenario(
            normalized_ticker,
            scenario["id"],
            result,
        )

    return result


def build_dcf_scenario_version(
    ticker: str,
    scenario_id: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    overrides: Optional[dict] = None,
) -> dict:
    existing = repository.get_valuation_scenario(ticker.strip().upper(), scenario_id)

    if existing is None:
        raise ValueError("DCF scenario not found.")

    merged_overrides = merge_scenario_overrides(existing, overrides or {})
    prior_scenario = existing.get("scenario") or {}
    merged_overrides["scenarioId"] = scenario_id
    merged_overrides["parentScenarioId"] = prior_scenario.get("parentScenarioId")
    merged_overrides["priorVersionId"] = prior_scenario.get("versionId")

    if "scenarioName" not in merged_overrides:
        merged_overrides["scenarioName"] = prior_scenario.get("name")

    result = build_dcf_result(
        ticker,
        fundamentals_provider,
        market_data_provider,
        overrides=merged_overrides,
        persist=False,
    )
    result["_auditEvents"] = assumption_change_events(existing, result)
    repository.upsert_valuation_scenario(
        ticker.strip().upper(),
        scenario_id,
        result,
    )

    return result


def get_or_build_dcf_result(
    ticker: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    persisted = repository.get_latest_valuation_scenario(normalized_ticker)

    if persisted is not None:
        return persisted

    return build_dcf_result(
        normalized_ticker,
        fundamentals_provider,
        market_data_provider,
        persist=False,
    )


def build_dcf_sensitivity(
    ticker: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
) -> dict:
    return get_or_build_dcf_result(
        ticker,
        fundamentals_provider,
        market_data_provider,
        repository,
    )["sensitivity"]


def get_saved_dcf_result(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
) -> Optional[dict]:
    return repository.get_valuation_scenario(ticker.strip().upper(), scenario_id)


def list_dcf_scenarios(
    ticker: str,
    repository: SnapshotRepository,
    limit: int = 10,
    include_archived: bool = False,
    include_deleted: bool = False,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    scenarios = repository.list_valuation_scenarios(
        normalized_ticker,
        limit,
        include_archived,
        include_deleted,
    )
    summaries = [scenario_summary(scenario) for scenario in scenarios]

    return {
        "ticker": normalized_ticker,
        "scenarios": summaries,
        "latestScenarioId": summaries[0]["scenarioId"] if summaries else None,
        "count": len(summaries),
        "message": "Saved DCF scenarios are listed newest first.",
    }


def build_dcf_comparison(
    ticker: str,
    repository: SnapshotRepository,
    limit: int = 5,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    scenarios = repository.list_valuation_scenarios(normalized_ticker, limit)

    return {
        "ticker": normalized_ticker,
        "rows": [scenario_comparison_row(scenario) for scenario in scenarios],
        "count": len(scenarios),
        "message": (
            "Saved DCF scenarios are compared on output value and primary "
            "editable assumptions. This is not a recommendation."
        ),
    }


def rename_dcf_scenario(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
    name: str,
) -> dict:
    existing = require_scenario(ticker, scenario_id, repository)
    payload = clone_for_lifecycle(existing)
    scenario = payload["scenario"]
    previous_name = scenario.get("name")
    scenario["name"] = scenario_name_from_overrides({"scenarioName": name}) or previous_name
    scenario["updatedAt"] = utc_now()
    payload["updatedAt"] = scenario["updatedAt"]
    payload["_auditEvents"] = [
        audit_event("rename", "scenario.name", previous_name, scenario["name"])
    ]
    repository.upsert_valuation_scenario(ticker.strip().upper(), scenario_id, payload)

    return payload


def duplicate_dcf_scenario(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
    name: Optional[str] = None,
) -> dict:
    existing = require_scenario(ticker, scenario_id, repository)
    payload = deepcopy(existing)
    timestamp = utc_now()
    source_scenario = existing.get("scenario") or {}
    new_scenario_id = f"dcf-{ticker.strip().upper()}-{uuid4().hex[:10]}"
    scenario = payload["scenario"]
    scenario["id"] = new_scenario_id
    scenario["name"] = scenario_name_from_overrides({"scenarioName": name}) or (
        f"{source_scenario.get('name') or 'DCF Scenario'} Copy"
    )
    scenario["createdAt"] = timestamp
    scenario["updatedAt"] = timestamp
    scenario["versionNumber"] = 1
    scenario["versionId"] = f"{new_scenario_id}-v1"
    scenario["priorVersionId"] = source_scenario.get("versionId")
    scenario["parentScenarioId"] = scenario_id
    scenario["status"] = "active"
    scenario["archivedAt"] = None
    scenario["deletedAt"] = None
    payload["ticker"] = ticker.strip().upper()
    payload["createdAt"] = timestamp
    payload["updatedAt"] = timestamp
    payload["_auditEvents"] = [
        audit_event("duplicate", "scenario.id", scenario_id, new_scenario_id)
    ]
    repository.upsert_valuation_scenario(
        ticker.strip().upper(),
        new_scenario_id,
        payload,
    )

    return payload


def set_dcf_scenario_status(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
    status: str,
) -> dict:
    if status not in {"active", "archived", "deleted"}:
        raise ValueError("Unsupported scenario status.")

    existing = require_scenario(ticker, scenario_id, repository)
    payload = clone_for_lifecycle(existing)
    scenario = payload["scenario"]
    previous_status = scenario.get("status") or "active"
    timestamp = utc_now()
    scenario["status"] = status
    scenario["updatedAt"] = timestamp
    scenario["archivedAt"] = timestamp if status == "archived" else None
    scenario["deletedAt"] = timestamp if status == "deleted" else None
    payload["updatedAt"] = timestamp
    payload["_auditEvents"] = [
        audit_event(f"status:{status}", "scenario.status", previous_status, status)
    ]
    repository.upsert_valuation_scenario(ticker.strip().upper(), scenario_id, payload)

    return payload


def build_dcf_history(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
) -> dict:
    scenario = require_scenario(ticker, scenario_id, repository)

    return {
        "ticker": ticker.strip().upper(),
        "scenarioId": scenario_id,
        "scenario": scenario_summary(scenario),
        "versions": [
            scenario_version_summary(version)
            for version in repository.list_valuation_scenario_versions(
                ticker.strip().upper(),
                scenario_id,
            )
        ],
        "auditEvents": repository.list_valuation_audit_events(
            ticker.strip().upper(),
            scenario_id,
        ),
        "message": "Valuation scenario history is immutable and newest first.",
    }


def build_dcf_scenario_diff(
    ticker: str,
    repository: SnapshotRepository,
    left_scenario_id: str,
    right_scenario_id: str,
    left_version_id: Optional[str] = None,
    right_version_id: Optional[str] = None,
) -> dict:
    normalized_ticker = ticker.strip().upper()
    left = require_scenario_for_diff(
        normalized_ticker,
        left_scenario_id,
        left_version_id,
        repository,
    )
    right = require_scenario_for_diff(
        normalized_ticker,
        right_scenario_id,
        right_version_id,
        repository,
    )

    return {
        "ticker": normalized_ticker,
        "left": scenario_summary(left),
        "right": scenario_summary(right),
        "valuationDelta": valuation_delta_summary(left, right),
        "assumptionDiffs": assumption_diff_rows(left, right),
        "outputDiffs": output_diff_rows(left, right),
        "warningDiffs": warning_diff_rows(left, right),
        "message": (
            "Scenario diff compares deterministic saved DCF payloads. It is "
            "not a ranking, recommendation, or automated investment opinion."
        ),
    }


def export_dcf_assumptions(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
) -> dict:
    scenario = require_scenario(ticker, scenario_id, repository)
    scenario_payload = scenario.get("scenario") or {}

    return {
        "schemaVersion": scenario.get("schemaVersion"),
        "modelVersion": scenario_payload.get("modelVersion")
        or (scenario.get("modelMetadata") or {}).get("modelVersion"),
        "exportedAt": utc_now(),
        "ticker": ticker.strip().upper(),
        "sourceScenario": scenario_summary(scenario),
        "assumptions": exportable_assumptions(scenario_payload),
        "warnings": scenario.get("warnings") or [],
        "message": (
            "Export contains editable DCF assumptions and reproducibility "
            "metadata only. It does not contain provider credentials."
        ),
    }


def import_dcf_assumptions(
    ticker: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
    repository: SnapshotRepository,
    payload: dict,
) -> dict:
    overrides, import_metadata = parse_assumption_import_payload(payload)
    timestamp = utc_now()
    result = build_dcf_result(
        ticker,
        fundamentals_provider,
        market_data_provider,
        overrides=overrides,
        persist=False,
    )
    result["importMetadata"] = {
        **import_metadata,
        "importedAt": timestamp,
        "createdScenarioId": result["scenario"]["id"],
        "createdVersionId": result["scenario"].get("versionId"),
    }
    result["_auditEvents"] = [
        audit_event(
            "import",
            "scenario.assumptions",
            import_metadata.get("sourceScenarioId"),
            result["scenario"]["id"],
            "Scenario assumptions imported from a validated JSON payload.",
        )
    ]
    repository.upsert_valuation_scenario(
        ticker.strip().upper(),
        result["scenario"]["id"],
        result,
    )

    return result


def add_dcf_note(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
    payload: dict,
) -> dict:
    scenario = require_scenario(ticker, scenario_id, repository)
    scenario_payload = scenario.get("scenario") or {}
    text_value = payload.get("text") if isinstance(payload, dict) else None

    if not isinstance(text_value, str) or not text_value.strip():
        raise ValueError("Analyst note text is required.")

    attachment_type = payload.get("attachmentType") or "scenario_version"

    if attachment_type not in {"scenario_version", "assumption", "warning"}:
        raise ValueError("Unsupported valuation note attachment type.")

    note = {
        "schemaVersion": SCHEMA_VERSION,
        "attachmentType": attachment_type,
        "versionId": payload.get("versionId") or scenario_payload.get("versionId"),
        "versionNumber": payload.get("versionNumber")
        or scenario_payload.get("versionNumber"),
        "fieldPath": nullable_string(payload.get("fieldPath")),
        "warningCode": nullable_string(payload.get("warningCode")),
        "text": text_value.strip()[:5000],
        "createdAt": utc_now(),
    }

    return repository.add_valuation_note(ticker.strip().upper(), scenario_id, note)


def list_dcf_notes(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
) -> dict:
    scenario = require_scenario(ticker, scenario_id, repository)

    return {
        "ticker": ticker.strip().upper(),
        "scenarioId": scenario_id,
        "scenario": scenario_summary(scenario),
        "notes": repository.list_valuation_notes(ticker.strip().upper(), scenario_id),
        "message": (
            "Analyst notes are immutable attachments to scenario versions, "
            "assumptions, or warnings."
        ),
    }


def load_valuation_materials(
    ticker: str,
    fundamentals_provider: FundamentalsProvider,
    market_data_provider: MarketDataProvider,
) -> dict:
    profile_response = fundamentals_provider.get_company_profile(ticker)
    income_response = fundamentals_provider.get_income_statement(ticker, "annual", 5)
    balance_response = fundamentals_provider.get_balance_sheet(ticker, "annual", 5)
    cash_flow_response = fundamentals_provider.get_cash_flow_statement(
        ticker,
        "annual",
        5,
    )
    computed_response = build_computed_metrics_response(
        fundamentals_provider,
        ticker,
        "annual",
        5,
    )
    market_snapshot_response = market_data_provider.get_market_snapshot(ticker)
    profile = mapping_or_none(profile_response.get("profile"))
    income_rows = rows_from_response(income_response, "incomeStatements")
    balance_rows = rows_from_response(balance_response, "balanceSheets")
    cash_flow_rows = rows_from_response(cash_flow_response, "cashFlowStatements")
    computed_rows = rows_from_response(computed_response, "computedMetrics")

    return {
        "profileResponse": profile_response,
        "incomeResponse": income_response,
        "balanceResponse": balance_response,
        "cashFlowResponse": cash_flow_response,
        "computedResponse": computed_response,
        "marketSnapshotResponse": market_snapshot_response,
        "profile": profile,
        "incomeRows": income_rows,
        "balanceRows": balance_rows,
        "cashFlowRows": cash_flow_rows,
        "computedRows": computed_rows,
        "latestIncome": first_row(income_rows),
        "latestBalance": first_row(balance_rows),
        "latestCashFlow": first_row(cash_flow_rows),
        "latestComputed": first_row(computed_rows),
    }


def build_reproducibility_metadata(
    materials: dict,
    sensitivity: dict,
    timestamp: str,
) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "statementSnapshotReferences": {
            "incomeStatement": source_reference(materials.get("latestIncome")),
            "balanceSheet": source_reference(materials.get("latestBalance")),
            "cashFlowStatement": source_reference(materials.get("latestCashFlow")),
        },
        "metricSnapshotsUsed": [
            source_reference(row)
            for row in materials.get("computedRows") or []
            if source_reference(row) is not None
        ],
        "marketDataSnapshotReference": market_snapshot_reference(
            materials.get("marketSnapshotResponse") or {}
        ),
        "valuationEngineVersions": {
            "dcfEngineVersion": DCF_ENGINE_VERSION,
            "valuationMethodologyVersion": VALUATION_METHODOLOGY_VERSION,
            "modelVersion": DCF_ENGINE_VERSION,
        },
        "sensitivityConfiguration": sensitivity_configuration(sensitivity),
        "calculationTimestampChain": {
            "materialsLoadedAt": timestamp,
            "assumptionsBuiltAt": timestamp,
            "valuationComputedAt": timestamp,
        },
        "completeness": {
            "hasIncomeStatement": materials.get("latestIncome") is not None,
            "hasBalanceSheet": materials.get("latestBalance") is not None,
            "hasCashFlowStatement": materials.get("latestCashFlow") is not None,
            "hasComputedMetrics": bool(materials.get("computedRows")),
            "hasMarketSnapshot": bool(materials.get("marketSnapshotResponse")),
        },
        "qualityFlags": reproducibility_quality_flags(materials),
    }


def source_reference(row: Optional[dict]) -> Optional[dict]:
    if not isinstance(row, dict):
        return None

    return {
        "provider": row.get("provider"),
        "providerVersion": row.get("providerVersion"),
        "fetchedAt": row.get("fetchedAt"),
        "sourceSymbol": row.get("sourceSymbol"),
        "currency": row.get("currency"),
        "fiscalYear": row.get("fiscalYear"),
        "fiscalPeriod": row.get("fiscalPeriod"),
        "qualityFlags": row.get("qualityFlags") or [],
    }


def market_snapshot_reference(response: dict) -> dict:
    provider = response.get("provider") or {}

    return {
        "provider": provider.get("provider"),
        "providerState": provider.get("state"),
        "fetchedAt": response.get("asOf") or provider.get("lastSuccessfulCallAt"),
        "sourceSymbol": response.get("ticker"),
        "currency": response.get("currency"),
        "asOf": response.get("asOf"),
        "qualityFlags": [],
    }


def sensitivity_configuration(sensitivity: dict) -> dict:
    return {
        key: {
            "rowVariable": matrix.get("rowVariable"),
            "columnVariable": matrix.get("columnVariable"),
            "rowValues": matrix.get("rowValues"),
            "columnValues": matrix.get("columnValues"),
        }
        for key, matrix in sensitivity.items()
        if isinstance(matrix, dict)
    }


def reproducibility_quality_flags(materials: dict) -> list[str]:
    flags = []

    if materials.get("latestIncome") is None:
        add_flag(flags, "missing_reproducibility_reference:incomeStatement")

    if materials.get("latestBalance") is None:
        add_flag(flags, "missing_reproducibility_reference:balanceSheet")

    if materials.get("latestCashFlow") is None:
        add_flag(flags, "missing_reproducibility_reference:cashFlowStatement")

    if not materials.get("computedRows"):
        add_flag(flags, "missing_reproducibility_reference:computedMetrics")

    return flags


def build_assumptions(materials: dict, overrides: dict) -> dict:
    latest_profile = materials["profile"]
    latest_income = materials["latestIncome"]
    latest_balance = materials["latestBalance"]
    latest_cash_flow = materials["latestCashFlow"]
    latest_computed = materials["latestComputed"]
    computed_rows = materials["computedRows"]
    revenue_growth = median_number(
        row.get("revenueGrowthYoY") for row in computed_rows
    )
    operating_margin = median_number(row.get("operatingMargin") for row in computed_rows)
    tax_rate = derived_tax_rate(materials["incomeRows"])
    reinvestment_rate = derived_reinvestment_rate(
        materials["incomeRows"],
        materials["cashFlowRows"],
        tax_rate,
    )
    beta = number(latest_profile.get("beta")) if latest_profile else None
    market_cap = number(latest_profile.get("marketCap")) if latest_profile else None
    total_debt = number(latest_balance.get("totalDebt")) if latest_balance else None
    cash = number(latest_balance.get("cashAndEquivalents")) if latest_balance else None
    capital = (market_cap or 0) + (total_debt or 0)
    debt_weight = safe_ratio(total_debt, capital) if capital > 0 else None
    equity_weight = safe_ratio(market_cap, capital) if capital > 0 else None
    risk_free_rate = assumption(
        0.04,
        "manual_default",
        "Editable macro input. Replace with the current normalized risk-free rate before relying on the valuation.",
        "decimal",
        ["manual_review_required:riskFreeRate"],
    )
    equity_risk_premium = assumption(
        0.05,
        "manual_default",
        "Editable market risk premium input. It is not inferred from company statements.",
        "decimal",
        ["manual_review_required:equityRiskPremium"],
    )
    beta_assumption = assumption(
        beta if beta is not None else 1.0,
        "company_profile" if beta is not None else "manual_default",
        "Uses provider-normalized profile beta when available; otherwise uses editable market beta of 1.0.",
        "multiple",
        [] if beta is not None else ["manual_review_required:beta"],
    )
    tax_assumption = assumption(
        tax_rate if tax_rate is not None else 0.21,
        "historical_normalized_statements" if tax_rate is not None else "manual_default",
        "Estimated from normalized net income versus operating income where possible.",
        "decimal",
        ["tax_rate_proxy_from_net_income"] if tax_rate is not None else ["manual_review_required:taxRate"],
    )
    pre_tax_cost_of_debt = assumption(
        0.05,
        "manual_default",
        "Editable debt cost input. Interest expense is not yet normalized in Phase 3A.",
        "decimal",
        ["manual_review_required:preTaxCostOfDebt"],
    )
    cost_of_equity_value = (
        risk_free_rate["value"]
        + beta_assumption["value"] * equity_risk_premium["value"]
    )
    after_tax_debt_value = pre_tax_cost_of_debt["value"] * (1 - tax_assumption["value"])
    debt_weight_assumption = assumption(
        debt_weight if debt_weight is not None else 0.0,
        "normalized_balance_sheet_and_profile" if debt_weight is not None else "manual_default",
        "Debt weight uses total debt over market capitalization plus debt when available.",
        "decimal",
        [] if debt_weight is not None else ["manual_review_required:debtWeight"],
    )
    equity_weight_assumption = assumption(
        equity_weight if equity_weight is not None else 1.0,
        "normalized_balance_sheet_and_profile" if equity_weight is not None else "manual_default",
        "Equity weight uses market capitalization over market capitalization plus debt when available.",
        "decimal",
        [] if equity_weight is not None else ["manual_review_required:equityWeight"],
    )
    wacc_value = (
        cost_of_equity_value * equity_weight_assumption["value"]
        + after_tax_debt_value * debt_weight_assumption["value"]
    )
    assumptions = {
        "discountRate": {
            "riskFreeRate": risk_free_rate,
            "equityRiskPremium": equity_risk_premium,
            "beta": beta_assumption,
            "costOfEquity": assumption(
                cost_of_equity_value,
                "derived_from_discount_rate_inputs",
                "riskFreeRate + beta * equityRiskPremium.",
                "decimal",
                [],
            ),
            "preTaxCostOfDebt": pre_tax_cost_of_debt,
            "taxRate": tax_assumption,
            "afterTaxCostOfDebt": assumption(
                after_tax_debt_value,
                "derived_from_discount_rate_inputs",
                "preTaxCostOfDebt * (1 - taxRate).",
                "decimal",
                [],
            ),
            "debtWeight": debt_weight_assumption,
            "equityWeight": equity_weight_assumption,
            "wacc": assumption(
                wacc_value,
                "derived_from_discount_rate_inputs",
                "costOfEquity * equityWeight + afterTaxCostOfDebt * debtWeight.",
                "decimal",
                [],
            ),
        },
        "growth": {
            "projectionYears": assumption(
                DEFAULT_PROJECTION_YEARS,
                "platform_default",
                "Five explicit projection years for the Phase 3A workbench.",
                "years",
                [],
            ),
            "revenueGrowthRate": assumption(
                revenue_growth if revenue_growth is not None else 0.03,
                "historical_normalized_metrics" if revenue_growth is not None else "manual_default",
                "Median available platform-owned revenue growth observation.",
                "decimal",
                [] if revenue_growth is not None else ["manual_review_required:revenueGrowthRate"],
            ),
        },
        "margin": {
            "operatingMargin": assumption(
                operating_margin
                if operating_margin is not None
                else safe_ratio(
                    number(latest_income.get("operatingIncome")) if latest_income else None,
                    number(latest_income.get("revenue")) if latest_income else None,
                ),
                "historical_normalized_metrics",
                "Median available platform-owned operating margin observation.",
                "decimal",
                [] if operating_margin is not None else ["manual_review_required:operatingMargin"],
            ),
        },
        "reinvestment": {
            "reinvestmentRate": assumption(
                reinvestment_rate if reinvestment_rate is not None else 0.05,
                "historical_normalized_statements" if reinvestment_rate is not None else "manual_default",
                "Historical reinvestment proxy as a percentage of revenue.",
                "decimal",
                [] if reinvestment_rate is not None else ["manual_review_required:reinvestmentRate"],
            ),
        },
        "shareCount": {
            "dilutedShareGrowthRate": assumption(
                0.0,
                "platform_default",
                "Base share count projection assumes no net diluted share growth until the analyst edits this assumption.",
                "decimal",
                ["manual_review_required:dilutedShareGrowthRate"],
            ),
            "stockBasedCompensationDilutionRate": assumption(
                0.0,
                "platform_default",
                "Optional SBC dilution support. Phase 3C does not model a full equity compensation waterfall.",
                "decimal",
                ["manual_review_required:stockBasedCompensationDilutionRate"],
            ),
            "buybackRate": assumption(
                0.0,
                "platform_default",
                "Optional buyback assumption applied against projected diluted shares.",
                "decimal",
                ["manual_review_required:buybackRate"],
            ),
        },
        "netDebt": {
            "operatingCashPercentOfRevenue": assumption(
                0.02,
                "platform_default",
                "Operating cash proxy used to separate excess cash from cash needed in the business.",
                "decimal",
                ["manual_review_required:operatingCashPercentOfRevenue"],
            ),
            "leaseDebt": assumption(
                None,
                "not_available",
                "Lease debt is nullable until normalized lease obligations are available.",
                "currency",
                ["missing_input:leaseDebt"],
            ),
            "preferredEquity": assumption(
                None,
                "not_available",
                "Preferred equity is nullable until normalized capital structure fields are available.",
                "currency",
                ["missing_input:preferredEquity"],
            ),
            "minorityInterest": assumption(
                None,
                "not_available",
                "Minority interest is nullable until normalized capital structure fields are available.",
                "currency",
                ["missing_input:minorityInterest"],
            ),
        },
        "terminalValue": {
            "terminalGrowthRate": assumption(
                min(max((revenue_growth or 0.03) * 0.5, 0.0), 0.03),
                "derived_from_growth_assumption",
                "Deterministic terminal growth starts at half of explicit revenue growth and is capped at 3%.",
                "decimal",
                ["manual_review_required:terminalGrowthRate"],
            ),
        },
    }
    apply_overrides(assumptions, overrides)
    refresh_derived_discount_rate_assumptions(assumptions)
    validate_assumptions(assumptions)

    return assumptions


def build_scenario(
    ticker: str,
    assumptions: dict,
    timestamp: str,
    name: Optional[str] = None,
    scenario_id: Optional[str] = None,
    parent_scenario_id: Optional[str] = None,
    prior_version_id: Optional[str] = None,
) -> dict:
    normalized_scenario_id = scenario_id or f"dcf-{ticker}-{uuid4().hex[:10]}"

    return {
        "id": normalized_scenario_id,
        "ticker": ticker,
        "name": name or "Base FCFF DCF",
        "schemaVersion": SCHEMA_VERSION,
        "modelVersion": DCF_ENGINE_VERSION,
        "versionNumber": None,
        "versionId": None,
        "priorVersionId": prior_version_id,
        "parentScenarioId": parent_scenario_id,
        "status": "active",
        "archivedAt": None,
        "deletedAt": None,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "discountRate": assumptions["discountRate"],
        "growth": assumptions["growth"],
        "margin": assumptions["margin"],
        "reinvestment": assumptions["reinvestment"],
        "shareCount": assumptions["shareCount"],
        "netDebt": assumptions["netDebt"],
        "terminalValue": assumptions["terminalValue"],
        "qualityFlags": assumption_quality_flags(assumptions),
    }


def calculate_dcf_result(
    ticker: str,
    scenario: dict,
    assumptions: dict,
    materials: dict,
    timestamp: str,
) -> dict:
    base_financials = base_financials_from_materials(materials)
    quality_flags = list(scenario["qualityFlags"])
    projections = project_fcff(base_financials, assumptions, quality_flags)
    terminal_value = calculate_terminal_value(projections, assumptions, quality_flags)
    present_value_terminal = present_value(
        terminal_value,
        assumptions["discountRate"]["wacc"]["value"],
        len(projections),
        "presentValueTerminalValue",
        quality_flags,
    )
    present_value_fcff = sum(
        row["presentValueFcff"] for row in projections if row["presentValueFcff"] is not None
    )
    enterprise_value = add_nullable(present_value_fcff, present_value_terminal)
    net_debt = calculate_refined_net_debt(base_financials, assumptions)
    equity_value = subtract_nullable(enterprise_value, net_debt)
    projected_shares = final_projected_shares(projections, base_financials)
    intrinsic_value_per_share = divide_nullable(
        equity_value,
        projected_shares,
        "intrinsicValuePerShare",
        quality_flags,
    )
    provider = aggregate_provider_status(
        [
            materials["profileResponse"].get("provider"),
            materials["incomeResponse"].get("provider"),
            materials["balanceResponse"].get("provider"),
            materials["cashFlowResponse"].get("provider"),
            materials["computedResponse"].get("provider"),
            materials["marketSnapshotResponse"].get("provider"),
        ]
    )
    sensitivity = build_sensitivity_grid(base_financials, assumptions)
    result = {
        "ticker": ticker,
        "schemaVersion": SCHEMA_VERSION,
        "scenario": scenario,
        "projections": projections,
        "sensitivity": sensitivity,
        "sensitivityVisualization": build_sensitivity_visualization(
            sensitivity,
            base_financials.get("currency"),
        ),
        "baseFinancials": base_financials,
        "modelMetadata": {
            "dcfEngineVersion": DCF_ENGINE_VERSION,
            "valuationMethodologyVersion": VALUATION_METHODOLOGY_VERSION,
            "modelVersion": DCF_ENGINE_VERSION,
            "computationTimestamp": timestamp,
        },
        "reproducibility": build_reproducibility_metadata(
            materials,
            sensitivity,
            timestamp,
        ),
        "terminalValue": terminal_value,
        "presentValueTerminalValue": present_value_terminal,
        "enterpriseValue": enterprise_value,
        "netDebt": net_debt,
        "projectedSharesDiluted": projected_shares,
        "equityValue": equity_value,
        "intrinsicValuePerShare": intrinsic_value_per_share,
        "formulas": dcf_formulas(),
        "provider": provider,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "message": (
            "DCF result is platform-calculated from normalized financials and "
            "transparent editable assumptions. It is not a buy/sell recommendation."
        ),
    }
    warnings = valuation_warnings(result, assumptions, materials)
    result["warnings"] = warnings
    result["qualityFlags"] = sorted(
        set(quality_flags + [f"warning:{warning['code']}" for warning in warnings])
    )
    result["scenario"]["qualityFlags"] = sorted(
        set(result["scenario"]["qualityFlags"] + result["qualityFlags"])
    )

    return result


def project_fcff(
    base_financials: dict,
    assumptions: dict,
    quality_flags: list[str],
) -> list[dict]:
    revenue = base_financials["revenue"]
    growth = assumptions["growth"]["revenueGrowthRate"]["value"]
    years = int(assumptions["growth"]["projectionYears"]["value"] or 0)
    margin = assumptions["margin"]["operatingMargin"]["value"]
    tax_rate = assumptions["discountRate"]["taxRate"]["value"]
    reinvestment_rate = assumptions["reinvestment"]["reinvestmentRate"]["value"]
    wacc = assumptions["discountRate"]["wacc"]["value"]
    shares = base_financials["sharesDiluted"]
    share_growth_rate = net_share_growth_rate(assumptions)
    projections = []

    for year in range(1, years + 1):
        if any(value is None for value in [revenue, growth, margin, tax_rate, reinvestment_rate, wacc]):
            add_flag(quality_flags, "missing_input:projection")
            projections.append(empty_projection_year(year))
            continue

        prior_revenue = revenue
        revenue = revenue * (1 + growth)
        operating_income = revenue * margin
        nopat = operating_income * (1 - tax_rate)
        reinvestment = max(revenue - prior_revenue, 0) * reinvestment_rate
        fcff = nopat - reinvestment
        discount_factor = 1 / ((1 + wacc) ** year) if wacc is not None else None
        present_value_fcff = fcff * discount_factor if discount_factor is not None else None
        shares = (
            shares * (1 + share_growth_rate)
            if shares is not None and share_growth_rate is not None
            else None
        )

        projections.append(
            {
                "year": year,
                "revenue": revenue,
                "revenueGrowthRate": growth,
                "operatingIncome": operating_income,
                "taxRate": tax_rate,
                "nopat": nopat,
                "reinvestment": reinvestment,
                "fcff": fcff,
                "discountFactor": discount_factor,
                "presentValueFcff": present_value_fcff,
                "sharesDiluted": shares,
                "shareCountGrowthRate": share_growth_rate,
            }
        )

    return projections


def calculate_terminal_value(
    projections: list[dict],
    assumptions: dict,
    quality_flags: list[str],
) -> Optional[float]:
    if not projections:
        add_flag(quality_flags, "missing_input:terminalValue")
        return None

    final_fcff = projections[-1].get("fcff")
    wacc = assumptions["discountRate"]["wacc"]["value"]
    terminal_growth = assumptions["terminalValue"]["terminalGrowthRate"]["value"]

    if final_fcff is None or wacc is None or terminal_growth is None:
        add_flag(quality_flags, "missing_input:terminalValue")
        return None

    if wacc <= terminal_growth:
        add_flag(quality_flags, "invalid_terminal_spread:wacc_lte_terminal_growth")
        return None

    return final_fcff * (1 + terminal_growth) / (wacc - terminal_growth)


def valuation_warnings(result: dict, assumptions: dict, materials: dict) -> list[dict]:
    warnings = []
    enterprise_value = result.get("enterpriseValue")
    present_value_terminal = result.get("presentValueTerminalValue")
    terminal_growth = assumptions["terminalValue"]["terminalGrowthRate"]["value"]
    wacc = assumptions["discountRate"]["wacc"]["value"]
    operating_margin = assumptions["margin"]["operatingMargin"]["value"]
    reinvestment_rate = assumptions["reinvestment"]["reinvestmentRate"]["value"]
    revenue_growth = assumptions["growth"]["revenueGrowthRate"]["value"]
    roic = (
        number((materials.get("latestComputed") or {}).get("returnOnInvestedCapital"))
        if materials.get("latestComputed")
        else None
    )

    dominance = safe_ratio(present_value_terminal, enterprise_value)

    if dominance is not None and dominance > 0.75:
        warnings.append(
            warning(
                "terminal_value_dominance",
                "high" if dominance > 0.8 else "medium",
                "Terminal value contributes an unusually large share of enterprise value.",
                dominance,
            )
        )

    if terminal_growth is not None and terminal_growth > LONG_TERM_GDP_GROWTH_PROXY:
        warnings.append(
            warning(
                "terminal_growth_above_gdp_proxy",
                "medium",
                "Terminal growth exceeds the long-term GDP proxy used by the platform.",
                terminal_growth,
            )
        )

    if wacc is not None and terminal_growth is not None and wacc <= terminal_growth:
        warnings.append(
            warning(
                "wacc_lte_terminal_growth",
                "high",
                "WACC must exceed terminal growth for a stable Gordon-growth terminal value.",
                wacc,
            )
        )

    if operating_margin is not None and (operating_margin > 0.5 or operating_margin < -0.1):
        warnings.append(
            warning(
                "unrealistic_operating_margin",
                "medium",
                "Operating margin is outside the platform's normal review band.",
                operating_margin,
            )
        )

    if reinvestment_rate is not None and reinvestment_rate < 0:
        warnings.append(
            warning(
                "negative_reinvestment_inconsistency",
                "medium",
                "Negative reinvestment is not supported by the Phase 3C FCFF model.",
                reinvestment_rate,
            )
        )

    if roic is not None and wacc is not None and roic < wacc and terminal_growth and terminal_growth > 0:
        warnings.append(
            warning(
                "roic_below_wacc_with_growth",
                "medium",
                "Positive terminal growth with ROIC below WACC requires analyst review.",
                roic,
            )
        )

    if revenue_growth is not None and abs(revenue_growth) > 0.25:
        warnings.append(
            warning(
                "projection_instability",
                "medium",
                "Explicit revenue growth is high enough to make the projection unstable.",
                revenue_growth,
            )
        )

    if result.get("projectedSharesDiluted") is None:
        warnings.append(
            warning(
                "missing_diluted_share_assumption",
                "high",
                "Diluted shares are missing, so intrinsic value per share cannot be audited.",
                None,
            )
        )

    return warnings


def warning(code: str, severity: str, message: str, value: Optional[float]) -> dict:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "value": value,
    }


def build_sensitivity_grid(base_financials: dict, assumptions: dict) -> dict:
    base_wacc = assumptions["discountRate"]["wacc"]["value"] or 0.09
    base_terminal = assumptions["terminalValue"]["terminalGrowthRate"]["value"] or 0.02
    base_margin = assumptions["margin"]["operatingMargin"]["value"] or 0.15
    wacc_values = rounded_values([base_wacc - 0.01, base_wacc, base_wacc + 0.01])
    terminal_values = rounded_values([base_terminal - 0.01, base_terminal, base_terminal + 0.01])
    margin_values = rounded_values([base_margin - 0.02, base_margin, base_margin + 0.02])

    return {
        "waccTerminalGrowth": sensitivity_matrix(
            "wacc",
            "terminalGrowthRate",
            wacc_values,
            terminal_values,
            base_financials,
            assumptions,
        ),
        "marginWacc": sensitivity_matrix(
            "operatingMargin",
            "wacc",
            margin_values,
            wacc_values,
            base_financials,
            assumptions,
        ),
        "marginTerminalGrowth": sensitivity_matrix(
            "operatingMargin",
            "terminalGrowthRate",
            margin_values,
            terminal_values,
            base_financials,
            assumptions,
        ),
    }


def build_sensitivity_visualization(
    sensitivity: dict,
    currency: Optional[str],
) -> dict:
    heatmaps = {
        key: sensitivity_heatmap(matrix)
        for key, matrix in sensitivity.items()
        if isinstance(matrix, dict)
    }

    return {
        "currency": currency,
        "heatmaps": heatmaps,
        "message": (
            "Heatmap intensities are derived from deterministic sensitivity "
            "cells for frontend visualization only."
        ),
    }


def sensitivity_heatmap(matrix: dict) -> dict:
    values = [
        cell.get("intrinsicValuePerShare")
        for row in matrix.get("cells") or []
        for cell in row
        if number(cell.get("intrinsicValuePerShare")) is not None
    ]
    numeric_values = [number(value) for value in values if number(value) is not None]
    minimum = min(numeric_values) if numeric_values else None
    maximum = max(numeric_values) if numeric_values else None

    return {
        "rowVariable": matrix.get("rowVariable"),
        "columnVariable": matrix.get("columnVariable"),
        "minimumIntrinsicValuePerShare": minimum,
        "maximumIntrinsicValuePerShare": maximum,
        "cells": [
            [
                {
                    **cell,
                    "intensity": sensitivity_intensity(
                        cell.get("intrinsicValuePerShare"),
                        minimum,
                        maximum,
                    ),
                    "tone": sensitivity_tone(
                        cell.get("intrinsicValuePerShare"),
                        minimum,
                        maximum,
                    ),
                }
                for cell in row
            ]
            for row in matrix.get("cells") or []
        ],
    }


def sensitivity_intensity(
    value: Optional[float],
    minimum: Optional[float],
    maximum: Optional[float],
) -> Optional[float]:
    numeric_value = number(value)

    if numeric_value is None or minimum is None or maximum is None:
        return None

    if maximum == minimum:
        return 0.5

    return round((numeric_value - minimum) / (maximum - minimum), 4)


def sensitivity_tone(
    value: Optional[float],
    minimum: Optional[float],
    maximum: Optional[float],
) -> str:
    intensity = sensitivity_intensity(value, minimum, maximum)

    if intensity is None:
        return "unavailable"

    if intensity < 0.34:
        return "low"

    if intensity > 0.67:
        return "high"

    return "mid"


def sensitivity_matrix(
    row_variable: str,
    column_variable: str,
    row_values: list[float],
    column_values: list[float],
    base_financials: dict,
    assumptions: dict,
) -> dict:
    cells = []

    for row_value in row_values:
        row_cells = []

        for column_value in column_values:
            scenario_assumptions = clone_assumptions(assumptions)
            set_assumption_value(scenario_assumptions, row_variable, row_value)
            set_assumption_value(scenario_assumptions, column_variable, column_value)
            quality_flags = []
            projections = project_fcff(base_financials, scenario_assumptions, quality_flags)
            terminal_value = calculate_terminal_value(
                projections,
                scenario_assumptions,
                quality_flags,
            )
            pv_terminal = present_value(
                terminal_value,
                scenario_assumptions["discountRate"]["wacc"]["value"],
                len(projections),
                "sensitivityTerminalValue",
                quality_flags,
            )
            pv_fcff = sum(
                row["presentValueFcff"]
                for row in projections
                if row["presentValueFcff"] is not None
            )
            enterprise_value = add_nullable(pv_fcff, pv_terminal)
            equity_value = subtract_nullable(
                enterprise_value,
                calculate_refined_net_debt(base_financials, scenario_assumptions),
            )
            intrinsic = divide_nullable(
                equity_value,
                final_projected_shares(projections, base_financials),
                "sensitivityIntrinsicValuePerShare",
                quality_flags,
            )
            row_cells.append(
                {
                    "rowValue": row_value,
                    "columnValue": column_value,
                    "intrinsicValuePerShare": intrinsic,
                    "qualityFlags": sorted(set(quality_flags)),
                }
            )

        cells.append(row_cells)

    return {
        "rowVariable": row_variable,
        "columnVariable": column_variable,
        "rowValues": row_values,
        "columnValues": column_values,
        "cells": cells,
    }


def base_financials_from_materials(materials: dict) -> dict:
    latest_income = materials["latestIncome"]
    latest_balance = materials["latestBalance"]
    latest_cash_flow = materials["latestCashFlow"]
    latest_profile = materials["profile"]
    market_snapshot = materials["marketSnapshotResponse"]

    revenue = number(latest_income.get("revenue")) if latest_income else None
    cash = number(latest_balance.get("cashAndEquivalents")) if latest_balance else None
    operating_cash = min(cash, revenue * 0.02) if cash is not None and revenue else None
    excess_cash = (
        max(cash - operating_cash, 0)
        if cash is not None and operating_cash is not None
        else None
    )

    return {
        "revenue": revenue,
        "operatingIncome": number(latest_income.get("operatingIncome")) if latest_income else None,
        "freeCashFlow": number(latest_cash_flow.get("freeCashFlow")) if latest_cash_flow else None,
        "cashAndEquivalents": cash,
        "operatingCash": operating_cash,
        "excessCash": excess_cash,
        "totalDebt": number(latest_balance.get("totalDebt")) if latest_balance else None,
        "leaseDebt": None,
        "preferredEquity": None,
        "minorityInterest": None,
        "sharesDiluted": number(latest_income.get("sharesDiluted")) if latest_income else None,
        "marketPrice": number(market_snapshot.get("price"))
        or (number(latest_profile.get("price")) if latest_profile else None),
        "currency": first_text(
            latest_income.get("currency") if latest_income else None,
            latest_balance.get("currency") if latest_balance else None,
            latest_cash_flow.get("currency") if latest_cash_flow else None,
            latest_profile.get("currency") if latest_profile else None,
            market_snapshot.get("currency"),
        ),
        "fiscalYear": text(latest_income.get("fiscalYear")) if latest_income else None,
        "fiscalPeriod": text(latest_income.get("fiscalPeriod")) if latest_income else None,
    }


def net_share_growth_rate(assumptions: dict) -> Optional[float]:
    share_count = assumptions["shareCount"]
    diluted_growth = share_count["dilutedShareGrowthRate"]["value"]
    sbc_dilution = share_count["stockBasedCompensationDilutionRate"]["value"]
    buyback_rate = share_count["buybackRate"]["value"]

    if None in [diluted_growth, sbc_dilution, buyback_rate]:
        return None

    return diluted_growth + sbc_dilution - buyback_rate


def final_projected_shares(
    projections: list[dict],
    base_financials: dict,
) -> Optional[float]:
    for row in reversed(projections):
        projected = number(row.get("sharesDiluted"))

        if projected is not None:
            return projected

    return base_financials["sharesDiluted"]


def calculate_refined_net_debt(base_financials: dict, assumptions: dict) -> Optional[float]:
    total_debt = base_financials["totalDebt"]
    cash = base_financials["cashAndEquivalents"]
    revenue = base_financials["revenue"]
    operating_cash_percent = assumptions["netDebt"]["operatingCashPercentOfRevenue"][
        "value"
    ]
    operating_cash = (
        min(cash, revenue * operating_cash_percent)
        if cash is not None and revenue is not None and operating_cash_percent is not None
        else base_financials["operatingCash"]
    )
    excess_cash = (
        max(cash - operating_cash, 0)
        if cash is not None and operating_cash is not None
        else base_financials["excessCash"]
    )
    base_financials["operatingCash"] = operating_cash
    base_financials["excessCash"] = excess_cash
    lease_debt = assumption_or_base(
        assumptions,
        "netDebt",
        "leaseDebt",
        base_financials.get("leaseDebt"),
    )
    preferred_equity = assumption_or_base(
        assumptions,
        "netDebt",
        "preferredEquity",
        base_financials.get("preferredEquity"),
    )
    minority_interest = assumption_or_base(
        assumptions,
        "netDebt",
        "minorityInterest",
        base_financials.get("minorityInterest"),
    )

    if total_debt is None or excess_cash is None:
        return None

    return (
        total_debt
        + (lease_debt or 0)
        + (preferred_equity or 0)
        + (minority_interest or 0)
        - excess_cash
    )


def assumption_or_base(
    assumptions: dict,
    group: str,
    key: str,
    base_value: Optional[float],
) -> Optional[float]:
    assumption_value_payload = assumptions.get(group, {}).get(key, {})
    value = assumption_value_payload.get("value")

    return number(value) if value is not None else base_value


def apply_overrides(assumptions: dict, overrides: dict) -> None:
    for group_key in [
        "discountRate",
        "growth",
        "margin",
        "reinvestment",
        "shareCount",
        "netDebt",
        "terminalValue",
    ]:
        group_overrides = overrides.get(group_key)

        if not isinstance(group_overrides, dict):
            continue

        for assumption_key, override_value in group_overrides.items():
            if assumption_key not in assumptions[group_key]:
                continue

            value = extract_override_value(override_value)

            if value is None:
                continue

            assumptions[group_key][assumption_key] = {
                **assumptions[group_key][assumption_key],
                "value": value,
                "source": "user_override",
                "rationale": "User-edited workbench assumption.",
                "qualityFlags": [],
            }


def validate_assumptions(assumptions: dict) -> None:
    for (group_key, assumption_key), limits in ASSUMPTION_LIMITS.items():
        assumption_payload = assumptions[group_key][assumption_key]
        value = assumption_payload.get("value")

        if value is None:
            continue

        minimum, maximum = limits

        if value < minimum or value > maximum:
            add_flag(
                assumption_payload["qualityFlags"],
                f"out_of_range:{assumption_key}",
            )

    projection_years = assumptions["growth"]["projectionYears"]["value"]

    if projection_years is not None and int(projection_years) != projection_years:
        add_flag(
            assumptions["growth"]["projectionYears"]["qualityFlags"],
            "invalid_integer:projectionYears",
        )

    debt_weight = assumptions["discountRate"]["debtWeight"]["value"]
    equity_weight = assumptions["discountRate"]["equityWeight"]["value"]

    if debt_weight is not None and equity_weight is not None:
        if abs((debt_weight + equity_weight) - 1) > 0.02:
            add_flag(
                assumptions["discountRate"]["debtWeight"]["qualityFlags"],
                "capital_weight_sum_mismatch",
            )
            add_flag(
                assumptions["discountRate"]["equityWeight"]["qualityFlags"],
                "capital_weight_sum_mismatch",
            )

    wacc = assumptions["discountRate"]["wacc"]["value"]
    terminal_growth = assumptions["terminalValue"]["terminalGrowthRate"]["value"]

    if wacc is not None and terminal_growth is not None and wacc <= terminal_growth:
        add_flag(
            assumptions["discountRate"]["wacc"]["qualityFlags"],
            "invalid_terminal_spread:wacc_lte_terminal_growth",
        )
        add_flag(
            assumptions["terminalValue"]["terminalGrowthRate"]["qualityFlags"],
            "invalid_terminal_spread:wacc_lte_terminal_growth",
        )


def refresh_derived_discount_rate_assumptions(assumptions: dict) -> None:
    discount = assumptions["discountRate"]
    risk_free = discount["riskFreeRate"]["value"]
    beta = discount["beta"]["value"]
    premium = discount["equityRiskPremium"]["value"]
    tax_rate = discount["taxRate"]["value"]
    pre_tax_debt = discount["preTaxCostOfDebt"]["value"]
    debt_weight = discount["debtWeight"]["value"]
    equity_weight = discount["equityWeight"]["value"]

    if None in [risk_free, beta, premium, tax_rate, pre_tax_debt, debt_weight, equity_weight]:
        return

    cost_of_equity = risk_free + beta * premium
    after_tax_debt = pre_tax_debt * (1 - tax_rate)
    wacc = cost_of_equity * equity_weight + after_tax_debt * debt_weight
    discount["costOfEquity"]["value"] = cost_of_equity
    discount["afterTaxCostOfDebt"]["value"] = after_tax_debt

    if discount["wacc"].get("source") != "user_override":
        discount["wacc"]["value"] = wacc


def scenario_name_from_overrides(overrides: dict) -> Optional[str]:
    raw_name = overrides.get("scenarioName") or overrides.get("name")

    if not isinstance(raw_name, str):
        return None

    normalized = " ".join(raw_name.strip().split())

    if not normalized:
        return None

    return normalized[:80]


def scenario_summary(result: dict) -> dict:
    scenario = result.get("scenario") or {}

    return {
        "scenarioId": scenario.get("id"),
        "ticker": result.get("ticker"),
        "name": scenario.get("name") or "DCF Scenario",
        "schemaVersion": result.get("schemaVersion"),
        "modelVersion": scenario.get("modelVersion")
        or (result.get("modelMetadata") or {}).get("modelVersion"),
        "versionNumber": scenario.get("versionNumber"),
        "versionId": scenario.get("versionId"),
        "priorVersionId": scenario.get("priorVersionId"),
        "parentScenarioId": scenario.get("parentScenarioId"),
        "status": scenario.get("status") or "active",
        "archivedAt": scenario.get("archivedAt"),
        "deletedAt": scenario.get("deletedAt"),
        "createdAt": scenario.get("createdAt") or result.get("createdAt"),
        "updatedAt": scenario.get("updatedAt") or result.get("updatedAt"),
        "intrinsicValuePerShare": result.get("intrinsicValuePerShare"),
        "equityValue": result.get("equityValue"),
        "enterpriseValue": result.get("enterpriseValue"),
        "currency": (result.get("baseFinancials") or {}).get("currency"),
        "providerState": (result.get("provider") or {}).get("state"),
        "qualityFlags": result.get("qualityFlags") or [],
        "warnings": result.get("warnings") or [],
    }


def scenario_comparison_row(result: dict) -> dict:
    scenario = result.get("scenario") or {}

    return {
        **scenario_summary(result),
        "assumptions": {
            "revenueGrowthRate": assumption_value(
                scenario,
                "growth",
                "revenueGrowthRate",
            ),
            "operatingMargin": assumption_value(
                scenario,
                "margin",
                "operatingMargin",
            ),
            "reinvestmentRate": assumption_value(
                scenario,
                "reinvestment",
                "reinvestmentRate",
            ),
            "taxRate": assumption_value(scenario, "discountRate", "taxRate"),
            "wacc": assumption_value(scenario, "discountRate", "wacc"),
            "terminalGrowthRate": assumption_value(
                scenario,
                "terminalValue",
                "terminalGrowthRate",
            ),
        },
    }


def require_scenario_for_diff(
    ticker: str,
    scenario_id: str,
    version_id: Optional[str],
    repository: SnapshotRepository,
) -> dict:
    if version_id:
        scenario = repository.get_valuation_scenario_version(
            ticker,
            scenario_id,
            version_id,
        )
    else:
        scenario = repository.get_valuation_scenario(ticker, scenario_id)

    if scenario is None:
        raise ValueError("DCF scenario or version not found.")

    return scenario


def valuation_delta_summary(left: dict, right: dict) -> dict:
    return {
        "intrinsicValuePerShare": diff_values(
            left.get("intrinsicValuePerShare"),
            right.get("intrinsicValuePerShare"),
        ),
        "equityValue": diff_values(left.get("equityValue"), right.get("equityValue")),
        "enterpriseValue": diff_values(
            left.get("enterpriseValue"),
            right.get("enterpriseValue"),
        ),
        "terminalValue": diff_values(
            left.get("terminalValue"),
            right.get("terminalValue"),
        ),
    }


def assumption_diff_rows(left: dict, right: dict) -> list[dict]:
    left_values = flat_assumption_values(left.get("scenario") or {})
    right_values = flat_assumption_values(right.get("scenario") or {})
    paths = sorted(set(left_values) | set(right_values))

    return [
        diff_row(path, left_values.get(path), right_values.get(path))
        for path in paths
        if left_values.get(path) != right_values.get(path)
    ]


def output_diff_rows(left: dict, right: dict) -> list[dict]:
    fields = [
        "intrinsicValuePerShare",
        "enterpriseValue",
        "equityValue",
        "terminalValue",
        "presentValueTerminalValue",
        "netDebt",
        "projectedSharesDiluted",
    ]

    return [
        diff_row(field, left.get(field), right.get(field))
        for field in fields
        if left.get(field) != right.get(field)
    ]


def warning_diff_rows(left: dict, right: dict) -> dict:
    left_warnings = {warning.get("code"): warning for warning in left.get("warnings") or []}
    right_warnings = {warning.get("code"): warning for warning in right.get("warnings") or []}
    left_codes = {code for code in left_warnings if code}
    right_codes = {code for code in right_warnings if code}

    return {
        "added": [
            right_warnings[code]
            for code in sorted(right_codes - left_codes)
        ],
        "removed": [
            left_warnings[code]
            for code in sorted(left_codes - right_codes)
        ],
        "shared": [
            right_warnings[code]
            for code in sorted(left_codes & right_codes)
        ],
    }


def flat_assumption_values(scenario: dict) -> dict:
    values = {}

    for group in assumption_group_keys():
        for key, payload in (scenario.get(group) or {}).items():
            if isinstance(payload, dict) and "value" in payload:
                values[f"{group}.{key}"] = payload.get("value")

    return values


def diff_row(field_path: str, left_value, right_value) -> dict:
    return {
        "fieldPath": field_path,
        "leftValue": left_value,
        "rightValue": right_value,
        **diff_values(left_value, right_value),
    }


def diff_values(left_value, right_value) -> dict:
    left_number = number(left_value)
    right_number = number(right_value)

    if left_number is None or right_number is None:
        return {
            "delta": None,
            "percentDelta": None,
        }

    delta = right_number - left_number

    return {
        "delta": delta,
        "percentDelta": safe_ratio(delta, abs(left_number)),
    }


def exportable_assumptions(scenario: dict) -> dict:
    return {
        group: assumption_group_values(scenario.get(group) or {})
        for group in assumption_group_keys()
    }


def parse_assumption_import_payload(payload: dict) -> tuple[dict, dict]:
    if not isinstance(payload, dict):
        raise ValueError("Import payload must be a JSON object.")

    schema_version = payload.get("schemaVersion")

    if schema_version != SCHEMA_VERSION:
        raise ValueError("Imported assumptions must use schemaVersion = 1.")

    model_version = payload.get("modelVersion")

    if not isinstance(model_version, str) or not model_version:
        raise ValueError("Imported assumptions must include modelVersion.")

    assumptions = payload.get("assumptions") if isinstance(payload.get("assumptions"), dict) else payload
    overrides = {}

    for group in assumption_group_keys():
        values = assumptions.get(group)

        if not isinstance(values, dict):
            continue

        normalized_values = {
            key: extract_override_value(value)
            for key, value in values.items()
            if extract_override_value(value) is not None
        }

        if normalized_values:
            overrides[group] = normalized_values

    if not overrides:
        raise ValueError("Imported assumptions did not contain editable values.")

    scenario_name = (
        payload.get("scenarioName")
        or (payload.get("sourceScenario") or {}).get("name")
        or "Imported DCF Scenario"
    )
    overrides["scenarioName"] = scenario_name_from_overrides(
        {"scenarioName": f"{scenario_name} Import"}
    )

    source_scenario = payload.get("sourceScenario") or {}

    return overrides, {
        "schemaVersion": schema_version,
        "modelVersion": model_version,
        "sourceScenarioId": source_scenario.get("scenarioId")
        or payload.get("sourceScenarioId"),
        "sourceVersionId": source_scenario.get("versionId")
        or payload.get("sourceVersionId"),
    }


def assumption_group_keys() -> list[str]:
    return [
        "discountRate",
        "growth",
        "margin",
        "reinvestment",
        "shareCount",
        "netDebt",
        "terminalValue",
    ]


def assumption_value(scenario: dict, group: str, key: str) -> Optional[float]:
    payload = (scenario.get(group) or {}).get(key) or {}

    return number(payload.get("value"))


def scenario_version_summary(result: dict) -> dict:
    summary = scenario_summary(result)
    summary["modelMetadata"] = result.get("modelMetadata")

    return summary


def require_scenario(
    ticker: str,
    scenario_id: str,
    repository: SnapshotRepository,
) -> dict:
    scenario = repository.get_valuation_scenario(ticker.strip().upper(), scenario_id)

    if scenario is None:
        raise ValueError("DCF scenario not found.")

    return scenario


def clone_for_lifecycle(result: dict) -> dict:
    payload = deepcopy(result)
    scenario = payload.get("scenario") or {}
    scenario.pop("versionNumber", None)
    scenario.pop("versionId", None)
    payload["scenario"] = scenario

    return payload


def audit_event(
    change_type: str,
    field_path: Optional[str],
    previous_value,
    new_value,
    message: Optional[str] = None,
) -> dict:
    return {
        "changeType": change_type,
        "fieldPath": field_path,
        "previousValue": previous_value,
        "newValue": new_value,
        "message": message,
    }


def merge_scenario_overrides(existing: dict, overrides: dict) -> dict:
    scenario = existing.get("scenario") or {}
    merged = {
        "discountRate": assumption_group_values(scenario.get("discountRate") or {}),
        "growth": assumption_group_values(scenario.get("growth") or {}),
        "margin": assumption_group_values(scenario.get("margin") or {}),
        "reinvestment": assumption_group_values(scenario.get("reinvestment") or {}),
        "shareCount": assumption_group_values(scenario.get("shareCount") or {}),
        "netDebt": assumption_group_values(scenario.get("netDebt") or {}),
        "terminalValue": assumption_group_values(scenario.get("terminalValue") or {}),
        "scenarioName": scenario.get("name"),
    }

    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value

    return merged


def assumption_group_values(group: dict) -> dict:
    return {
        key: payload.get("value")
        for key, payload in group.items()
        if isinstance(payload, dict) and "value" in payload
    }


def assumption_change_events(previous: dict, current: dict) -> list[dict]:
    events = []
    previous_scenario = previous.get("scenario") or {}
    current_scenario = current.get("scenario") or {}

    for group in [
        "discountRate",
        "growth",
        "margin",
        "reinvestment",
        "shareCount",
        "netDebt",
        "terminalValue",
    ]:
        previous_values = assumption_group_values(previous_scenario.get(group) or {})
        current_values = assumption_group_values(current_scenario.get(group) or {})

        for key, new_value in current_values.items():
            old_value = previous_values.get(key)

            if old_value != new_value:
                events.append(
                    audit_event(
                        "assumption_update",
                        f"{group}.{key}",
                        old_value,
                        new_value,
                    )
                )

    if previous_scenario.get("name") != current_scenario.get("name"):
        events.append(
            audit_event(
                "rename",
                "scenario.name",
                previous_scenario.get("name"),
                current_scenario.get("name"),
            )
        )

    return events or [
        audit_event(
            "version",
            None,
            previous_scenario.get("versionId"),
            current_scenario.get("versionId"),
        )
    ]


def set_assumption_value(assumptions: dict, variable: str, value: float) -> None:
    if variable == "wacc":
        assumptions["discountRate"]["wacc"]["value"] = value
    elif variable == "terminalGrowthRate":
        assumptions["terminalValue"]["terminalGrowthRate"]["value"] = value
    elif variable == "operatingMargin":
        assumptions["margin"]["operatingMargin"]["value"] = value


def clone_assumptions(assumptions: dict) -> dict:
    return {
        group: {key: dict(value) for key, value in values.items()}
        for group, values in assumptions.items()
    }


def derived_tax_rate(income_rows: list[dict]) -> Optional[float]:
    rates = []

    for row in income_rows:
        operating_income = number(row.get("operatingIncome"))
        net_income = number(row.get("netIncome"))

        if operating_income is None or net_income is None or operating_income <= 0:
            continue

        rates.append(min(max(1 - net_income / operating_income, 0), 0.4))

    return median_number(rates)


def derived_reinvestment_rate(
    income_rows: list[dict],
    cash_flow_rows: list[dict],
    tax_rate: Optional[float],
) -> Optional[float]:
    if tax_rate is None:
        return None

    rates = []

    for index, income in enumerate(income_rows):
        if index >= len(cash_flow_rows):
            continue

        revenue = number(income.get("revenue"))
        operating_income = number(income.get("operatingIncome"))
        free_cash_flow = number(cash_flow_rows[index].get("freeCashFlow"))

        if revenue is None or revenue == 0 or operating_income is None or free_cash_flow is None:
            continue

        nopat = operating_income * (1 - tax_rate)
        rates.append(max((nopat - free_cash_flow) / revenue, 0))

    return median_number(rates)


def assumption(
    value: Optional[float],
    source: str,
    rationale: str,
    unit: str,
    quality_flags: list[str],
) -> dict:
    return {
        "value": value,
        "source": source,
        "rationale": rationale,
        "editable": True,
        "unit": unit,
        "qualityFlags": quality_flags,
    }


def assumption_quality_flags(assumptions: dict) -> list[str]:
    flags = []

    for group in assumptions.values():
        for assumption_payload in group.values():
            for flag in assumption_payload.get("qualityFlags") or []:
                add_flag(flags, flag)

            if assumption_payload.get("value") is None:
                add_flag(flags, "missing_assumption")

    return sorted(set(flags))


def empty_projection_year(year: int) -> dict:
    return {
        "year": year,
        "revenue": None,
        "revenueGrowthRate": None,
        "operatingIncome": None,
        "taxRate": None,
        "nopat": None,
        "reinvestment": None,
        "fcff": None,
        "discountFactor": None,
        "presentValueFcff": None,
        "sharesDiluted": None,
        "shareCountGrowthRate": None,
    }


def present_value(
    value: Optional[float],
    discount_rate: Optional[float],
    year: int,
    metric_name: str,
    quality_flags: list[str],
) -> Optional[float]:
    if value is None or discount_rate is None:
        add_flag(quality_flags, f"missing_input:{metric_name}")
        return None

    if discount_rate <= -1:
        add_flag(quality_flags, f"invalid_discount_rate:{metric_name}")
        return None

    return value / ((1 + discount_rate) ** year)


def divide_nullable(
    numerator: Optional[float],
    denominator: Optional[float],
    metric_name: str,
    quality_flags: list[str],
) -> Optional[float]:
    if numerator is None or denominator is None:
        add_flag(quality_flags, f"missing_input:{metric_name}")
        return None

    if denominator == 0:
        add_flag(quality_flags, f"zero_denominator:{metric_name}")
        return None

    return numerator / denominator


def add_nullable(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None

    return left + right


def subtract_nullable(left: Optional[float], right: Optional[float]) -> Optional[float]:
    if left is None or right is None:
        return None

    return left - right


def aggregate_provider_status(statuses: list[Optional[dict]]) -> dict:
    normalized = [status for status in statuses if isinstance(status, dict)]

    if not normalized:
        return provider_not_connected("valuation_data", [])

    states = {status.get("state") for status in normalized}
    last_success = max(
        [
            status.get("lastSuccessfulCallAt")
            for status in normalized
            if status.get("lastSuccessfulCallAt")
        ],
        default=None,
    )

    if states == {"connected"}:
        return provider_connected(
            "valuation_data",
            "Valuation inputs are connected.",
            last_success,
        )

    if "degraded" in states or "connected" in states:
        return provider_degraded(
            "valuation_data",
            "One or more valuation input providers are degraded, unavailable, or partial.",
            [],
            last_success,
            "Valuation was calculated with degraded or partial input data.",
        )

    return provider_not_connected(
        "valuation_data",
        ["FMP_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"],
    )


def dcf_formulas() -> list[str]:
    return [
        "revenue[t] = revenue[t-1] * (1 + revenueGrowthRate)",
        "operatingIncome[t] = revenue[t] * operatingMargin",
        "nopat[t] = operatingIncome[t] * (1 - taxRate)",
        "reinvestment[t] = max(revenue[t] - revenue[t-1], 0) * reinvestmentRate",
        "fcff[t] = nopat[t] - reinvestment[t]",
        "sharesDiluted[t] = sharesDiluted[t-1] * (1 + dilutedShareGrowthRate + stockBasedCompensationDilutionRate - buybackRate)",
        "presentValueFcff[t] = fcff[t] / (1 + wacc)^t",
        "terminalValue = fcff[final] * (1 + terminalGrowthRate) / (wacc - terminalGrowthRate)",
        "enterpriseValue = sum(presentValueFcff) + presentValueTerminalValue",
        "netDebt = totalDebt + leaseDebt + preferredEquity + minorityInterest - excessCash",
        "equityValue = enterpriseValue - netDebt",
        "intrinsicValuePerShare = equityValue / projectedSharesDiluted",
    ]


def extract_override_value(value) -> Optional[float]:
    if isinstance(value, dict):
        return number(value.get("value"))

    return number(value)


def rows_from_response(response: dict, key: str) -> list[dict]:
    rows = response.get(key)

    if not isinstance(rows, list):
        return []

    return [row for row in rows if isinstance(row, dict)]


def first_row(rows: list[dict]) -> Optional[dict]:
    return rows[0] if rows else None


def mapping_or_none(value) -> Optional[dict]:
    return value if isinstance(value, dict) else None


def median_number(values) -> Optional[float]:
    numbers = sorted(number(value) for value in values if number(value) is not None)

    if not numbers:
        return None

    middle = len(numbers) // 2

    if len(numbers) % 2:
        return numbers[middle]

    return (numbers[middle - 1] + numbers[middle]) / 2


def safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None

    return numerator / denominator


def rounded_values(values: list[float]) -> list[float]:
    return [round(value, 4) for value in values]


def number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def text(value) -> Optional[str]:
    if isinstance(value, str) and value:
        return value

    return None


def nullable_string(value) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()

        return normalized or None

    return str(value)


def first_text(*values) -> Optional[str]:
    for value in values:
        text_value = text(value)

        if text_value:
            return text_value

    return None


def add_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
