"""
Generates training-curve plots for the Brief 2 report from
results/logs/{multiexit,baseline}/history.csv.
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
PLOTS = RESULTS / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)


def load_history(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {k: [float(r[k]) for r in rows] for k in rows[0].keys()}


def main():
    me = load_history(RESULTS / "logs" / "multiexit" / "history.csv")
    bl = load_history(RESULTS / "logs" / "baseline" / "history.csv")

    epochs = me["epoch"]

    # Plot 1: per-exit train + val accuracy over training
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = {"exit1": "tab:blue", "exit2": "tab:orange", "exit3": "tab:green"}
    for exit_name in ("exit1", "exit2", "exit3"):
        ax.plot(epochs, me[f"{exit_name}_acc"], color=colors[exit_name], linestyle="--",
                 alpha=0.5, label=f"{exit_name} train")
        ax.plot(epochs, me[f"val_{exit_name}_acc"], color=colors[exit_name], linestyle="-",
                 linewidth=2, label=f"{exit_name} val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("accuracy")
    ax.set_title("Multi-exit model: per-exit accuracy over training\n"
                  "(GTSRB, val = track-aware monitoring slice of train)")
    ax.legend(loc="lower right", ncol=2, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTS / "multiexit_accuracy_curves.png", dpi=150)
    plt.close(fig)

    # Plot 2: per-exit loss over training
    fig, ax = plt.subplots(figsize=(9, 6))
    for exit_name in ("exit1", "exit2", "exit3"):
        ax.plot(epochs, me[f"{exit_name}_loss"], color=colors[exit_name], linestyle="--",
                 alpha=0.5, label=f"{exit_name} train")
        ax.plot(epochs, me[f"val_{exit_name}_loss"], color=colors[exit_name], linestyle="-",
                 linewidth=2, label=f"{exit_name} val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("sparse categorical cross-entropy")
    ax.set_title("Multi-exit model: per-exit loss over training")
    ax.legend(loc="upper right", ncol=2, fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTS / "multiexit_loss_curves.png", dpi=150)
    plt.close(fig)

    # Plot 3: multi-exit exit3 vs baseline (same backbone, single output)
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(epochs, me["val_exit3_acc"], color="tab:green", linewidth=2,
             label="multi-exit final exit (val)")
    ax.plot(bl["epoch"], bl["val_acc"], color="tab:red", linewidth=2,
             label="no-exit baseline (val)")
    ax.set_xlabel("epoch")
    ax.set_ylabel("accuracy")
    ax.set_title("Final classifier: multi-exit joint training vs no-exit baseline\n"
                  "(same backbone; does deep supervision cost final accuracy?)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOTS / "multiexit_vs_baseline.png", dpi=150)
    plt.close(fig)

    print(f"wrote plots to {PLOTS}")


if __name__ == "__main__":
    main()
