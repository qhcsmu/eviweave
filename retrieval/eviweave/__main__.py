"""Command line entry point with a model-free demo and a local API."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from . import __version__
from .runtime import Runtime, Settings


def demo():
    with tempfile.TemporaryDirectory(prefix="eviweave-demo-") as directory:
        with Runtime(Settings(database=str(Path(directory) / "memory.sqlite3"))) as runtime:
            runtime.store.add(user_id="demo", request_id="example-1", session_id="demo-session",
                              messages=[dict(role="user", content="Luna prefers the blue feather wand."),
                                        dict(role="assistant", content="The wand is kept in the hallway drawer.")])
            hits = runtime.store.search(user_id="demo", query="Luna blue feather wand",
                                        top_k=5, mode="query_document_evidence")
            print(json.dumps(dict(system="EviWeave", encoder="demo hash, not a semantic model",
                                  memories=hits), indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(prog="eviweave", description="Local raw-source memory retrieval")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Run a model-free, synthetic CPU example")
    serve = commands.add_parser("serve", help="Run the local HTTP API")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost", "::1"])
    serve.add_argument("--port", type=int, default=18403)
    serve.add_argument("--db", default="data/memory.sqlite3")
    serve.add_argument("--encoder", default="hash", choices=["hash", "bge"])
    serve.add_argument("--model-dir")
    serve.add_argument("--device", default="cpu")
    serve.add_argument("--context-chars", type=int, default=24000)
    serve.add_argument("--experimental-colbert", action="store_true")
    serve.add_argument("--colbert-dir")
    serve.add_argument("--colbert-device", default="cpu")
    serve.add_argument("--adapter-path")
    serve.add_argument("--adapter-sha256")
    serve.add_argument("--index-dir", default="data/colbert-index")
    serve.add_argument("--gpu-lock-dir", default=os.getenv("EVIWEAVE_GPU_LOCK_DIR"))
    args = parser.parse_args()
    if args.command == "demo":
        demo()
        return
    from .api import create_app
    import uvicorn
    settings = Settings(database=args.db, encoder=args.encoder, model_dir=args.model_dir,
                        device=args.device, context_chars=args.context_chars,
                        api_token=os.getenv("EVIWEAVE_API_TOKEN"), experimental=args.experimental_colbert,
                        colbert_dir=args.colbert_dir, colbert_device=args.colbert_device,
                        adapter_path=args.adapter_path, adapter_sha256=args.adapter_sha256,
                        index_dir=args.index_dir, gpu_lock_dir=args.gpu_lock_dir)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
