import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import Field
from typing_extensions import override

from ..core import Block, FloatExpr, FloatLike, GeneratorBlock
from ..core.ScalaCompilerInterface import ScalaCompilerInstance
from .api import ExpertParameters, ModuleSpec, Registry


class GainParameters(ExpertParameters):
    gain: float = Field(gt=0, le=20, description="Dimensionless gain; protocol test only")


class GainGenerator(GeneratorBlock):
    """Exercises real parameter propagation; this is not a physical circuit."""

    def __init__(self, gain: FloatLike) -> None:
        super().__init__()
        self.gain = self.ArgParameter(gain)
        self.result = self.Parameter(FloatExpr())
        self.generator_param(self.gain)

    @override
    def generate(self) -> None:
        super().generate()
        self.assign(self.result, self.get(self.gain) * 2)


class FailingBlock(Block):
    def __init__(self, gain: FloatLike) -> None:
        super().__init__()
        self.gain = self.ArgParameter(gain)
        self.require(self.gain < 1, "gain must be below one")


def make_registry() -> Registry:
    registry = Registry()
    registry.register(
        ModuleSpec(module_id="test.gain", version="0.1", description="Compiler protocol fixture"),
        GainParameters,
        GainGenerator,
    )
    return registry


class RegistryTest(unittest.TestCase):
    def test_schema_and_duplicate(self) -> None:
        registry = make_registry()
        schema = registry.describe("test.gain", "0.1")["parameter_schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["gain"]["maximum"], 20)
        with self.assertRaises(ValueError):
            registry.register(
                ModuleSpec(module_id="test.gain", version="0.1", description=""), GainParameters, GainGenerator
            )

    def test_invalid_requests_do_not_start_compiler(self) -> None:
        registry = make_registry()
        with patch.object(ScalaCompilerInstance, "compile", side_effect=AssertionError("must not run")):
            for params in ({"gain": 0}, {"gain": "2"}, {"gain": float("nan")}, {"gain": 2, "code": "x"}, {}):
                result = registry.compile("test.gain", "0.1", params)
                self.assertFalse(result.success)
                self.assertEqual(result.diagnostics[0].kind, "input_validation")
            self.assertEqual(registry.compile("os.system", "0.1", {}).diagnostics[0].kind, "unknown_module")

    def test_compile_and_repeat(self) -> None:
        registry = make_registry()
        for gain in (2.0, 3.0):
            result = registry.compile("test.gain", "0.1", {"gain": gain})
            self.assertTrue(result.success, result.model_dump_json())
            assert result.snapshot is not None
            self.assertEqual(result.snapshot["blocks"]["module"]["params"]["result"]["value"], gain * 2)
            self.assertEqual(result.validation["hardware"], "unverified")

    def test_electrical_failure_has_location(self) -> None:
        registry = Registry()
        registry.register(
            ModuleSpec(module_id="test.fail", version="0.1", description=""), GainParameters, FailingBlock
        )
        result = registry.compile("test.fail", "0.1", {"gain": 2.0})
        self.assertFalse(result.success)
        self.assertEqual(result.validation["compile"], "fail", result.model_dump_json())
        self.assertTrue(any("module" in item.path for item in result.diagnostics))

    def test_runtime_error_is_structured(self) -> None:
        with patch.object(ScalaCompilerInstance, "check_started", side_effect=RuntimeError("missing JRE")):
            result = make_registry().compile("test.gain", "0.1", {"gain": 2.0})
        self.assertEqual(result.diagnostics[0].kind, "runtime")
        self.assertEqual(result.validation["compile"], "unverified")

    def test_jre_override_and_idempotent_close(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"EDG_JRE_DIR": directory}):
                compiler = ScalaCompilerInstance()
                self.assertEqual(compiler.kInstallJrePath, Path(directory).resolve())
                compiler.close()
                compiler.close()
