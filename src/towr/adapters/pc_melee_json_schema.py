"""Current PC melee shapes and local reference registry; no network lookup."""
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=6)
def _validator(kind: str, family: str = "simulation") -> Draft202012Validator:
    if kind not in ("request", "result", "error"):
        raise ValueError("unknown PC melee schema kind")
    if family not in ("simulation", "balance"):
        raise ValueError("unknown PC melee schema family")
    names = [f"pc-melee-{group}-{shape}-v1.schema.json"
             for group in ("simulation", "balance") for shape in ("request", "result", "error")]
    names.append("pc-melee-common.schema.json")
    documents = {name: json.loads(files("towr.adapters.schemas").joinpath(name)
                 .read_text(encoding="utf-8")) for name in names}
    registry = Registry().with_resources(
        (document["$id"], Resource.from_contents(document)) for document in documents.values())
    for document in documents.values():
        Draft202012Validator.check_schema(document)
    return Draft202012Validator(documents[f"pc-melee-{family}-{kind}-v1.schema.json"], registry=registry)


def validate_pc_melee_simulation_document(document: object, kind: str = "request") -> None:
    _validator(kind, "simulation").validate(document)


def validate_pc_melee_balance_document(document: object, kind: str = "request") -> None:
    _validator(kind, "balance").validate(document)


validate_pc_melee_document = validate_pc_melee_simulation_document
