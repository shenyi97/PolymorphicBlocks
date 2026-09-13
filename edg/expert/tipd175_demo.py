"""Generate review artifacts: python -m edg.expert.tipd175_demo --output DIR."""

import argparse
import json
from pathlib import Path

from ..core import Block, ScalaCompiler
from ..BoardCompiler import compile_board
from ..electronics_model.NetlistGenerator import NetlistTransform
from .tipd175 import Tipd175Fixture, dc_analysis, tipd175_registry


class Tipd175OneAmp(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=1.0))


class Tipd175TwoAmp(Block):
    def __init__(self) -> None:
        super().__init__()
        self.dut = self.Block(Tipd175Fixture(current_limit_a=2.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(
        "# TIPD175 review artifacts\n\n"
        "NOT FOR MANUFACTURING. Kelvin footprint/pad map is unreviewed; 2 A shunt part is unselected.\n"
        "No PCB routing, SPICE, stability, temperature or hardware validation.\n"
        "Read each analysis.json: offset/tolerance corner headroom fails even though nominal compile passes.\n\n"
        "## 审查说明\n\n"
        "1A 为原参考配置，2A 为计算变体。每版包含 12 个电子元件、10 个网络。\n"
        "BOM 为 tipd175.csv，网表为 tipd175.net，component-map.json 对应生成位号与 TI 位号。\n"
        "pin-nets.json 用于逐引脚审查，analysis.json 保留角点余量失败和验证边界。\n"
        "这不是制造发布：Kelvin 焊盘未核对，2A 分流电阻料号未选定，尚无 SPICE 或硬件验证。\n",
        encoding="utf-8",
    )
    (output / "catalog.json").write_text(json.dumps(tipd175_registry().list_modules(), indent=2), encoding="utf-8")
    try:
        for limit, board in ((1.0, Tipd175OneAmp), (2.0, Tipd175TwoAmp)):
            folder = output / f"{int(limit)}A"
            folder.mkdir(exist_ok=True)
            compiled = compile_board(board, (str(folder), "tipd175"))
            netlist = next(iter(NetlistTransform(compiled).run().values()))
            pin_nets = [
                [f'{".".join(pin.block_path.to_tuple())}:{pin.pin_name}' for pin in net.pins]
                for net in netlist.nets
                if net.pins
            ]
            (folder / "pin-nets.json").write_text(json.dumps(pin_nets, indent=2), encoding="utf-8")
            component_map = [
                {
                    "generated_refdes": block.refdes,
                    "ti_refdes": block.full_path.to_tuple()[-1],
                    "path": ".".join(block.full_path.to_tuple()),
                    "part": block.part,
                    "footprint": block.footprint,
                }
                for block in netlist.blocks
            ]
            (folder / "component-map.json").write_text(json.dumps(component_map, indent=2), encoding="utf-8")
            (folder / "analysis.json").write_text(json.dumps(dc_analysis(limit), indent=2), encoding="utf-8")
            print(
                f"{int(limit)} A: compiled {len(netlist.blocks)} parts, {len(pin_nets)} nets; manufacturing_ready=false"
            )
    finally:
        ScalaCompiler.close()


if __name__ == "__main__":
    main()
