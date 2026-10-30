# 源码、模型与研究来源

## 原版来源

`adaptive_evidence/*.py` 从项目中经核验的 exact official Context Weave / SourceTrail0.32.0 源码提取副本逐字节复制。本发布未修改这些文件。原始源码归档SHA256：

```text
bff4443ee3cbdf4a5e320dfa56fb8e65ca7775d857550c4112de7ddb7a9c74fa
```

逐文件校验值在 `docs/source-manifest.json`。原始MIT版权声明保留在LICENSE，原版命名空间和版本号也保留；EviWeave0.1.0是新增封装的版本，不修改原版0.32.0身份。

原版 `preflight.py` 同样原样保留，供原生测试使用。历史 `adaptive_evidence.api`、`remote_encoder` 和该辅助脚本仍有远端embedding兼容能力，但不是EviWeave默认入口；本地运行使用 `python -m eviweave`。发布测试只对这些历史HTTP调用使用MockTransport，不发起真实远端模型请求。

## 实验来源

`eviweave/experimental/corpus_index.py` 逐字节来自固定的`corpus-index-v2/mechanism.py`；内容词元评分器来自同方向的`token_model.py`，ColBERT编码和LoRA加载器来自固定0.50源码参考。它们的哈希同样在清单中。这里只复用评分和适配器加载，不复用0.50的森林打包或整版检索服务。

查询保护表达式复制自固定研究代码；独立服务新增模型加载、生命周期、公共GPU锁和本地API封装。新封装的功能测试不能替代原固定配对研究；没有新增训练、没有用holdout结果调参。

## 模型身份

| 项目 | 固定身份 |
|---|---|
| ColBERT源 | `colbert-ir/colbertv2.0` |
| Revision | `c1e84128e85ef755c096a95bdb06b47793b13acf` |
| ColBERT权重SHA256 | `3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017` |
| 历史step80适配器SHA256 | `13d4b3a1af6d47d697f12e3970171d07c9bbbfa993521efda3c9bebb30021d04` |
| 本地Answer/Judge参考权重 | Qwen3.5-4B Q4_K_M，`2c9f9dcd9581c94510a1d033421114a67aedf7c948bcbd4f4aa4a01fb610880c` |

仓库不分发上述权重，也不在服务中加载Answer/Judge。历史适配器训练来自独立公开训练/验证来源，历史声明排除了全部评测persona；本次沿用既有身份与出处，不声称完成了对上游训练集的新独立泄漏审计。

原项目研究的本地BGE缓存、HF/GGUF分词差异和评估模型与官方环境不同；本包的任意本地BGE路径也不自动等同该缓存。功能复用不构成官方分数复现。

## 发布范围

仅发布源码、合成示例、测试、说明与模型身份。未发布任何数据集、题目、选项、参考答案、评测提示、用户历史、生成答案、日志、SQLite数据库、访问凭据或浏览器状态。原始数据、模型和评测材料仍留在原项目只读位置，不作为本仓库的安装依赖。
