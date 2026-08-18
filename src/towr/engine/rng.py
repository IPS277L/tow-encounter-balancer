from __future__ import annotations

import random


class SeededRandom:
    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def randint(self, start: int, end: int) -> int:
        return self._random.randint(start, end)

