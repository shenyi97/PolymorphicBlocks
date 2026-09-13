import unittest
from typing import List, cast
from typing_extensions import override

from .tipd175 import Tipd175, Tipd175Fixture, Tipd175Load, Tipd175Supply, dc_analysis, dc_output, tipd175_registry
from ..core import Block
from ..core.ScalaCompilerInterface import ScalaCompilerInstance
from ..electronics_model.NetlistGenerator import NetlistTransform, NetPin
from ..electronics_model.RefdesRefinementPass import RefdesRefinementPass


class ReferenceBoard(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=1.0, supply_v=3.3, load_ohm=10000, shunt_rating_w=0.5))


class TwoAmpBoard(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=2.0, supply_v=3.3, load_ohm=10000, shunt_rating_w=0.5))


class WrongSupply(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=1.0, supply_v=5.0, load_ohm=10000, shunt_rating_w=0.5))


class HeavyLoad(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=1.0, supply_v=3.3, load_ohm=1000, shunt_rating_w=0.5))


class WeakShunt(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=1.0, supply_v=3.3, load_ohm=10000, shunt_rating_w=0.1))


class InvalidCurrent(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=0, supply_v=3.3, load_ohm=10000, shunt_rating_w=0.5))


class LoadedReference(Block):
    def __init__(self) -> None:
        super().__init__()
        self.sense = self.Block(Tipd175())
        self.supply = self.Block(Tipd175Supply())
        self.output_load = self.Block(Tipd175Load())
        self.load = self.Block(Tipd175Load())
        self.connect(self.supply.pwr, self.sense.pwr)
        self.connect(self.supply.current, self.sense.iin)
        self.connect(self.sense.out, self.output_load.input)
        self.connect(self.sense.ref, self.load.input)
        self.connect(self.supply.gnd, self.sense.gnd, self.output_load.gnd, self.load.gnd)


def solve(matrix: List[List[float]], rhs: List[float]) -> List[float]:
    """Independent Gaussian elimination for the ideal circuit's nodal equations."""
    augmented = [row[:] + [b] for row, b in zip(matrix, rhs)]
    n = len(rhs)
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        augmented[col] = [x / divisor for x in augmented[col]]
        for row in range(n):
            if row != col:
                multiplier = augmented[row][col]
                augmented[row] = [a - multiplier * b for a, b in zip(augmented[row], augmented[col])]
    return [row[-1] for row in augmented]


class Tipd175Test(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.compiler = ScalaCompilerInstance()

    @override
    def tearDown(self) -> None:
        self.compiler.close()

    def test_reference_values_and_variant(self) -> None:
        for board, resistance in ((ReferenceBoard, 0.1), (TwoAmpBoard, 0.05)):
            compiled = self.compiler.compile(board)
            self.assertAlmostEqual(cast(float, compiled.get_value(["dut", "sense", "shunt_resistance"])), resistance)
            self.assertAlmostEqual(cast(float, compiled.get_value(["dut", "sense", "output_min"])), 0.11, delta=1e-6)
            self.assertAlmostEqual(cast(float, compiled.get_value(["dut", "sense", "output_max"])), 3.19, delta=1e-6)
            self.assertLess(cast(float, compiled.get_value(["dut", "sense", "shunt_power_max"])), 0.25)
            self.assertEqual(
                compiled.get_value(["dut", "sense", "Rshunt", "fp_part"]),
                "LVK12R100DER" if board is ReferenceBoard else "UNSELECTED_50mOhm_Kelvin",
            )
            self.assertAlmostEqual(
                cast(float, compiled.get_value(["dut", "sense", "C3", "capacitance"])), 100e-12, delta=1e-15
            )

    def test_every_net_matches_reviewed_schematic(self) -> None:
        compiled = self.compiler.compile(ReferenceBoard)
        compiled.append_values(RefdesRefinementPass().run(compiled))
        netlist = next(iter(NetlistTransform(compiled).run().values()))
        self.assertEqual(len(netlist.blocks), 12)

        def pin_name(pin: NetPin) -> str:
            # NetPin is a NamedTuple; keep a concrete name in assertions.
            return ".".join(pin.block_path.to_tuple()).removeprefix("dut.").removeprefix("sense.") + ":" + pin.pin_name

        actual = {frozenset(pin_name(pin) for pin in net.pins) for net in netlist.nets if net.pins}
        expected = {
            frozenset(["U1:8", "R5:1", "C1:1", "C2:1", "C3:1"]),
            frozenset(["U1:4", "R6:2", "Rshunt:I-", "C1:2", "C2:2", "C3:2", "RL:2"]),
            frozenset(["Rshunt:I+"]),
            frozenset(["Rshunt:S+", "R1:1"]),
            frozenset(["Rshunt:S-", "R3:1"]),
            frozenset(["R1:2", "R2:2", "U1:3"]),
            frozenset(["R3:2", "R4:2", "U1:2"]),
            frozenset(["R4:1", "U1:1", "RL:1"]),
            frozenset(["R5:2", "R6:1", "U1:5"]),
            frozenset(["R2:1", "U1:7", "U1:6"]),
        }
        self.assertEqual(actual, expected)
        opa = next(b for b in netlist.blocks if b.full_path.to_tuple()[-1] == "U1")
        self.assertIn("OPA2313IDGK", opa.part)
        self.assertEqual(opa.footprint, "Package_SO:VSSOP-8_3x3mm_P0.65mm")
        for block in netlist.blocks:
            name = block.full_path.to_tuple()[-1]
            if name in ("R1", "R2", "R3", "R4", "R5", "R6", "C1", "C2", "C3", "U1"):
                self.assertEqual(block.refdes, name)
            if name.startswith("C"):
                self.assertTrue(block.value)

    def test_direct_block_rejects_unsafe_conditions(self) -> None:
        for board, expected in (
            (WrongSupply, "voltage out of limits"),
            (HeavyLoad, "output_load_at_least_10k"),
            (WeakShunt, "shunt_50_percent_power_derating"),
            (InvalidCurrent, "supported_current_1_or_2_A"),
            (LoadedReference, "external_reference_loading_not_supported"),
        ):
            with self.subTest(board=board.__name__):
                compiled = self.compiler.compile(board, ignore_errors=True)
                self.assertIn(expected, [error.name for error in compiled.errors])
                self.assertTrue(all(error.kind == "Failed assertion" for error in compiled.errors))

    def test_registry_and_strict_parameters(self) -> None:
        registry = tipd175_registry()
        for value in (0, 1.5, 3, True, "2", float("nan")):
            result = registry.compile("ti.tipd175.dc_fixture", "0.1.0", {"current_limit_a": value})
            self.assertFalse(result.success)
            self.assertEqual(result.diagnostics[0].kind, "input_validation")
        result = registry.compile("ti.tipd175.dc_fixture", "0.1.0", {"current_limit_a": 2.0})
        self.assertTrue(result.success, result.model_dump_json())
        self.assertEqual(result.validation["hardware"], "unverified")

    def test_independent_nodal_solution(self) -> None:
        # Unknowns: sense, noninverting, inverting, output; reference is ideal 1.65 V.
        for rs in (0.1, 0.05):
            for current in (-2, -1, 0, 1, 2):
                r1, r2, r3, r4 = 1000.0, 15400.0, 1000.0, 15400.0
                solution = solve(
                    [
                        [1 / rs + 1 / r1, -1 / r1, 0, 0],
                        [-1 / r1, 1 / r1 + 1 / r2, 0, 0],
                        [0, 0, 1 / r3 + 1 / r4, -1 / r4],
                        [0, 1, -1, 0],
                    ],
                    [current, 1.65 / r2, 0, 0],
                )
                self.assertAlmostEqual(solution[3], dc_output(current, [rs, r1, r2, r3, r4, 10000, 10000]), places=10)

    def test_corner_failure_is_not_hidden(self) -> None:
        for current in (1.0, 2.0):
            result = dc_analysis(current)
            self.assertFalse(result["corner_headroom_pass"])
            self.assertFalse(result["manufacturing_ready"])
