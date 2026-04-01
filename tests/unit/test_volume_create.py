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
        HTTP_500="500 Internal Server Error",
    ),
)

import truenascsp  # noqa: E402


class FakeBackendResponse:
    def __init__(self, dataset):
        self.status_code = 200
        self._dataset = dataset

    def json(self):
        return self._dataset


class FakeAPI:
    def __init__(self):
        self.dataset_defaults = {
            "description": "Dataset created by HPE CSI Driver for Kubernetes as {pv} in {namespace} from {pvc}",
            "volblocksize": "8K",
            "sparse": "true",
            "deduplication": "OFF",
            "sync": "STANDARD",
            "compression": "LZ4",
        }
        self.logger = logging.getLogger("test-volume-create")
        self.req_backend = None
        self.last_post = None

    def post(self, resource, body):
        self.last_post = (resource, body)
        self.req_backend = FakeBackendResponse(
            {
                "id": body["name"],
                "name": body["name"],
                "comments": {"value": body["comments"]},
                "volsize": {"rawvalue": str(body["volsize"])},
                "compression": {"value": body["compression"]},
                "deduplication": {"value": body["deduplication"]},
                "sync": {"value": body["sync"]},
                "volblocksize": {"value": body["volblocksize"]},
                "origin": None,
            }
        )

    def create_target(self, dataset, **kwargs):
        return {"dataset": dataset, "content": kwargs.get("content")}

    def dataset_to_volume(self, dataset):
        return {
            "id": dataset["id"].replace("/", "_"),
            "name": dataset["name"].split("/")[-1],
            "size": int(dataset["volsize"]["rawvalue"]),
        }


class VolumeCreateTests(unittest.TestCase):
    def test_volume_create_posts_integer_volsize(self):
        api = FakeAPI()
        req = SimpleNamespace(
            context=api,
            media={
                "name": "pvc-test",
                "size": "1073741824",
                "description": "Created for {pv}",
                "config": {
                    "root": "tank/csi",
                    "volblocksize": "16K",
                    "sparse": "false",
                    "deduplication": "OFF",
                    "sync": "STANDARD",
                    "compression": "LZ4",
                    "csi.storage.k8s.io/pvc/name": "claim-a",
                    "csi.storage.k8s.io/pvc/namespace": "ns-a",
                    "csi.storage.k8s.io/pv/name": "pv-a",
                },
            },
        )
        resp = SimpleNamespace(body=None, status=None)

        truenascsp.Volumes().on_post(req, resp)

        self.assertIsNotNone(api.last_post)
        resource, payload = api.last_post
        self.assertEqual(resource, "pool/dataset")
        self.assertEqual(payload["type"], "VOLUME")
        self.assertEqual(payload["name"], "tank/csi/pvc-test")
        self.assertEqual(payload["volsize"], 1073741824)
        self.assertIsInstance(payload["volsize"], int)
        self.assertFalse(payload["sparse"])

        body = json.loads(resp.body)
        self.assertEqual(body["id"], "tank_csi_pvc-test")
        self.assertEqual(body["size"], 1073741824)


if __name__ == "__main__":
    unittest.main()
