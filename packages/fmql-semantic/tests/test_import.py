import fmql_semantic
from fmql_semantic import SemanticBackend


def test_version():
    assert fmql_semantic.__version__


def test_backend_exposed():
    assert SemanticBackend.name == "semantic"


def test_entrypoint_discoverable():
    from fmql.search.registry import clear_cache, discover_backends

    clear_cache()
    backends = discover_backends()
    assert "semantic" in backends, f"registered backends: {sorted(backends)}"
    assert backends["semantic"] is SemanticBackend
