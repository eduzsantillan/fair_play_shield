#!/usr/bin/env python3
import sys
import argparse
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.integrity_scorer import IntegrityScorer
from config.settings import PROCESSED_DATA_DIR


def main():
    parser = argparse.ArgumentParser(description="Score matches using trained models")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input CSV with match data"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save scored results (default: input_scored.csv)"
    )
    parser.add_argument(
        "--model-prefix",
        type=str,
        default="fps_leagues",
        help="Prefix of trained model files to load"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=60,
        help="Minimum integrity score to flag as suspicious"
    )
    args = parser.parse_args()

    if args.output is None:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}_scored.csv")

    print("=" * 60)
    print("FAIR PLAY SHIELD — Match Scoring")
    print("=" * 60)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Model: {args.model_prefix}")
    print(f"Threshold: {args.threshold}")
    print("=" * 60)

    df = pd.read_csv(args.input, parse_dates=["date"] if "date" in pd.read_csv(args.input, nrows=1).columns else None)
    print(f"\nLoaded {len(df)} matches")

    scorer = IntegrityScorer()
    scorer.load(args.model_prefix)

    results = scorer.score(df)

    results.to_csv(args.output, index=False)
    print(f"\n✅ Results saved to: {args.output}")

    print("\n--- Alert Distribution ---")
    alert_dist = results["alert_level"].value_counts()
    for level in ["normal", "monitor", "suspicious", "high_alert"]:
        count = alert_dist.get(level, 0)
        pct = count / len(results) * 100
        emoji = {"normal": "🟢", "monitor": "🟡", "suspicious": "🟠", "high_alert": "🔴"}.get(level, "")
        print(f"  {emoji} {level:15s}: {count:5d} ({pct:.1f}%)")

    suspicious = results[results["integrity_score"] >= args.threshold]
    if len(suspicious) > 0:
        print(f"\n--- {len(suspicious)} Matches Above Threshold ({args.threshold}) ---")
        display_cols = ["date", "home_team", "away_team", "integrity_score", "alert_level"]
        available = [c for c in display_cols if c in suspicious.columns]
        print(suspicious[available].sort_values("integrity_score", ascending=False).head(20).to_string(index=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
