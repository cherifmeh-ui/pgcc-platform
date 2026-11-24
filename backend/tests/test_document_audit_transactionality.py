"""Source-level regression checks for transactional document/RAG audit writes."""
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _function(tree: ast.AST, name: str):
    return next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _calls(function: ast.AST, name: str):
    return [
        node for node in ast.walk(function)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and (
            isinstance(node.value.func, ast.Name)
            and node.value.func.id == name
            or isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == name
        )
    ]


def test_document_upload_and_delete_enqueue_audit_before_commit():
    source = (ROOT / "app/api/v1/endpoints/documents.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in ("upload_document", "delete_document"):
        function = _function(tree, name)
        enqueue = _calls(function, "enqueue_audit_event")
        commits = _calls(function, "commit")
        assert enqueue, f"{name} must enqueue an audit event"
        assert commits, f"{name} must commit its business transaction"
        assert min(node.lineno for node in enqueue) < min(node.lineno for node in commits)


def test_document_mutations_roll_back_unexpected_transaction_errors():
    source = (ROOT / "app/api/v1/endpoints/documents.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in ("upload_document", "delete_document"):
        function = _function(tree, name)
        handlers = [
            handler
            for node in ast.walk(function)
            if isinstance(node, ast.Try)
            for handler in node.handlers
            if isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
        ]
        assert handlers, f"{name} must handle unexpected transaction errors"
        assert any(
            any(
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Await)
                and isinstance(item.value.value, ast.Call)
                and isinstance(item.value.value.func, ast.Attribute)
                and item.value.value.func.attr == "rollback"
                for item in handler.body
            )
            and any(isinstance(item, ast.Raise) and item.exc is None for item in handler.body)
            for handler in handlers
        ), f"{name} must roll back and re-raise unexpected errors"


def test_rag_indexing_audit_is_enqueued_before_chunk_transaction_commit():
    source = (ROOT / "app/services/rag_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = _function(tree, "index_document")
    enqueue = _calls(function, "enqueue_audit_event")
    commits = _calls(function, "commit")
    assert enqueue, "RAG indexing must enqueue its audit event"
    assert commits, "RAG indexing must commit chunk replacement"
    assert min(node.lineno for node in enqueue) < min(node.lineno for node in commits)
