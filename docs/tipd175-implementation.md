# TIPD175 首个专家模块：实现边界

依据 MinerU VLM 解析的 TIDU675、TIDRG85、TIDRG86 和 OPA313 数据手册，以及 TIDRG85 第 1 页视觉核对。源文件、完整解析工件保存在本任务 work/tipd175-sources；版本化仓库保存来源与校验和，不复制整份第三方文档。

本轮实现 3.3 V、25°C、DC 的低侧双向电流检测电路，固定 TI 的电阻比和参考分压，仅开放 ±1 A 原始配置与 ±2 A 计算变体。±2 A 使用 50 mΩ 候选分流电阻，尚未完成具体料号选型。参数范围是本原型支持策略，不能说成 TI 产品适用范围。

## 已核对拓扑

- U1A: 1 OUT，2 IN-，3 IN+；U1B: 5 IN+，6 IN-，7 OUT；4 GND，8 VCC。器件 OPA2313IDGK，VSSOP/MSOP-8。
- R1: shunt sense+ → U1.3；R2: U1.7 → U1.3；R3: shunt sense- → U1.2；R4: U1.1 → U1.2。
- R5: VCC → U1.5；R6: U1.5 → GND；U1.6 与 U1.7 直接连接。
- C1=10 µF 钽、C2=0.1 µF、C3=100 pF 均接 VCC/GND。C1 正极接 VCC。
- R1/R3=1 kΩ、0.1%；R2/R4=15.4 kΩ、0.1%；R5/R6=10 kΩ、0.5%。RL=10 kΩ、1% 属于验收载板，模块外部负载显式建模。
- Ohmite LVK12 是四端 Kelvin 器件。current+/current- 和 sense+/sense- 保留为不同网络，禁止在模块里短接成普通两端元件。

## 模型与校验

保留真实器件、无源件和逐引脚连接的 Block 图，使用 GeneratorBlock 联动 shunt 阻值与功耗。模拟闭环采用模块级 DC 行为约束；运放输入和内部反馈为 Passive，不声称已有通用 SPICE 级运放求解器。边界供电使用 VoltageSink，输出使用 AnalogSource；显式检查 3.3 V 供电、名义输出摆幅、功耗降额及负载下限。电流激励是公开工况参数，本轮尚未实现跨模块自动传播负载电流的端口。

TI 简化公式 Vo=1.65+15.4*I*Rshunt 作为标称目标；独立电阻网络 DC 分析考虑参考经 R2/R1 对分流节点的微小注入。有限阻值容差与运放最大偏置的角点分析单独报告，不将 TI 的实测精度移植为新实现保证，也不强行截断输出误差范围来通过检查。

生成 netlist/BOM/编译快照供审查；制造就绪状态必须为 false。原因：LVK12 的四焊盘物理映射尚待原厂尺寸及 CAD 核查，网表使用明确的 ExpertUnreviewed 占位封装；±2 A 变体 shunt 料号未选定。常规 0603 与 DGK 封装也未做独立 PCB 制造验证。实际 PCB 布局、瞬态、稳定性、EMI、温升及实测均为 unverified。

不使用原来的 DifferentialAmplifier 直接替换 TI 回路：它的 E-series 自动选择、参考符号命名和信号范围截断不利于首轮逐元件追溯。复用 EDG 的 Block／GeneratorBlock、类型端口、编译器和导出后端；此模块固定连接并保留 TI designator。

## 验收

正向：原配置、2 A 变体、公开参数 schema、真实 Scala 编译、12 个电子元件（含 RL 的载板）、各引脚网络逐项比较、shunt 额定功率与 operating power 比较。

反例：非法电流、非 3.3 V 供电、过重外部负载、过低 shunt 功耗预算；底层直接调用 Block 也执行约束，不能仅依赖 API 参数校验。

DC 分析测试独立建立节点电导矩阵，与模块计算结果对比，避免只重复同一个公式。原 ±1 A 的 0.11/3.19 V 是名义目标，不是所有容差角点的保证。

## 来源追溯和解析质量

完整来源、SHA-256、MinerU VLM 批次和解析工件哈希见 [tipd175-sources.json](tipd175-sources.json)。2026-09-13 完成四份文档的服务解析。MinerU 返回的 origin PDF 与本地按相同 URL 下载的 PDF 字节不同；分别记录哈希，不声称两者输入字节一致。关键电路连接和失调／摆幅参数已对本地原件视觉核对。

| 依据 | 位置与用途 | 核对状态 |
| --- | --- | --- |
| TIDU675 | PDF 第 2、5 页：拓扑和电阻计算；第 13 页 BOM | MinerU 正文／公式解析；最终连接以专门原理图为准，修订日期未独立核对 |
| TIDRG85 | 第 1 页，Rev B，图纸日期 2015-07-27 | MinerU 输出不能可靠恢复网络；已逐引脚视觉核对，包括 C3 与 Kelvin 端子 |
| TIDRG86 | 第 1 页 BOM | MinerU 表格用于料号、容差及额定值追溯；机械件和测试点未纳入原型 |
| OPA313 数据手册 SBOS649C，2013-03 修订 | 第 3 页失调、第 4 页输出摆幅 | MinerU 表格与原页视觉核对；某些解析脚注温度字符损坏，未直接采信 |
| [Ohmite LVK 产品页](https://www.ohmite.com/res-lvk/) | LVK12 四端结构、1206、0.5 W | 原厂网页核对；焊盘尺寸与编号尚未批准 |

2.5 mV 失调来自数据手册特定测试条件。本轮将其作为 3.3 V 理想 DC 分析的假定输入，未计入 PSRR、CMRR、输入偏置电流、有限开环增益等误差，不能视作完整最坏误差包络。100 mV 摆幅余量沿用 TI 参考设计目标；数据手册第 4 页的 2 kΩ 测试条件也不等同当前 10 kΩ 对地负载。15 mA 典型短路电流没有用作保证驱动能力。

## 当前结果与调用

±1 A 的理想节点解为约 0.110164／1.650155／3.190146 V；±2 A 为 0.110082／1.650077／3.190073 V。512 组电阻／失调符号角点在两个满量程端点得到约 0.047～3.259 V，超出 0.1～3.2 V 目标余量。报告保留此失败；它既不是 SPICE 结果，也不证明实体电路必定在此范围。

输出端口保守声明 0～3.3 V 电压和信号范围，未把名义输出误当成保证。参考输出暂不支持外部连接，直接 Block 调用也会拒绝外部加载。2 mA 供电预算与 0.33 mA 输出边界是此 DC 夹具的设计约束，不是通用运放能力模型。负载模型使用标称阻值，负载容差和动态特性未纳入分析。

```python
from edg.expert.tipd175 import tipd175_registry, dc_analysis

registry = tipd175_registry()
schema = registry.describe("ti.tipd175.dc_fixture", "0.1.0")
result = registry.compile("ti.tipd175.dc_fixture", "0.1.0", {"current_limit_a": 2.0})
analysis = dc_analysis(2.0)
```

公开注册项包含显式供电和负载夹具，供 AI 选择参数并检查诊断。可复用子电路本体为 `Tipd175`。本轮不开放任意 Python 导入或自动拼接任意接口。

从仓库根目录生成审查工件：

```powershell
$env:EDG_JRE_DIR=(Resolve-Path '../../work/jre-17').Path
& ../../work/venv/Scripts/python.exe -X utf8 -m edg.expert.tipd175_demo --output ../TIPD175-review
```

每个变体输出 KiCad 网表、BOM、编译快照、逐引脚网络、分析报告和位号对应表。R1～R6、C1～C3、U1 保留 TI 位号；自动生成的 R7 对应 TI Rshunt，R8 对应 RL，见 `component-map.json`。没有生成完整传统原理图或 PCB。

后续优先核对 Kelvin 封装及 50 mΩ 料号，导入官方运放模型进行 DC／稳定性仿真，再决定扩大参数空间或增加模块组合接口。
