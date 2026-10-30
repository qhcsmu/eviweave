import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient

from eviweave.api import create_app
from eviweave.locking import ModelLease
from eviweave.runtime import Runtime, Settings


class RuntimeTests(unittest.TestCase):
    def test_api_idempotence_isolation_persistence_and_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(database=str(Path(directory) / "memory.sqlite3"), api_token="synthetic-test-token")
            headers = {"Authorization": "Bearer synthetic-test-token"}
            payload = dict(user_id="alice", request_id="one", session_id="session",
                           messages=[dict(role="user", content="Luna likes the blue feather wand.")])
            with TestClient(create_app(settings)) as client:
                self.assertEqual(client.post("/add", json=payload).status_code, 401)
                self.assertGreater(client.post("/add", json=payload, headers=headers).json()["added_chunks"], 0)
                self.assertEqual(client.post("/add", json=payload, headers=headers).json()["added_chunks"], 0)
                changed = {**payload, "messages": [dict(role="user", content="Luna likes red yarn.")]}
                self.assertEqual(client.post("/add", json=changed, headers=headers).status_code, 409)
                response = client.post("/search", json=dict(user_id="alice", query="Luna wand"), headers=headers)
                self.assertIn("blue feather wand", response.json()["memories"][0]["content"])
                self.assertEqual(client.post("/search", json=dict(user_id="bob", query="Luna wand"), headers=headers).json()["memories"], [])
            with TestClient(create_app(settings)) as client:
                self.assertTrue(client.post("/search", json=dict(user_id="alice", query="Luna"), headers=headers).json()["memories"])

    def test_lock_never_steals_or_releases_another_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.lock"
            with ModelLease(path) as first:
                original = (path / "owner.json").read_bytes()
                with self.assertRaises(RuntimeError):
                    with ModelLease(path):
                        self.fail("Must not acquire another owner's lock")
                self.assertEqual((path / "owner.json").read_bytes(), original)
                first.assert_owned()
            self.assertFalse(path.exists())

    def test_gpu_refused_before_loading_any_model_without_lock_path(self):
        with self.assertRaisesRegex(ValueError, "shared --gpu-lock-dir"):
            with Runtime(Settings(encoder="bge", model_dir="not-loaded", device="cuda:0")):
                self.fail("GPU runtime should not start")

    def test_default_path_keeps_exact32_search_outputs(self):
        from eviweave import MemoryStore, HashEncoder, Config
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "memory.sqlite3")
            with Runtime(Settings(database=path)) as runtime:
                runtime.store.add(user_id="u", request_id="r", session_id="s",
                                  messages=[dict(role="user", content="Always include a short closing line."),
                                            dict(role="user", content="The cobalt seal must stay dry.")])
                reference = MemoryStore(path, HashEncoder(), Config())
                query = dict(user_id="u", query="cobalt seal", mode="query_document_evidence")
                self.assertEqual(runtime.store.search(**query), reference.search(**query))


if __name__ == "__main__":
    unittest.main()
