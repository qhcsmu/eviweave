# 已完成的有界容量核验与运行条件

2026-10-31记录。用户已要求停止优化及进一步容量测试；本文件只整理已完成结果，没有修改候选。结果不是Full全量或多日稳定性的保证。

## 身份与资源

候选`eviweave-v03-search-credit-v34-cpu-reference-v36`，平台版本`v0.3`，仅Textual。源码首次发布提交`3a35fa6c3c77202c271754d0909954b9c8d75c80`；`SOURCE_MAP.json`对应24个Python执行/运维文件，云端13个实际执行文件核对一致。部署manifest SHA256：`c2ccd8d8bb9e3b37412cb68cd3107df1967708400180d14fe46eb93ec7b1794c`。模型身份见`MODEL_IDENTITY.json`，未更换模型或参数。

云端4 CPU，物理内存约30.7 GiB、可用27.2 GiB；磁盘总约58.7 GiB、空闲50.1 GiB。m02生产服务MemoryMax为10 GiB，检查时约119 MiB、历史峰值约125 MiB。共享主机可用资源会变化。systemd为Restart=on-failure、RuntimeMax=infinity、LimitNOFILE=65536；nginx请求体上限64 MiB、proxy read/send timeout1800秒、connect timeout10秒、worker_connections768。这些配置值不是持续负载保证。

生产SQLite检查时为55,754,752字节，8976 sources、9598 chunks、130 users、809 requests。没有导出内容或用户标识。容量测试使用独立合成数据库，生产数据库前后SHA256一致。

## 已完成结果

使用当前CandidateStore、真实ASGI handlers及真实CPU词元RPC。存储部分使用确定性1024维embedding替身，不能代表text-embedding-v4的延迟或配额。

| 场景 | 结果 |
|---|---|
| 1000次同步Add，20000 sources/chunks、6用户，单用户最大10000条 | 写入83.193秒；Add p50 0.088秒、p95 0.098秒、最大0.120秒 |
| 上述数据库3次Search | 4.701 / 0.846 / 0.849秒；各31条、约23744字符，满足top_k100及24000字符预算 |
| 上述存储进程 | peak RSS约321 MiB，合成数据库约123 MiB |
| 固定16并发Add，每请求20条 | 16/16 HTTP200；p50 0.319秒、p95/最大1.136秒；最终20320 sources、1016请求 |
| 固定16并发Search，单用户10000条 | 16/16 HTTP200；p50 148.018秒、p95/最大148.720秒；每次31条 |
| 16并发真实学习RPC自检 | 16/16通过；p50 0.965秒、p95/最大1.810秒；16次neural_queries、16次changed、0错误 |
| 并发16独立测试进程 | peak RSS约3.51 GiB，总153.270秒 |

学习RPC自检共享一个暖缓存来源，不代表16个最大128来源池的冷请求。存储Search场景未触发学习选择，不能将两项结果拼成完整最坏端到端延迟。ASGI测试在进程内进行，未包含公网TLS，未覆盖真实embedding配额、带宽、多日稳定性或全部未知峰值。

并发16原始结果SHA256：`5cddf46e9856e2bbca811bca593849db482688d64fcec2c4de7971487762598b`。两轮均无生产写入、评测POST、Answer/Judge调用、GPU工作或付费embedding调用。硬件与电力成本未核算；真实服务原生embedding及平台统一Answer/Judge费用另计。

## Full运行条件

实时Textual合同`textual-v1`要求Add并发16–64、Search并发16–256；最终手动提交的最低值均为16。历史材料中的1/1建议已纠正。

端点保持`https://101.201.226.162/m02/add`、`/m02/search`、`/m02/health`。鉴权仅在赛事私有字段提供。云端API依赖本机CPU词元服务与SSH反向隧道；本机必须持续开机、联网、禁止休眠，并保留服务会话。断开后返回503，不静默换版本。systemd重启云端API不会自动恢复本机模型与隧道。

Full期间冻结源码、模型、参数和路由，不主动重启。已完成的有界核验不能单独支持勾选“Full evaluation capacity confirmed”；提交人仍需确认实际全量存储、带宽、提供商额度和全程供电/网络。原创性披露及学术榜模型规则适用性仍须准确补齐。没有Full提交或自动晋升。
