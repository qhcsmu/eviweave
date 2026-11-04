# 源码、模型与研究来源

## 正式版本索引

赛事版本v0.3的源码与模型见[candidate-v03](candidate-v03/README.md)；正式适配器SHA256为`d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619`。正式查询修复、Linux适配与依赖另列于[运行补充清单](candidate-v03/runtime-linux/SUPPLEMENT_MANIFEST.json)。以下记录根目录0.1.0研究包的技术身份，历史适配器不等同于正式候选。版权和第三方许可保留。

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
