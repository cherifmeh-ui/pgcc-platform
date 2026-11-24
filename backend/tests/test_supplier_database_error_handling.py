import ast
from pathlib import Path


def test_supplier_conflict_handlers_only_map_integrity_errors_to_http_409():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "app" / "api" / "v1" / "endpoints" / "suppliers.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    matching_handlers = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        integrity_handlers = [
            handler for handler in node.handlers
            if handler.type is not None
            and isinstance(handler.type, ast.Name)
            and handler.type.id == "IntegrityError"
        ]
        generic_handlers = [
            handler for handler in node.handlers
            if handler.type is not None
            and isinstance(handler.type, ast.Name)
            and handler.type.id == "Exception"
        ]
        if not integrity_handlers and not generic_handlers:
            continue
        if not generic_handlers:
            continue

        matching_handlers += 1
        assert integrity_handlers, "Generic database handler must have a specific IntegrityError branch"
        generic = generic_handlers[0]
        assert any(
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Await)
            and isinstance(item.value.value, ast.Call)
            and isinstance(item.value.value.func, ast.Attribute)
            and item.value.value.func.attr == "rollback"
            for item in generic.body
        ), "Unexpected database errors must roll back the transaction"
        assert any(
            isinstance(item, ast.Raise) and item.exc is None
            for item in generic.body
        ), "Unexpected database errors must be re-raised unchanged"
        assert not any(
            isinstance(item, ast.Raise)
            and isinstance(item.exc, ast.Call)
            and isinstance(item.exc.func, ast.Name)
            and item.exc.func.id == "HTTPException"
            for item in generic.body
        ), "Unexpected database errors must not be converted into HTTP business conflicts"

    assert matching_handlers == 8
