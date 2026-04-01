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
        self.normalize_volsize_calls = []

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

    def normalize_volsize(self, size):
        self.normalize_volsize_calls.append(size)
        return int(size)


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
        self.assertEqual(api.normalize_volsize_calls, ["1073741824"])
        self.assertFalse(payload["sparse"])

        body = json.loads(resp.body)
        self.assertEqual(body["id"], "tank_csi_pvc-test")
        self.assertEqual(body["size"], 1073741824)

    def test_volume_update_uses_normalized_volsize(self):
        api = FakeVolumeUpdateAPI()
        req = SimpleNamespace(
            context=api,
            media={
                "size": "2147483648",
                "description": "updated",
                "config": {},
            },
        )
        resp = SimpleNamespace(body=None, status=None)

        truenascsp.Volume().on_put(req, resp, "tank_csi_pvc-test")

        self.assertEqual(api.normalize_volsize_calls, ["2147483648"])
        self.assertEqual(api.last_put[1]["volsize"], 2147483648)


class FakeVolumeUpdateAPI:
    def __init__(self):
        self.logger = logging.getLogger("test-volume-update")
        self.req_backend = SimpleNamespace(
            status_code=200,
            content=b"",
        )
        self.dataset_mutables = [
            "size",
            "description",
            "deduplication",
            "compression",
            "sync",
            "volblocksize",
        ]
        self.normalize_volsize_calls = []
        self.last_put = None
        self.fetch_count = 0

    def normalize_volsize(self, size):
        self.normalize_volsize_calls.append(size)
        return int(size)

    def xslt_id_to_dataset(self, xslt):
        return xslt.replace("_", "/")

    def fetch(self, resource, **kwargs):
        self.fetch_count += 1
        return {
            "id": "tank/csi/pvc-test",
            "name": "tank/csi/pvc-test",
            "comments": {"value": "updated"},
            "volsize": {"rawvalue": "2147483648"},
            "compression": {"value": "LZ4"},
            "deduplication": {"value": "OFF"},
            "sync": {"value": "STANDARD"},
            "volblocksize": {"value": "8K"},
            "origin": None,
        }

    def put(self, uri, payload):
        self.last_put = (uri, payload)

    def uri_id(self, resource, rid):
        return f"{resource}/id/{rid}"

    def dataset_to_volume(self, dataset):
        return {
            "id": dataset["id"].replace("/", "_"),
            "name": dataset["name"].split("/")[-1],
            "size": int(dataset["volsize"]["rawvalue"]),
        }


if __name__ == "__main__":
    unittest.main()
