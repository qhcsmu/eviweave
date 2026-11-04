# EviWeave · 证据织忆

**参评版本：v0.3 · Textual Memory · 自托管 Add/Search API**

EviWeave 保存对话、文档、角色、时间和来源跨度，按问题返回可追溯的记忆证据。服务负责写入和检索，最终回答及评分由 AML 平台统一完成。

## Full 结果

2026年11月4日核对官方任务接口：原 Full 已于北京时间 **2026-11-04 00:48:22** 成功完成，**9602/9602** 项有效完成。

| 指标 | 官方返回值（百分制） | 完成情况 |
|---|---:|---|
| Overall | **53.40** | 9602/9602 |
| Streaming | **49.68** | 3993/3993 |
| Textual 分支 | 见官方分项结果 | 5609/5609 |

完整能力分项见 [Full 结果记录](candidate-v03/EVALUATION.md)。任务完成状态与公榜审核是不同步骤；本页不声明榜单名次，也不把研究演示或 Smoke 成绩当作本次 Full 成绩。

## v0.3 如何检索

1. **同步写入。** 原文及元数据写入 SQLite，持久化并可立即检索后返回成功；相同 `user_id + request_id` 的重复请求按幂等记录处理。
2. **限定用户范围。** `user_id` 是检索边界；同一用户的不同 `session_id` 可跨会话检索。
3. **保留上下文。** 使用 `text-embedding-v4`、1024维向量及原文证据打包。文档走既定文档路径；对话路径保留规则、事件和已有原文跨度。
4. **词元级选择。** ColBERTv2 加固定 LoRA，对原生前128项来源池中满足约束的完整来源做 MaxSim 匹配。利用可还原的时间头压缩节省预算，只有通过原文、顺序、字符预算及词元位置检查的方案才可加入额外来源；不满足条件时保持原结果。
5. **返回证据。** Search 输出按优先顺序排列的 `data` 数组，不生成答案、选项字母或评分。词元服务故障时返回503，避免静默替换受测实现。

正式 v0.3 使用上述固定来源池机制。仓库还保留了早期研究 CLI 和默认关闭的全库 ColBERT 实验，使用方法见 [研究包运行指南](RUNNING.md)。

## 正式源码与模型身份

| 项目 | 固定身份 |
|---|---|
| 系统 / 赛事版本 | EviWeave / v0.3 |
| 候选 ID | `eviweave-v03-search-credit-v34-cpu-reference-v36` |
| 部署 manifest SHA256 | `c2ccd8d8bb9e3b37412cb68cd3107df1967708400180d14fe46eb93ec7b1794c` |
| ColBERT 基础权重 SHA256 | `3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017` |
| 正式适配器 SHA256 | `d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619` |
| 查询修复源码 SHA256 | `5df870361bb3e804bc679e86ff13474e75f44c200a69b8b143d277d3770962e3` |

正式入口与初始24文件快照见 [candidate-v03](candidate-v03/README.md)；后续查询修复、Linux 运行代码和补充哈希见 [运行补充清单](candidate-v03/runtime-linux/SUPPLEMENT_MANIFEST.json)。初始冻结清单保持原样，后续差异单独登记。

ColBERT 在 Linux CPU 上常驻运行，保持 FP32 编码和 MaxSim、FP64 求和、unmerged LoRA、query32/window177/stride145、2线程。Qwen 分词器仅用于预算与位置检查，记忆服务不加载其生成模型。基础语义 embedding 使用外部 DashScope 接口；ColBERT 和预算分词器从本地工件加载。查询修复仅在供应商明确拒绝查询长度时启用，文档侧不启用该恢复。

模型与外部工件要求见 [正式运行指南](candidate-v03/LINUX_RUNTIME.md) 和 [模型身份](candidate-v03/MODEL_IDENTITY.json)。

## 赛事 API

参评时登记的路由如下。服务器目前由运营方关闭；下表是登记信息，不表示当前在线。

| 操作 | 地址 | 鉴权 |
|---|---|---|
| Add | `https://101.201.226.162/m02/add` | 已登记的 Bearer Token |
| Search | `https://101.201.226.162/m02/search` | 已登记的 Bearer Token |
| Health | `https://101.201.226.162/m02/health` | 无需鉴权 |

实际密钥仅通过赛事私有流程配置，不进入仓库。正式版本接收 Textual 字符串内容；多模态内容数组不在本版本支持范围内。

Add 请求：

```json
{
  "request_id": "example-write-1",
  "user_id": "example-user",
  "session_id": "example-session-1",
  "messages": [{"role": "user", "content": "The blue folder is in the study.", "timestamp": 1767225600000}]
}
```

持久化成功后返回 HTTP200：

```json
{"success": true, "request_id": "example-write-1", "user_id": "example-user", "session_id": "example-session-1"}
```

Search 请求：

```json
{"user_id": "example-user", "query": "Where is the blue folder?", "top_k": 100}
```

成功返回 `{"data": [...]}`；每项包含非空 `id`、原文 `content` 及可选排序分数。没有相关记忆时返回 `{"data": []}`，条目数不超过 `top_k`，顺序就是证据优先顺序。完整字段、幂等与错误处理见 [接口说明](candidate-v03/LINUX_RUNTIME.md#赛事接口约定)。

## Linux 常驻运行与复现

已部署环境由 `memory-lab@m02.service`（API，18102）和 `eviweave-m02-token.service`（词元 RPC，回环18403）组成，完成过开机启用及异常退出恢复配置。运行不再依赖个人 Windows 电脑或 SSH 反向隧道。

服务器开启后的只读检查：

```shell
systemctl status memory-lab@m02.service eviweave-m02-token.service
systemctl is-enabled eviweave-m02-token.service
journalctl -u eviweave-m02-token.service -n 50 --no-pager
```

完整重建需另行准备匹配的模型权重、适配器、分词器、资格元数据和私有配置；目录布局与边界见 [Linux 运行指南](candidate-v03/LINUX_RUNTIME.md)。评测或复核期间保留数据库、命名空间及幂等记录，维护按 AML 确认的兼容断点处理。

固定五组合成输入的 Windows/Linux CPU 对照通过：最大分数差 `6.0051679611206055e-06 < 1e-5`，来源选择、顺序和最终 Search 证据一致。该结论限于所测输入；延迟、容量和成本边界见 [容量记录](candidate-v03/CAPACITY.md)。

本地核验发布材料，无需模型、GPU或赛事账号：

```shell
python tools/verify_v03_snapshot.py
python tools/verify_v03_supplement.py
```

## 本地研究演示

仓库内 Python 包版本仍为 `0.1.0`。在独立环境运行：

```shell
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[api,test]"
python -m eviweave demo
```

`demo` 使用合成数据和 HashEncoder，无需模型或账号。演示接口与部署范围见 [RUNNING.md](RUNNING.md)。

## 材料索引

- [提交补充说明](SUBMISSION.md)：参评版本、固定提交及核验范围。
- [正式候选源码](candidate-v03/README.md)、[Linux 运行与接口](candidate-v03/LINUX_RUNTIME.md)、[官方 Full 结果](candidate-v03/EVALUATION.md)。
- [模型与工件身份](PROVENANCE.md)、[历史研究状态](docs/RESEARCH_STATUS.md)、[验证记录](docs/VALIDATION.md)。
- 赛事依据：[API Guide](https://agentmemoryleaderboard.ai/api-guide)、[Documentation](https://agentmemoryleaderboard.ai/docs)、[赛事说明](https://agentmemoryleaderboard.ai/competition/)。

源码按 [MIT License](LICENSE) 分发，保留版权与 [第三方许可](THIRD_PARTY_NOTICES.md)。模型权重、用户数据库、评测数据、答案、提示、日志和凭据不随仓库发布。
