"""Generate weekly business reports from processed analytics data."""

import json
import os
import re

import pandas as pd

from .config import ROOT


def validate_numeric_draft(draft, facts):
    tokens = re.findall(r"\{\{([a-z_]+)\}\}", draft)
    prose = re.sub(r"\{\{[a-z_]+\}\}", "", draft)

    number_words = (
        r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
        r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
        r"seventy|eighty|ninety|hundred|thousand|million|billion|"
        r"trillion|twice|double|half|quarter|percent"
    )

    if any(token not in facts for token in tokens) or re.search(
        rf"\d|\b({number_words})\b", prose, re.I
    ):
        raise ValueError("AI draft contains an unapproved numeric claim")

    for token in tokens:
        draft = draft.replace("{{" + token + "}}", str(facts[token]))

    return draft


def delivery_summary(reporting_end):
    path = ROOT / "reports/weekly_delivery_alerts.csv"

    if not path.exists():
        return ""

    alerts = pd.read_csv(path, parse_dates=["week"])
    alerts = alerts[alerts["week"] + pd.Timedelta(days=6) <= pd.Timestamp(reporting_end)]

    if alerts.empty:
        return "\n## Weekly delivery performance\n\nNo complete weeks available.\n"

    week = alerts.sort_values("week").iloc[-1]
    alert = str(week["late_rate_alert"]).lower() == "true"

    if pd.isna(week["alert_threshold_pct"]):
        status = "Not evaluated (insufficient history)"
    elif alert:
        status = "Triggered - investigate delivery delays"
    else:
        status = "Not triggered"

    previous = week["previous_4_week_late_rate_pct"]
    change = week["change_vs_previous_4w_pp"]
    threshold = week["alert_threshold_pct"]

    previous_text = f"{previous:.2f}%" if pd.notna(previous) else "N/A"
    change_text = f"{change:+.2f} pp" if pd.notna(change) else "N/A"
    threshold_text = f"{threshold:.2f}%" if pd.notna(threshold) else "N/A"

    return f"""
## Weekly delivery performance

Week starting {week["week"].date()}:

- Delivered orders: {int(week["delivered_orders"]):,}
- Late deliveries: {int(week["late_orders"]):,}
- Late-delivery rate: {week["late_rate_pct"]:.2f}%
- Previous four-week rate: {previous_text}
- Change: {change_text}
- Average review score: {week["avg_review_score"]:.2f}/5
- Alert threshold: {threshold_text}
- Alert status: {status}

Delivery results are historical observations, not causal evidence.
"""


def write_report(use_llm=False):
    out = ROOT / "reports"

    metrics = json.loads((out / "analysis.json").read_text())
    weekly = pd.read_csv(out / "weekly_kpis.csv").sort_values("week")

    eligible = weekly.is_complete_week & (
        pd.to_datetime(weekly.week) + pd.Timedelta(days=6) <= pd.Timestamp(metrics["reporting_end"])
    )

    complete = weekly[eligible].tail(2)

    if len(complete) != 2:
        raise ValueError("Need two complete weeks")

    prior, current = complete.iloc[0], complete.iloc[1]

    change = (current.gmv / prior.gmv - 1) * 100 if prior.gmv else None
    change_text = f"{change:+.1f}%" if change is not None else "N/A"

    test = metrics["delivery_test"]
    retention = metrics["retention"]

    deep_path = out / "deepdive.json"
    deep = json.loads(deep_path.read_text()) if deep_path.exists() else None

    if deep:
        concentration = (
            f"{deep['sellers_for_80pct_gmv']:,} of "
            f"{deep['seller_count']:,} sellers account for "
            "80% of delivered merchandise GMV."
        )
    else:
        concentration = (
            f"{metrics['customers_for_80pct_gmv']:,} customers "
            f"({metrics['customer_share_for_80pct_gmv']:.1%}) "
            "account for 80% of delivered-order GMV."
        )

    body = f"""# Weekly operating review

Historical e-commerce analysis. Purchase cutoff: {metrics["cutoff"]}.
Order statuses reflect the final source snapshot.

Comparisons stop at {metrics["reporting_end"]}.
August remains in descriptive totals but is excluded from weekly
comparisons and forecasts because coverage is uncertain.

## Last eligible complete week: {current.week}

- Delivered-order merchandise GMV: BRL {current.gmv:,.2f}.
- Orders: {int(current.orders):,}; AOV: BRL {current.aov:,.2f}.
- GMV versus previous complete week: {change_text}.

## Findings across the analysis window

- {concentration}
- Repeat-customer share: {metrics["repeat_customer_rate"]:.2%}. Repeat means at least two delivered orders in the observed purchase window.
- Average review score for late orders: {test["late_mean"]:.2f}, compared with {test["on_time_mean"]:.2f} for on-time orders.
- Review-score difference: {test["difference_points"]:.2f} points, with 95% Welch interval [{test["ci95"][0]:.2f}, {test["ci95"][1]:.2f}]. This does not establish causation.

## Actions to investigate

1. Review late deliveries by state and seller. Compare both delay rates and order volumes.
2. Test a second-purchase campaign with a randomized holdout before claiming an improvement in retention.

The forecast and backtest errors are saved in `analysis.json`.
Anomalies are investigation prompts, not confirmed business incidents.
No manual time-saving claim has been measured.
"""

    body += delivery_summary(metrics["reporting_end"])

    body += "\n## Repeat purchases after the first delivery\n\n"

    for group in retention["groups"]:
        body += (
            f"- {group['experience']}: "
            f"{group['repeat_customers']:,}/{group['customers']:,} "
            f"customers repeated within 90 days "
            f"({group['repeat_rate']:.2%}); "
            "subsequent merchandise GMV per eligible customer: "
            f"BRL {group['followup_gmv_per_customer']:.2f}.\n"
        )

    adjusted = retention["adjusted"]

    if adjusted["odds_ratio"] is not None:
        body += (
            f"\nAdjusted late/on-time odds ratio: "
            f"{adjusted['odds_ratio']:.2f}, "
            f"95% interval [{adjusted['ci95'][0]:.2f}, "
            f"{adjusted['ci95'][1]:.2f}], "
            f"across {adjusted['strata']} comparable strata "
            f"({adjusted['overlap_customers']:,} customers).\n"
        )

    body += "\n" + retention["interpretation"] + "\n"

    if deep:
        findings_path = out / "findings.json"

        if findings_path.exists():
            findings = json.loads(findings_path.read_text())

            rates = pd.DataFrame(findings["handoff"])
            columns = [
                "handoff",
                "orders",
                "late_orders",
                "late_rate",
                "order_share",
                "late_order_share",
            ]

            table = rates[columns].copy()

            for column in ["late_rate", "order_share", "late_order_share"]:
                table[column] = table[column].map(lambda value: f"{value:.2%}")

            body += (
                "\n## Handoff: rates and denominators\n\n" + table.to_markdown(index=False) + "\n"
            )

            body += (
                f"\nLate-handoff orders have "
                f"{findings['handoff_rate_ratio']:.2f} times "
                "the observed late-delivery rate. "
                "Applying the timely-handoff rate gives a scenario of "
                f"{findings['handoff_scenario_fewer']:,.0f} fewer late orders; "
                "these are not proven avoidable orders.\n"
            )

            distance = findings["rj_distance_scenario"]

            body += (
                f"\nRJ distance-band comparison: "
                f"{distance['observed_late']:,} observed late orders "
                f"among {distance['eligible_rj_orders']:,} eligible orders "
                f"versus {distance['expected_late']:,.0f} expected "
                "at the non-RJ distance-band rates. "
                f"Scenario difference: {distance['fewer_late']:,.0f}. "
                "The separate SP-rate scenario is "
                f"{deep['rj_scenario']['fewer_late_orders']:,.0f}; "
                "it is not an upper bound.\n"
            )

            body += "\n## Retention: full cohort and sensitivity\n\n"

            for estimate in findings["retention_differences"]:
                low, high = estimate["ci95_pp"]

                body += (
                    f"- {estimate['definition']}: late minus on-time "
                    f"{estimate['difference_pp']:+.2f} pp, "
                    f"95% interval [{low:+.2f}, {high:+.2f}] pp. "
                    f"Late repeat buyers: {estimate['late_repeat']}/"
                    f"{estimate['late_n']}; "
                    f"on time: {estimate['on_time_repeat']}/"
                    f"{estimate['on_time_n']}.\n"
                )

            body += (
                "\nIntervals use independent-proportion normal "
                "approximations. Broader exposure is longer, "
                "and neither estimate establishes causation.\n"
            )

        sensitivity_path = out / "retention_sensitivity.csv"

        if sensitivity_path.exists():
            sensitivity = pd.read_csv(sensitivity_path)

            body += (
                "\nRetention counts (same eligible cohort):\n\n"
                + sensitivity.to_markdown(index=False)
                + "\n"
            )

    (out / "weekly_report.md").write_text(body, encoding="utf-8", newline="\n")

    if use_llm:
        from openai import OpenAI

        model = os.environ["OPENAI_MODEL"]
        client = OpenAI(timeout=60, max_retries=2)

        payload = {
            "complete_weeks": json.loads(complete.to_json(orient="records")),
            "analysis": metrics,
        }

        facts = {
            "weekly_gmv": f"BRL {current.gmv:,.2f}",
            "weekly_orders": str(int(current.orders)),
            "late_review": f"{test['late_mean']:.2f}",
            "on_time_review": f"{test['on_time_mean']:.2f}",
        }

        response = client.responses.create(
            model=model,
            store=False,
            max_output_tokens=1000,
            instructions=(
                "Write a concise executive draft using only the supplied "
                "aggregate facts. Separate observations, hypotheses, and "
                "proposed actions. Do not invent causes, savings, ROI or "
                "causal effects. Preserve dates, units and historical-replay "
                "limitations. Do not include personal information. Never "
                "write numbers as digits or words. Use only "
                "{{weekly_gmv}}, {{weekly_orders}}, {{late_review}}, "
                "{{on_time_review}} for numeric claims. "
                "Do not number headings or lists."
            ),
            input=json.dumps(
                {
                    "context": payload,
                    "allowed_numeric_placeholders": facts,
                }
            ),
        )

        if not response.output_text.strip():
            raise ValueError("Empty model response")

        (out / "ai_report_draft.md").write_text(
            "# AI-assisted draft - review before sharing\n\n"
            + validate_numeric_draft(response.output_text, facts),
            encoding="utf-8",
        )
