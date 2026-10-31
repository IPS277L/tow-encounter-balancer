"""Magic wire shapes with bundled references only (ADR-0043/0047)."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def _require_schema_version(family: str, schema_version: str) -> None:
    if (type(schema_version) is not str or schema_version not in ("1", "2")
            or (family == "balance" and schema_version != "1")):
        raise ValueError(f"unsupported magic {family} schema version")


@lru_cache(maxsize=9)
def _validator(kind: str, family: str = "simulation", schema_version: str = "1") -> Draft202012Validator:
    if kind not in ("request", "result", "error"):
        raise ValueError(f"unknown magic {family} schema kind")
    if family not in ("simulation", "balance"):
        raise ValueError("unknown magic schema family")
    _require_schema_version(family, schema_version)
    groups = ("simulation",) if family == "simulation" else ("simulation", "balance")
    names = [f"magic-{group}-{name}-v1.schema.json"
             for group in groups for name in ("request", "result", "error")]
    if schema_version == "2":
        names.extend(f"magic-simulation-{name}-v2.schema.json"
                     for name in ("request", "result", "error"))
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
    return Draft202012Validator(
        documents[f"magic-{family}-{kind}-v{schema_version}.schema.json"], registry=registry)


def validate_magic_simulation_document(document: object, kind: str = "request", *,
                                       schema_version: str = "1") -> None:
    """Validate structure; strict token spelling and typed admission are separate.

    Raises jsonschema.ValidationError. No remote retrieval or simulation occurs.
    """
    _require_schema_version("simulation", schema_version)
    _validator(kind, "simulation", schema_version).validate(document)


def validate_magic_balance_document(document: object, kind: str = "request", *,
                                    schema_version: str = "1") -> None:
    """Validate balance shape; typed models enforce source, stages and budgets."""
    _require_schema_version("balance", schema_version)
    _validator(kind, "balance", schema_version).validate(document)
