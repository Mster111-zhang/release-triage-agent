# 基于多源证据的发布异常归因 Agent

张艺豪的求职作品。输入告警并选择模拟场景，也可以导入自己的结构化证据。Agent 根据已有信息决定下一项查询。报告包含原因、证据编号与后续核对建议。

## 在 Windows 本机启动

从 PyCharm 打开本目录，选择已安装的 `.venv\Scripts\python.exe`。也可以在项目目录的 PowerShell 运行：

```powershell
.\uv.exe run --offline --frozen --no-sync python -m release_triage.main
```

浏览器地址为 [127.0.0.1:8767](http://127.0.0.1:8767)。在终端按 Ctrl+C 结束。重新安装环境时用 `uv sync --locked`。

## 项目设计

- `release_triage/data.py` 定义证据格式与 SQLite 查询。SQL 使用参数化的场景、来源及 UTC 查询时段。
- `release_triage/agent.py` 定义 LangGraph 的决策与查询节点。决策节点先检查证据充分性，再决定下一项查询。每类来源最多查一次。证据缺失、同时间点数值冲突或关键时间顺序不匹配时，允许返回证据不足。
- `release_triage/main.py` 校验证据包，并向 FastAPI 客户端返回诊断、原始证据和调用轨迹。`release_triage/web` 展示每一步的来源、查询时段和用时。
- `release_triage/evaluate.py` 保存评测标签。比较 Agent 与「有发布就归因发布」的基线，并检查每条引用确实来自本次查询。

## 导入你自己的结构化证据

页面的事故场景里选择「导入自定义证据」，可以下载并上传 `release_triage/web/example-incident.json`。证据包包含告警 `alert` 与最多 100 条 `records`。每条需要唯一的证据编号、来源、同一 UTC 日期的 `HH:MM` 时刻、信号名与说明，数值型信号按要求携带前值和后值。三个来源分别是 `releases`、`logs` 和 `metrics`。应用识别的信号名及要求写在 `data.py` 的 `SIGNALS` 中。

改示例里的配置、日志或指标再跑一次。例如，把发版时间改到超时日志之后，原先的发布归因就无法通过时间顺序校验。报告里的证据编号可以定位到查询结果。

## 离线评测

```powershell
.\uv.exe run --offline --frozen --no-sync python -m release_triage.evaluate
.\uv.exe run --offline --frozen --no-sync python -m unittest discover -s tests -v
```

重点案例是「演示 02 · 支付请求积压」。虽有同时间发版，变更记录和支付 P95 指标表明超时源于下游变慢。「演示 04」用来验证证据缺失时输出待补充结论，「演示 06」验证在确认结算指标稳定后能提前结束查询。数据是本项目的合成案例，结果只描述这些案例的表现。

## 可选接入百炼

使用本机环境设置 `DASHSCOPE_API_KEY` 后启动服务，界面即可选「百炼模型」。默认使用华北 2 的兼容地址和 `kimi-k3`。如工作空间在其他地域，可在本机设置 `BAILIAN_BASE_URL` 和 `BAILIAN_MODEL`。

本地策略无需密钥。在线模式会把告警与已查到的证据发送到百炼，让模型选择工具及可选的 `start`、`end` 参数。程序校验参数，再执行查询。请求失败或参数无效会切回本地策略，调用轨迹会标出原因。模型请求可能计费。在线协议、查询过滤和回退逻辑可以通过模拟响应测试。

## 面试时怎么讲

先用「演示 02」说明为什么仅看发版时间会归错原因，再用自定义证据包演示一次工具参数或时序变化怎样影响结论。顺序讲清三个环节：

1. **模型负责选择查询。** 说明工具描述、时间参数的约束，以及怎样处理无效调用。
2. **程序负责获取和校验证据。** 说明 SQLite 查询范围、时间顺序检查和报告引用来自哪一行记录。
3. **评测验证行为。** 分别检查分类、引用和故障回退。对照成绩只反映固定的合成案例。

## 来源和开发记录

这个目录是新实现。原仓库 [incident-investigator](https://github.com/knocBack/incident-investigator) 作为选题参考，应用、界面和案例数据独立编写。初版在 Codex 协助下完成。按实际工作记录今后补充的案例、评测、实现和设计取舍，可用于简历和面试。


## 网页免费体验

[打开演示](https://mster111-zhang.github.io/projects/release-triage/) · [个人作品集](https://mster111-zhang.github.io/)

网页演示在浏览器中执行 JavaScript 规则，支持内置案例和结构化证据导入。此仓库提供完整 Python、LangGraph 和 FastAPI 实现。在线百炼调用需在自己的电脑配置密钥。

## 本机试用 Kimi K3

在项目根目录的 PowerShell 设置本机密钥后，运行服务，再在页面选择百炼模型：

```powershell
$env:DASHSCOPE_API_KEY = "在本机填写密钥"
$env:BAILIAN_MODEL = "kimi-k3"
.\uv.exe run --offline --frozen --no-sync python -m release_triage.main
```

接口地址和密钥需来自同一百炼地域。可用 `BAILIAN_BASE_URL` 指定控制台给出的兼容地址。新安装使用 `uv sync --locked`，并用 PATH 上的 `uv` 执行命令。

Kimi K3 使用默认采样参数，请求超时设为 60 秒。此处配置与调用协议通过模拟响应检查，真实账号连通性需要本机密钥验证。网页公开体验无需填写密钥。

调用说明见 [百炼 Kimi 官方文档](https://help.aliyun.com/zh/model-studio/kimi-api)。
