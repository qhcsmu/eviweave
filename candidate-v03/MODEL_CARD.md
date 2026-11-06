# v0.3 正式检索适配器

本卡对应参评时已冻结的v29 step80工件，2026-11-04仅补充交付材料，没有重新训练或替换权重。

## 获取与身份

| 项目 | 固定记录 |
|---|---|
| 文件 | [adapter-step80.safetensors](https://raw.githubusercontent.com/qhcsmu/eviweave/082390824fae661659557adc74de14251522904e/candidate-v03/artifacts/adapter-step80.safetensors) |
| 大小 / SHA256 | 788,584字节 / `d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619` |
| 基础模型 | `colbert-ir/colbertv2.0`，revision `c1e84128e85ef755c096a95bdb06b47793b13acf` |
| 基础权重SHA256 | `3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017` |
| 张量 / 参数 | 17个FP32张量，196,608个参数 |
| 形式 | 最后4层（8–11）query/value LoRA，rank8、alpha16；另含完整训练后投影矩阵 |

这是自定义加载格式，不是可直接交给PEFT的标准目录。加载器和`metric_model.py`在[公开启动包](ARTIFACT_ACCESS.md)内，必须保持unmerged LoRA、FP32编码/MaxSim、FP64求和及原始query32/window177/stride145。SHA相同的基础模型与适配器共同构成词元模型。不能使用研究包中旧的`13d4b3…`适配器替代。

## 训练来源与许可

来源是[Bowen Jiang等人的PersonaMem-v2](https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/tree/ed956dea41521fc4499acbc63f966e0fd3c053ba)，固定revision `ed956dea41521fc4499acbc63f966e0fd3c053ba`。上游数据卡声明[CC BY 4.0](licenses/CC-BY-4.0.txt)，引用：*PersonaMem-v2: Towards Personalized Intelligence via Learning Implicit User Personas and Agentic Memory*, arXiv:2512.06688。改动包括：persona重新划分、原文分段/去重、重合排除、词元化和公开来源相关性标注转为正负例。原始来源署名和许可保留；不暗示数据作者或赛事方背书。

读取公开native train/val CSV的并集（18,549 / 2,061行），按persona重新划为24个训练、8个验证persona；两个原生CSV本身存在735个persona重用，不能把原生文件名当作独立性证明。最初排除全部200个benchmark persona及早先数值研究的16个persona，没有使用LoCoMo训练。完整native32K历史共有7,320条父消息、10,379个唯一role/span；按1000字符窗口、120重叠切分，无标注来源插入。之后应用冻结的v9排除账本。

最终保留训练477条查询 / 7,686个chunk，验证64条查询 / 2,645个chunk。仅问题、原始历史和公开相关消息标注用于检索训练；不以答案文本、选项文字/字母或评测成绩作训练目标。原始CSV具有其他字段，原始case/bank JSON会先完整解析再筛选，不能把“未作训练特征”写成“从未读取过含这些字段的文件”。公开的来源及指纹见[DATA_PROVENANCE.json](training/DATA_PROVENANCE.json)。

基础ColBERT元数据声明[MIT](licenses/COLBERT-MIT.txt)，包含的上游派生投影保留该许可。新发布的适配器按本仓库[MIT](../LICENSE)提供；这不改变训练数据的CC BY 4.0许可。预算分词器文件来自Qwen3.5-4B，适用[Apache 2.0](licenses/QWEN-APACHE-2.0.txt)。不同工件各自遵守其许可；软件许可不等于赛事训练来源准入。基础模型的上游预训练数据没有在本项目做完整独立审计。

## 冻结配方与选择

[RECIPE.json](training/RECIPE.json)原字节SHA256为`8dcd11744b0620a75cd40ca03446e08e13f7a0b92b34389c2fc951575fa9365a`，在本次训练前冻结。seed20261031，从原始基础权重初始化，不加载历史适配器或向量缓存。80次AdamW更新、160个microbatch、每批4查询，共640次查询呈现，覆盖全部477条训练查询。LoRA学习率1e-4、投影2e-5、常数学习率、weight decay0.01、梯度裁剪1；其余超参数见配方。

每条查询在8个固定候选上使用均匀多正例log-softmax；raw-body SHA等价正例合并，负例是同persona保留文本的原生BM25固定非正例，无模型挖掘。验证集不计算梯度。该配方只检查最终step80，未作本配方的epoch/LR/step扫描；设计参考过历史实验，这不是没有历史选择的首次试验。源码在公开启动包的`metric-space-v29/`原路径中；执行训练会另需公共GPU锁，本次未执行。

## 防污染措施及边界

v9审计在训练前冻结，检查576个固定本地保护案例及其169,185条来源记录；只用来源、问题/Search查询的哈希进行排除，不用评测答案、选项或成绩。检查包括Unicode规范化、空白处理、casefold后的完整文本、固定跨度、父消息，以及训练/验证之间的重复。

| 划分 | 查询：原始 → 保留 | chunk：原始 → 保留 |
|---|---:|---:|
| 训练 | 479 → 477 | 7,720 → 7,686 |
| 验证 | 64 → 64 | 2,659 → 2,645 |

训练排除了2条与保护问题/Search查询同一的查询。文档原因中，训练33条、验证13条涉及保护来源/父消息匹配，另有跨划分chunk/父消息重用；原因可能重合，不能直接相加。persona无交集仍可能共享文本，不能用persona隔离替代文本检查。[原审计聚合](training/ISOLATION_AUDIT.json)保留原字节；含逐记录指纹的原账本通过受控包交付。

这些检查不覆盖任意偏移子串、语义改写或基础模型上游预训练暴露，也不证明对未知正式Full内容完成了全量排除。正式评测已写入的记忆没有被回用于本适配器训练。不能宣称“完全无污染”或“赛事已认可来源”。

## 已有结果与成本

64条固定来源验证中，chunk MRR为0.31621820 → 0.35189056（38升、6降、20相同），chunk recall@10为0.28723958 → 0.30989583（8升、8降、48相同）；完整父消息支持仍为7/64（3升、3降）。不同来源MRR为0.32098825 → 0.35606365（39升、6降），来源recall@10为0.31380208 → 0.32552083（6升、8降），来源完整支持仍为8/64（2升、2降）。原记录见[TRAINING_RESULT.json](training/TRAINING_RESULT.json)。

训练耗时17.547秒、整个训练子进程55.297秒、GPU峰值971.683MiB，Answer/Judge调用0，货币费用未核算。这些是历史训练记录；本次仅做CPU文件校验。正式推理在CPU上运行。来源检索指标不是最终答案收益；[Full结果](EVALUATION.md)也没有单独证明适配器的因果收益或消除上述回退。

## 准入状态

**这份精确适配器及其训练来源的单独AML准入确认仍待补充。** 本地`source_gate.passed`只批准进入后续研究；原`MODEL_CARD.json`的历史研究状态保持。Linux等价迁移批复只覆盖运行平台与进程管理。Full完成、接口可用或代码许可都不能代替模型来源准入。[ADMISSION_STATUS.json](training/ADMISSION_STATUS.json)列出已有证据与待办，负责人应在原AML线程补交并取得明确回复。
