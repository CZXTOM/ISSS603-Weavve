"""Figures 5 to 7 of the final report, drawn from the check results and the campaign snapshot.

Each function returns the matplotlib figure and saves a PNG when given a folder. Colours follow the report:
blue for the main series, orange for the second, grey for reference lines.
"""

from datetime import date, timedelta

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, DayLocator

BLUE, ORANGE, LIGHT_BLUE, DARK_BLUE = "#2a78d6", "#eb6834", "#86b6ef", "#1c5cab"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
STYLE = {
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": "#c3c2b7",
    "axes.labelcolor": INK2,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
}


def _save(fig, out, name):
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / name)
    return fig


def figure5(lens5, out=None):
    """Website net sales by year, split into that year's new buyers and earlier buyers, 2021 to 2025."""
    years = [str(y) for y in range(2021, 2026)]
    new = [lens5[y]["sales_from_new_buyers"] / 1000 for y in years]
    old = [lens5[y]["sales_from_earlier_buyers"] / 1000 for y in years]
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(6.9, 2.5), dpi=220)
        x = range(len(years))
        ax.bar(
            x,
            old,
            width=0.5,
            color=ORANGE,
            edgecolor="white",
            linewidth=1.5,
            label="Sales from earlier buyers",
            zorder=3,
        )
        ax.bar(
            x,
            new,
            width=0.5,
            bottom=old,
            color=BLUE,
            edgecolor="white",
            linewidth=1.5,
            label="Sales from that year's new buyers",
            zorder=3,
        )
        for i in x:
            ax.text(
                i,
                old[i] + new[i] + 18,
                f"${old[i] + new[i]:,.0f}k",
                ha="center",
                va="bottom",
                color=INK,
                fontsize=8.5,
                fontweight="bold",
            )
            ax.text(
                i + 0.29,
                old[i] + new[i] / 2,
                f"${new[i]:,.0f}k",
                ha="left",
                va="center",
                color=INK2,
                fontsize=7.5,
            )
            ax.text(
                i + 0.29, old[i] / 2, f"${old[i]:,.0f}k", ha="left", va="center", color=INK2, fontsize=7.5
            )
        ax.set_xticks(list(x), years)
        ax.set_ylabel("Website net sales, SGD thousands")
        ax.set_ylim(0, 1120)
        ax.set_xlim(-0.5, len(years) - 0.2)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(axis="x", length=0)
        ax.legend(
            loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, ncol=2, fontsize=8, handlelength=1.2
        )
        fig.tight_layout()
        return _save(fig, out, "fig5_website_sales_new_vs_earlier.png")


def figure6(quarters, out=None):
    """New sign-ups' 90-day website buying by quarter of sign-up, with the Alia pop-up's start marked."""
    keys = sorted(quarters)
    rate = [quarters[q]["pct"] for q in keys]
    x = list(range(len(keys)))
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(6.9, 2.4), dpi=220)
        ax.plot(
            x,
            rate,
            color=BLUE,
            linewidth=2,
            marker="o",
            markersize=5,
            markeredgecolor="white",
            markeredgewidth=1,
            zorder=3,
        )
        alia = 2 + (date(2024, 8, 27) - date(2024, 8, 15)).days / 92  # each quarter's point sits mid-quarter
        ax.axvline(alia, color=MUTED, linewidth=0.9, linestyle=":", zorder=1)
        ax.text(
            alia + 0.08, 35, "Alia pop-up starts, 27 Aug 2024", ha="left", va="top", color=INK2, fontsize=7.5
        )
        for i, dx, ha in ((0, 0, "center"), (2, -0.06, "right"), (len(x) - 1, 0, "center")):
            ax.text(
                x[i] + dx,
                rate[i] + 1.8,
                f"{rate[i]:.1f}%",
                ha=ha,
                va="bottom",
                color=INK,
                fontsize=8,
                fontweight="bold",
            )
        ax.set_xticks(x, [q.replace(" ", "\n") for q in keys])
        ax.set_ylabel("Bought on the website\nwithin 90 days, %")
        ax.set_ylim(0, 37)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(axis="x", length=0)
        fig.tight_layout()
        return _save(fig, out, "fig6_signups_by_quarter.png")


def figure7(ads, past_ctr, out=None):
    """Paid-search views and click rate by day, 13 to 30 October 2026, marking the three rounds of changes.

    past_ctr is Weavve's past click rate on the same keywords, in per cent, from the plan snapshot.
    """
    days = [date.fromisoformat(r["date"]) for r in ads["daily"]]
    views = [r["impressions"] for r in ads["daily"]]
    ctr = [100 * r["clicks"] / r["impressions"] for r in ads["daily"]]
    periods = [
        ("2026-10-13", "2026-10-18"),
        ("2026-10-19", "2026-10-21"),
        ("2026-10-22", "2026-10-23"),
        ("2026-10-24", "2026-10-30"),
    ]
    rounds = [
        (date(2026, 10, 19), "Round 1"),
        (date(2026, 10, 22), "Round 2"),
        (date(2026, 10, 24), "Round 3"),
    ]
    with plt.rc_context(STYLE):
        fig, (a1, a2) = plt.subplots(
            2,
            1,
            figsize=(6.9, 3.6),
            dpi=220,
            sharex=True,
            gridspec_kw={"height_ratios": [1, 1.1], "hspace": 0.18},
        )
        a1.bar(days, views, width=0.6, color=BLUE, zorder=3)
        a1.set_ylabel("Views per day")
        a1.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        a1.set_ylim(0, 450)
        a2.scatter(
            days,
            ctr,
            s=16,
            color=LIGHT_BLUE,
            edgecolor="white",
            linewidth=1,
            zorder=4,
            label="Click rate that day",
        )
        for n, (a, b) in enumerate(periods):
            rows = [r for r in ads["daily"] if a <= r["date"] <= b]
            avg = 100 * sum(r["clicks"] for r in rows) / sum(r["impressions"] for r in rows)
            x0, x1 = date.fromisoformat(a) - timedelta(hours=10), date.fromisoformat(b) + timedelta(hours=10)
            a2.plot([x0, x1], [avg, avg], color=DARK_BLUE, linewidth=2, solid_capstyle="round", zorder=5)
            below = n == 2
            a2.text(
                x0 + (x1 - x0) / 2,
                avg - 1.0 if below else avg + 1.0,
                f"{avg:.1f}%",
                ha="center",
                va="top" if below else "bottom",
                color=INK,
                fontsize=8,
            )
        a2.plot([], [], color=DARK_BLUE, linewidth=2, label="Average for the period")
        a2.axhline(past_ctr, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        a2.text(
            days[-1] + timedelta(hours=14),
            past_ctr,
            f"Weavve's past\nrate, {past_ctr}%",
            va="center",
            ha="left",
            color=INK2,
            fontsize=7.5,
        )
        a2.set_ylabel("Click rate, %")
        a2.set_ylim(0, 22)
        a2.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
        a2.legend(loc="upper right", frameon=False, ncol=2, fontsize=7.5, handlelength=1.4)
        for ax in (a1, a2):
            for dt, _ in rounds:
                ax.axvline(dt - timedelta(hours=12), color=MUTED, linewidth=0.9, linestyle=":", zorder=1)
        for dt, label in rounds:
            a1.text(dt - timedelta(hours=8), 430, label, ha="left", va="top", color=INK2, fontsize=7.5)
        a2.xaxis.set_major_locator(DayLocator(interval=2))
        a2.xaxis.set_major_formatter(DateFormatter("%d %b"))
        a2.set_xlim(days[0] - timedelta(days=1), days[-1] + timedelta(days=2.3))
        fig.subplots_adjust(left=0.09, right=0.97, top=0.97, bottom=0.09)
        return _save(fig, out, "fig7_paid_search_daily.png")
