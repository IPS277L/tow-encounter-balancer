"""Strict JSON reading; v1 by default, with an explicit magic-only v2 path."""
from collections.abc import Callable
from functools import partial
import json

from jsonschema import ValidationError
from towr.adapters.ranged_json_errors import RangedInputError, RangedInputErrorCode as Code
from towr.adapters.melee_json_errors import MeleeInputError
from towr.adapters.mixed_json_errors import MixedInputError
from towr.adapters.magic_json_errors import MagicInputError


InputErrorType = type[RangedInputError] | type[MeleeInputError] | type[MixedInputError] | type[MagicInputError]


def _object(pairs, error_type):
    result = {}
    for key, value in pairs:
        if key in result:
            raise error_type(Code.INVALID_JSON, f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_float(token, error_type):
    raise error_type(Code.INVALID_INPUT, "request numbers must use integer tokens")


def _reject_constant(token, error_type):
    raise error_type(Code.INVALID_JSON, f"non-finite JSON number: {token}")


def _pointer(parts) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def build_value(error_type: InputErrorType, path: str, constructor, *args, **kwargs):
    try:
        return constructor(*args, **kwargs)
    except (TypeError, ValueError) as error:
        raise error_type(Code.INVALID_INPUT, str(error), path=path) from error


def read_request(text: str | bytes, error_type: InputErrorType,
                 validate: Callable[..., None], *, magic_v2: bool = False) -> dict:
    """Read strict UTF-8 and validate envelope structure; constructors admit rules."""
    if magic_v2 and not issubclass(error_type, MagicInputError):
        raise TypeError("v2 reading is restricted to magic boundaries")
    if not isinstance(text, (str, bytes)):
        raise TypeError("request JSON must be str or UTF-8 bytes")
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        text.encode("utf-8")
        document = json.loads(text, object_pairs_hook=partial(_object, error_type=error_type),
                              parse_float=partial(_reject_float, error_type=error_type),
                              parse_constant=partial(_reject_constant, error_type=error_type))
        # Escaped lone surrogates parse in stdlib JSON but cannot be emitted as
        # UTF-8 by the encoder. Validate decoded strings, including object keys.
        pending = [document]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
    except error_type:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise error_type(Code.INVALID_JSON, str(error)) from error
    request_id = document.get("request_id") if isinstance(document, dict) else None
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = None
    version = document.get("schema_version") if isinstance(document, dict) else None
    supported = ("1", "2") if magic_v2 else ("1",)
    if isinstance(version, str) and version not in supported:
        raise error_type(Code.UNSUPPORTED_VERSION, "unsupported schema_version",
                                         path="/schema_version", request_id=request_id)
    try:
        if magic_v2:
            validate(document, "request", schema_version="2" if version == "2" else "1")
        else:
            validate(document, "request")
    except ValidationError as error:
        raise error_type(Code.INVALID_INPUT, error.message,
            path=_pointer(error.absolute_path), request_id=request_id,
            **({"schema_version": "2" if version == "2" else "1"} if magic_v2 else {})) from error
    return document


def parse_seed(value: str, error_type: InputErrorType, path: str) -> int:
    seed = int(value)
    if seed >= 2**64:
        raise error_type(Code.INVALID_INPUT, "master_seed must be less than 2**64", path=path)
    return seed
