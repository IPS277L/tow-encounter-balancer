"""Magic simulation/balance wire shapes with bundled references only (ADR-0043)."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=6)
def _validator(kind: str, family: str = "simulation") -> Draft202012Validator:
    if kind not in ("request", "result", "error"):
        raise ValueError(f"unknown magic {family} schema kind")
    if family not in ("simulation", "balance"):
        raise ValueError("unknown magic schema family")
    groups = ("simulation",) if family == "simulation" else ("simulation", "balance")
    names = [f"magic-{group}-{name}-v1.schema.json"
             for group in groups for name in ("request", "result", "error")]
    names.append("ranged-simulation-request-v1.schema.json")
    documents = {
        name: json.loads(files("towr.adapters.schemas").joinpath(name).read_text(encoding="utf-8"))
        for name in names
    }
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document)) for document in documents.values()
    )
    for document in documents.values():
        Draft202012Validator.check_schema(document)
    return Draft202012Validator(documents[f"magic-{family}-{kind}-v1.schema.json"], registry=registry)


def validate_magic_simulation_document(document: object, kind: str = "request") -> None:
    """Validate structure; strict token spelling and typed admission are separate.

    Raises jsonschema.ValidationError. No remote retrieval or simulation occurs.
    """
    _validator(kind).validate(document)


def validate_magic_balance_document(document: object, kind: str = "request") -> None:
    """Validate balance shape; typed models enforce source, stages and budgets."""
    _validator(kind, "balance").validate(document)
