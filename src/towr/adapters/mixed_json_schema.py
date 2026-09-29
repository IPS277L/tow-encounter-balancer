"""Mixed wire shapes with bundled references only, without remote retrieval."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=6)
def _validator(kind: str, family: str = "simulation") -> Draft202012Validator:
    if kind not in ("request", "result", "error"):
        raise ValueError("unknown mixed schema kind")
    if family not in ("simulation", "balance"):
        raise ValueError("unknown mixed schema family")
    groups = ("simulation",) if family == "simulation" else ("simulation", "balance")
    names = [f"mixed-{group}-{name}-v1.schema.json"
             for group in groups for name in ("request", "result", "error")]
    names.append("ranged-simulation-request-v1.schema.json")
    documents = {
        name: json.loads(files("towr.adapters.schemas").joinpath(name).read_text(encoding="utf-8"))
        for name in names
    }
    registry = Registry().with_resources(
        (doc["$id"], Resource.from_contents(doc)) for doc in documents.values()
    )
    for doc in documents.values():
        Draft202012Validator.check_schema(doc)
    return Draft202012Validator(documents[f"mixed-{family}-{kind}-v1.schema.json"], registry=registry)


def validate_mixed_document(document: object, kind: str) -> None:
    """Validate simulation shape; token spelling and domain admission are separate.

    Raises jsonschema.ValidationError. The cached schema/registry stay private.
    """
    _validator(kind).validate(document)


def validate_mixed_balance_document(document: object, kind: str) -> None:
    """Validate balance structure with local Mixed refs; typed models admit semantics."""
    _validator(kind, "balance").validate(document)
