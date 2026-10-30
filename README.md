# EviWeave · 证据织忆

Local, source-faithful memory retrieval with an optional ColBERT candidate index.

EviWeave 把对话和文档保存为带角色、时间及原文跨度的记忆，按查询检索并返回原文。它提供 Python 接口和本地 HTTP 服务，不调用生成式模型改写记忆或回答问题。

- 默认使用 exact Context Weave / SourceTrail **0.32.0 的原始检索与打包代码**，保留来源、规则、章节与邻接上下文。
- 可选 **ColBERT 全库独立召回**：从全部原生分块提出原前128名之外的新来源，再交给原版打包器。
- 使用 SQLite 持久化、幂等 Add、用户隔离和模型身份校验。
- 模型从本地路径加载；默认不下载模型，不向云端发送记忆。

**版本状态：0.1.0 研究发布。实验通道默认关闭，尚无完整配对最终答案增益结论，也没有新的官方评测成绩。** 继承源码不代表本包、示例编码器或新实验已经复现官方成绩。

## 一分钟运行

Python 3.10+，进入仓库根目录：

```shell
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[api,test]"
python -m eviweave demo
```

`demo` 使用合成示例和确定性的 HashEncoder，只验证功能，不代表语义模型质量；不需要 GPU、模型权重或账号。

启动本地服务：

```shell
python -m eviweave serve --encoder hash --port 18403
```

在另一个终端执行：

```shell
python examples/client.py
```

服务默认只监听 `127.0.0.1`。`GET /health` 查看状态，`POST /add` 写入原文，`POST /search` 返回证据。原文及向量保存在本地 `data/`，不进入 Git。

## 本地语义检索

```shell
python -m pip install -e ".[api,ml]"
python -m eviweave serve --encoder bge --model-dir ./models/bge-small-en-v1.5 --device cpu
```

先自行从模型官方来源取得 BGE 权重并放入本地目录；服务使用 `local_files_only=True`。HashEncoder 与 BGE 的数据库身份不同，切换编码器时使用新的 `--db`。

## Python 使用

```python
from eviweave import MemoryStore, HashEncoder

store = MemoryStore("data/demo.sqlite3", HashEncoder())
store.add(
    user_id="alice", request_id="note-1", session_id="session-1",
    messages=[{"role": "user", "content": "Luna prefers the blue feather wand."}],
)
hits = store.search(
    user_id="alice", query="Luna wand", top_k=5,
    mode="query_document_evidence",
)
print(hits)
```

## 验证与文档

```shell
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s tests/upstream -p "test_*.py"
python tools/release_audit.py
```

- [完整运行指南](RUNNING.md)：API、持久化、本地模型、实验开关、GPU锁和排错。
- [提交说明](SUBMISSION.md)：首次提交内容、验证方式和发布边界。
- [研究状态](docs/RESEARCH_STATUS.md)：已知负结果、开发诊断及未验证部分。
- [源码与模型身份](PROVENANCE.md)、[逐文件哈希](docs/source-manifest.json)。
- [更新记录](CHANGELOG.md)、[第三方声明](THIRD_PARTY_NOTICES.md)。

MIT License。原始版权及许可保留在 [LICENSE](LICENSE)。模型权重、训练数据及评测材料各自遵守其来源许可，不随本仓库分发。
