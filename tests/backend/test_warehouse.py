from __future__ import annotations
import pytest
from databricks.sdk.service.sql import StatementState


class _Col:
    def __init__(self, name): self.name = name

class _Schema:
    def __init__(self, names): self.columns = [_Col(n) for n in names]

class _Manifest:
    def __init__(self, names): self.schema = _Schema(names)

class _Err:
    def __init__(self, code="BAD_REQUEST", msg="boom"):
        self.error_code = code; self.message = msg

class _Status:
    def __init__(self, state, error=None): self.state = state; self.error = error

class _Result:
    def __init__(self, data_array): self.data_array = data_array

class _Resp:
    def __init__(self, state, manifest, result, error=None):
        self.statement_id = "st-1"
        self.status = _Status(state, error); self.manifest = manifest; self.result = result

class _ExecApi:
    def __init__(self, resp, polls=()):
        self._resp = resp; self._polls = list(polls); self.kwargs = None
        self.get_calls = 0; self.canceled = []
    def execute_statement(self, **kw): self.kwargs = kw; return self._resp
    def get_statement(self, statement_id):
        self.get_calls += 1
        return self._polls.pop(0) if self._polls else self._resp
    def cancel_execution(self, statement_id): self.canceled.append(statement_id)

class _WS:
    def __init__(self, api): self.statement_execution = api


def _install(monkeypatch, resp, polls=()):
    from data_classification_review_app.backend.clients import warehouse as mod
    monkeypatch.setenv("WAREHOUSE_ID", "wh-1")
    monkeypatch.setattr(mod, "_sleep", lambda s: None)
    api = _ExecApi(resp, polls)
    monkeypatch.setattr(mod, "_sdk", lambda: _WS(api))
    return mod, api


def test_execute_sql_maps_inline_rows(monkeypatch):
    resp = _Resp(StatementState.SUCCEEDED, _Manifest(["id", "name"]), _Result([[1, "a"], [2, "b"]]))
    mod, api = _install(monkeypatch, resp)
    rows = mod.execute_sql("SELECT id, name FROM t")
    assert rows == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    assert "disposition" not in api.kwargs  # default INLINE


def test_execute_sql_empty(monkeypatch):
    resp = _Resp(StatementState.SUCCEEDED, _Manifest(["id"]), _Result(None))
    mod, _ = _install(monkeypatch, resp)
    assert mod.execute_sql("SELECT id FROM t") == []


def test_execute_sql_raises_on_failure(monkeypatch):
    resp = _Resp(StatementState.FAILED, None, None, error=_Err("BAD_REQUEST", "nope"))
    mod, _ = _install(monkeypatch, resp)
    with pytest.raises(RuntimeError, match=r"BAD_REQUEST.*nope"):
        mod.execute_sql("SELECT 1")


def test_execute_sql_polls_statement_still_pending_after_wait_timeout(monkeypatch):
    # A cold warehouse returns the statement still PENDING after the 30 s wait, with no
    # error; it must be polled to completion rather than treated as a failure (#15).
    pending = _Resp(StatementState.PENDING, None, None)
    running = _Resp(StatementState.RUNNING, None, None)
    done = _Resp(StatementState.SUCCEEDED, _Manifest(["id"]), _Result([[1]]))
    mod, api = _install(monkeypatch, pending, polls=[running, done])
    assert mod.execute_sql("CREATE OR REPLACE VIEW v AS SELECT 1 AS id") == [{"id": 1}]
    assert api.get_calls == 2


def test_execute_sql_terminal_state_without_error_names_the_state(monkeypatch):
    resp = _Resp(StatementState.CANCELED, None, None)
    mod, _ = _install(monkeypatch, resp)
    with pytest.raises(RuntimeError, match=r"CANCELED"):
        mod.execute_sql("SELECT 1")


def test_execute_sql_cancels_statement_still_pending_at_deadline(monkeypatch):
    pending = _Resp(StatementState.PENDING, None, None)
    mod, api = _install(monkeypatch, pending)
    monkeypatch.setattr(mod, "_MAX_WAIT_S", 3 * mod._POLL_INTERVAL_S)
    with pytest.raises(RuntimeError, match=r"still PENDING"):
        mod.execute_sql("SELECT 1")
    assert api.get_calls == 3
    assert api.canceled == ["st-1"]


class _HttpResp:
    def __init__(self, data): self._data = data
    def raise_for_status(self): pass
    def json(self): return self._data


def test_execute_sql_obo_polls_statement_still_pending(monkeypatch):
    from data_classification_review_app.backend.clients import warehouse as mod
    monkeypatch.setenv("WAREHOUSE_ID", "wh-1")
    monkeypatch.setattr(mod, "_sleep", lambda s: None)
    gets = []
    pending = {"statement_id": "st-1", "status": {"state": "PENDING"}}
    done = {"statement_id": "st-1", "status": {"state": "SUCCEEDED"},
            "manifest": {"schema": {"columns": [{"name": "id"}]}},
            "result": {"data_array": [["1"]]}}
    monkeypatch.setattr(mod.httpx, "post", lambda url, **kw: _HttpResp(pending))
    def fake_get(url, **kw):
        gets.append((url, kw["headers"]["Authorization"]))
        return _HttpResp(done)
    monkeypatch.setattr(mod.httpx, "get", fake_get)
    rows = mod.execute_sql("SELECT 1 AS id", token="tok", host="example.cloud.databricks.com")
    assert rows == [{"id": "1"}]
    assert gets == [("https://example.cloud.databricks.com/api/2.0/sql/statements/st-1",
                     "Bearer tok")]
