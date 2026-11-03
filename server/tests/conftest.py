import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    return create_app({"DATABASE": str(tmp_path / "test.sqlite"), "FETCH_WEATHER": False, "TESTING": True,
                       "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def demo(client):
    """API client signed in to a fresh sample household."""
    tok = client.post("/api/demo").get_json()["token"]

    class C:
        def get(self, url, **kw):
            return client.get(url, headers={"Authorization": f"Bearer {tok}"}, **kw)

        def post(self, url, json=None):
            return client.post(url, json=json or {}, headers={"Authorization": f"Bearer {tok}"})

        def put(self, url, json=None):
            return client.put(url, json=json or {}, headers={"Authorization": f"Bearer {tok}"})

        def delete(self, url):
            return client.delete(url, headers={"Authorization": f"Bearer {tok}"})
    return C()


def appliance_id(demo, type_):
    return next(a["id"] for a in demo.get("/api/appliances").get_json()["appliances"] if a["type"] == type_)
