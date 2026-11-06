# v0.3 工件获取与文件复原

2026-11-04补充。以下交付同一份参评工件，不重训、不改加载器，不绕过历史完整性校验。文件复原不会启动服务或连接评测平台。

## 实际获取渠道

| 工件 | 获取方式 | 大小 / SHA256 |
|---|---|---|
| 正式适配器 | [固定提交下载](https://raw.githubusercontent.com/qhcsmu/eviweave/082390824fae661659557adc74de14251522904e/candidate-v03/artifacts/adapter-step80.safetensors) | 788,584字节 / `d86e773035f920b9d5dc23ba91e4c802dfcbf6d897813029b012057d62316619` |
| 67个公开启动文件 | [公开ZIP](https://raw.githubusercontent.com/qhcsmu/eviweave/082390824fae661659557adc74de14251522904e/candidate-v03/artifacts/eviweave-v03-public-startup-20261104.zip)，或本仓库`candidate-v03/artifacts/` | 7,467,157字节 / `f223d013bf2e713f490ddf28bc68976d60b2beab564ddb8472929246da8ee373` |
| 基础权重 | [固定上游revision](https://huggingface.co/colbert-ir/colbertv2.0/resolve/c1e84128e85ef755c096a95bdb06b47793b13acf/model.safetensors) | 438,349,816字节 / `3f58890b1dfdfec066ef12ba431fa9d56992da9e30a53489242c4156e37e9017` |
| 11个受控启动文件 | 本次交付给负责人的本地`eviweave-v03-controlled-startup-20261104.zip`；官方复核由负责人在原AML线程安排受控传递 | 7,911,038字节 / `e204354df5ebcd234eae0ad0ad07751019bb1bb6a76ac7d106c5e9ed6c0067d2` |

公开适配器与ZIP固定在提交`082390824fae661659557adc74de14251522904e`，既可随Git克隆取得，也可直接下载，不要求服务器在线。ZIP包含精确的ColBERT元数据/分词器、预算分词器、冻结源码、配方、汇总资格记录及Linux补充身份。预算分词器的历史上游revision未记录，故直接提供已部署的原字节与哈希，不拿上游latest替代。

受控包已实际生成并校验，不是只有哈希的占位。它含原公开训练文本（含后来被排除的重合片段）、词元ID、标注调度及评测排除指纹，因此不上传公开GitHub。它不含正式评测已写入的用户数据库、请求内容、答案、选项、提示、运行日志或凭据。公开下载目前仍**不能独立完成全部正式启动文件复原**：审核方须通过负责人取得上述受控包；未建立公开自动授权下载。各文件、获取类别及精确哈希列于[ARTIFACTS.json](artifacts/ARTIFACTS.json)。

## 在全新目录复原

只需Python标准库，无需GPU或模型导入。先克隆本仓库。仅检验公开部分：

```shell
python tools/fetch_v03_artifacts.py --destination /new/path/eviweave-public --public-only --offline
python tools/fetch_v03_artifacts.py --destination /new/path/eviweave-public --public-only --verify-only
```

拿到受控包后，复原全部80个启动校验文件；缺少基础模型时从固定上游下载：

```shell
python tools/fetch_v03_artifacts.py --destination /new/path/eviweave-workspace --controlled-bundle /secure/path/eviweave-v03-controlled-startup-20261104.zip
python tools/fetch_v03_artifacts.py --destination /new/path/eviweave-workspace --verify-only
```

已有同一基础权重时可加`--base-file /path/to/model.safetensors --offline`，工具先校验再复制。Windows将示例路径换为新的绝对路径。目标目录必须尚不存在；工具不覆盖已有部署，不修改数据库、私有配置、锁或端口。失败时保留新目录供检查；再次准备使用另一个新目录。

## 从文件完整到可运行

80文件校验仅证明工件齐备，不证明已通过赛事准入、环境兼容或新机器数值对照。

1. 按[Linux运行指南](LINUX_RUNTIME.md)准备隔离的Python3.10.11及固定依赖；安装完整[freeze清单](runtime-linux/requirements.freeze.txt)。[BUILD_INPUTS.json](runtime-linux/BUILD_INPUTS.json)补充了原Python归档、Torch wheel及57个依赖wheel的实际下载URL、字节数和SHA256。Python为python-build-standalone 20230507版，Torch为官方cu128/cp310/manylinux_2_28 wheel。按清单下载、逐一核验后，可在隔离目录用`python -m pip install --no-index --find-links /verified/wheels -r requirements.freeze.txt`安装。系统库与运行二进制不随仓库打包，须保留清单的发行版本；本次未重新下载全部运行环境或重建。API使用独立Python3.12环境。
2. 保持复原workspace的目录结构。词元启动目录为`competition/research/parallel-seven-20261030/03-token-retrieval/deployment-v36-cpu-reference/`。Linux owner在原路径读取`LINUX_RESIDENT_RUNTIME_SUPPLEMENT.json`、manifest、来源资格与训练依赖，无需删校验或伪造资格文件。
3. RPC私有`private/rpc-token.txt`由运营者安全生成至少40字符随机串（目录0700、文件0600），与API的`EVIWEAVE_RPC_TOKEN`一致，不复用公开示例。正式恢复应保留原私有配置。API源码按[SOURCE_MAP](SOURCE_MAP.json)装入独立release，应用已归档的query-only `remote_encoder.py`覆盖层；不能把完整性校验用的旧源码目录直接当当前API覆盖层。
4. 先预热，检查本进程的`resident-runs/.../PREWARMED.json`身份及端口所有权。新隔离复核环境经操作者确认18403可用后，可用`open(...,'x')`在启动目录创建`LINUX_RESIDENT_ACTIVATED.json`，记录本次操作者/时间/用途。这只是进程启用标记，不是模型准入记录；不复制旧PID、锁或旧交接状态，也不在他人占用端口时创建标记。既有生产恢复保留原状态并走AML兼容断点流程。
5. 准备独立`EVIWEAVE_OWNER_LOCK_ROOT`，再按原systemd单元布局运行；PID/start-ticks/boot检查由owner原子取得自己的锁。新机器需明确配置路径，单元文件本身不负责安装所有工件。API鉴权、DashScope凭据、数据库/幂等记录和TLS路由仍由运营者私有配置。
6. 接入正式请求前，重复既有固定合成输入对照，分数差不超过`1e-5`，来源、顺序与最终Search相同；选择变化或超阈值先反馈AML。不得清库续跑、新建Full或重放已成功Add。

本次文件恢复及拒绝测试见[VALIDATION.json](artifacts/VALIDATION.json)。验证限于文件和交付工具，没有开机、冷启动、训练或新数值评测。单独模型/来源准入状态见[模型卡](MODEL_CARD.md#准入状态)。
