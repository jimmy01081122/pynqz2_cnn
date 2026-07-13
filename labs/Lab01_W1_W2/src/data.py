"""Offline-first data loaders for CIFAR-10 and deterministic smoke data."""

from __future__ import annotations


CIFAR10_CLASSES = (
    "airplane",
    "automobile",
    "bird",
    "cat",
    "deer",
    "dog",
    "frog",
    "horse",
    "ship",
    "truck",
)


def make_loaders(
    mode: str,
    data_root: str,
    batch_size: int,
    workers: int,
    download: bool,
    seed: int,
    train_samples: int = 1024,
    test_samples: int = 256,
):
    """Return train/test loaders without ever downloading implicitly."""
    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch 尚未安裝。請先安裝 requirements.txt。"
        ) from exc

    generator = torch.Generator().manual_seed(seed)
    if mode == "synthetic":
        # Labels intentionally follow a simple deterministic statistic so a
        # short run can exercise learning, but this is never a benchmark.
        def synthetic_dataset(samples: int, offset: int):
            local = torch.Generator().manual_seed(seed + offset)
            images = torch.randn(samples, 3, 32, 32, generator=local)
            channel_scores = images.mean(dim=(2, 3))
            labels = (
                channel_scores.argmax(dim=1)
                + (images[:, 0, :16, :16].mean(dim=(1, 2)) > 0).long() * 3
            ) % 10
            return TensorDataset(images, labels)

        train_set = synthetic_dataset(train_samples, 0)
        test_set = synthetic_dataset(test_samples, 1)
    elif mode == "cifar10":
        try:
            from torchvision import datasets, transforms
        except ImportError as exc:
            raise RuntimeError(
                "torchvision 尚未安裝。請先安裝 requirements.txt。"
            ) from exc
        train_transform = transforms.Compose(
            [
                transforms.RandomCrop(32, padding=4),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor(),
                transforms.Normalize(
                    (0.4914, 0.4822, 0.4465),
                    (0.2470, 0.2435, 0.2616),
                ),
            ]
        )
        test_transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    (0.4914, 0.4822, 0.4465),
                    (0.2470, 0.2435, 0.2616),
                ),
            ]
        )
        try:
            train_set = datasets.CIFAR10(
                data_root, train=True, transform=train_transform, download=download
            )
            test_set = datasets.CIFAR10(
                data_root, train=False, transform=test_transform, download=download
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "找不到本機 CIFAR-10。請準備 data/cifar-10-batches-py，"
                "改用 --data-mode synthetic，或在允許連網時明確加 --download。"
            ) from exc
    else:
        raise ValueError(f"未知資料模式：{mode}")

    train_loader = DataLoader(
        train_set,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        pin_memory=False,
        generator=generator,
    )
    test_loader = DataLoader(
        test_set,
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=False,
    )
    return train_loader, test_loader

