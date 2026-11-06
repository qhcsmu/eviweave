# Third-party notices

The unmodified `adaptive_evidence` implementation and historical local ColBERT/adapter loader code are distributed under the MIT license included in `LICENSE`, retaining the original copyright notice.

The ColBERTv2 checkpoint referenced by the optional loader is published at `https://huggingface.co/colbert-ir/colbertv2.0` and declares MIT licensing in the pinned upstream model metadata. Its upstream implementation reference is `https://github.com/stanford-futuredata/ColBERT/tree/cc4f3dc91c0b45d2d08c251d9d95178285c65f1c`. This repository does not distribute checkpoint weights.

BGE is separately obtained from `https://huggingface.co/BAAI/bge-small-en-v1.5`. NumPy, FastAPI, Uvicorn, HTTPX, PyTorch, Transformers and Safetensors retain their respective licenses. Installing dependencies does not relicense their code or model artifacts.

## v0.3 published artifacts

The exact v0.3 step80 adapter is now distributed under this repository's MIT license. It includes LoRA tensors and a trained projection derived from ColBERTv2; retain the [upstream MIT notice](candidate-v03/licenses/COLBERT-MIT.txt). The 67-file public startup archive contains the exact deployed Qwen3.5-4B tokenizer/configuration files under [Apache 2.0](candidate-v03/licenses/QWEN-APACHE-2.0.txt), with their upstream source at <https://huggingface.co/Qwen/Qwen3.5-4B>. No Qwen generation weights are included.

The adapter training data source is Bowen Jiang et al., *PersonaMem-v2: Towards Personalized Intelligence via Learning Implicit User Personas and Agentic Memory*, arXiv:2512.06688, <https://huggingface.co/datasets/bowen-upenn/PersonaMem-v2/tree/ed956dea41521fc4499acbc63f966e0fd3c053ba>. Its dataset card declares [CC BY 4.0](candidate-v03/licenses/CC-BY-4.0.txt). Transformations included persona regrouping, source chunking/deduplication, exclusions and tokenization; attribution and the data license remain separate from the code/adapter license. No endorsement is implied. See [model card](candidate-v03/MODEL_CARD.md) for fields used and limitations.

Raw training/benchmark text, prompts, conversations, answers, protected exclusion fingerprints and user databases are not redistributed publicly. Eleven exact startup dependencies are instead provided to the operator in a controlled local package, pending delivery to reviewers via their confirmed channel. License availability does not establish competition admission. See [artifact access](candidate-v03/ARTIFACT_ACCESS.md) and [admission status](candidate-v03/training/ADMISSION_STATUS.json).
