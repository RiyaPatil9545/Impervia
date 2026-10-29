# Impervia: Privacy Model Lifecycle & Retraining Guide

## 1. Core Principles & Privacy Safeguards

Impervia operates under strict student data-protection mandates:

1. **Zero Production Data Training**: Production conversations, student chat messages, and private user questions are **NEVER** automatically used as training data. Retraining on live student submissions is strictly prohibited by design.
2. **Decoupled Offline Retraining**: Real-time privacy inference in FastAPI services is completely decoupled from model training. Retraining scripts run in standalone offline environments and never interact with live student sessions.
3. **Curated & Synthetic Datasets Only**: Training corpora must be certified as either synthetic (e.g. programmatically generated academic scenarios) or explicitly de-identified and ethically approved research benchmarks. Every sample in the dataset must contain an `is_synthetic` or `is_anonymized` certification flag.
4. **Explainability & Model Replacability**: Detection components adhere to standardized interfaces (`BasePIIDetector`, `BaseSensitiveContentDetector`, `AcademicRelevanceDetector`) allowing drop-in upgrades from rule-based baselines to fine-tuned local Small Language Models (SLMs) or named entity recognizers (NER) without changing the database schema or downstream pipeline.

---

## 2. Model Lifecycle Stages

```
   +------------------------------+
   | 1. Synthetic Data Generation |
   |  & Benchmark Curation        |
   +--------------+---------------+
                  |
                  v
   +------------------------------+
   | 2. Offline Training &        |
   |    Hyperparameter Tuning     |
   +--------------+---------------+
                  |
                  v
   +------------------------------+
   | 3. Safety & Accuracy Eval    |
   |  (False Positives / Redaction|
   +--------------+---------------+
                  |
                  v
   +------------------------------+
   | 4. Controlled Deployment     |
   |    (Versioned in Config)     |
   +------------------------------+
```

---

## 3. Running Offline Retraining

To train or evaluate privacy detection models against the synthetic benchmark:

```powershell
# From the backend directory
python scripts/train_privacy_model.py --dataset data/synthetic_benchmark.jsonl --version v1.1-offline
```

The script performs the following validation steps:
- Validates the presence of `is_synthetic: true` on each training record.
- Computes PII category distributions and false positive rates on safe academic prompts.
- Exports a training audit report to `models_cache/training_report_<version>.json`.
