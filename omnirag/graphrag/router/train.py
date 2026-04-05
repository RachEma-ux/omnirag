"""Training script — fine-tune distilbert for query routing + export ONNX.

Usage:
  python -m omnirag.graphrag.router.train --data data/router_training.jsonl --output models/router_classifier
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def train(data_path: str, output_dir: str, epochs: int = 3, batch_size: int = 32, lr: float = 2e-5):
    """Train distilbert-base-uncased for 4-class query classification."""
    try:
        import torch
        from transformers import (
            AutoTokenizer, AutoModelForSequenceClassification,
            TrainingArguments, Trainer,
        )
        from datasets import Dataset
    except ImportError:
        print("Install: pip install transformers datasets torch")
        return

    # Load data
    data = []
    with open(data_path) as f:
        for line in f:
            item = json.loads(line.strip())
            data.append(item)

    print(f"Loaded {len(data)} samples")

    # Split 80/20
    split = int(len(data) * 0.8)
    train_data = data[:split]
    val_data = data[split:]

    train_ds = Dataset.from_list(train_data)
    val_ds = Dataset.from_list(val_data)

    # Tokenize
    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=128, padding="max_length")

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)

    train_ds.set_format("torch", columns=["input_ids", "attention_mask", "label"])
    val_ds.set_format("torch", columns=["input_ids", "attention_mask", "label"])

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=4,
        id2label={0: "BASIC", 1: "LOCAL", 2: "GLOBAL", 3: "DRIFT"},
        label2id={"BASIC": 0, "LOCAL": 1, "GLOBAL": 2, "DRIFT": 3},
    )

    # Training
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=lr,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_steps=50,
        report_to="none",
    )

    def compute_metrics(eval_pred):
        import numpy as np
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        accuracy = (preds == labels).mean()
        return {"accuracy": accuracy}

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print("Training...")
    trainer.train()

    # Evaluate
    results = trainer.evaluate()
    print(f"Validation accuracy: {results['eval_accuracy']:.4f}")

    # Save model + tokenizer
    model.save_pretrained(str(output))
    tokenizer.save_pretrained(str(output))
    print(f"Model saved to {output}")

    # Export ONNX
    try:
        export_onnx(model, tokenizer, str(output / "model.onnx"))
        print(f"ONNX exported to {output / 'model.onnx'}")
    except Exception as e:
        print(f"ONNX export failed: {e}")


def export_onnx(model, tokenizer, output_path: str):
    """Export PyTorch model to ONNX format."""
    import torch
    dummy = tokenizer("test query", return_tensors="pt", truncation=True, max_length=128, padding="max_length")
    torch.onnx.export(
        model,
        (dummy["input_ids"], dummy["attention_mask"]),
        output_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch"},
            "attention_mask": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=14,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train query router classifier")
    parser.add_argument("--data", required=True, help="Path to JSONL training data")
    parser.add_argument("--output", default="models/router_classifier", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()
    train(args.data, args.output, args.epochs, args.batch_size, args.lr)
