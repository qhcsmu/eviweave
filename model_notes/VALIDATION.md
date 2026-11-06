# 发布材料验证

## v0.3 补充材料 — 2026-11-04

本次只核验文档、归档及聚合记录，未运行模型、训练、压力测试或新评测：

- `python artifacts/tools/verify_v03_snapshot.py`：初始24个Python源码文件和冻结manifest的字节身份及AST通过。
- `python artifacts/tools/verify_v03_supplement.py`：7个补充工件哈希、Python AST、13个API运行文件与修复后源码归档的对应关系通过；核验五组合成迁移结果和完整Full聚合记录。
- 本次文档的本地链接均存在，JSON示例可解析，Markdown代码围栏成对。
- `python artifacts/tools/release_audit.py`与Git空白检查通过；发布前另核对暂存文件和凭据模式。

本次未重新运行历史72项功能测试，也未据文档验证推断新的性能或质量结论。原Full的完整成绩见[结果记录](../candidate-v03/EVALUATION.md)。源码归档验证来自本地备份及已保存摘要，没有进行实时部署验证。

## 0.1.0 历史发布验证

核验日期：2026-10-31。以下是本地功能与打包检查，不是官方评测，也不证明语义检索或最终答案提升。

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 8项通过：API、持久化、隔离、锁所有权及实验候选机制 |
| `python -m unittest discover -s benchmarks/tests/upstream -p "test_*.py"` | 64项原版测试通过 |
| `python -m eviweave demo` | 通过，返回合成示例的两条原文跨度 |
| 隔离构建wheel | 通过；未向共享模型环境安装或升级构建依赖 |
| 将wheel安装到独立目录，再从源码仓库之外运行demo | 通过；使用已安装包返回相同两条跨度 |

共72项测试通过。测试使用合成数据、假编码器及被模拟的HTTP请求；没有研究Answer/Judge调用，没有加载GPU模型。

本地验证环境：Python 3.10.11，NumPy 2.2.6、FastAPI 0.141.1、Starlette 1.6.0、Uvicorn 0.52.4、HTTPX 0.28.1、Pydantic 2.13.4。Starlette给出了HTTPX兼容性弃用警告；本轮测试仍全部通过。GitHub Actions另配置Python 3.10与3.12；本地通过不等于远端CI已经通过。

构建产物：`eviweave_memory-0.1.0-py3-none-any.whl`，45045字节，SHA256：

```text
f917a5c1ab755763585cbd4f26897ab7b941ffc9597c17e7d748e94e872fa845
```

构建命令：

```shell
python -m pip wheel --no-deps --index-url https://pypi.org/simple --wheel-dir ../artifacts .
```

源码发布前运行`python artifacts/tools/release_audit.py`，核对16个冻结源文件的SHA256，并扫描暂存的公开文件。该检查不能替代人工审阅或证明不存在所有类型的秘密。模型权重、适配器、数据集、评测提示与答案、用户数据库、运行日志和登录凭据不随源码发布。

真实BGE/ColBERT加载、GPU延迟、研究调用成本及新候选六数据集最终答案成绩在本次发布验证中未运行；不能由以上72项功能测试推断。历史负结果与当前候选边界见[RESEARCH_STATUS.md](RESEARCH_STATUS.md)。
