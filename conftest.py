"""Test-wide safety net: isolate HERMES_HOME for every test.

Several steps (board install, doctor/diagnose, wireup, runtime) resolve the
Hermes data dir from ``$HERMES_HOME`` (default ``~/.hermes``) to read or write
config.yaml, sidecars, and the mention map. Without isolation a test that runs
those steps would read — or worse, mutate — the developer's real ~/.hermes.
This autouse fixture points HERMES_HOME at a fresh temp dir per test. Tests that
need a specific config still write to ``$HERMES_HOME/config.yaml`` or override
the env via their own monkeypatch (which runs after this fixture)."""
import pytest


@pytest.fixture(autouse=True)
def _isolate_hermes_home(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("hermes_home")
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home
