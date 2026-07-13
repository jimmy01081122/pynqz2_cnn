"""A deliberately small CIFAR-10 CNN used throughout the course."""

from __future__ import annotations


def build_model(num_classes: int = 10):
    """Build the model lazily so --dry-run works before PyTorch is installed."""
    try:
        import torch.nn as nn
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch 尚未安裝。請先執行 python -m pip install -r requirements.txt"
        ) from exc

    class SmallCIFAR10CNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 16, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(16),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
                nn.Conv2d(16, 32, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
                nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.classifier = nn.Linear(64, num_classes)

        def forward(self, x):
            x = self.features(x)
            x = x.flatten(1)
            return self.classifier(x)

    return SmallCIFAR10CNN()


QUANTIZABLE_TYPES = ("Conv2d", "Linear")


def is_quantizable_module(module) -> bool:
    """Avoid importing torch at module import time."""
    return module.__class__.__name__ in QUANTIZABLE_TYPES

