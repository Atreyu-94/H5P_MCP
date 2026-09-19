"""Configurable budgets, shared by name with the Node bridge."""
import os


def limit(name: str, default: int) -> int:
    value = int(os.environ.get(f"H5P_MCP_MAX_{name}", default))
    if value < 1:
        raise ValueError(f"Invalid limit {name}")
    return value


def check_tree(root) -> None:
    stack = [(root, 0)]
    nodes = 0
    maximum = limit('NODES', 100000)
    depth_limit = limit('DEPTH', 64)
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if depth > depth_limit:
            raise ValueError('INPUT_TOO_DEEP: input nesting budget exceeded')
        if nodes > maximum:
            raise ValueError('INPUT_TOO_LARGE: input node budget exceeded')
        children = value.values() if isinstance(value, dict) else value if isinstance(value, list) else ()
        if len(children) + len(stack) + nodes > maximum:
            raise ValueError('INPUT_TOO_LARGE: input node budget exceeded')
        stack.extend((child, depth + 1) for child in children)
