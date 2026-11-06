# EviWeave 检索包贡献指南

开发代码位于 `retrieval/eviweave/`。`dependencies/exact32/` 保存基础依赖，`benchmarks/` 提供测试与示例，研究包的使用说明另见 [model_notes/DEVELOPMENT.md](../model_notes/DEVELOPMENT.md)。

从仓库根目录安装 API 与测试依赖：

```shell
python -m pip install -e ".[api,test]"
```

分别运行检索包测试和依赖兼容性测试：

```shell
python -m unittest discover -s benchmarks/tests -p "test_*.py"
python -m unittest discover -s benchmarks/tests/upstream -p "test_*.py"
```

本地测试使用合成数据及模拟编码器，不要求连接赛事服务。模型、API 凭据和运行数据需要单独配置。

正式 v0.3 的工件与补充材料保存在 [candidate-v03](../candidate-v03/README.md)。工件维护命令位于 `artifacts/tools/`；根目录 `tools/` 的转发入口用于兼容既有运行说明。开发包和研究 CLI 的测试不能代替固定候选的复现验证。

检查开发文件或固定发布材料：

```shell
python artifacts/tools/verify_layout.py
python artifacts/tools/verify_layout.py --frozen-only
```

来源记录和第三方许可分别见 [PROVENANCE.md](../PROVENANCE.md) 与 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
