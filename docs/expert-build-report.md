# 本地构建与交付记录

日期：2026-09-13。上游基线：`bb18274e1494d43de20c2b41419246271f9724f6`。开发分支：`prototype/expert-library`。

## 已完成

- 完整克隆上游历史，远端命名 upstream，建立开发分支。
- 在任何原型源代码修改之前完成 `expert-library-design.md`。
- 安装隔离 Python 3.12.14 环境、上游 edg 依赖及工作区内 JRE 17。
- 新增 `edg/expert`：版本化元数据、证据、严格参数 schema、白名单注册、结构化编译适配器。
- 新增 6 个测试方法，覆盖真实生成器、重复编译、故意失败约束、非法参数、未知模块、环境异常和 JRE 配置。
- 核心兼容补丁：EDG_JRE_DIR；支持重复 close；处理未配置 stderr；关闭超时后终止 JVM。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 上游 editable 安装 | 成功 |
| 修改前 Block 基线 | 16/16 通过 |
| 修改前生成器 + Blinky，系统默认 GBK | 24 项，14 项在 UTF-8 网表读取时报 UnicodeDecodeError |
| 同一基线使用 -X utf8 | 24/24 通过 |
| 原型接口测试 | 6/6 通过 |
| 修改后 Block + 生成器 + Blinky + 原型 | 46/46 通过，37.796 秒 |
| git diff --check | 通过；只有 Git 的 LF/CRLF 提示 |
| Scala 源码构建、全仓库测试、硬件仿真／实测 | 本轮未执行 |

后续小改的最终复测结果追加在本文末尾。测试生成器是协议夹具，不是 TI 电路；Blinky 覆盖上游实际网表生成及其既有快照对比。

## 在此工作区复现

从仓库根目录运行 PowerShell：

```powershell
$env:EDG_JRE_DIR=(Resolve-Path '../../work/jre-17').Path
& '../../work/venv/Scripts/python.exe' -X utf8 -m unittest edg.core.test_block edg.core.test_generator examples.test_blinky edg.expert.test_api
git diff --check
```

新环境：用 Python >=3.9 创建 venv，运行 `python -m pip install -e .`，设置 EDG_JRE_DIR 为允许写入的位置，然后运行上述测试。首次运行需要网络下载 JRE。现有安装使用附带预编译 JAR，没有重建 Scala。

依赖实测版本：protobuf 7.36.1、sexpdata 0.0.3、Deprecated 1.2.14、typing_extensions 4.16.0、pydantic 2.8.2、pydantic_core 2.20.1、install-jdk 1.1.0、annotated-types 0.8.0、wrapt 1.17.3。这是环境记录，不是跨平台完整锁文件。

## GitHub CLI 与远端

已按用户要求将官方 GitHub CLI 2.100.0 安装在工作区 `work/tools/github-cli/bin/gh.exe`。用户完成设备授权后确认账号为 shenyi97。CLI 配置放在 `work/tools/github-config`，不将凭据写入仓库或报告。

已创建并通过 `gh repo view --json isFork,parent,url` 确认远程 fork：https://github.com/shenyi97/PolymorphicBlocks ，父仓库为 BerkeleyHCI/PolymorphicBlocks。开发分支为 prototype/expert-library，上游 master 保持原始基线。最终推送以远端分支 SHA 与本地 HEAD 一致为验收条件。

## 后续工作

1. 在远端开发分支继续迭代本原型，按 docs → SDK → TI 模块拆分改动。
2. 获取并核对 TIPD175 的原始资料，按设计文档的验收表实现器件与完整子电路。
3. 实现显式端口组合、可信环境载板及 BOM／网表交付接口。
4. 生产服务采用独立 Python worker、超时和只读专家库；改善 Scala 端异常详情并重编 JAR。

本轮不包含 TIPD175 实际实现、原理图自动生成、SPICE 验证或 PCB 布局。

## 最终局部复测

清理异常处理和类型注解补充后：`edg.expert.test_api` 6/6 通过（1.708 秒）；Black 以 Python 3.9 为目标检查 4 个源码文件通过；mypy 对新增包及改动核心文件检查通过（follow-imports=silent，不代表全仓库类型检查）。`git diff --check` 通过。

远端 CI 本轮未启用：尝试新增开发分支 smoke workflow 时，GitHub 因 OAuth 授权缺少 workflow scope 拒绝推送，因此移除了该新增配置，再推送源码与文档。没有扩大用户授权范围。既有上游 workflow 保留原样，开发分支推送不触发其 master-only push 条件。后续可在用户需要时配置 Python 3.10／3.13 的相同 46 项 smoke tests。
