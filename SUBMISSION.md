# GitHub 首次提交说明

建议仓库名称：`eviweave`。系统名称：**EviWeave · 证据织忆**。发行版本：`0.1.0`，研究发布。

## 提交标题

```text
feat: publish EviWeave local source-faithful memory retrieval
```

## 提交正文

```text
Package exact official 0.32 retrieval sources without changing their bytes.
Add a standalone local CLI, deterministic CPU demo and loopback HTTP API.
Expose the independent ColBERT corpus candidate index as an opt-in experiment.
Preserve original source spans, native packing and returned-rule fallback.
Require an owner-checked shared directory lock before GPU model loading.
Document model provenance, offline loading, run commands and research limits.
Exclude credentials, benchmark material, user databases, logs and model weights.
```

## 发布内容

默认路径为原版检索机制；演示编码器仅帮助无需权重地验证功能。本地BGE需要单独准备模型。ColBERT全库召回默认关闭，固定源代码的实验设计与独立服务封装分别记录；没有把未完成评测宣称为已验证提升。

运行方法见 [RUNNING.md](RUNNING.md)。代码来源与逐文件哈希见 [PROVENANCE.md](PROVENANCE.md) 和 `docs/source-manifest.json`。原始MIT许可完整保留。

## 验证命令

```shell
python -m eviweave demo
python -m unittest discover -s tests -p "test_*.py"
python -m unittest discover -s tests/upstream -p "test_*.py"
python tools/release_audit.py
```

验证记录写入 `docs/VALIDATION.md`。功能测试不等于真实语义检索或最终答案准确率。代码审计核对被冻结原版与实验模块哈希，并检查待提交文件中是否出现模型、数据库、凭据文件或常见令牌。

## 评测与声明边界

- 不包含数据集、评测题目、选项、参考答案、生成答案或Answer/Judge提示。
- 不包含云端评测提交器、账户配置、官方路由、自动晋升或定时提交任务。
- 不提交Smoke/Full。发布GitHub仓库不改变incumbent或永久回归门槛。
- 公共套件历史已有暴露，原研究本地模型与官方不同；检索覆盖上界不能当成答案提升。
- 历史0.50版本不是本次基线；新功能不会整版替换exact0.32。

## 发布到远端

目标GitHub账号需要先在浏览器登录。仓库URL必须以登录后的实际用户名为准，不从邮箱推测。首次创建空仓库`eviweave`后，将本地`main`提交推送到该仓库，并在GitHub页面核对README、源码及提交ID。不要把账号密码、PAT或浏览器Cookie放入远端URL、Git配置、提交或命令记录。

本文是GitHub源码提交说明，不是官方竞赛提交授权。
