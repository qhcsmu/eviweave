# EviWeave v0.3 提交后补充材料

更新日期：2026-11-04。系统EviWeave，赛事版本v0.3，Textual Memory；固定候选为`eviweave-v03-search-credit-v34-cpu-reference-v36`。原Full成功完成9602/9602项，聚合记录见[Full结果](candidate-v03/EVALUATION.md)。仓库承担源码及运行材料核验，参评接入使用登记的自托管API。

## 本次补充

- 首页以正式v0.3为入口，列明接口约定、模型身份、完整Full结果及依赖。
- 归档正式查询长度修复、Linux常驻适配、依赖版本和合成一致性结果；保留初始快照与增量哈希。
- 更新正式运行与提交状态，保留版权和第三方许可。
- 保留0.1.0研究演示及历史测量的适用范围。
- 新增正式适配器实文件、67文件公开启动包、80文件获取清单及校验工具；11个含原文本或排除指纹的依赖以本地受控包交付。
- 补充训练来源、许可、冻结配方、污染排除及回退；精确模型/训练来源的AML单独准入仍待确认。

本次材料更新没有更换受测模型、算法、关键配置或数据，没有新建评测、重放成功Add或修改线上服务。

## 固定提交

仓库：<https://github.com/qhcsmu/eviweave>。初始源码提交为`3a35fa6c3c77202c271754d0909954b9c8d75c80`，历史容量材料提交为`34bac34b947b2367548c353226fe039b15b1f98e`。本次补充以实际提交SHA登记，不改写原评测绑定的历史提交。

```shell
git log -1 --format=%H
python artifacts/tools/verify_v03_snapshot.py
python artifacts/tools/verify_v03_supplement.py
```

审核时同时使用初始24文件`candidate-v03/SOURCE_MAP.json`和增量`candidate-v03/runtime-linux/SUPPLEMENT_MANIFEST.json`。

## 部署与材料边界

正式入口、依赖、模型身份、API字段、鉴权、幂等、隔离、错误处理和复现工件要求见[Linux运行指南](candidate-v03/LINUX_RUNTIME.md)。容量、延迟及成本边界见[容量记录](candidate-v03/CAPACITY.md)。正式适配器已经公开；基础权重用固定上游下载。密钥、原始训练/评测内容、逐记录排除指纹、用户数据库及日志不公开。完整工件获取与受控交付见[ARTIFACT_ACCESS.md](candidate-v03/ARTIFACT_ACCESS.md)。

接口字段和相对路由见 README；访问基址及私密鉴权由运行环境配置。

本次核对了2026年11月4日可读取的[API Guide](https://agentmemoryleaderboard.ai/api-guide)、[Documentation](https://agentmemoryleaderboard.ai/docs)及[赛事说明](https://agentmemoryleaderboard.ai/competition/)。平台的模型、套件、统一Answer/Judge、评分及发布审核由赛事方控制；仓库补充不代替平台审核，也不自行修改评测绑定。
