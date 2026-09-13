# 专家接口原型用法

API 是本地 Python SDK，没有 HTTP 服务、MCP 服务或完整电路组合协议。外部调用者提供模块 ID、版本和公开参数；注册由可信专家代码负责。

```python
from pydantic import Field
from edg.core import FloatExpr, FloatLike, GeneratorBlock
from edg.expert import ExpertParameters, ModuleSpec, Registry

class Parameters(ExpertParameters):
    gain: float = Field(gt=0, le=20, description="Dimensionless gain")

class DemoGenerator(GeneratorBlock):
    # Protocol demonstration, not a physical circuit or TI implementation.
    def __init__(self, gain: FloatLike):
        super().__init__()
        self.gain = self.ArgParameter(gain)
        self.actual_gain = self.Parameter(FloatExpr())
        self.generator_param(self.gain)

    def generate(self):
        super().generate()
        self.assign(self.actual_gain, self.get(self.gain))

registry = Registry()
registry.register(
    ModuleSpec(module_id="demo.gain", version="0.1", description="Protocol demo"),
    Parameters,
    DemoGenerator,
)
description = registry.describe("demo.gain", "0.1")
result = registry.compile("demo.gain", "0.1", {"gain": 15.4})
print(result.model_dump_json(indent=2))
```

将 Block 定义保存到可导入的 Python 模块，再从调用程序 import，避免在临时交互上下文中定义无法被 HDL 回调解析的类。HDL 构造器使用 FloatLike 等上游表达式类型；外部参数模型使用严格的普通 Python 类型。

`list_modules()` 返回目录及参数 schema。`describe(id, version)` 对未知 ID 抛 KeyError；`compile` 对未知 ID 返回 unknown_module。输入验证错误不启动编译器。重复注册拒绝覆盖。参数传递通过 model_dump，复杂参数类型需要专家包装明确转换，不能假定任何 Pydantic 对象都能直接传入 HDL。

返回值包含 schema_version、模块版本、规范参数、success、diagnostics、snapshot 和 validation。诊断保留编译器 kind/path/name/details。字段校验错误使用 input_validation；环境或 Python 异常使用 runtime；清理失败使用 cleanup。

snapshot 是可读编译结果，不是可回写的完整 IR。`validation.compile=pass` 仅表示已运行的 EDG 模型检查通过；simulation 和 hardware 仍为 unverified。ModuleSpec.evidence 是专家声明的来源证据，不会自动升格为本次构建的验证结果。

当前每次请求创建独立 JVM 编译器实例，Python 调用受进程级锁串行化。注册及检索应在启动阶段完成；并发注册不是受支持 API。编译没有执行时限或独立 Python worker，尚不适合直接提供给不可信网络调用者。全局锁只约束本适配器，不能保护另行并发调用上游 ScalaCompiler 的代码。

带电气端口的真实模块必须提供明确的供电、接地、输入与负载环境；可注册专家编写的顶层测试载板，也可等后续组合接口显式连接。当前适配器不自动连接端口，不生成制造工件。

环境变量 `EDG_JRE_DIR` 指向 JRE 安装根目录，其中包含一个 jre/jdk 子目录。设置它可避免默认下载至用户主目录。Windows 建议使用 `python -X utf8` 运行；上游测试的默认编码读取与 UTF-8 网表存在不兼容。
