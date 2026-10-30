# 0.1.0 发布验证

核验日期：2026-10-31。以下是本地功能与打包检查，不是官方评测，也不证明语义检索或最终答案提升。

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -p "test_*.py"` | 8项通过：API、持久化、隔离、锁所有权及实验候选机制 |
| `python -m unittest discover -s tests/upstream -p "test_*.py"` | 64项原版测试通过 |
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

源码发布前运行`python tools/release_audit.py`，核对16个冻结源文件的SHA256，并扫描暂存的公开文件。该检查不能替代人工审阅或证明不存在所有类型的秘密。模型权重、适配器、数据集、评测提示与答案、用户数据库、运行日志和登录凭据不随源码发布。

真实BGE/ColBERT加载、GPU延迟、研究调用成本及新候选六数据集最终答案成绩在本次发布验证中未运行；不能由以上72项功能测试推断。历史负结果与当前候选边界见[RESEARCH_STATUS.md](RESEARCH_STATUS.md)。
