import json
import unittest

from towr.adapters.ranged_json_errors import RangedInputErrorCode as Code
from towr.adapters.mixed_json_errors import MixedSimulationInputError
from towr.adapters.mixed_json_schema import validate_mixed_document
from towr.adapters.mixed_simulation_json import encode_mixed_simulation_error as encode, parse_mixed_simulation_request as parse
from towr.application.mixed_simulation_errors import MixedSimulationExecutionError


class M7MixedErrorJsonTests(unittest.TestCase):
    def test_ranged_failures_are_not_mixed_failures(self):
        from towr.adapters.ranged_json_errors import RangedSimulationInputError
        from towr.application.ranged_simulation_errors import RangedSimulationExecutionError
        from towr.adapters.melee_json_errors import MeleeSimulationInputError, MeleeBalanceInputError
        from towr.application.melee_simulation_errors import MeleeSimulationExecutionError
        for error in (RangedSimulationInputError(Code.INVALID_INPUT, "invalid"), RangedSimulationExecutionError("request"),
                      MeleeSimulationInputError(Code.INVALID_INPUT, "invalid"), MeleeSimulationExecutionError("request"),
                      MeleeBalanceInputError(Code.INVALID_INPUT, "invalid")):
            with self.assertRaises(TypeError):
                encode(error)

    def test_execution_message_is_generic_even_if_exception_has_extra_details(self):
        error = MixedSimulationExecutionError("request")
        error.args = ("private worker detail",)
        error.add_note("private worker note")
        actual = encode(error)
        self.assertNotIn("private", actual)
        self.assertEqual(json.loads(actual)["error"]["message"], "Simulation execution failed")

    def test_input_categories_pointer_and_request_id_are_preserved(self):
        for code in Code:
            for request_id, path in ((None, None), ("запрос", ""), ("request", "/a~1b/~0")):
                error = MixedSimulationInputError(code, "Ошибка входа", request_id=request_id, path=path)
                with self.subTest(code=code, path=path):
                    text = encode(error)
                    self.assertTrue(text.endswith("\n"))
                    actual = json.loads(text.encode("utf-8"))
                    self.assertEqual(actual, {
                        "schema_version": "1", "kind": "mixed_simulation_error", "request_id": request_id,
                        "error": {"code": code.value, "path": path, "message": "Ошибка входа"},
                    })
                    validate_mixed_document(actual, "error")

    def test_execution_error_excludes_cause_traceback_and_partial_results(self):
        cause = RuntimeError("internal detail")
        try:
            raise MixedSimulationExecutionError("request") from cause
        except MixedSimulationExecutionError as error:
            actual = json.loads(encode(error))
            self.assertEqual(actual, {
                "schema_version": "1", "kind": "mixed_simulation_error", "request_id": "request",
                "error": {"code": "execution_failed", "path": None, "message": "Simulation execution failed"},
            })
            self.assertIs(error.__cause__, cause)

    def test_malformed_unicode_diagnostic_can_be_encoded_as_utf8(self):
        with self.assertRaises(MixedSimulationInputError) as caught:
            parse('{"\\ud800":1,"\\ud800":2}')
        actual = json.loads(encode(caught.exception).encode("utf-8"))
        self.assertEqual(actual["error"]["code"], "invalid_json")
        self.assertEqual(actual["error"]["message"], str(caught.exception))

    def test_unknown_exceptions_are_not_classified(self):
        for error in (ValueError("input?"), RuntimeError("execution?"), KeyboardInterrupt(), None):
            with self.subTest(error=type(error)), self.assertRaises(TypeError):
                encode(error)
