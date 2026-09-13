"""The public request boundary accepts data, never import paths or Python code.

Registration is privileged Python code. This is not a sandbox. Use isolated
workers with deadlines before exposing compilation as a network service.
"""

import threading
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .. import edgir
from ..core import Block, CompiledDesignExportTransform
from ..core.ScalaCompilerInterface import CompilerCheckError, ScalaCompilerInstance


class ExpertParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Evidence(BaseModel):
    kind: Literal["reference", "calculation", "compile", "simulation", "hardware"]
    status: Literal["pass", "fail", "unverified"]
    conditions: str
    artifact: Optional[str] = None
    note: str = ""


class ModuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str
    sources: List[str] = Field(default_factory=list)
    ports: Dict[str, str] = Field(default_factory=dict)
    applicability: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)


class Diagnostic(BaseModel):
    kind: str
    path: List[str] = Field(default_factory=list)
    name: str = ""
    details: str


class CompileResult(BaseModel):
    schema_version: Literal[1] = 1
    module_id: str
    version: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    success: bool = False
    diagnostics: List[Diagnostic] = Field(default_factory=list)
    snapshot: Optional[Dict[str, Any]] = None
    validation: Dict[str, str] = Field(
        default_factory=lambda: {"compile": "unverified", "simulation": "unverified", "hardware": "unverified"}
    )


# EDG's Python elaborator and temporary top-level binding are process-global.
_compile_lock = threading.Lock()


class Registry:
    def __init__(self) -> None:
        self._entries: Dict[Tuple[str, str], Tuple[ModuleSpec, Type[ExpertParameters], Type[Block]]] = {}

    def register(self, spec: ModuleSpec, parameters: Type[ExpertParameters], block: Type[Block]) -> None:
        key = (spec.module_id, spec.version)
        if key in self._entries:
            raise ValueError(f"Duplicate expert module {key}")
        if not issubclass(parameters, ExpertParameters) or not issubclass(block, Block):
            raise TypeError("Registration requires ExpertParameters and Block subclasses")
        if parameters.model_config.get("extra") != "forbid" or not parameters.model_config.get("strict"):
            raise ValueError("Expert parameter models must forbid extra fields and require strict types")
        self._entries[key] = (spec.model_copy(deep=True), parameters, block)

    def list_modules(self) -> List[Dict[str, Any]]:
        return [self.describe(*key) for key in sorted(self._entries)]

    def describe(self, module_id: str, version: str) -> Dict[str, Any]:
        spec, parameters, _ = self._entries[(module_id, version)]
        return {**spec.model_dump(mode="json"), "parameter_schema": parameters.model_json_schema()}

    def compile(self, module_id: str, version: str, parameters: Dict[str, Any]) -> CompileResult:
        result = CompileResult(module_id=module_id, version=version)
        entry = self._entries.get((module_id, version))
        if entry is None:
            result.diagnostics.append(Diagnostic(kind="unknown_module", details="Module ID/version is not registered"))
            return result
        _, parameter_type, block_type = entry
        try:
            validated = parameter_type.model_validate(parameters)
        except ValidationError as error:
            result.diagnostics = [
                Diagnostic(kind="input_validation", path=[str(part) for part in item["loc"]], details=item["msg"])
                for item in error.errors()
            ]
            return result
        result.parameters = validated.model_dump(mode="json")

        with _compile_lock:
            # Stable module-level name is required by the compiler's HDL callbacks.
            class ExpertCompileTop(Block):
                def __init__(self) -> None:
                    super().__init__()
                    self.module = self.Block(block_type(**validated.model_dump()))

            ExpertCompileTop.__qualname__ = "ExpertCompileTop"
            globals()["ExpertCompileTop"] = ExpertCompileTop
            compiler = ScalaCompilerInstance()
            try:
                compiled = compiler.compile(ExpertCompileTop, ignore_errors=True)
                result.diagnostics = [
                    Diagnostic(
                        kind=error.kind,
                        path=edgir.local_path_to_str_list(error.path),
                        name=error.name,
                        details=error.details,
                    )
                    for error in compiled.errors
                ]
                result.validation["compile"] = "fail" if compiled.errors else "pass"
                # A partial snapshot is useful even when an electrical constraint fails.
                snapshot = CompiledDesignExportTransform(compiled).transform()
                result.snapshot = snapshot.model_dump(mode="json", exclude_none=True)
                result.success = not compiled.errors
            except (Exception, CompilerCheckError) as error:
                result.diagnostics.append(Diagnostic(kind="runtime", details=str(error)))
            finally:
                try:
                    compiler.close()
                except Exception as error:
                    result.success = False
                    result.diagnostics.append(Diagnostic(kind="cleanup", details=str(error)))
                finally:
                    globals().pop("ExpertCompileTop", None)
        return result
