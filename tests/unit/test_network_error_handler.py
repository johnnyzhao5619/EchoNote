import sys
import types
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")
    for name in [
        "ConnectError",
        "TimeoutException",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "NetworkError",
        "ProxyError",
        "UnsupportedProtocol",
        "RemoteProtocolError",
        "LocalProtocolError",
        "HTTPStatusError",
    ]:
        setattr(httpx_stub, name, type(name, (Exception,), {}))
    sys.modules["httpx"] = httpx_stub

from utils.network_error_handler import check_network_connectivity


class DummySocket:
    instances: list["DummySocket"] = []

    def __init__(self, *args, **kwargs):
        self.addresses = []
        self.close_count = 0
        DummySocket.instances.append(self)

    def connect(self, address):
        self.addresses.append(address)

    def close(self):
        self.close_count += 1


@pytest.fixture(autouse=True)
def reset_dummy_socket_instances():
    DummySocket.instances.clear()
    yield
    DummySocket.instances.clear()


def test_check_network_connectivity_closes_socket_each_time(monkeypatch):
    monkeypatch.setattr(
        "utils.network_error_handler.socket.setdefaulttimeout", lambda *_, **__: None
    )
    monkeypatch.setattr(
        "utils.network_error_handler.socket.socket",
        lambda *args, **kwargs: DummySocket(*args, **kwargs),
    )

    attempts = 3
    for _ in range(attempts):
        assert check_network_connectivity()

    assert len(DummySocket.instances) == attempts
    assert all(instance.close_count >= 1 for instance in DummySocket.instances)
