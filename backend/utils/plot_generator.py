import os
import json
import re
from typing import List, Dict, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


# MARS dark theme
MARS_STYLE = {
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


def _apply_style():
    plt.style.use("dark_background")
    plt.rcParams.update(MARS_STYLE)
    sns.set_palette("husl")


def generate_automatic_plots(df: pd.DataFrame, session_id: str) -> List[Dict]:
    """Generate standard plots for any dataset. Returns list of {filename, title, path}."""
    _apply_style()
    plots_dir = os.path.join("reports", session_id, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    results = []

    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    # 1. Correlation heatmap
    if len(numeric_cols) >= 2:
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            corr = df[numeric_cols].corr()
            sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=ax,
                        linewidths=0.5, linecolor="#30363D", cbar_kws={"shrink": 0.8})
            ax.set_title("Correlation Heatmap", fontsize=14, pad=12)
            filename = "correlation_heatmap.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": filename, "title": "Correlation Heatmap", "path": path})
        except Exception:
            pass

    # 2. Distribution histograms
    if numeric_cols:
        try:
            n = len(numeric_cols)
            cols_grid = min(n, 3)
            rows_grid = (n + cols_grid - 1) // cols_grid
            fig, axes = plt.subplots(rows_grid, cols_grid, figsize=(4 * cols_grid, 3 * rows_grid))
            if n == 1:
                axes = [axes]
            else:
                axes = axes.flatten() if hasattr(axes, "flatten") else [axes]
            for i, col in enumerate(numeric_cols):
                if i < len(axes):
                    sns.histplot(df[col].dropna(), ax=axes[i], kde=True, color="#58A6FF")
                    axes[i].set_title(col, fontsize=10)
            for j in range(len(numeric_cols), len(axes)):
                axes[j].set_visible(False)
            fig.suptitle("Distributions", fontsize=14, y=1.02)
            fig.tight_layout()
            filename = "distributions.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": filename, "title": "Variable Distributions", "path": path})
        except Exception:
            pass

    # 3. Missing data bar chart
    try:
        missing = df.isnull().sum()
        missing = missing[missing > 0]
        if len(missing) > 0:
            fig, ax = plt.subplots(figsize=(8, 4))
            missing.sort_values(ascending=True).plot.barh(ax=ax, color="#F85149")
            ax.set_title("Missing Data by Column", fontsize=14, pad=12)
            ax.set_xlabel("Missing Count")
            filename = "missing_data.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": filename, "title": "Missing Data Summary", "path": path})
    except Exception:
        pass

    return results


def generate_agent_requested_plots(
    df: pd.DataFrame, plot_requests: List[Dict], session_id: str
) -> List[Dict]:
    """Generate plots requested by the Data Agent. Returns list of {filename, title, path}."""
    _apply_style()
    plots_dir = os.path.join("reports", session_id, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    results = []

    for i, req in enumerate(plot_requests[:6]):
        plot_type = req.get("type", "scatter")
        title = req.get("title", f"Plot {i+1}")
        x = req.get("x")
        y = req.get("y")
        hue = req.get("hue")

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
                numeric = df.select_dtypes(include="number")
                sns.heatmap(numeric.corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
            else:
                plt.close(fig)
                continue

            ax.set_title(title, fontsize=12, pad=10)
            plt.xticks(rotation=45, ha="right")
            filename = f"agent_plot_{i+1}.png"
            path = os.path.join(plots_dir, filename)
            fig.savefig(path, bbox_inches="tight", facecolor="#161B22")
            plt.close(fig)
            results.append({"filename": filename, "title": title, "path": path})
        except Exception:
            plt.close("all")

    return results


def parse_plot_requests(agent_output: str) -> List[Dict]:
    """Extract plot request JSON from agent output."""
    match = re.search(r'```json\s*(\{.*?\})\s*```', agent_output, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("plots", [])
        except json.JSONDecodeError:
            pass
    return []


def generate_all_plots(
    data_file_paths: List[str], agent_output: str, session_id: str
) -> List[Dict]:
    """Generate all plots (automatic + agent-requested). Returns plot metadata list."""
    all_plots = []

    # Load first data file as DataFrame
    df = None
    for path in data_file_paths:
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            if df is not None:
                break
        except Exception:
            continue

    if df is None:
        return all_plots

    # Automatic plots
    all_plots.extend(generate_automatic_plots(df, session_id))

    # Agent-requested plots
    plot_requests = parse_plot_requests(agent_output)
    if plot_requests:
        all_plots.extend(generate_agent_requested_plots(df, plot_requests, session_id))

    return all_plots
