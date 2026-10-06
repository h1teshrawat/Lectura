"""Report-ready charts (PNG) with matplotlib.

Style rules (same data-viz guidelines as the web dashboard):
- categorical colours in a fixed order, validated for colour-blind separation;
- the baseline is a neutral grey, so it reads as "reference", not as a competitor;
- one axis per chart (different units -> different charts);
- thin marks, recessive grid, value labels in text colours.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # render to files, no window
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # validated categorical slots 1-4 (light)
BASELINE = "#a8a69f"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Segoe UI", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlecolor": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": MUTED,
    "figure.dpi": 100,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def _style(ax: plt.Axes, ylabel: str) -> None:
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    ax.set_ylabel(ylabel)


def _label(ax: plt.Axes, bars, fmt: str) -> None:
    for bar in bars:
        height = bar.get_height()
        if height == height:  # skip NaN
            ax.annotate(fmt.format(height), (bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=8, color=INK_2)


def grouped_bars(
    path: Path,
    title: str,
    groups: list[str],
    series: list[tuple[str, list[float], bool]],
    ylabel: str,
    fmt: str = "{:.2f}",
    ymax: float | None = None,
) -> None:
    """Bars grouped by `groups`; each series is (name, values, is_baseline)."""
    fig, ax = plt.subplots(figsize=(7.5, 4))
    width = 0.8 / len(series)
    colour_index = 0
    for i, (name, values, is_baseline) in enumerate(series):
        colour = BASELINE if is_baseline else SERIES[colour_index % len(SERIES)]
        colour_index += 0 if is_baseline else 1
        positions = [g + (i - (len(series) - 1) / 2) * width for g in range(len(groups))]
        # A white edge gives the 2px gap between neighbouring bars.
        bars = ax.bar(positions, values, width, label=name, color=colour, edgecolor="white", linewidth=1.5)
        _label(ax, bars, fmt)
    ax.set_xticks(range(len(groups)), groups)
    _style(ax, ylabel)
    if ymax is not None:
        ax.set_ylim(0, ymax)
    ax.set_title(title)
    ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0), labelcolor=INK_2)
    fig.savefig(path)
    plt.close(fig)


def simple_bars(path: Path, title: str, labels: list[str], values: list[float], ylabel: str,
                fmt: str = "{:.1f}", ymax: float | None = None) -> None:
    """One bar per label, a single colour (no legend needed for a single series)."""
    fig, ax = plt.subplots(figsize=(7, 3.8))
    bars = ax.bar(labels, values, width=0.55, color=SERIES[0], edgecolor="white", linewidth=1.5)
    _label(ax, bars, fmt)
    _style(ax, ylabel)
    if ymax is not None:
        ax.set_ylim(0, ymax)
    ax.set_title(title)
    fig.savefig(path)
    plt.close(fig)
