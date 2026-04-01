import json
import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "truenascsp"))
sys.modules.setdefault(
    "falcon",
    SimpleNamespace(
        HTTP_200="200 OK",
        HTTP_204="204 No Content",
        HTTP_400="400 Bad Request",
        HTTP_404="404 Not Found",
        HTTP_500="500 Internal Server Error",
    ),
)

import backend  # noqa: E402
import truenascsp  # noqa: E402


class SnapshotResourceTests(unittest.TestCase):
    def test_scale_uses_pool_snapshot_resource(self):
        handler = backend.Handler()
        self.assertEqual(handler.snapshot_resource("SCALE"), "pool/snapshot")
        self.assertEqual(
            handler.uri_id("pool/snapshot", "tank/csi@daily"),
            "pool/snapshot/id/tank%2fcsi@daily",
        )

    def test_core_uses_legacy_snapshot_resource(self):
        handler = backend.Handler()
        self.assertEqual(handler.snapshot_resource("CORE"), "zfs/snapshot")

    def test_normalize_volsize_returns_integer(self):
        handler = backend.Handler()
        self.assertEqual(handler.normalize_volsize("1073741824", "CORE"), 1073741824)
        self.assertIsInstance(handler.normalize_volsize("1073741824", "SCALE"), int)


class FakeSnapshotAPI:
    def __init__(self):
        self.logger = logging.getLogger("test-snapshot-compat")
        self.fetch_calls = []

    def snapshot_resource(self):
        return "pool/snapshot"

    def fetch(self, resource, **kwargs):
        self.fetch_calls.append((resource, kwargs))
        return None

    def xslt_id_to_dataset(self, xslt):
        return xslt.replace("_", "/")


class SnapshotListTests(unittest.TestCase):
    def test_snapshot_list_handles_missing_results(self):
        api = FakeSnapshotAPI()
        req = SimpleNamespace(
            context=api,
            params={"volume_id": "tank_csi_pvc-test"},
        )
        resp = SimpleNamespace(body=None, status=None)

        truenascsp.Snapshots().on_get(req, resp)

        self.assertEqual(api.fetch_calls[0][0], "pool/snapshot")
        self.assertEqual(resp.status, "200 OK")
        self.assertEqual(json.loads(resp.body), [])


if __name__ == "__main__":
    unittest.main()
