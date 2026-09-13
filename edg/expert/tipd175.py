"""TI TIPD175 DC prototype. See docs/tipd175-implementation.md for model limits."""

from itertools import product
from typing import Dict, List

from pydantic import Field, field_validator
from typing_extensions import override

from ..core import Block, FloatExpr, FloatLike, GeneratorBlock, StringLike, Range
from ..electronics_model import FootprintBlock, Passive
from ..electronics_interfaces import AnalogSink, AnalogSource, Ground, GroundReference, VoltageSink, VoltageSource
from .api import Evidence, ExpertParameters, ModuleSpec, Registry


class Tipd175Parameters(ExpertParameters):
    current_limit_a: float = Field(default=1.0, description="Symmetric DC current limit in A; supported values 1 or 2")

    @field_validator("current_limit_a")
    @classmethod
    def supported_current(cls, value: float) -> float:
        if value not in (1.0, 2.0):
            raise ValueError("Only the 1 A reference and 2 A calculated variant are supported")
        return value


def dc_output(current_a: float, resistances: List[float], offset_a: float = 0, offset_b: float = 0) -> float:
    """Ideal closed-loop DC, finite shunt loading, and input offsets; no rail clipping.

    resistances is [Rshunt, R1, R2, R3, R4, R5, R6] in ohms.
    Input current is injected into the shunt current+ terminal.
    """
    rs, r1, r2, r3, r4, r5, r6 = resistances
    reference = 3.3 * r6 / (r5 + r6) + offset_b
    sense = (current_a + reference / (r1 + r2)) / (1 / rs + 1 / (r1 + r2))
    positive = (sense * r2 + reference * r1) / (r1 + r2)
    return (positive + offset_a) * (1 + r4 / r3)


def dc_analysis(current_limit_a: float) -> Dict[str, object]:
    Tipd175Parameters(current_limit_a=current_limit_a)
    nominal = [0.1 / current_limit_a, 1000, 15400, 1000, 15400, 10000, 10000]
    tolerance = [0.005, 0.001, 0.001, 0.001, 0.001, 0.005, 0.005]
    values = []
    for signs in product((-1, 1), repeat=9):
        resistances = [r * (1 + s * t) for r, t, s in zip(nominal, tolerance, signs)]
        for current in (-current_limit_a, current_limit_a):
            values.append(dc_output(current, resistances, signs[7] * 0.0025, signs[8] * 0.0025))
    return {
        "nominal_output_v": [dc_output(i, nominal) for i in (-current_limit_a, 0, current_limit_a)],
        "linear_corner_output_v": [min(values), max(values)],
        "corner_headroom_pass": min(values) >= 0.1 and max(values) <= 3.2,
        "nominal_shunt_power_w": current_limit_a**2 * nominal[0],
        "shunt_tolerance_power_w": current_limit_a**2 * nominal[0] * 1.005,
        "assumptions": "25 C, 3.3 V, ideal infinite open-loop gain, assumed +/-2.5mV offsets, resistor tolerances; no clipping",
        "limitations": "Not a guaranteed error envelope; excludes PSRR, CMRR, bias current, finite gain and load tolerance",
        "manufacturing_ready": False,
        "simulation": "unverified",
        "hardware": "unverified",
    }


class Tipd175Resistor(FootprintBlock, GeneratorBlock):
    def __init__(
        self, resistance: FloatLike, tolerance: FloatLike, rating: FloatLike, part: StringLike, manufacturer: StringLike
    ) -> None:
        super().__init__()
        self.a = self.Port(Passive())
        self.b = self.Port(Passive())
        self.resistance = self.ArgParameter(resistance)
        self.tolerance = self.ArgParameter(tolerance)
        self.rating = self.ArgParameter(rating)
        self.part = self.ArgParameter(part)
        self.manufacturer = self.ArgParameter(manufacturer)
        self.generator_param(self.resistance, self.tolerance, self.rating)

    @override
    def generate(self) -> None:
        super().generate()
        self.footprint(
            "R",
            "Resistor_SMD:R_0603_1608Metric",
            {"1": self.a, "2": self.b},
            mfr=self.manufacturer,
            part=self.part,
            value=f"{self.get(self.resistance):g} ohm, {self.get(self.tolerance)*100:g}%, {self.get(self.rating):g} W",
        )


class Tipd175Capacitor(FootprintBlock, GeneratorBlock):
    def __init__(
        self,
        capacitance: FloatLike,
        voltage_rating: FloatLike,
        tolerance: FloatLike,
        footprint: StringLike,
        part: StringLike,
    ) -> None:
        super().__init__()
        self.positive = self.Port(Passive())
        self.negative = self.Port(Passive())
        self.capacitance = self.ArgParameter(capacitance)
        self.voltage_rating = self.ArgParameter(voltage_rating)
        self.tolerance = self.ArgParameter(tolerance)
        self.package = self.ArgParameter(footprint)
        self.part = self.ArgParameter(part)
        self.generator_param(self.capacitance, self.voltage_rating, self.tolerance)

    @override
    def generate(self) -> None:
        super().generate()
        self.footprint(
            "C",
            self.package,
            {"1": self.positive, "2": self.negative},
            mfr="AVX",
            part=self.part,
            value=f"{self.get(self.capacitance):g} F, {self.get(self.tolerance)*100:g}%, {self.get(self.voltage_rating):g} V",
        )


class Opa2313Dgk(FootprintBlock):
    """Physical pin map; analog closed-loop behavior belongs to the expert circuit.

    All pins are passive here. This is not a generally usable electrical opamp model.
    """

    def __init__(self) -> None:
        super().__init__()
        self.outa = self.Port(Passive())
        self.inna = self.Port(Passive())
        self.inpa = self.Port(Passive())
        self.gnd = self.Port(Passive())
        self.inpb = self.Port(Passive())
        self.innb = self.Port(Passive())
        self.outb = self.Port(Passive())
        self.vcc = self.Port(Passive())
        self.footprint(
            "U",
            "Package_SO:VSSOP-8_3x3mm_P0.65mm",
            {
                "1": self.outa,
                "2": self.inna,
                "3": self.inpa,
                "4": self.gnd,
                "5": self.inpb,
                "6": self.innb,
                "7": self.outb,
                "8": self.vcc,
            },
            mfr="Texas Instruments",
            part="OPA2313IDGK",
            datasheet="https://www.ti.com/lit/ds/symlink/opa313.pdf",
        )


class Tipd175KelvinShunt(FootprintBlock, GeneratorBlock):
    def __init__(self, resistance: FloatLike, rating: FloatLike) -> None:
        super().__init__()
        self.current_positive = self.Port(Passive())
        self.current_negative = self.Port(Passive())
        self.sense_positive = self.Port(Passive())
        self.sense_negative = self.Port(Passive())
        self.resistance = self.ArgParameter(resistance)
        self.rating = self.ArgParameter(rating)
        self.generator_param(self.resistance, self.rating)

    @override
    def generate(self) -> None:
        super().generate()
        # FloatExpr values cross the compiler boundary as float32.
        original = abs(self.get(self.resistance) - 0.1) < 1e-6
        # Functional pad labels deliberately prevent accidental use as a reviewed footprint.
        self.footprint(
            "R",
            "ExpertUnreviewed:Ohmite_LVK12_Kelvin",
            {
                "I+": self.current_positive,
                "I-": self.current_negative,
                "S+": self.sense_positive,
                "S-": self.sense_negative,
            },
            mfr="Ohmite" if original else "UNSELECTED",
            part="LVK12R100DER" if original else "UNSELECTED_50mOhm_Kelvin",
            value=f"{self.get(self.resistance):g} ohm, 0.5%, {self.get(self.rating):g} W; FOOTPRINT UNREVIEWED",
        )


class Tipd175(GeneratorBlock):
    """Fixed expert topology; current limit is a declared DC operating condition.

    The output port conservatively permits the full supply range. dc_analysis reports
    tolerance/offset corners separately; passing compile does not guarantee 1% accuracy.
    """

    def __init__(self, current_limit_a: FloatLike = 1.0, shunt_rating_w: FloatLike = 0.5) -> None:
        super().__init__()
        self.current_limit_a = self.ArgParameter(current_limit_a)
        self.shunt_rating_w = self.ArgParameter(shunt_rating_w)
        self.shunt_resistance = self.Parameter(FloatExpr())
        self.shunt_power_max = self.Parameter(FloatExpr())
        self.output_min = self.Parameter(FloatExpr())
        self.output_max = self.Parameter(FloatExpr())
        self.pwr = self.Port(VoltageSink(voltage_limits=(3.3, 3.3), current_draw=(0, 0.002)))
        self.gnd = self.Port(Ground())
        self.iin = self.Port(Passive())
        self.out = self.Port(AnalogSource(voltage=(0, 3.3), signal=(0, 3.3), current_limits=(-0.00033, 0.00033)))
        self.ref = self.Port(AnalogSource(voltage=(0, 3.3), signal=(0, 3.3)), optional=True)
        self.require(~self.ref.is_connected(), "external_reference_loading_not_supported")
        self.require((self.current_limit_a == 1) | (self.current_limit_a == 2), "supported_current_1_or_2_A")
        self.require(self.shunt_power_max <= self.shunt_rating_w * 0.5, "shunt_50_percent_power_derating")
        self.require(self.output_min >= 0.1, "nominal_low_swing_margin")
        self.require(self.output_max <= 3.2, "nominal_high_swing_margin")
        self.require(self.out.link().sink_impedance.lower() >= 10000, "output_load_at_least_10k")
        self.generator_param(self.current_limit_a, self.shunt_rating_w)

    @override
    def generate(self) -> None:
        super().generate()
        limit = self.get(self.current_limit_a)
        rs = 0.1 / limit if limit > 0 else 0.1  # invalid requests retain failed require, avoid divide-by-zero
        self.assign(self.shunt_resistance, rs)
        # Include a conservative bound on reference injection through R2/R1.
        self.assign(self.shunt_power_max, (abs(limit) + 3.3 / (16400 * 0.999)) ** 2 * rs * 1.005)
        self.assign(self.output_min, 1.65 - limit * rs * 15.4)
        self.assign(self.output_max, 1.65 + limit * rs * 15.4)
        self.U1 = self.Block(Opa2313Dgk())
        self.R1 = self.Block(Tipd175Resistor(1000, 0.001, 0.0625, "CRT0603-BY-1001ELF", "Bourns"))
        self.R2 = self.Block(Tipd175Resistor(15400, 0.001, 0.1, "RG1608P-1542-B-T5", "Susumu"))
        self.R3 = self.Block(Tipd175Resistor(1000, 0.001, 0.0625, "CRT0603-BY-1001ELF", "Bourns"))
        self.R4 = self.Block(Tipd175Resistor(15400, 0.001, 0.1, "RG1608P-1542-B-T5", "Susumu"))
        self.R5 = self.Block(Tipd175Resistor(10000, 0.005, 0.0625, "RR0816P-103-D", "Susumu"))
        self.R6 = self.Block(Tipd175Resistor(10000, 0.005, 0.0625, "RR0816P-103-D", "Susumu"))
        self.Rshunt = self.Block(Tipd175KelvinShunt(rs, self.get(self.shunt_rating_w)))
        self.C1 = self.Block(
            Tipd175Capacitor(10e-6, 25, 0.1, "Capacitor_Tantalum_SMD:CP_EIA-6032-28_Kemet-C", "TPSC106K025R0500")
        )
        self.C2 = self.Block(Tipd175Capacitor(0.1e-6, 25, 0.1, "Capacitor_SMD:C_0603_1608Metric", "06033C104KAT2A"))
        self.C3 = self.Block(Tipd175Capacitor(100e-12, 50, 0.05, "Capacitor_SMD:C_0603_1608Metric", "06035A101JAT2A"))
        self.connect(self.pwr.net, self.U1.vcc, self.R5.a, self.C1.positive, self.C2.positive, self.C3.positive)
        self.connect(
            self.gnd.net,
            self.U1.gnd,
            self.R6.b,
            self.Rshunt.current_negative,
            self.C1.negative,
            self.C2.negative,
            self.C3.negative,
        )
        self.connect(self.iin, self.Rshunt.current_positive)
        self.connect(self.Rshunt.sense_positive, self.R1.a)
        self.connect(self.Rshunt.sense_negative, self.R3.a)
        self.connect(self.R1.b, self.R2.b, self.U1.inpa)
        self.connect(self.R3.b, self.R4.b, self.U1.inna)
        self.connect(self.R4.a, self.U1.outa, self.out.net)
        self.connect(self.R5.b, self.R6.a, self.U1.inpb)
        self.connect(self.R2.a, self.U1.outb, self.U1.innb, self.ref.net)


class Tipd175Supply(Block):
    def __init__(self, voltage: FloatLike = 3.3) -> None:
        super().__init__()
        self.pwr = self.Port(VoltageSource(voltage=(voltage, voltage), current_limits=(0, 0.01)))
        self.gnd = self.Port(GroundReference())
        self.current = self.Port(Passive())


class Tipd175Load(FootprintBlock):
    def __init__(self, load_ohm: FloatLike = 10000) -> None:
        super().__init__()
        self.input = self.Port(
            AnalogSink(voltage_limits=(0, 3.3), signal_limits=(0, 3.3), impedance=(load_ohm, load_ohm))
        )
        self.gnd = self.Port(Ground())
        self.footprint(
            "R",
            "Resistor_SMD:R_0603_1608Metric",
            {"1": self.input, "2": self.gnd},
            part="RMCF0603FT10K0",
            mfr="Stackpole",
            value="10k, 1%, 0.1W",
        )


class Tipd175Fixture(Block):
    """Explicit nominal DC source/load fixture, not a manufactured TI EVM."""

    def __init__(
        self,
        current_limit_a: FloatLike = 1.0,
        supply_v: FloatLike = 3.3,
        load_ohm: FloatLike = 10000,
        shunt_rating_w: FloatLike = 0.5,
    ) -> None:
        super().__init__()
        self.sense = self.Block(Tipd175(current_limit_a, shunt_rating_w))
        self.supply = self.Block(Tipd175Supply(supply_v))
        self.RL = self.Block(Tipd175Load(load_ohm))
        self.connect(self.supply.pwr, self.sense.pwr)
        self.connect(self.supply.gnd, self.sense.gnd, self.RL.gnd)
        self.connect(self.supply.current, self.sense.iin)
        self.connect(self.sense.out, self.RL.input)


def tipd175_registry() -> Registry:
    registry = Registry()
    registry.register(
        ModuleSpec(
            module_id="ti.tipd175.dc_fixture",
            version="0.1.0",
            description="TIPD175 fixed topology with explicit 3.3 V supply and 10k DC load fixture; review-only",
            sources=[
                "https://www.ti.com/tool/TIPD175",
                "https://www.ti.com/lit/pdf/TIDU675",
                "https://www.ti.com/lit/pdf/TIDRG85",
                "https://www.ti.com/lit/pdf/TIDRG86",
            ],
            applicability=[
                "25 C, nominal 3.3 V DC",
                "1 A reference or 2 A calculated variant",
                "Current is declared, not inferred from connected load",
                "Unreviewed Kelvin footprint; no manufacturing release",
            ],
            evidence=[
                Evidence(
                    kind="reference",
                    status="pass",
                    conditions="Original TI documents retrieved; schematic visually checked",
                    artifact="docs/tipd175-implementation.md",
                    note="Does not transfer TI hardware validation to this implementation",
                )
            ],
        ),
        Tipd175Parameters,
        Tipd175Fixture,
    )
    return registry
