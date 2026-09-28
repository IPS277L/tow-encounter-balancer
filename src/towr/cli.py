"""Local command-line adapter for admitted ranged simulation and balance."""
import argparse
import os
from pathlib import Path
import sys
from typing import TextIO

from towr.adapters.ranged_json_errors import RangedSimulationInputError
from towr.adapters.ranged_simulation_json import (
    encode_ranged_simulation_error, encode_ranged_simulation_result,
    parse_ranged_simulation_request,
)
from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
from towr.application.ranged_simulation_service import execute_ranged_simulation
from towr.adapters.ranged_balance_json import (
    encode_ranged_balance_error, encode_ranged_balance_result, parse_ranged_balance_request,
)
from towr.adapters.ranged_balance_json_errors import RangedBalanceInputError
from towr.application.ranged_balance_errors import RangedBalanceGenerationError, RangedBalanceExecutionError
from towr.application.ranged_balance_service import execute_ranged_balance


def _diagnose(message: str) -> bool:
    # Keep diagnostics on one line and independent of the console code page.
    data = ("towr: " + " ".join(message.splitlines()) + "\n").encode("utf-8", errors="backslashreplace")
    try:
        sys.stderr.buffer.write(data)
        sys.stderr.buffer.flush()
    except OSError:
        _silence_failed_stream(sys.stderr)
        return False
    return True


def _silence_failed_stream(stream: TextIO) -> None:
    # Avoid a second failed flush during interpreter shutdown (exit status 120).
    try:
        with open(os.devnull, "wb") as sink:
            os.dup2(sink.fileno(), stream.fileno())
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="towr", description="Simulate or balance a TOWR ranged Minion encounter.")
    commands = parser.add_subparsers(dest="command", required=True)
    simulate = commands.add_parser("simulate", help="execute a JSON v1 request")
    simulate.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    balance = commands.add_parser("balance", help="generate and evaluate a JSON balance v1 request")
    balance.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    args = parser.parse_args(argv)

    if args.command == "balance":
        parse, execute, encode = parse_ranged_balance_request, execute_ranged_balance, encode_ranged_balance_result
        encode_error, input_error = encode_ranged_balance_error, RangedBalanceInputError
        execution_errors = (RangedBalanceGenerationError, RangedBalanceExecutionError)
    else:
        parse, execute, encode = parse_ranged_simulation_request, execute_ranged_simulation, encode_ranged_simulation_result
        encode_error, input_error = encode_ranged_simulation_error, RangedSimulationInputError
        execution_errors = (RangedSimulationExecutionError,)

    try:
        raw = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
    except OSError as error:
        _diagnose(f"input I/O error: {error}")
        return 4

    diagnostic = None
    try:
        command = parse(raw)
        result = execute(command)
    except input_error as error:
        output = encode_error(error)
        diagnostic = f"{error.code.value}: {error}"
        status = 2
    except execution_errors as error:
        output = encode_error(error)
        code = "generation_failed" if isinstance(error, RangedBalanceGenerationError) else "execution_failed"
        diagnostic = f"{code}: {error}"
        status = 3
    else:
        # Encoder bugs, including typed exceptions, are not execution failures.
        output = encode(command, result)
        status = 0

    # Finish execution and encoding before writing any response bytes.
    try:
        sys.stdout.buffer.write(output.encode("utf-8"))
        sys.stdout.buffer.flush()
    except OSError as error:
        _silence_failed_stream(sys.stdout)
        _diagnose(f"output I/O error: {error}")
        return 4
    if diagnostic is not None and not _diagnose(diagnostic):
        return 4
    return status
