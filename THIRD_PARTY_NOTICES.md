# Third-party notices

The unmodified `adaptive_evidence` implementation and historical local ColBERT/adapter loader code are distributed under the MIT license included in `LICENSE`, retaining the original copyright notice.

The ColBERTv2 checkpoint referenced by the optional loader is published at `https://huggingface.co/colbert-ir/colbertv2.0` and declares MIT licensing in the pinned upstream model metadata. Its upstream implementation reference is `https://github.com/stanford-futuredata/ColBERT/tree/cc4f3dc91c0b45d2d08c251d9d95178285c65f1c`. This repository does not distribute checkpoint weights.

BGE is separately obtained from `https://huggingface.co/BAAI/bge-small-en-v1.5`. NumPy, FastAPI, Uvicorn, HTTPX, PyTorch, Transformers and Safetensors retain their respective licenses. Installing dependencies does not relicense their code or model artifacts.

No benchmark dataset, prompt, conversation, answer or trained adapter weight is redistributed here. Users must obtain any optional external model/data artifacts under the terms of their sources.
