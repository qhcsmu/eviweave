# EviWeave v0.3 Linux运行与接口

本说明对应固定v36 CPU候选。归档、依赖和哈希见[运行补充清单](runtime-linux/SUPPLEMENT_MANIFEST.json)，模型工件身份见[MODEL_IDENTITY.json](MODEL_IDENTITY.json)。服务器目前由运营方关闭；以下描述已有部署。

## 部署结构

| 组件 | 位置或配置 |
|---|---|
| API单元 | `memory-lab@m02.service` |
| API源码 | `/opt/memory-lab/releases/eviweave-v03-v36cpu-c2ccd8d8bb9e/source` |
| API进程 | Python3.12，既有独立release入口与私有配置 |
| SQLite | `/var/lib/memory-lab/m02/memory.sqlite3` |
| API端口 | 18102 |
| 词元单元 | `eviweave-m02-token.service` |
| 词元运行根目录 | `/opt/memory-lab/resident-staging/eviweave-v03-c2ccd8d8bb9e-20261101` |
| 词元Python | 上述目录的`linux-build-v2/venv/bin/python`，3.10.11 |
| 词元工作区 | 上述目录的`workspace/` |
| 词元RPC | `127.0.0.1:18403`，私有Bearer鉴权 |
| CPU进程锁 | `/run/eviweave-m02-token/cpu-service.lock` |

目录名虽然包含`resident-staging`，它是正式运行目录；模型、venv、workspace和激活标记不可当临时文件删除。词元单元已配置`Restart=on-failure`、10秒重试及开机启用。Linux所有权检查包含PID、进程启动ticks和boot ID，锁由持有者管理。

## 模型、依赖与数据流

- 外部embedding：DashScope `text-embedding-v4`，1024维、最大批次10，需供应商凭据和额度。
- 本地词元匹配：`colbert-ir/colbertv2.0`，revision `c1e84128e85ef755c096a95bdb06b47793b13acf`，加正式LoRA适配器。CPU FP32编码/MaxSim、FP64求和、unmerged LoRA、query32/window177/stride145、2线程。
- 本地预算检查：Qwen3.5-4B分词器，只计数与检查位置，不生成回答。
- 词元依赖：Python3.10.11、Torch2.11.0+cu128、NumPy2.2.6、Transformers5.16.1、tokenizers0.23.1、safetensors0.8.0。完整版本见[requirements.freeze.txt](runtime-linux/requirements.freeze.txt)。Torch为已有带CUDA构建，正式词元进程仅使用CPU。

API无生成式Add/Search LLM，Answer/Judge由平台统一运行。待编码的原文和查询会发给配置的embedding供应商，正式部署不是完全离线处理。

配置变量包括`AE_DATABASE`、`AE_MODE=query_document_evidence`、`AE_CONTEXT_CHARS=24000`、`MEMORY_API_KEY`、`DASHSCOPE_API_KEY`、`AE_EMBEDDING_URL`、`AE_EMBEDDING_DIMENSIONS=1024`、`EVIWEAVE_RPC_URL=http://127.0.0.1:18403/transform`及`EVIWEAVE_RPC_TOKEN`。实际密钥从原私有配置读取，不进入仓库。

### 查询长度恢复

正式源码见[source/remote_encoder.py](runtime-linux/source/remote_encoder.py)，SHA256为`5df870361bb3e804bc679e86ff13474e75f44c200a69b8b143d277d3770962e3`。仅当供应商以HTTP400、`InvalidParameter`和可识别的输入长度错误拒绝**query**时，保留全文和Unicode字符边界，以`min(7680, N-256)`的UTF-8字节预算分段；N来自供应商错误中的上限。每段使用原query角色、同一模型及1024维，按各段UTF-8字节长度加权平均单位向量后作L2归一化。字节预算不等于token数。

文档侧不启用该恢复，其他错误沿既有流程处理。修复使原先被拒绝的查询得到向量，可能改变召回或排序，不能用平台数值一致性检查代替此范围说明。

历史恢复版摘要为`3959e2d8c8d3d95aa1e92f553bcfe59d8670dd39ed7e2b3a6a274157beea3174`，代码缺少query-only条件，已被正式版替代。历史版于11月1日22:44:19启动，正式仅查询版于11月2日14:38:34启动；Linux交接于11月2日21:18:56完成。两项变更及历史运行窗口分别留档，由赛事方按已提交材料复核。

## 已有工件的复原步骤

1. 固定材料提交，运行两个源码核验工具；初始源码清单与运行补充清单共同核验对应关系。
2. 准备匹配哈希的ColBERT权重、正式适配器、两个分词器、来源资格和训练完整性元数据。按`DEPLOYED_MANIFEST.json`的相对路径恢复workspace，依`SOURCE_MAP.json`还原API包；API侧应用补充清单中的正式查询编码器覆盖层。
3. 使用隔离的Linux Python3.10.11环境及记录的词元依赖；API使用独立环境。安装版本清单是运行记录，不包含全部wheel、系统库或可移植镜像。
4. 恢复私有RPC配置及原激活标记。owner读取`LINUX_RESIDENT_RUNTIME_SUPPLEMENT.json`核验工件；RPC检查`SOURCE128`资格、模型和manifest。缺少工件时停止，不绕过校验或自动替换模型。
5. 配置[systemd单元归档](runtime-linux/eviweave-m02-token.service)，等模型预热、鉴权Health通过后接入API。该单元使用原目录布局；新机器需先准备workspace、私有文件和激活状态，单元文件不会自动创建它们。
6. 用预先固定的合成输入核验分数、来源、顺序及最终Search；沿用`1e-5`门槛。若超门槛或选择变化，先反馈赛事方，不接入正式请求。

公开仓库不分发权重、适配器、私有资格工件或评测内容。完整冷启动复现需另行取得匹配工件；根目录HashEncoder demo用于研究包功能演示。

## 已部署环境的维护

只读检查：

```shell
systemctl status memory-lab@m02.service eviweave-m02-token.service
systemctl is-enabled eviweave-m02-token.service
journalctl -u memory-lab@m02.service -n 50 --no-pager
journalctl -u eviweave-m02-token.service -n 50 --no-pager
ss -ltnp 'sport = :18403'
```

运营方开启服务器且确认数据、配置完整后，已有部署可依次启动：

```shell
systemctl start eviweave-m02-token.service
# 等模型预热，再确认鉴权RPC Health和API Health。
systemctl start memory-lab@m02.service
```

这不是新安装命令。维护重启使用对应单元的`systemctl restart`，限维护窗口或AML确认的兼容断点；不要启动旧Windows18403隧道、占用别人的端口或释放别人的锁。本次没有开机、重启或故障注入测试。

## 赛事接口约定

公开API挂载`/m02`，内层为`/add`、`/search`、`/health`。Add/Search使用已登记Bearer密钥，Health无需鉴权。

| 约定 | v0.3行为 |
|---|---|
| 用户隔离 | 仅相同`user_id`；`session_id`组织来源，可跨会话检索 |
| 同步Add | 持久化并可检索后返回200；`success=true`且原样回传三个ID |
| 幂等 | 相同用户和`request_id`重复同内容不重复写入；冲突内容409 |
| Search成功 | 顶层`data`数组，无结果`{"data": []}`；条目有非空`id`与原文`content`，可选数值`score` |
| 顺序/数量 | 按证据优先顺序，不超过`top_k`；本版本1–100，正式评测100 |
| 错误 | 未授权401；字段/数据校验422；写入冲突409；embedding/词元依赖不可用503 |
| 最终回答 | 平台统一Answer/Judge；服务不将答案、选项字母或金标伪装成记忆 |

Add必填`request_id`、`user_id`、`session_id`及非空`messages`；每条含非空字符串`role`、`content`，可选整数Unix毫秒`timestamp`。Search必填`user_id`、非空字符串`query`、整数`top_k`；可选字符串数组`options`，不接受额外金标或证据字段。选择题选项可参与既定原生检索视图，词元评分只读取查询。本版本支持Textual字符串，不支持多模态数组。

重试Add保留原`request_id`和请求体；409不能直接当成功。恢复保留数据库、用户命名空间、幂等记录和原任务身份，不清库或重放成功Add。

## 验证、性能与成本

五组固定CPU合成输入最大分数差`6.0051679611206055e-06 < 1e-5`；token IDs、来源选择与顺序、同分选择及Search证据一致。Linux进程所有权7项检查、接入后5项RPC检查通过。平台二进制及指令集不同，结论限于所测输入。

接入后五次固定RPC中位延迟1.665秒，不含生产embedding、SQLite检索、公网和平台Answer/Judge。历史容量测量及边界见[CAPACITY.md](CAPACITY.md)。记忆服务生成式LLM调用为0；实际embedding调用随输入和重试变化，查询恢复增加分段调用。CPU、存储、带宽及embedding费用未按完整账单核算。

评测数据和派生材料只用于对应任务，按赛事期限、审计要求及书面例外处理保留与删除，不公开或用于训练。本次未执行数据清理。
