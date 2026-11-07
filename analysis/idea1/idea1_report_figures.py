"""Idea 1 report figures (Section 6). Needs idea1_v8.py and idea1_slide_numbers.py in the same folder.
Writes PNGs to ~/Desktop/idea1_figures (or FIG_DIR)."""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("OUT_CSV", os.devnull)
exec(open(os.path.join(HERE, "idea1_slide_numbers.py")).read().split("sec_g = sec.reindex")[0])
FIG = os.environ.get("FIG_DIR", os.path.expanduser("~/Desktop/idea1_figures")); os.makedirs(FIG, exist_ok=True)
BLUE, LBLUE, OLIVE, BROWN, GREY, DARK = "#52778b", "#8eaabb", "#66694e", "#8c523c", "#bcb3a5", "#3b2f26"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#999", "axes.labelcolor": DARK, "xtick.color": "#555", "ytick.color": "#555", "axes.titleweight": "bold",
                     "axes.titlesize": 13, "axes.titlelocation": "left", "figure.dpi": 200})
def save(f, name): f.tight_layout(); f.savefig(os.path.join(FIG, name), dpi=200, bbox_inches="tight"); plt.close(f); print("saved", name)
first_rep = rep.groupby("person_id").age.min()
M = 30.44

# Figure 1. Cumulative share back, by first sheet item, Sep 2022 to Aug 2024 starters
groups = [("Sheet set", c[c.sg == "Sheet set"], BLUE, "-"), ("Fitted sheet", c[c.sg == "Fitted sheet"], OLIVE, "-"),
          ("Duvet cover", c[c.sg == "Duvet cover"], BROWN, "-"), ("Pillowcases only", c[c.sg == "Pillowcases only"], LBLUE, "-"),
          ("Other newcomers", c[~c.sf], GREY, "--")]
months = np.arange(0, 25)
f, ax = plt.subplots(figsize=(8, 4.4))
for nm, g, col, ls in groups:
    fr = first_rep.reindex(g.index)
    y = [100 * (fr <= m * M).mean() for m in months]
    ax.plot(months, y, color=col, ls=ls, lw=2.4 if nm != "Other newcomers" else 2)
    dy = {"Fitted sheet": 7, "Sheet set": -6}.get(nm, 0)
    ax.annotate(f"{nm} {y[-1]:.0f}%", (24, y[-1]), xytext=(6, dy), textcoords="offset points", va="center", color=col, fontsize=10, fontweight="bold")
ax.axvspan(0.6, 12, color="#f3efe8", zorder=0); ax.text(6.3, 1.2, "No emails from day 18 to one year", ha="center", fontsize=9, color="#777")
ax.set_xlim(0, 24); ax.set_ylim(0, 32); ax.set_xticks([0, 2, 4, 6, 8, 10, 12, 18, 24])
ax.set_xlabel("Months after the first order"); ax.set_ylabel("Came back, cumulative %")
ax.set_title("Every kind of sheet starter comes back more than other newcomers")
save(f, "fig1_cumulative_back_by_first_item.png")

# Figure 2. When sheet starters' second orders come, by month, with Weavve's email schedule
s_ = first_rep.reindex(c[c.sf].index).dropna(); s_ = s_[s_ < 730]
bins = np.arange(0, 25) * M; cnt, _ = np.histogram(s_, bins=bins); share = 100 * cnt / len(s_)
f, ax = plt.subplots(figsize=(8, 4.2))
cols = [OLIVE if i == 0 else (BLUE if i < 12 else GREY) for i in range(24)]
ax.bar(np.arange(24) + 0.5, share, width=0.85, color=cols)
for mth in [2, 4, 8]:
    ax.axvline(mth, color=BROWN, ls=":", lw=1.6); ax.text(mth + 0.12, share.max() * 0.97, f"Proposed email, month {mth}", rotation=90, ha="left", va="top", fontsize=8.5, color=BROWN)
ax.text(12.5, share[0] * 0.98, "Olive bar is month 1, the 3 welcome\nemails end on day 18", ha="left", va="top", fontsize=9, color=OLIVE)
ax.text(18, share[12:].max() + 1.5, "Win-back after a year", ha="center", fontsize=9, color="#777")
ax.set_ylim(0, share.max() * 1.08); ax.set_xlim(0, 24); ax.set_xticks([0, 2, 4, 6, 8, 10, 12, 18, 24])
ax.set_xlabel("Months after the first order"); ax.set_ylabel("Share of second orders, %")
ax.set_title(f"69% of second orders come in the gap with no emails, median day {int(s_.median())}")
save(f, "fig2_second_order_timing.png")

# Figure 3. Cohort curves, list sheet starters by start year, first 12 months
f, ax = plt.subplots(figsize=(8, 4.2))
for nm, (a, b), col in [("2024 starters", ("2023-08-29", "2024-08-28"), GREY), ("2025 starters", ("2024-08-29", "2025-08-28"), BLUE),
                        ("2026 starters, Sep to Feb", ("2025-08-29", "2026-02-28"), BROWN)]:
    g = nw[(nw.order_date >= a) & (nw.order_date <= b) & nw.on_list & nw.sf]
    xs, ys = [], []
    for m in range(0, 13):
        el = g[g.follow >= m * M]
        if len(el) < 0.9 * len(g) and m > 0: break
        xs.append(m); ys.append(100 * (first_rep.reindex(el.index) <= m * M).mean())
    ax.plot(xs, ys, color=col, lw=2.4, marker="o", ms=3.5)
    ax.annotate(f"{nm} {ys[-1]:.1f}%", (xs[-1], ys[-1]), xytext=(6, 0), textcoords="offset points", va="center", color=col, fontsize=9.5, fontweight="bold")
ax.axvline(6, color="#999", ls=":", lw=1); ax.text(6.1, 1, "6 months", fontsize=9, color="#777")
ax.set_xlim(0, 14.5); ax.set_xticks(range(0, 13, 2)); ax.set_ylim(0, 26)
ax.set_xlabel("Months after the first order"); ax.set_ylabel("Came back, cumulative %")
ax.set_title("Each year's sheet starters on the email list, share back over time")
save(f, "fig3_cohort_curves_by_year.png")

# Figure 4. What the second order holds, by first order
rows = []
for kk, lab in [("Sheet set only", "Sheet set only"), ("Sheet separates only", "Sheet separates only"), ("Whole bed", "Whole bed")]:
    d = sr[sr.person_id.map(c.entry) == kk]
    rows.append((lab, 100 * d.cats.apply(lambda z: "1. Bedsheets" in z).mean(), 100 * d.cats.apply(lambda z: "2. Bedding" in z).mean(), len(d)))
f, ax = plt.subplots(figsize=(8, 3.6)); y = np.arange(len(rows))
ax.barh(y + 0.2, [r[1] for r in rows], height=0.38, color=BLUE, label="Includes sheets")
ax.barh(y - 0.2, [r[2] for r in rows], height=0.38, color=BROWN, label="Includes bedding")
for i, r in enumerate(rows):
    ax.text(r[1] + 1, i + 0.2, f"{r[1]:.0f}%", va="center", fontsize=10, color=BLUE, fontweight="bold")
    ax.text(r[2] + 1, i - 0.2, f"{r[2]:.0f}%", va="center", fontsize=10, color=BROWN, fontweight="bold")
ax.set_yticks(y); ax.set_yticklabels([f"{r[0]}\n{r[3]} returners" for r in rows]); ax.invert_yaxis(); ax.set_xlim(0, 100)
ax.set_xlabel("Share of second orders, %"); ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
ax.set_title("Whatever they bought first, the second order is mostly sheets")
save(f, "fig4_second_order_contents.png")

# Figure 5. First-order value and whole-bed share
f, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4), gridspec_kw={"width_ratios": [1, 1.25]})
w2 = nw[nw.w == "W2"]
vals = [("Whole bed", w2[w2.wb].net.mean(), OLIVE), ("Sheets only", w2[w2.entry.isin(["Sheet set only", "Sheet separates only"])].net.mean(), BLUE),
        ("Any other", w2[~w2.wb].net.mean(), GREY)]
a1.bar([v[0] for v in vals], [v[1] for v in vals], color=[v[2] for v in vals], width=0.6)
for i, v in enumerate(vals): a1.text(i, v[1] + 10, f"${int(v[1] + 0.51)}", ha="center", fontweight="bold", color=DARK)
a1.set_ylabel("Average first order, $"); a1.set_title("First order, 2025 newcomers", fontsize=12); a1.set_ylim(0, 640)
yrs = ["W1", "W2", "W3"]; lab = ["2024", "2025", "2026"]
for flag, nm, col in [(True, "With a welcome code", BROWN), (False, "Without a welcome code", GREY)]:
    ys = [100 * nw[(nw.w == w_) & (nw.welcome == flag)].wb.mean() for w_ in yrs]
    a2.plot(lab, ys, marker="o", lw=2.4, color=col)
    off = 0.5 if not flag else -1.1
    for xx, yy in zip(lab, ys): a2.text(xx, yy + off, f"{yy:.1f}%", ha="center", fontsize=9.5, color=col, fontweight="bold")
    a2.annotate(nm, (2, ys[-1]), xytext=(10, 0), textcoords="offset points", va="center", color=col, fontsize=9.5)
a2.set_ylim(0, 17); a2.set_xlim(-0.3, 3.3); a2.set_ylabel("Whole-bed first orders, %"); a2.set_title("Whole-bed share of first orders", fontsize=12)
f.suptitle("The whole bed is worth more, but welcome-code newcomers choose it less", x=0.01, ha="left", fontweight="bold", fontsize=13, color=DARK)
save(f, "fig5_whole_bed_value_and_share.png")
