"""Local command-line adapter for admitted ranged, Melee and mixed encounters."""
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
from towr.adapters.melee_json_errors import MeleeSimulationInputError, MeleeBalanceInputError
from towr.adapters.melee_simulation_json import (
    encode_melee_simulation_error, encode_melee_simulation_result, parse_melee_simulation_request,
)
from towr.application.melee_simulation_errors import MeleeSimulationExecutionError
from towr.application.melee_simulation_service import execute_melee_simulation
from towr.adapters.melee_balance_json import (
    encode_melee_balance_error, encode_melee_balance_result, parse_melee_balance_request,
)
from towr.application.melee_balance_errors import MeleeBalanceGenerationError, MeleeBalanceExecutionError
from towr.application.melee_balance_service import execute_melee_balance
from towr.adapters.mixed_json_errors import MixedSimulationInputError, MixedBalanceInputError
from towr.adapters.mixed_simulation_json import (
    encode_mixed_simulation_error, encode_mixed_simulation_result, parse_mixed_simulation_request,
)
from towr.application.mixed_simulation_errors import MixedSimulationExecutionError
from towr.application.mixed_simulation_service import execute_mixed_simulation
from towr.adapters.mixed_balance_json import (
    encode_mixed_balance_error, encode_mixed_balance_result, parse_mixed_balance_request,
)
from towr.application.mixed_balance_errors import MixedBalanceGenerationError, MixedBalanceExecutionError
from towr.application.mixed_balance_service import execute_mixed_balance


def _diagnose(message: str) -> bool:
    # Keep diagnostics on one line and independent of the console code page.
    data = ("towr: " + " ".join(message.splitlines()) + "\n").encode("utf-8", errors="backslashreplace")
    try:
        sys.stderr.buffer.write(data)
        sys.stderr.buffer.flush()
    except (OSError, ValueError):
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
    parser = argparse.ArgumentParser(prog="towr", description="Simulate or balance TOWR Minion encounters.")
    commands = parser.add_subparsers(dest="command", required=True)
    simulate = commands.add_parser("simulate", help="execute a JSON v1 request")
    simulate.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    balance = commands.add_parser("balance", help="generate and evaluate a JSON balance v1 request")
    balance.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    melee = commands.add_parser("simulate-melee", help="execute a Melee JSON v1 request")
    melee.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    melee_balance = commands.add_parser("balance-melee", help="generate and evaluate a Melee JSON balance v1 request")
    melee_balance.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    mixed = commands.add_parser("simulate-mixed", help="execute a mixed JSON v1 request")
    mixed.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    mixed_balance = commands.add_parser("balance-mixed", help="generate and evaluate a mixed JSON balance v1 request")
    mixed_balance.add_argument("input", metavar="INPUT", help="UTF-8 JSON file, or - for stdin")
    args = parser.parse_args(argv)

    if args.command == "balance":
        parse, execute, encode = parse_ranged_balance_request, execute_ranged_balance, encode_ranged_balance_result
        encode_error, input_error = encode_ranged_balance_error, RangedBalanceInputError
        execution_errors = (RangedBalanceGenerationError, RangedBalanceExecutionError)
    elif args.command == "simulate-melee":
        parse, execute, encode = parse_melee_simulation_request, execute_melee_simulation, encode_melee_simulation_result
        encode_error, input_error = encode_melee_simulation_error, MeleeSimulationInputError
        execution_errors = (MeleeSimulationExecutionError,)
    elif args.command == "balance-melee":
        parse, execute, encode = parse_melee_balance_request, execute_melee_balance, encode_melee_balance_result
        encode_error, input_error = encode_melee_balance_error, MeleeBalanceInputError
        execution_errors = (MeleeBalanceGenerationError, MeleeBalanceExecutionError)
    elif args.command == "balance-mixed":
        parse, execute, encode = parse_mixed_balance_request, execute_mixed_balance, encode_mixed_balance_result
        encode_error, input_error = encode_mixed_balance_error, MixedBalanceInputError
        execution_errors = (MixedBalanceGenerationError, MixedBalanceExecutionError)
    elif args.command == "simulate-mixed":
        parse, execute, encode = parse_mixed_simulation_request, execute_mixed_simulation, encode_mixed_simulation_result
        encode_error, input_error = encode_mixed_simulation_error, MixedSimulationInputError
        execution_errors = (MixedSimulationExecutionError,)
    else:
        parse, execute, encode = parse_ranged_simulation_request, execute_ranged_simulation, encode_ranged_simulation_result
        encode_error, input_error = encode_ranged_simulation_error, RangedSimulationInputError
        execution_errors = (RangedSimulationExecutionError,)

    try:
        raw = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
    except (OSError, ValueError) as error:
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
        code = "generation_failed" if isinstance(error, (RangedBalanceGenerationError, MeleeBalanceGenerationError, MixedBalanceGenerationError)) else "execution_failed"
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
    except (OSError, ValueError) as error:
        _silence_failed_stream(sys.stdout)
        _diagnose(f"output I/O error: {error}")
        return 4
    if diagnostic is not None and not _diagnose(diagnostic):
        return 4
    return status
