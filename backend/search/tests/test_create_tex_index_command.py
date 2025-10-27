from __future__ import annotations

from django.core.management import call_command

from search.management.commands import create_tex_index


class DummyIndices:
    def __init__(self, *, exists_result: bool):
        self.exists_result = exists_result
        self.exists_calls: list[str] = []
        self.create_calls: list[tuple[str, dict]] = []
        self.close_calls: list[str] = []
        self.put_settings_calls: list[tuple[str, dict]] = []
        self.put_mapping_calls: list[tuple[str, dict]] = []
        self.open_calls: list[str] = []
        self.refresh_calls: list[str] = []

    def exists(self, *, index: str) -> bool:
        self.exists_calls.append(index)
        return self.exists_result

    def create(self, *, index: str, body: dict) -> None:
        self.create_calls.append((index, body))

    def close(self, *, index: str) -> None:
        self.close_calls.append(index)

    def put_settings(self, *, index: str, body: dict) -> None:
        self.put_settings_calls.append((index, body))

    def put_mapping(self, *, index: str, body: dict) -> None:
        self.put_mapping_calls.append((index, body))

    def open(self, *, index: str) -> None:
        self.open_calls.append(index)

    def refresh(self, *, index: str) -> None:
        self.refresh_calls.append(index)


class DummyClient:
    def __init__(self, indices: DummyIndices):
        self.indices = indices


def test_create_tex_index_creates_index(monkeypatch):
    monkeypatch.setattr(
        create_tex_index.settings, "OPENSEARCH_INDEX", "test-index", raising=False
    )
    indices = DummyIndices(exists_result=False)
    client = DummyClient(indices)

    monkeypatch.setattr(create_tex_index.opensearch_client, "create_client", lambda: client)
    monkeypatch.setattr(create_tex_index, "get_index_definition", lambda: {"settings": {}, "mappings": {}})

    call_command("create_tex_index")

    assert indices.exists_calls == ["test-index"]
    assert indices.create_calls == [("test-index", {"settings": {}, "mappings": {}})]
    assert not indices.close_calls
    assert not indices.put_settings_calls
    assert not indices.put_mapping_calls
    assert not indices.open_calls
    assert not indices.refresh_calls


def test_create_tex_index_updates_existing_index(monkeypatch):
    monkeypatch.setattr(
        create_tex_index.settings, "OPENSEARCH_INDEX", "test-index", raising=False
    )
    definition = {
        "settings": {"number_of_replicas": 0},
        "mappings": {"properties": {"field": {"type": "keyword"}}},
    }
    indices = DummyIndices(exists_result=True)
    client = DummyClient(indices)

    monkeypatch.setattr(create_tex_index.opensearch_client, "create_client", lambda: client)
    monkeypatch.setattr(create_tex_index, "get_index_definition", lambda: definition)

    call_command("create_tex_index")

    assert indices.exists_calls == ["test-index"]
    assert not indices.create_calls
    assert indices.close_calls == ["test-index"]
    assert indices.put_settings_calls == [("test-index", definition["settings"])]
    assert indices.put_mapping_calls == [("test-index", definition["mappings"])]
    assert indices.open_calls == ["test-index"]
    assert indices.refresh_calls == ["test-index"]
