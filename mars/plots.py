"""Dataset visualisations. Ported from backend/utils/plot_generator.py, but
writes into an explicit output directory (the run folder) instead of a hardcoded
reports/ path, so plots live alongside the rest of a run's artifacts.

Automatic plots (correlation heatmap, distributions, missing-data) plus any
plots the Data Agent requests via its JSON block. Uses the Agg backend, so it
is safe to call from a worker thread.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")  # non-interactive; thread-safe for our use
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

_MARS_STYLE = {
    "figure.facecolor": "#161B22",
    "axes.facecolor": "#0D1117",
    "text.color": "#E6EDF3",
    "axes.labelcolor": "#E6EDF3",
    "xtick.color": "#8B949E",
    "ytick.color": "#8B949E",
    "grid.color": "#30363D",
    "figure.dpi": 150,
    "axes.edgecolor": "#30363D",
    "legend.facecolor": "#161B22",
    "legend.edgecolor": "#30363D",
}


def _apply_style() -> None:
    plt.style.use("dark_background")
    plt.rcParams.update(_MARS_STYLE)
    sns.set_palette("husl")


def _automatic_plots(df: pd.DataFrame, plots_dir: str) -> List[Dict]:
    results: List[Dict] = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    # 1. Correlation heatmap
    if len(numeric_cols) >= 2:
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            sns.heatmap(
                df[numeric_cols].corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax,
                linewidths=0.5, linecolor="#30363D", cbar_kws={"shrink": 0.8},
            )
            ax.set_title("Correlation Heatmap", fontsize=14, pad=12)
            path = os.path.join(plots_dir, "correlation_heatmap.png")
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": "correlation_heatmap.png", "title": "Correlation Heatmap", "path": path})
        except Exception:
            plt.close("all")

    # 2. Distribution histograms
    if numeric_cols:
        try:
            n = len(numeric_cols)
            cols_grid = min(n, 3)
            rows_grid = (n + cols_grid - 1) // cols_grid
            fig, axes = plt.subplots(rows_grid, cols_grid, figsize=(4 * cols_grid, 3 * rows_grid))
            axes = [axes] if n == 1 else (axes.flatten() if hasattr(axes, "flatten") else [axes])
            for i, col in enumerate(numeric_cols):
                if i < len(axes):
                    sns.histplot(df[col].dropna(), ax=axes[i], kde=True, color="#58A6FF")
                    axes[i].set_title(col, fontsize=10)
            for j in range(len(numeric_cols), len(axes)):
                axes[j].set_visible(False)
            fig.suptitle("Distributions", fontsize=14, y=1.02)
            fig.tight_layout()
            path = os.path.join(plots_dir, "distributions.png")
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": "distributions.png", "title": "Variable Distributions", "path": path})
        except Exception:
            plt.close("all")

    # 3. Missing-data bar chart
    try:
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if len(missing) > 0:
            fig, ax = plt.subplots(figsize=(8, 4))
            missing.sort_values(ascending=True).plot.barh(ax=ax, color="#F85149")
            ax.set_title("Missing Data by Column", fontsize=14, pad=12)
            ax.set_xlabel("Missing Count")
            path = os.path.join(plots_dir, "missing_data.png")
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": "missing_data.png", "title": "Missing Data Summary", "path": path})
    except Exception:
        plt.close("all")

    return results


def _requested_plots(df: pd.DataFrame, plot_requests: List[Dict], plots_dir: str) -> List[Dict]:
    results: List[Dict] = []
    for i, req in enumerate(plot_requests[:6]):
        plot_type = req.get("type", "scatter")
        title = req.get("title", f"Plot {i + 1}")
        x, y, hue = req.get("x"), req.get("y"), req.get("hue")
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            if plot_type == "scatter" and x and y:
                sns.scatterplot(data=df, x=x, y=y, hue=hue, ax=ax, alpha=0.7)
            elif plot_type == "bar" and x and y:
                sns.barplot(data=df, x=x, y=y, hue=hue, ax=ax)
            elif plot_type == "box" and x and y:
                sns.boxplot(data=df, x=x, y=y, hue=hue, ax=ax)
            elif plot_type == "histogram" and x:
                sns.histplot(data=df, x=x, hue=hue, ax=ax, kde=True)
            elif plot_type == "line" and x and y:
                sns.lineplot(data=df, x=x, y=y, hue=hue, ax=ax)
            elif plot_type == "heatmap":
                sns.heatmap(df.select_dtypes(include="number").corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
            else:
                plt.close(fig)
                continue
            ax.set_title(title, fontsize=12, pad=10)
            plt.xticks(rotation=45, ha="right")
            filename = f"agent_plot_{i + 1}.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": filename, "title": title, "path": path})
        except Exception:
            plt.close("all")
    return results


def parse_plot_requests(agent_output: str) -> List[Dict]:
    """Extract the Data Agent's plot-request JSON block, if present."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", agent_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1)).get("plots", [])
        except json.JSONDecodeError:
            pass
    return []


def generate_plots(df: pd.DataFrame, data_agent_output: str, plots_dir: str) -> List[Dict]:
    """Generate automatic + agent-requested plots into plots_dir. Returns metadata."""
    if df is None:
        return []
    _apply_style()
    os.makedirs(plots_dir, exist_ok=True)
    plots = _automatic_plots(df, plots_dir)
    requests_ = parse_plot_requests(data_agent_output)
    if requests_:
        plots.extend(_requested_plots(df, requests_, plots_dir))
    return plots
