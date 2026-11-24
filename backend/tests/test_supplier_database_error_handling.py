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

    assert matching_handlers == 26


def test_supplier_access_lifecycle_writes_enqueue_audit_before_commit():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "app" / "api" / "v1" / "endpoints" / "suppliers.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    expected = {
        "decide_supplier_access_request": "SUPPLIER_ACCESS_",
        "review_supplier_access": "REVIEW_SUPPLIER_ACCESS",
        "revoke_supplier_access_request": "REVOKE_SUPPLIER_ACCESS",
        "expire_supplier_access_request": "EXPIRE_SUPPLIER_ACCESS",
        "link_supplier_to_risk": "LINK_SUPPLIER_RISK",
        "link_supplier_asset": "LINK_SUPPLIER_ASSET",
        "terminate_supplier_asset_link": "TERMINATE_SUPPLIER_ASSET_LINK",
        "create_supplier_assessment": "CREATE_ASSESSMENT",
        "save_supplier_assessment_answers": "UPDATE_ASSESSMENT_ANSWERS",
        "submit_supplier_assessment": "SUBMIT_ASSESSMENT",
        "validate_supplier_assessment": "VALIDATE_ASSESSMENT",
        "create_supplier_contract": "CREATE_CONTRACT",
        "update_supplier_contract": "UPDATE_CONTRACT",
        "create_supplier_contact": "CREATE_CONTACT",
        "update_supplier_contact": "UPDATE_CONTACT",
        "create_supplier": "CREATE",
        "update_supplier": "UPDATE",
        "archive_supplier": "ARCHIVE",
    }
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for function_name, action_marker in expected.items():
        function = functions[function_name]
        enqueue_calls = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "enqueue_audit_event"
        ]
        commit_calls = [
            node for node in ast.walk(function)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "commit"
        ]
        assert enqueue_calls, f"{function_name} must enqueue audit"
        assert commit_calls, f"{function_name} must commit"
        assert any(action_marker in ast.unparse(node.value) for node in enqueue_calls)
        assert min(node.lineno for node in enqueue_calls) < min(node.lineno for node in commit_calls)
