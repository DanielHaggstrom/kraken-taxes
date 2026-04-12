from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path

from .config import AppConfig
from .models import PriceCacheStats, RewardReportSummary, RewardValuation
from .timezones import resolve_timezone


def export_reward_report_html(
    rewards: list[RewardValuation],
    summary: RewardReportSummary,
    output_path: Path,
    config: AppConfig,
    cache_stats: PriceCacheStats,
    max_event_rows: int = 500,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_tz = resolve_timezone(config.output_timezone)
    generated_at = datetime.now(tz=output_tz)
    visible_rewards = rewards[:max(max_event_rows, 0)]
    truncated = len(visible_rewards) < len(rewards)
    audit_metrics = _build_audit_metrics(rewards)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(summary.tax_profile_display_name)} - Kraken Taxes</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f1ea;
      --panel: #fffdf8;
      --ink: #1d1c1a;
      --muted: #635d55;
      --accent: #0f766e;
      --accent-soft: #dff4ef;
      --line: #d8d0c6;
      --shadow: 0 14px 35px rgba(29, 28, 26, 0.08);
      --mono: "IBM Plex Mono", "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
      --sans: "Segoe UI", "Inter", system-ui, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.09), transparent 28%),
        linear-gradient(180deg, #f7f5ef 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 32px 20px 72px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(17, 24, 39, 0.96));
      color: white;
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }}
    .eyebrow {{
      font-family: var(--mono);
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      opacity: 0.84;
    }}
    h1 {{
      margin: 10px 0 6px;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 1.02;
    }}
    .hero p {{
      margin: 8px 0 0;
      color: rgba(255, 255, 255, 0.88);
      max-width: 72ch;
    }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      margin: 24px 0;
    }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}
    .card {{
      padding: 18px;
    }}
    .label {{
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }}
    .metric {{
      font-size: 1.9rem;
      font-weight: 700;
      line-height: 1;
    }}
    .submetric {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .panel {{
      padding: 22px;
      margin-top: 18px;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 1.25rem;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px 18px;
      margin-top: 14px;
    }}
    .meta div {{
      color: var(--muted);
    }}
    .meta strong {{
      color: var(--ink);
      display: block;
      margin-bottom: 2px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    td.code {{
      font-family: var(--mono);
      font-size: 0.88rem;
    }}
    .note {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .pill {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.85rem;
      font-weight: 700;
      margin-right: 8px;
      margin-bottom: 8px;
    }}
    a {{
      color: var(--accent);
    }}
    @media (max-width: 720px) {{
      .page {{ padding: 18px 14px 56px; }}
      .hero {{ padding: 22px; border-radius: 20px; }}
      .panel, .card {{ border-radius: 16px; }}
      th, td {{ padding: 9px 8px; }}
      .table-wrap {{ overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">Kraken Taxes HTML Report</div>
      <h1>Reward income and estimated tax summary</h1>
      <p>
        Generated for {escape(config.target_currency)} valuations using the
        <strong>{escape(summary.tax_profile_display_name)}</strong> tax profile.
      </p>
    </section>

    <section class="grid">
      <article class="card">
        <div class="label">Reward Events</div>
        <div class="metric">{summary.event_count}</div>
        <div class="submetric">Rows included in this report</div>
      </article>
      <article class="card">
        <div class="label">Gross Value</div>
        <div class="metric">{_fmt_money(summary.gross_value, summary.target_currency)}</div>
        <div class="submetric">Market value at receipt</div>
      </article>
      <article class="card">
        <div class="label">Taxable Value</div>
        <div class="metric">{_fmt_money(summary.taxable_value, summary.target_currency)}</div>
        <div class="submetric">Basis: {escape(summary.taxable_basis)}</div>
      </article>
      <article class="card">
        <div class="label">Estimated Incremental Tax</div>
        <div class="metric">{_fmt_money(summary.estimated_tax, summary.target_currency)}</div>
        <div class="submetric">Effective rate: {_fmt_percent(summary.effective_tax_rate)}</div>
      </article>
    </section>

    <section class="panel">
      <h2>Assumptions and runtime context</h2>
      <div class="pill">{escape(summary.tax_profile_display_name)}</div>
      <div class="pill">{escape(summary.tax_profile_kind)}</div>
      <div class="pill">{escape(config.target_currency)}</div>
      <div class="pill">Cache hits: {cache_stats.cache_hits}</div>
      <div class="pill">Cache misses: {cache_stats.cache_misses}</div>
      <div class="meta">
        <div><strong>Generated at</strong>{escape(generated_at.isoformat())}</div>
        <div><strong>Config file</strong>{escape(_display_path(config.config_path))}</div>
        <div><strong>Ledger source</strong>{escape(config.ledger_glob)} in configured input directory</div>
        <div><strong>Starting taxable base</strong>{_fmt_money(summary.starting_taxable_base, summary.target_currency)}</div>
        <div><strong>Price cache file</strong>{escape(_display_path(config.price_cache_path))}</div>
        <div><strong>Cache entries loaded</strong>{cache_stats.entries_loaded}</div>
      </div>
      <p class="note">{escape(summary.tax_profile_notes)}</p>
      <p class="note">
        Display values are rounded for readability. CSV exports keep higher precision for audit and reconciliation work.
      </p>
      {_render_reference_list(summary.tax_profile_references)}
    </section>

    <section class="panel">
      <h2>Totals by asset</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Events</th>
              <th>Gross Amount</th>
              <th>Net Amount</th>
              <th>Gross Value</th>
              <th>Taxable Value</th>
              <th>Estimated Tax</th>
            </tr>
          </thead>
          <tbody>
            {_render_asset_rows(summary)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Monthly progression</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Month</th>
              <th>Events</th>
              <th>Gross Value</th>
              <th>Net Value</th>
              <th>Taxable Value</th>
              <th>Estimated Incremental Tax</th>
            </tr>
          </thead>
          <tbody>
            {_render_monthly_rows(summary)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>Audit checks</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Metric</th>
              <th>Exact Sum From Rows</th>
              <th>Displayed Summary</th>
              <th>Rounding Delta</th>
            </tr>
          </thead>
          <tbody>
            {_render_audit_rows(audit_metrics, summary.target_currency)}
          </tbody>
        </table>
      </div>
      <p class="note">
        Micro-events below 0.01 {escape(summary.target_currency)}:
        gross={audit_metrics['micro_gross_count']},
        taxable={audit_metrics['micro_taxable_count']},
        tax={audit_metrics['micro_tax_count']}.
      </p>
    </section>

    <section class="panel">
      <h2>Reward events</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Local Time</th>
              <th>Asset</th>
              <th>Gross Amount</th>
              <th>Gross Value</th>
              <th>Taxable Value</th>
              <th>Estimated Incremental Tax</th>
              <th>Rate</th>
              <th>Route</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {_render_event_rows(visible_rewards, output_tz)}
          </tbody>
        </table>
      </div>
      {"<p class=\"note\">The event table is truncated to the first "
      + str(max_event_rows)
      + " rows for readability.</p>" if truncated else ""}
    </section>
  </main>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")


def _render_reference_list(references: tuple[str, ...]) -> str:
    if not references:
        return ""
    items = "".join(
        f'<li><a href="{escape(url)}">{escape(url)}</a></li>'
        for url in references
    )
    return f"<div class=\"note\"><strong>References</strong><ul>{items}</ul></div>"


def _render_asset_rows(summary: RewardReportSummary) -> str:
    return "".join(
        f"""
        <tr>
          <td class="code">{escape(item.asset)}</td>
          <td>{item.event_count}</td>
          <td class="code">{escape(str(item.gross_amount))}</td>
          <td class="code">{escape(str(item.net_amount))}</td>
          <td>{_fmt_money(item.gross_value, summary.target_currency)}</td>
          <td>{_fmt_money(item.taxable_value, summary.target_currency)}</td>
          <td>{_fmt_money(item.estimated_tax, summary.target_currency)}</td>
        </tr>
        """
        for item in summary.asset_summaries
    )


def _render_monthly_rows(summary: RewardReportSummary) -> str:
    return "".join(
        f"""
        <tr>
          <td class="code">{escape(item.month)}</td>
          <td>{item.event_count}</td>
          <td>{_fmt_money(item.gross_value, summary.target_currency)}</td>
          <td>{_fmt_money(item.net_value, summary.target_currency)}</td>
          <td>{_fmt_money(item.taxable_value, summary.target_currency)}</td>
          <td>{_fmt_money(item.estimated_tax, summary.target_currency)}</td>
        </tr>
        """
        for item in summary.monthly_summaries
    )


def _render_event_rows(rewards: list[RewardValuation], output_tz) -> str:
    return "".join(
        f"""
        <tr>
          <td class="code">{escape(reward.entry.time.astimezone(output_tz).isoformat())}</td>
          <td class="code">{escape(reward.entry.asset_normalized)}</td>
          <td class="code">{escape(str(reward.entry.amount))}</td>
          <td>{_fmt_money(reward.gross_value, reward.target_currency)}</td>
          <td>{_fmt_money(reward.taxable_value, reward.target_currency)}</td>
          <td>{_fmt_money(reward.estimated_tax, reward.target_currency)}</td>
          <td class="code">{escape(str(reward.quote.rate))}</td>
          <td>{escape(reward.quote.route)}</td>
          <td class="code">{escape(reward.entry.source_file.name)}:{reward.entry.source_line}</td>
        </tr>
        """
        for reward in rewards
    )


def _render_audit_rows(metrics: dict[str, Decimal | int], currency: str) -> str:
    rows = (
        ("Gross value", metrics["gross_exact"], metrics["gross_displayed"], metrics["gross_delta"]),
        (
            "Taxable value",
            metrics["taxable_exact"],
            metrics["taxable_displayed"],
            metrics["taxable_delta"],
        ),
        (
            "Estimated incremental tax",
            metrics["tax_exact"],
            metrics["tax_displayed"],
            metrics["tax_delta"],
        ),
    )
    return "".join(
        f"""
        <tr>
          <td>{escape(label)}</td>
          <td class="code">{escape(str(exact_value))}</td>
          <td>{_fmt_money(displayed_value, currency)}</td>
          <td>{_fmt_money(delta_value, currency)}</td>
        </tr>
        """
        for label, exact_value, displayed_value, delta_value in rows
    )


def _build_audit_metrics(rewards: list[RewardValuation]) -> dict[str, Decimal | int]:
    gross_exact = sum((reward.gross_value for reward in rewards), start=Decimal("0"))
    taxable_exact = sum((reward.taxable_value for reward in rewards), start=Decimal("0"))
    tax_exact = sum((reward.estimated_tax for reward in rewards), start=Decimal("0"))

    gross_displayed = quantize_for_display(gross_exact)
    taxable_displayed = quantize_for_display(taxable_exact)
    tax_displayed = quantize_for_display(tax_exact)

    return {
        "gross_exact": gross_exact,
        "gross_displayed": gross_displayed,
        "gross_delta": gross_displayed - gross_exact,
        "taxable_exact": taxable_exact,
        "taxable_displayed": taxable_displayed,
        "taxable_delta": taxable_displayed - taxable_exact,
        "tax_exact": tax_exact,
        "tax_displayed": tax_displayed,
        "tax_delta": tax_displayed - tax_exact,
        "micro_gross_count": sum(1 for reward in rewards if Decimal("0") < abs(reward.gross_value) < Decimal("0.01")),
        "micro_taxable_count": sum(
            1 for reward in rewards if Decimal("0") < abs(reward.taxable_value) < Decimal("0.01")
        ),
        "micro_tax_count": sum(1 for reward in rewards if Decimal("0") < abs(reward.estimated_tax) < Decimal("0.01")),
    }


def _fmt_money(value: Decimal, currency: str) -> str:
    magnitude = abs(value)
    if value == 0:
        return f"0.00 {currency}"
    if magnitude < Decimal("0.01"):
        return f"{value:,.6f} {currency}"
    return f"{value:,.2f} {currency}"


def _fmt_percent(value: Decimal) -> str:
    return f"{(value * Decimal('100')):,.2f}%"


def quantize_for_display(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return path.name
