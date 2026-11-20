"""Explicit GM behaviour for retained dismounted mounts (ADR-0141 C11)."""
from enum import Enum


class DismountedMountPolicy(str,Enum):
    WAIT_AND_RECOVER='wait_and_recover'
