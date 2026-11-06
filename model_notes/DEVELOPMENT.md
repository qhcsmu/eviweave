# 运行指南

本页描述包版本0.1.0的本地研究演示，其Search响应为`memories`。正式参评v0.3的Linux部署、`data`响应及模型配置见[candidate-v03/LINUX_RUNTIME.md](../candidate-v03/LINUX_RUNTIME.md)。在与正式服务共用的机器上，演示请显式使用其他端口，例如`--port 18503`。

## 1. 环境与安装

需要 Python 3.10+。基础功能只依赖 NumPy；服务、模型、测试按需安装。

```shell
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate
python -m pip install -e ".[api,test]"
python -m eviweave --version
python -m eviweave demo
```

若 PowerShell 不允许激活脚本，可直接使用 `.\.venv\Scripts\python.exe` 执行命令，不需要修改系统策略。

## 2. 启动 API

```shell
python -m eviweave serve --db ./data/memory.sqlite3 --encoder hash --port 18403
```

`hash` 是无需模型的词法演示编码器；真实语义检索使用后面的 BGE 配置。服务只提供检索，不内置 Answer/Judge。交互式 API 文档为 `http://127.0.0.1:18403/docs`。

健康检查：

```shell
curl http://127.0.0.1:18403/health
```

跨平台完整客户端：

```shell
python benchmarks/examples/client.py
```

### 写入

`POST /add`，JSON：

```json
{
  "user_id": "alice",
  "request_id": "note-1",
  "session_id": "session-1",
  "messages": [
    {"role": "user", "content": "Luna prefers the blue feather wand.", "timestamp": null},
    {"role": "assistant", "content": "It is stored in the hallway drawer.", "timestamp": null}
  ]
}
```

`timestamp` 可省略，或为 Unix 毫秒整数。相同用户的相同 `request_id`、相同请求内容重复提交时返回 `added_chunks: 0`；请求内容不同返回409，不覆盖历史。消息角色与原文保留。

### 检索

`POST /search`，JSON：

```json
{"user_id": "alice", "query": "Where is Luna's wand stored?", "top_k": 5}
```

返回 `{"memories": [...]}`。每个结果有稳定跨度ID、带角色和可选时间的原文内容，以及排序分数；分数是排序值，不是答案置信度。`top_k` 为1–100；可提供 `options`，默认路径保持原版对选项的对称低权重检索视图，新增 ColBERT 匹配只看查询。不存在的用户返回空结果。

检索默认 `query_document_evidence`、24000字符预算，原生块1000字符、重叠120字符。最终 Answer 的 token 打包和提示由调用方负责，本服务的字符预算不等于4096个模型token。

### 可选本地认证

在启动服务和客户端的终端各设置 `EVIWEAVE_API_TOKEN`。服务读取环境变量，写入/检索请求使用 `Authorization: Bearer ...`。不要将真实值写入仓库。默认启动器仅允许回环地址；本项目没有自动公网部署脚本。

## 3. BGE 本地模型

```shell
python -m pip install -e ".[api,ml]"
python -m eviweave serve --encoder bge --model-dir ./models/bge-small-en-v1.5 --device cpu --db ./data/bge.sqlite3
```

模型官方来源：`https://huggingface.co/BAAI/bge-small-en-v1.5`。先在允许联网的下载阶段取得模型，确保本地目录包含配置、权重和分词器。运行阶段只从该目录加载，不自动联网。编码器使用CLS、L2归一化、最大512-token；完整原文另行保存，嵌入截断不删除原文。

编码器/模型/分块身份绑定数据库。更换模型、Hash/BGE模式或分块设置时新建数据库；不要删除身份校验来复用不兼容向量。

## 4. ColBERT 实验通道（默认关闭）

此通道没有已证明的最终答案提升。它索引全部原生分块，选出学习排序前10个不同来源，只提名原排名前128项未覆盖的来源，并与原排名交错后执行原版打包。文档、规则请求、多事件请求、CJK及超出固定查询长度的请求回到原版；原版返回的规则项若被改变或遗漏，整题恢复原版。

```shell
python -m eviweave serve --encoder bge --model-dir ./models/bge-small-en-v1.5 --db ./data/experimental.sqlite3 --experimental-colbert --colbert-dir ./models/colbertv2.0 --colbert-device cpu --index-dir ./data/colbert-index
```

固定官方模型来源：`colbert-ir/colbertv2.0`，revision `c1e84128e85ef755c096a95bdb06b47793b13acf`。模型身份和SHA256在 `model_notes/source-manifest.json`；加载时核验权重身份。完整分块使用重叠窗口编码，不静默丢弃尾部。

上述命令使用基础权重，是一个未评分的配置，**不等于训练适配器版本**。复现原研究的step80配置时，还需在命令末尾指定：

```shell
--adapter-path ./models/retrieval_adapter.safetensors --adapter-sha256 13d4b3a1af6d47d697f12e3970171d07c9bbbfa993521efda3c9bebb30021d04
```

仓库不分发适配器、其他模型权重或训练/评测数据。仅提供加载器与固定身份；若没有匹配适配器，不能声称复现训练版。索引与模型身份绑定，更换模型时使用新的 `--index-dir`。

## 5. GPU 与共享锁

CPU演示不需要GPU锁。任何GPU模型启动都要求显式的公共锁目录，先原子创建锁再加载模型，服务退出后仅由持有者释放：

```shell
python -m eviweave serve --encoder bge --model-dir ./models/bge-small-en-v1.5 --device cuda:0 --gpu-lock-dir ./shared/local-model.lock
```

与其他研究共用机器时，`--gpu-lock-dir` 必须指向所有研究实际共用的那一个目录，不能新建私人锁绕过协调。原项目共用的是 `competition/research/parallel-seven-20261030/local-model.lock`；私有服务端口18403。实验 ColBERT 可另设 `--colbert-device cuda:0`，遵守同一把锁。锁已存在时启动失败，不抢锁、不清除他人锁、不停止他人服务。等待期间可以做CPU分析。

## 6. 验证

```shell
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s benchmarks/tests/upstream -p "test_*.py"
python artifacts/tools/release_audit.py
```

测试使用合成数据/假编码器，不运行 GPU、不提交官方评测、不需要评测答案。它们检验API、隔离、幂等、持久化、原文预算、规则回退及锁所有权，不构成语义模型准确率评估。

## 7. 常见问题

| 现象 | 处理 |
|---|---|
| `Database uses a different model...` | 为新编码器或模型使用新的 `--db`，保留旧数据库。 |
| `Model lock is occupied` | 等持有者完成；不要删除他人的锁。 |
| `Provide an existing local BGE model directory` | 先取得模型，检查 `--model-dir`，运行阶段不会替你下载。 |
| ColBERT checkpoint/adapter hash mismatch | 使用固定版本与匹配SHA256；不要跳过校验。 |
| 端口18403被占用 | 原项目不要终止别人的服务；等待端口可用。独立环境可显式选别的本地端口。 |
| 检索到了证据但回答错误 | 检索覆盖不等于阅读或最终答案正确；用固定模型与原生评分做配对验证。 |

需要备份时正常停止自己的服务，再复制SQLite数据库；若服务运行中，使用SQLite备份API，避免只复制主文件而遗漏WAL事务。
