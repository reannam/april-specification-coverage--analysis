import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from Backend.config import (
    LANGSMITH_LOGS_DIR as LOGS_DIR,
    USAGE_CHARTS_DIR as CHARTS_DIR,
)

MASTER_USAGE_FILE = LOGS_DIR / "all_usage_runs.json"


def load_usage_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not MASTER_USAGE_FILE.exists():
        return pd.DataFrame(), pd.DataFrame()

    with MASTER_USAGE_FILE.open("r", encoding="utf-8") as file:
        runs = json.load(file)

    run_rows = []
    agent_rows = []

    for index, run in enumerate(runs, start=1):
        summary = run.get("summary", {})

        agents = summary.get("agents", [])

        models_used = sorted(
            {agent.get("model_name") for agent in agents if agent.get("model_name")}
        )

        models_used_text = ", ".join(models_used) if models_used else "Unknown model"

        run_rows.append(
            {
                "run_id": index,
                "timestamp": run.get("timestamp"),
                "output_file": run.get("output_file"),
                "models_used": models_used_text,
                "prompt_tokens": int(summary.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(summary.get("completion_tokens", 0) or 0),
                "total_tokens": int(summary.get("total_tokens", 0) or 0),
                "total_cost": float(summary.get("total_cost", 0) or 0),
            }
        )

        for agent in summary.get("agents", []):
            agent_rows.append(
                {
                    "run_id": index,
                    "timestamp": run.get("timestamp"),
                    "output_file": run.get("output_file"),
                    "agent_name": agent.get("agent_name"),
                    "model_name": agent.get("model_name"),
                    "prompt_tokens": int(agent.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(agent.get("completion_tokens", 0) or 0),
                    "total_tokens": int(agent.get("total_tokens", 0) or 0),
                    "total_cost": float(agent.get("total_cost", 0) or 0),
                }
            )

    return pd.DataFrame(run_rows), pd.DataFrame(agent_rows)


def save_csvs(run_df: pd.DataFrame, agent_df: pd.DataFrame) -> None:
    run_df.to_csv(CHARTS_DIR / "usage_by_run.csv", index=False)
    agent_df.to_csv(CHARTS_DIR / "usage_by_agent.csv", index=False)


def plot_total_cost_by_run(run_df: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 6))
    plt.bar(run_df["run_id"], run_df["total_cost"])

    for _, row in run_df.iterrows():
        plt.text(
            row["run_id"],
            row["total_cost"],
            row["models_used"],
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=45,
        )

    plt.xlabel("Run")
    plt.ylabel("Estimated cost USD")
    plt.title("Estimated cost by run, grouped by GPT model used")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "estimated_cost_by_run.png")
    plt.close()


def plot_total_tokens_by_run(run_df: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 6))
    plt.plot(run_df["run_id"], run_df["total_tokens"], marker="o")

    for _, row in run_df.iterrows():
        plt.text(
            row["run_id"],
            row["total_tokens"],
            row["models_used"],
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=45,
        )

    plt.xlabel("Run")
    plt.ylabel("Total tokens")
    plt.title("Total tokens by run, grouped by GPT model used")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "total_tokens_by_run.png")
    plt.close()


def plot_cost_by_agent(agent_df: pd.DataFrame) -> None:
    agent_df = agent_df.copy()
    agent_df["agent_model"] = agent_df["agent_name"] + "\n" + agent_df["model_name"]

    grouped = agent_df.groupby("agent_model", as_index=False)["total_cost"].sum()

    plt.figure(figsize=(10, 6))
    plt.bar(grouped["agent_model"], grouped["total_cost"])
    plt.xlabel("Agent / Model")
    plt.ylabel("Estimated cost USD")
    plt.title("Total estimated cost by agent and model")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "estimated_cost_by_agent.png")
    plt.close()


def plot_tokens_by_agent(agent_df: pd.DataFrame) -> None:
    agent_df = agent_df.copy()
    agent_df["agent_model"] = agent_df["agent_name"] + "\n" + agent_df["model_name"]

    grouped = agent_df.groupby("agent_model", as_index=False)["total_tokens"].sum()

    plt.figure(figsize=(10, 6))
    plt.bar(grouped["agent_model"], grouped["total_tokens"])
    plt.xlabel("Agent / Model")
    plt.ylabel("Total tokens")
    plt.title("Total tokens by agent and model")
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "tokens_by_agent.png")
    plt.close()


def generate_usage_reports() -> dict[str, str]:
    run_df, agent_df = load_usage_data()

    if run_df.empty:
        return {}

    save_csvs(run_df, agent_df)

    reports = {
        "usage_by_run_csv": "usage_by_run.csv",
        "usage_by_agent_csv": "usage_by_agent.csv",
    }

    plot_total_cost_by_run(run_df)
    reports["estimated_cost_by_run"] = "estimated_cost_by_run.png"

    plot_total_tokens_by_run(run_df)
    reports["total_tokens_by_run"] = "total_tokens_by_run.png"

    if not agent_df.empty:
        plot_cost_by_agent(agent_df)
        reports["estimated_cost_by_agent"] = "estimated_cost_by_agent.png"

        plot_tokens_by_agent(agent_df)
        reports["tokens_by_agent"] = "tokens_by_agent.png"

    return reports


def main() -> None:
    generated = generate_usage_reports()
    print(f"Generated usage reports: {generated}")
    print(f"Saved usage CSVs and charts to: {CHARTS_DIR}")


if __name__ == "__main__":
    main()
