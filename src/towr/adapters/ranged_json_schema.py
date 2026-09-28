"""Only bundled schemas are resolvable; no remote retrieval or rule DSL."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=6)
def _validator(kind: str, family: str = "simulation") -> Draft202012Validator:
    if kind not in ("request", "result", "error"):
        raise ValueError("unknown ranged schema kind")
    if family not in ("simulation", "balance"):
        raise ValueError("unknown ranged schema family")
    groups = ("simulation",) if family == "simulation" else ("simulation", "balance")
    documents = {(group, name): json.loads(files("towr.adapters.schemas").joinpath(
        f"ranged-{group}-{name}-v1.schema.json").read_text(encoding="utf-8"))
        for group in groups for name in ("request", "result", "error")}
    registry = Registry().with_resources((doc["$id"], Resource.from_contents(doc)) for doc in documents.values())
    for doc in documents.values():
        Draft202012Validator.check_schema(doc)
    return Draft202012Validator(documents[family, kind], registry=registry)


def validate_ranged_document(document: object, kind: str) -> None:
    """Validate structure, not strict JSON token spelling or domain admission.

    Raises jsonschema.ValidationError. Schema files and their registry are private
    so callers cannot mutate subsequent validations through this public helper.
    """
    _validator(kind).validate(document)


def validate_ranged_balance_document(document: object, kind: str) -> None:
    """Validate balance structure with bundled M4 references, not semantic admission."""
    _validator(kind, "balance").validate(document)
