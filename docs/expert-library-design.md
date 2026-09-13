# 专家参数化子电路 fork 原型设计

日期：2026-09-13。本文先于原型源代码修改完成，作为首轮实现边界。

## 目标和当前阶段

专家维护带适用条件的 Block / GeneratorBlock；AI 只检索模块、提交公开参数、组合端口并读取诊断。第一阶段实现目录与调用契约、编译适配器；TI TIPD175 是后续首个完整电路验收对象。本阶段不把公式计算器冒充经过验证的 TIPD175 电路。

源码基线：`BerkeleyHCI/PolymorphicBlocks`，`bb18274e1494d43de20c2b41419246271f9724f6`，Python 包 `edg==0.5.2`。完整 Git 历史已克隆。本地 `upstream` 指向 https://github.com/BerkeleyHCI/PolymorphicBlocks.git 。工作分支：`prototype/expert-library`。

设计落盘时远程 fork 尚未创建；随后经用户授权，已通过 GitHub CLI 创建并验证 https://github.com/shenyi97/PolymorphicBlocks ，父仓库为 BerkeleyHCI/PolymorphicBlocks。origin 用于该 fork，upstream 只用于同步原项目。最终提交和推送状态见构建记录。

## 源码分析与扩展位置

| 能力 | 实际代码位置 | 结论 |
| --- | --- | --- |
| 层级模块、接口、连接 | `edg/core/HierarchyBlock.py`、`Ports.py`、`Blocks.py` | 复用既有 Block、Port、connect 与 require；不另造底层电路 IR。 |
| 参数化生成 | `edg/core/Generator.py::GeneratorBlock` | 用 generator_param 显式声明依赖，在 generate 中通过 get 取求解结果；只能依赖支持的构造参数、端口请求及连接状态，不能任意读取内部未求解量。 |
| 约束表达与传播 | `edg/core/ConstraintExpr.py`、`compiler/src/main/scala/edg/compiler/` | Python 形成表达式，Scala 展开与传播；跨候选实现的搜索由外层调度，不能假设编译器会做任意全局优化。 |
| 实现选择 | `edg/core/Refinements.py::Refinements` | 支持类／实例细化和参数值；AI 接口第一版不开放任意 refinement 或 Python 类路径。 |
| 电流检测复用 | `edg/circuits/OpampCurrentSensor.py` | 已有采样电阻、差分放大器和浮动输出参考组合，但不是 OPA2313 的 TI 完整实现。 |
| 差分放大器 | `edg/circuits/OpampCircuits.py::DifferentialAmplifier` | 已有 GeneratorBlock、阻值选取和实际增益；可作为专家模块的内部子电路。 |
| 原理图导入 | `edg/electronics_model/KiCadSchematicBlock.py`，`getting_started_schimport.md` | 导入满足约定的 KiCad 子电路并补充模型；不是通用 TI PDF 转换器。 |
| 编译和诊断 | `edg/core/ScalaCompilerInterface.py` | CompiledDesign.errors 已含 path/name/kind/details。用 ignore_errors=True 保留结构化错误；不要只抓取终端文本。 |
| 快照 | `edg/core/CompiledDesignExport.py` | Pydantic/JSON 包含层级、参数和连接；代码有完整约束导出 TODO，不能作为可往返编辑设计源。 |
| 交付 | `edg/BoardCompiler.py::compile_board` | 导出 .edg、.net、BOM、SVGPCB 和 compiled.json。失败时可能只留下 .edg；AI 适配器需独立提供诊断。没有完整 KiCad 原理图输出。 |

## 设计决策

新增 `edg/expert/`，保持 Scala、protobuf、现有 Block 和器件库兼容。专家目录通过 Python 显式注册可信 Block 类型和 Pydantic 参数模型；外部请求只能给出版本化模块 ID 和参数字典。拒绝额外字段、非法值、未知模块和任意导入路径。目录支持列举及单模块说明，其参数 schema 可直接供后续工具调用使用。

元数据包括：稳定 ID、版本、能力说明、来源链接、端口说明、适用条件，以及逐项证据。证据区分 reference、calculation、compile、simulation、hardware，状态区分 pass/fail/unverified，并记录具体工况、工件和说明。引用 TI 实测资料不意味着本 fork 的实现或参数变体也经过实测。元数据本身不是电气约束执行器；可执行规则仍在参数模型与 Block.require 中。

编译适配器返回版本化 JSON envelope：请求模块与版本、规范化参数、成功标志、结构化诊断、编译快照和验证范围。仅在无编译错误时标记 compile pass；仿真／实物状态保持 unverified。编译成功不直接给出 design_verified。保留错误 path/name/kind/details，输入验证错误保留字段位置。运行时异常单独归类，不混同电气规则错误。

由于底层编译入口接受无参顶层类型，参数通过可信包装 Block 实例化子模块。包装类必须在模块命名空间可解析，以适配 HDL 回调；首次原型限制单进程串行调用，结束后清理临时绑定。生产服务使用独立 worker 进程、超时和资源限制。注册白名单只是调用边界，不是 Python 沙箱；有源码写权限的 AI 仍能修改专家库，生产部署须另设只读库和审查发布流程。

首轮只验证单模块编译协议。端口组合 DSL、BOM／网表交付 API、模块检索排序、跨模块搜索暂留后续。协议不得声称支持未实现的 compose 接口。

## 构建流程与已发现问题

- Python 要求 >=3.9；CI 覆盖 3.10/3.13，本机隔离环境为 3.12.14。`python -m pip install -e .` 已成功。
- 核心编译使用仓库附带 `edg/core/resources/edg-compiler-precompiled.jar`，运行需要 JRE 17；只改 Python 无需重编 Scala。
- 若改 Scala：JDK 17、sbt 1.9.9、Scala 2.13.14；在 compiler 目录执行 `sbt +test` 与 `sbt assembly`，本地构建 JAR 优先于预编译 JAR。本机未配置 sbt，不声称已验证源码重编译。
- `developing.md` 中部分路径仍写 edg_core，执行时应使用实际目录 edg/core，测试包名是 edg.core。
- 上游 JRE 下载路径写死为用户目录 `.edg/jre-17`；本任务基线通过显式设置 ScalaCompiler.kInstallJrePath 指向工作区，避免写入用户主目录。首轮补充可选 `EDG_JRE_DIR` 环境配置，未设置时维持上游行为。
- 上游 ScalaCompilerInstance.close 无条件关闭未配置的 stderr，存在资源清理风险；本轮如新增独立实例生命周期管理应同时修复并测试。
- 基线 `edg.core.test_block` 16 项通过；生成器与 Blinky 的 JRE 下载／编译测试在本文落盘时运行中，最终结果单独记录。

## Fork 和分支策略

保留 master 作为上游基线，不改变上游包名、不发布到上游 PyPI。开发在 prototype/expert-library；按文档、SDK、TI 模块、导出扩展拆分后续提交。先记录基线 SHA，再维护小型兼容补丁。更新时 fetch upstream，单独分支验证升级和模块回归后再合入开发线。不要把 fork 的历史兼容性寄托于永远固定 master 最新状态。

远程 fork 接入后将 origin URL、创建状态和推送 SHA 写入构建记录。没有可验证远端时不得宣称 fork 或推送完成。

## TIPD175 后续验收方案

来源入口：https://www.ti.com/tool/TIPD175 。下一阶段下载设计说明、BOM、原理图及仿真模型，记录文档修订、文件校验和和对应页码；先逐项核实原对话中的数值，再编码。

分成 OPA2313 器件模型、低侧采样子电路、中点参考缓冲、完整 TI 模块和测试载板。需审核双运放封装分配、引脚映射、输入共模、输出摆幅、供电／负载、采样电阻额定功率及温度降额、阻值容差、参考误差和布局约束。原模块保持 Block／GeneratorBlock，计算逻辑与实际选型结果均可追踪。

验收：原始设计元件／网络对比；标称传递关系；±2 A 等候选变体的功耗联动；不可支持参数的拒绝；断电／失配供电／输出过载等反例；仿真波形与 TI 基准对比。没有仿真模型或实测工件的项目标为 unverified。布局和实物结果独立记录，不由编译通过替代。

## 本轮代码验收

1. 可注册与检索可信专家模块并导出 JSON schema。
2. 非法参数、未知字段和未知模块产生结构化错误；重复注册不覆盖已注册实现。
3. 真实 GeneratorBlock 通过预编译 Scala JAR 执行并导出求解值。
4. 故意失败的 Block.require 保留编译器错误位置。
5. 现有 Block、生成器与 Blinky 回归继续通过。
6. JRE 路径可放在工作区；资源清理不会掩盖原始编译错误。

最后将精确命令、测试结果与仍未完成事项写入 `docs/expert-build-report.md`，方便下一阶段直接继续。

## 独立源码复核补充

- `compiler/src/main/scala/edg/compiler/CompilerError.scala` 的 LibraryError／GeneratorError 中部分字符串直接写出 err，异常详情可能丢失。后续修改须同时测试 Scala、重建 JAR 并绑定版本，本次不只改源码而继续运行旧 JAR。
- CompilerServerMain 内部失败可能返回没有 design 的结果，Python 编译适配层此时断言失败。当前 API 归为 runtime；更完整的协议诊断是下一次兼容补丁。
- `KiCadSchematicBlock.import_kicad` 包含 eval 路径。生产 AI 请求不直接接收任意上传原理图并导入，应只引用经过专家审查的资源。
- Refinements 拼接及 protobuf 到 map 转换不是可靠的冲突处理 API；公开接口不开放任意内部参数覆盖。
- 本次包装只创建 module 子块，不推断供电和负载。带外部端口的专家电路需要注册可信测试载板／环境包装，或后续实现显式组合请求。未连接端口产生编译错误是预期行为。
