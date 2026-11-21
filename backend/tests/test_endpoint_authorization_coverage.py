"""Endpoint authorization coverage: require explicit backend protection."""
import ast
from pathlib import Path


ENDPOINTS_DIR = Path(__file__).parents[1] / "app" / "api" / "v1" / "endpoints"
AUTHENTICATION_ONLY_FILES = {"auth.py", "me.py"}


def _is_router_endpoint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == "router":
                return decorator.func.attr in {"get", "post", "put", "patch", "delete"}
    return False


def _has_permission_dependency(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
        for child in ast.walk(default):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id in {"require_permission", "require_role", "get_current_user"}:
                    return True
    return False


def test_all_non_authentication_endpoints_have_backend_authorization_dependency():
    violations = []
    for endpoint_file in ENDPOINTS_DIR.glob("*.py"):
        if endpoint_file.name in AUTHENTICATION_ONLY_FILES:
            continue
        tree = ast.parse(endpoint_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_router_endpoint(node):
                if not _has_permission_dependency(node):
                    violations.append(f"{endpoint_file.name}:{node.name}")
    assert violations == [], f"Endpoints without explicit backend authorization: {violations}"
