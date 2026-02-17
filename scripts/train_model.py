#!/usr/bin/env python3
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.integrity_scorer import train_and_score, IntegrityScorer
from config.settings import PROCESSED_DATA_DIR


def main():
    parser = argparse.ArgumentParser(description="Train Fair Play Shield models")
    parser.add_argument(
        "--data-path",
        type=str,
        default=str(PROCESSED_DATA_DIR / "european_leagues_with_odds_processed.csv"),
        help="Path to processed data CSV"
    )
    parser.add_argument(
        "--model-prefix",
        type=str,
        default="fps_leagues",
        help="Prefix for saved model files"
    )
    parser.add_argument(
        "--output-scores",
        type=str,
        default=str(PROCESSED_DATA_DIR / "integrity_scores.csv"),
        help="Path to save integrity scores"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("FAIR PLAY SHIELD — Model Training")
    print("=" * 60)
    print(f"Data path: {args.data_path}")
    print(f"Model prefix: {args.model_prefix}")
    print(f"Output scores: {args.output_scores}")
    print("=" * 60)

    scorer, results = train_and_score()

    if scorer is not None and results is not None:
        print("\n✅ Training completed successfully!")
        print(f"   Models saved with prefix: {args.model_prefix}")
        print(f"   Scores saved to: {args.output_scores}")
        return 0
    else:
        print("\n❌ Training failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
