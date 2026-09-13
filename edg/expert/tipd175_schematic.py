"""Fixed TIPD175 KiCad layout; values and footprints come from compiled artifacts."""

import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import xml.etree.ElementTree as ET


def uid(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, "edg-tipd175-template/" + value))


def q(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def effects(size: float = 1.27, hide: bool = False) -> str:
    return f"(effects (font (size {size} {size}))" + (" (hide yes)" if hide else "") + ")"


def prop(name: str, value: object, x: float = 0, y: float = 0, hide: bool = False) -> str:
    return f"(property {q(name)} {q(value)} (at {x} {y} 0) {effects(hide=hide)})"


def pin(number: str, name: str, x: float, y: float, angle: float, length: float = 5.08, kind: str = "passive") -> str:
    return f"(pin {kind} line (at {x} {y} {angle}) (length {length}) (name {q(name)} {effects(1)}) (number {q(number)} {effects(1)}))"


def poly(points: list[tuple[float, float]]) -> str:
    pts = " ".join(f"(xy {x} {y})" for x, y in points)
    return f"(polyline (pts {pts}) (stroke (width 0.254) (type default)) (fill (type none)))"


def library(name: str, units: list[str], prefix: str = "R", hide_names: bool = True) -> str:
    return (
        f'(symbol "Expert:{name}" (pin_names (offset 0.5) {"(hide yes)" if hide_names else ""}) (in_bom yes) (on_board yes) {prop("Reference",prefix)} {prop("Value",name)} '
        + " ".join(f'(symbol "{name}_{i}_1" {body})' for i, body in enumerate(units, 1))
        + ")"
    )


def libraries() -> list[str]:
    rh = poly([(-2.54, 1.016), (2.54, 1.016), (2.54, -1.016), (-2.54, -1.016), (-2.54, 1.016)])
    rv = poly([(-1.016, 2.54), (1.016, 2.54), (1.016, -2.54), (-1.016, -2.54), (-1.016, 2.54)])
    capacitor = poly([(-2.54, 1.016), (2.54, 1.016)]) + poly([(-2.54, -1.016), (2.54, -1.016)])
    triangle = poly([(-5.08, 5.08), (5.08, 0), (-5.08, -5.08), (-5.08, 5.08)])
    amp = []
    for plus, minus, out in [("3", "2", "1"), ("5", "6", "7")]:
        amp.append(
            triangle
            + pin(plus, "+", -10.16, 2.54, 0, kind="input")
            + pin(minus, "-", -10.16, -2.54, 0, kind="input")
            + pin(out, "OUT", 10.16, 0, 180, kind="output")
        )
    amp.append(
        poly([(-3.81, 5.08), (3.81, 5.08), (3.81, -5.08), (-3.81, -5.08), (-3.81, 5.08)])
        + pin("8", "V+", 0, 10.16, 270, kind="power_in")
        + pin("4", "V-", 0, -10.16, 90, kind="power_in")
    )
    shunt = rv + pin("I+", "I+", 0, 10.16, 270, 7.62) + pin("I-", "I-", 0, -10.16, 90, 7.62)
    shunt += poly([(0, 2.54), (2.54, 2.54), (2.54, 5.08)]) + poly([(0, -2.54), (2.54, -2.54), (2.54, -5.08)])
    shunt += pin("S+", "S+", 10.16, 5.08, 180, 7.62) + pin("S-", "S-", 10.16, -5.08, 180, 7.62)
    return [
        library("RH", [rh + pin("1", "", -5.08, 0, 0, 2.54) + pin("2", "", 5.08, 0, 180, 2.54)]),
        library("RHR", [rh + pin("2", "", -5.08, 0, 0, 2.54) + pin("1", "", 5.08, 0, 180, 2.54)]),
        library("RV", [rv + pin("1", "", 0, 5.08, 270, 2.54) + pin("2", "", 0, -5.08, 90, 2.54)]),
        library("C", [capacitor + pin("1", "", 0, 5.08, 270, 4.064) + pin("2", "", 0, -5.08, 90, 4.064)], "C"),
        library(
            "CP",
            [
                capacitor
                + poly([(-4.064, 3.048), (-2.032, 3.048)])
                + poly([(-3.048, 2.032), (-3.048, 4.064)])
                + pin("1", "+", 0, 5.08, 270, 4.064)
                + pin("2", "-", 0, -5.08, 90, 4.064)
            ],
            "C",
        ),
        library("OPA2313", amp, "U", False),
        library("Kelvin", [shunt]),
    ]


def generate(folder: Path, output: Path) -> None:
    data = json.loads((folder / "tipd175.compiled.json").read_text(encoding="utf-8"))
    components = {v["ti_refdes"]: v for v in json.loads((folder / "component-map.json").read_text())}
    root = uid("sheet")
    entries: list[str] = []

    def text(value: str, x: float, y: float, size: float = 1.27) -> None:
        entries.append(f'(text {q(value)} (at {x} {y} 0) {effects(size)} (uuid "{uid(value+str(x)+str(y))}"))')

    def wire(*points: tuple[float, float]) -> None:
        for a, b in zip(points, points[1:]):
            if a == b:
                continue
            entries.append(
                f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid "{uid(str(a)+str(b))}"))'
            )

    def dot(x: float, y: float) -> None:
        entries.append(f'(junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid "{uid("dot"+str(x)+str(y))}"))')

    def label(value: str, x: float, y: float) -> None:
        entries.append(f'(label {q(value)} (at {x} {y} 0) {effects()} (uuid "{uid("label"+value+str(x)+str(y))}"))')

    def part(ref: str, lib: str, x: float, y: float, unit: int = 1) -> None:
        block = data
        for step in components[ref]["path"].split("."):
            block = block["blocks"][step]
        params = {k: v.get("value") for k, v in block["params"].items()}
        value = params["fp_value"] or params["fp_part"]
        if "resistance" in params:
            r = params["resistance"]
            value = f"{r/1000:g}k" if r >= 1000 else f"{r:g} ohm"
        if "capacitance" in params:
            c = params["capacitance"]
            value = f"{c*1e6:g}uF" if c >= 1e-9 else f"{c*1e12:g}pF"
        if ref == "RL":
            value = "10k"
        if ref == "U1":
            value = "OPA2313IDGK"
        display_ref = components[ref]["generated_refdes"]
        px, py = x, y - 5.08
        if lib in ("RV", "C", "CP"):
            px, py = x + 8.89, y - 1.27
        if ref == "R6":
            px = x - 8.89
        if lib == "Kelvin":
            px, py = x - 10.16, y - 1.27
        if lib == "OPA2313":
            px, py = (x - 15.24, y - 1.27) if unit == 3 else (x, y - 8.89)
        props = prop("Reference", display_ref, px, py) + prop("Value", value, px, py + 2.54)
        props += prop("Footprint", params["fp_footprint"], x, y, True) + prop(
            "Datasheet", params.get("fp_datasheet", ""), x, y, True
        )
        props += prop("MPN", params["fp_part"], x, y, True) + prop("EDG_Path", components[ref]["path"], x, y, True)
        instance = uid(ref + str(unit))
        entries.append(
            f'(symbol (lib_id "Expert:{lib}") (at {x} {y} 0) (unit {unit}) (in_bom yes) (on_board yes) (dnp no) (uuid "{instance}") {props} (instances (project "tipd175" (path "/{root}" (reference {q(display_ref)}) (unit {unit})))))'
        )

    # Layout follows the functional grouping of TI TIDRG85 Rev B, independently redrawn.
    for args in [
        ("R1", "RH", 91.44, 114.3),
        ("R3", "RH", 91.44, 124.46),
        ("R2", "RV", 111.76, 99.06),
        ("R4", "RHR", 139.7, 144.78),
        ("R5", "RV", 111.76, 43.18),
        ("R6", "RV", 111.76, 63.5),
        ("Rshunt", "Kelvin", 45.72, 116.84),
        ("RL", "RV", 187.96, 132.08),
        ("C1", "CP", 45.72, 50.8),
        ("C2", "C", 218.44, 63.5),
        ("C3", "C", 243.84, 63.5),
        ("U1", "OPA2313", 139.7, 116.84, 1),
        ("U1", "OPA2313", 139.7, 55.88, 2),
        ("U1", "OPA2313", 193.04, 63.5, 3),
    ]:
        part(str(args[0]), str(args[1]), float(args[2]), float(args[3]), int(args[4]) if len(args) > 4 else 1)
    wire((45.72, 106.68), (45.72, 101.6))
    label("I_IN", 45.72, 101.6)
    wire((45.72, 127), (45.72, 134.62))
    label("GND", 45.72, 134.62)
    wire((55.88, 111.76), (73.66, 111.76), (73.66, 114.3), (86.36, 114.3))
    wire((55.88, 121.92), (73.66, 121.92), (73.66, 124.46), (86.36, 124.46))
    wire((96.52, 114.3), (111.76, 114.3), (129.54, 114.3))
    dot(111.76, 114.3)
    wire((111.76, 104.14), (111.76, 114.3))
    wire((111.76, 93.98), (111.76, 86.36))
    label("VREF", 111.76, 86.36)
    wire((96.52, 124.46), (121.92, 124.46), (121.92, 119.38), (129.54, 119.38))
    dot(121.92, 124.46)
    wire((121.92, 124.46), (121.92, 144.78), (134.62, 144.78))
    wire((144.78, 144.78), (170.18, 144.78), (170.18, 116.84))
    dot(170.18, 116.84)
    wire((149.86, 116.84), (170.18, 116.84), (187.96, 116.84), (203.2, 116.84))
    dot(187.96, 116.84)
    label("VOUT", 203.2, 116.84)
    wire((187.96, 116.84), (187.96, 127))
    wire((187.96, 137.16), (187.96, 144.78))
    label("GND", 187.96, 144.78)
    wire((111.76, 38.1), (111.76, 33.02))
    label("VCC", 111.76, 33.02)
    wire((111.76, 48.26), (111.76, 53.34), (111.76, 58.42))
    dot(111.76, 53.34)
    wire((111.76, 53.34), (129.54, 53.34))
    wire((111.76, 68.58), (111.76, 73.66))
    label("GND", 111.76, 73.66)
    wire((149.86, 55.88), (162.56, 55.88), (172.72, 55.88))
    dot(162.56, 55.88)
    label("VREF", 172.72, 55.88)
    wire((162.56, 55.88), (162.56, 78.74), (121.92, 78.74), (121.92, 58.42), (129.54, 58.42))
    wire((45.72, 45.72), (45.72, 38.1))
    label("VCC", 45.72, 38.1)
    wire((45.72, 55.88), (45.72, 63.5))
    label("GND", 45.72, 63.5)
    wire((193.04, 53.34), (218.44, 53.34), (243.84, 53.34))
    label("VCC", 193.04, 53.34)
    dot(218.44, 53.34)
    wire((218.44, 53.34), (218.44, 58.42))
    wire((243.84, 53.34), (243.84, 58.42))
    wire((193.04, 73.66), (218.44, 73.66), (243.84, 73.66))
    label("GND", 193.04, 73.66)
    dot(218.44, 73.66)
    wire((218.44, 68.58), (218.44, 73.66))
    wire((243.84, 68.58), (243.84, 73.66))
    text("TIPD175  |  Bidirectional low-side current sense", 148.59, 15.24, 2.54)
    text("Editable expert template - independently redrawn from TI TIDRG85 Rev B", 148.59, 21.59)
    text("Bulk decoupling", 45.72, 27.94)
    text("1.65 V reference buffer", 139.7, 27.94)
    text("U1 supply + local decoupling", 220.98, 38.1)
    text("Four-terminal Kelvin sense", 58.42, 91.44)
    text("Signal amplifier + explicit 10k load", 163.83, 96.52)
    text("REVIEW ONLY - shunt footprint/pad mapping not approved for manufacture.", 111.76, 162.56)
    text("No SPICE/hardware validation. Corner headroom fails; see analysis.json.", 111.76, 167.64)
    text("External 3.3 V supply and current stimulus are represented by net labels.", 111.76, 172.72)
    text("Functional shunt pad IDs I+/I-/S+/S- preserve EDG connectivity.", 111.76, 177.8)
    content = (
        f'(kicad_sch (version 20250114) (generator "edg_expert_template") (uuid "{root}") (paper "A4") (lib_symbols '
        + "".join(libraries())
        + ") "
        + "".join(entries)
        + ")\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    project = output.with_suffix(".kicad_pro")
    if not project.exists():
        project.write_text("{}\n", encoding="utf-8")
    library_text = "".join(libraries()).replace('(symbol "Expert:', '(symbol "')
    (output.parent / "Expert.kicad_sym").write_text(
        '(kicad_symbol_lib (version 20241209) (generator "edg_expert_template") ' + library_text + ")", encoding="utf-8"
    )
    (output.parent / "sym-lib-table").write_text(
        '(sym_lib_table (lib (name "Expert") (type "KiCad") (uri "${KIPRJMOD}/Expert.kicad_sym") (options "") (descr "TIPD175 template symbols")))',
        encoding="utf-8",
    )
    footprint_libraries = ["Resistor_SMD", "Capacitor_SMD", "Capacitor_Tantalum_SMD", "Package_SO"]
    (output.parent / "fp-lib-table").write_text(
        "(fp_lib_table "
        + "".join(
            "(lib (name "
            + q(name)
            + ') (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/'
            + name
            + '.pretty") (options "") (descr "KiCad standard footprints"))'
            for name in footprint_libraries
        )
        + ")",
        encoding="utf-8",
    )


def verify(folder: Path, xml_path: Path) -> None:
    mapping = {x["generated_refdes"]: x["path"] for x in json.loads((folder / "component-map.json").read_text())}
    root = ET.parse(xml_path).getroot()
    actual = {
        frozenset(mapping[n.attrib["ref"]] + ":" + n.attrib["pin"] for n in net.findall("node"))
        for net in root.findall("./nets/net")
    }
    expected = {frozenset(net) for net in json.loads((folder / "pin-nets.json").read_text())}
    if actual != expected:
        raise ValueError(f"Netlist mismatch: missing={expected-actual}; extra={actual-expected}")
    assert len(root.findall("./components/comp")) == len(mapping) == 12
    snapshot = json.loads((folder / "tipd175.compiled.json").read_text(encoding="utf-8"))
    for component in root.findall("./components/comp"):
        block = snapshot
        for step in mapping[component.attrib["ref"]].split("."):
            block = block["blocks"][step]
        params = {k: v.get("value") for k, v in block["params"].items()}
        if component.findtext("footprint") != params["fp_footprint"]:
            raise ValueError("Footprint differs from compiled artifact")
        mpn = component.find("./property[@name='MPN']")
        if mpn is None or mpn.attrib["value"] != params["fp_part"]:
            raise ValueError("MPN differs from compiled artifact")
    report = {
        "connectivity": "pass",
        "components": 12,
        "nets": len(actual),
        "checker": "KiCad-exported XML versus EDG physical pin nets",
        "manufacturing_ready": False,
    }
    (xml_path.parent / "connectivity-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-xml", type=Path)
    args = parser.parse_args()
    if args.output:
        generate(args.compiled, args.output)
    if args.verify_xml:
        verify(args.compiled, args.verify_xml)
    if not args.output and not args.verify_xml:
        parser.error("choose --output or --verify-xml")


if __name__ == "__main__":
    main()
