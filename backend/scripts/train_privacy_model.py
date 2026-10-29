"""
Impervia Offline Model Retraining Script

Usage:
    python scripts/train_privacy_model.py [--dataset path/to/synthetic_dataset.jsonl]

SAFETY NOTE:
This script executes strictly offline on synthetic benchmark datasets.
It does NOT connect to production databases or process live student chats.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure backend root is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.training import PrivacyModelTrainer


def generate_sample_synthetic_data(target_path: Path) -> None:
    """Generate sample synthetic benchmarks if none provided."""
    samples = [
        {
            "text": "Can you explain Dijkstra's algorithm? My email is student123@example.com.",
            "is_synthetic": True,
            "pii_spans": [{"category": "email", "start": 51, "end": 74}],
            "has_sensitive": False,
        },
        {
            "text": "I am feeling really anxious about my calculus exam. What is integration by parts?",
            "is_synthetic": True,
            "pii_spans": [],
            "has_sensitive": True,
        },
        {
            "text": "Calculate the derivative of f(x) = x^2 + 5x.",
            "is_synthetic": True,
            "pii_spans": [],
            "has_sensitive": False,
        },
        {
            "text": "My phone is 555-019-2834 and my ID is PRN-998877.",
            "is_synthetic": True,
            "pii_spans": [
                {"category": "phone_number", "start": 12, "end": 24},
                {"category": "student_id", "start": 38, "end": 48},
            ],
            "has_sensitive": False,
        },
    ]

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(s) + "\n" for s in samples)
    print(f"Generated synthetic benchmark dataset with {len(samples)} samples at {target_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Impervia Offline Privacy Model Retraining")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/synthetic_benchmark.jsonl"),
        help="Path to synthetic labeled JSONL dataset",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="v1.1-offline",
        help="Model artifact version tag",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Dataset {args.dataset} not found. Generating initial synthetic data...")
        generate_sample_synthetic_data(args.dataset)

    trainer = PrivacyModelTrainer()
    records = trainer.load_training_dataset(args.dataset)
    print(f"Loaded {len(records)} verified synthetic records.")

    report = trainer.train_or_evaluate(records, version_tag=args.version)
    print("Training/Evaluation Report:")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
