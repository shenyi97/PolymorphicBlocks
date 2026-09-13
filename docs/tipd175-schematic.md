# TIPD175 可编辑原理图模板

已依据 TI TIDRG85 Rev B 原图独立重绘，生成 1 A 和 2 A 两个 KiCad 工程。图中包含真实符号、引脚、导线与网络标签，不是把原图图片放进编辑器。

## 打开

- 1A/tipd175.kicad_pro：原参考配置，R7=100 mΩ。
- 2A/tipd175.kicad_pro：计算变体，R7=50 mΩ。
- 同目录 tipd175.kicad_sch 可在 KiCad 10 编辑；tipd175.pdf / .svg / .png 用于查看。
- Expert.kicad_sym 和 sym-lib-table 是随工程附带的符号库，请保留在一起。
- R7 对应 TI 的 Rshunt，R8 对应 RL；U1A/B/C 是同一颗双运放的信号单元与电源单元。

## 模板工作方式

仓库 edg/expert/tipd175_schematic.py 固定符号位置和连线，从编译快照读取阻值、电容、料号和封装。1 A 与 2 A 使用同一布局。它是 TIPD175 专用布局生成器，不是任意网表的自动排版器。可编辑生成的 .kicad_sch；如需长期保留布局修改，应同步修改生成器，重新生成会覆盖原理图。

在仓库根目录执行：

```powershell
& ../../work/venv/Scripts/python.exe -X utf8 -m edg.expert.tipd175_schematic --compiled ../TIPD175-review/1A --output ../TIPD175-schematic/1A/tipd175.kicad_sch
```

KiCad 10 CLI 导出 kicadxml 后，运行同模块的 --verify-xml 参数。检查器比较全部元件引脚组成的网络、实际料号和封装，不仅比较网络名称。

## 验证与边界

两版均由 KiCad 10.0.4 成功导出 XML 网表、PDF 和 SVG。各 12 个物理元件、10 个网络与 EDG 编译工件完全一致，料号和封装也一致，详见 connectivity-check.json。已视觉检查渲染页。

ERC 每版保留 4 项，未隐藏：2 项外部供电未声明驱动，1 项电流输入标签只连接单个引脚，1 项 Kelvin 占位封装库未解析。前三项来自当前显式外部激励边界；最后一项必须在制造前核对封装与焊盘。此结果不能称为 ERC 全通过。

制造状态仍为 false，2 A 分流电阻未选定料号，角点输出余量失败尚未解决，也没有 SPICE 或实物验证。图中只保留电子电路，未复制 TI 测试点、机械件和品牌标识。源资料处理仍遵循 MinerU，当前渲染的是本地新生成文件。
