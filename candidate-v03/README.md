# EviWeave v0.3 正式源码与运行材料

本目录对应赛事版本v0.3，候选ID为`eviweave-v03-search-credit-v34-cpu-reference-v36`。完整Full已成功完成，结果见[EVALUATION.md](EVALUATION.md)。本次补充只更新材料及归档副本，没有部署新实现。

## 源码映射

初始源码发布提交为`3a35fa6c3c77202c271754d0909954b9c8d75c80`；容量材料提交为`34bac34b947b2367548c353226fe039b15b1f98e`。本次补充以实际Git提交SHA另行登记，不改写历史绑定。

- [SOURCE_MAP.json](SOURCE_MAP.json)：初始24个Python文件的路径和SHA256，含根目录`adaptive_evidence/`及`source/`中的API包装、评分与打包机制。
- [DEPLOYED_MANIFEST.json](DEPLOYED_MANIFEST.json)：冻结部署身份，SHA256为`c2ccd8d8bb9e3b37412cb68cd3107df1967708400180d14fe46eb93ec7b1794c`，历史字段按原件保留。
- [运行补充清单](runtime-linux/SUPPLEMENT_MANIFEST.json)：正式查询修复、Linux进程适配、依赖和验证记录。重建API时，将补充的`remote_encoder.py`置于API包的`adaptive_evidence/remote_encoder.py`；初始快照继续保留以便核验差异。

本次从服务器修复后的本地源码归档逐一核验了13个API运行文件；结合正式编码器覆盖层后均与公开文件逐字节一致。Linux归档文件与已登记部署哈希一致。服务器已关闭，未将本地归档核验表述为本次实时线上检查。

正式API入口是`source/deployment-v36-cpu-reference/server.py`及`runtime_store.py`；词元入口是`runtime-linux/source/linux_owner_resident.py`，由其调用`rpc_server_resident.py`。这些是生产布局的归档副本，直接在本目录启动不会自动准备模型或资格元数据。

在仓库根目录核验：

```shell
python tools/verify_v03_snapshot.py
python tools/verify_v03_supplement.py
```

## 两项运行补充

**查询长度修复。** 正式源码SHA256为`5df870361bb3e804bc679e86ff13474e75f44c200a69b8b143d277d3770962e3`，仅在供应商明确拒绝查询长度时无损分段编码和加权合并。正式版具有query-only条件，见[查询修复范围](LINUX_RUNTIME.md#查询长度恢复)。

**Linux常驻迁移。** 2026年11月2日完成同机18403端口交接，保持同一模型及CPU评分精度，由systemd管理生命周期。合成数值对照、进程检查和接入验证摘要见[VALIDATION.json](runtime-linux/VALIDATION.json)。原API与SQLite位置保持。

## 复现边界

正式模型、适配器、分词器和参数见[MODEL_IDENTITY.json](MODEL_IDENTITY.json)。根目录研究CLI的旧实验适配器与本候选不同；包版本0.1.0不等同于赛事版本v0.3。

完整重建需要匹配的本地权重、正式适配器、预算分词器、训练完整性与来源资格元数据，以及私有embedding/RPC配置。公开仓库不分发这些工件；已有工件的布局、运行命令、接口和依赖见[LINUX_RUNTIME.md](LINUX_RUNTIME.md)。

当前服务器由运营方关闭。历史容量、延迟和成本范围见[CAPACITY.md](CAPACITY.md)。固定验证不证明全域浮点等价或未知负载下的稳定性。
