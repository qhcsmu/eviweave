# EviWeave v0.3 已部署候选的源码对应

这里保存现有 v36 的逐字节源码快照和部署映射。它与仓库根目录的0.1.0研究CLI、可选全库实验是不同发布范围。加入快照没有改变受测代码、模型、接口或参数，也不是新的优化实验。

原创性及来源说明等待作者补充。文件哈希只证明技术身份，不代表作者声明；不能据此勾选赛事的完整原创性披露。许可证、版权和历史证据保留。

候选：`eviweave-v03-search-credit-v34-cpu-reference-v36`；平台系统EviWeave，版本v0.3；Textual。Manifest SHA256：`c2ccd8d8bb9e3b37412cb68cd3107df1967708400180d14fe46eb93ec7b1794c`。

## 核验方法

`SOURCE_MAP.json`逐一对应原工作区路径、当前GitHub文件路径和SHA256。11个共享API模块位于仓库根目录`adaptive_evidence/`；其余源码位于本目录`source/`，内容未改。云端实际执行`server.py`和`runtime_store.py`，词元服务在本机以原FP32 CPU实现执行；不是在云端运行根目录的演示HashEncoder。

`DEPLOYED_MANIFEST.json`是部署时的原始冻结记录；其中旧资格/授权布尔值按历史原件保存，不能当作当前提交许可。`MODEL_IDENTITY.json`标识当前适配器，避免与根目录旧实验的适配器混用。

## 模型与运行边界

- 基础权重SHA256：`3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017`。
- 当前适配器SHA256：`d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619`。
- 原FP32编码/MaxSim、FP64求和；query32/window177/stride145、unmerged LoRA、2 CPU线程。
- 原文与元数据保留，使用固定Search credit机制；没有新训练、图森林、全历史短句或多轮规划。
- 无生成式Add/Search LLM，平台负责Answer/Judge。原生embedding声明为text-embedding-v4；ColBERT用于来源池评分。

## 当前生产运行说明

已部署的m02使用独立release、独立venv入口，端口18102，由systemd管理；依赖只读引用原环境。其他九套服务和共享源码未修改。版本更新只能在没有官方在途任务、核验完整身份后进行；Full期间保持源码、模型和参数冻结。

云端API依赖本机CPU词元服务和SSH反向隧道。本机必须全程保持开机、联网、禁用休眠，不能结束该服务会话；断开后系统返回503，不静默回退。容量与持续运行条件应在赛事说明中如实填写。

运维检查：`systemctl status memory-lab@m02.service`；既定重启命令为`systemctl restart memory-lab@m02.service`，评测在途时不要主动重启。配置中的鉴权、embedding凭据及RPC凭据均不公开。

## 重建限制

本目录提供完整执行源码与哈希映射，不把私有运行目录伪装成一个无需外部工件即可启动的Python安装包。原始启动检查还要求匹配的模型/tokenizer、适配器、来源资格凭证与训练完整性元数据；这些路径和哈希保留在原代码和manifest中。模型权重、用户数据库、评测数据/题目/答案/提示以及凭据不随Git仓库分发。
根目录`RUNNING.md`继续描述0.1.0研究包的本地演示；运行该演示不等于复现此v36候选。正式申请请绑定含本快照的固定Git Commit，并如实说明外部模型工件与运行条件。
