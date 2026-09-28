"""Compatibility exports for the shared strict JSON reader."""
from towr.adapters._json_common import (
    build_value, parse_seed, read_request,
)

__all__ = ["build_value", "parse_seed", "read_request"]
