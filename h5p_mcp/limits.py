"""Configurable budgets, shared by name with the Node bridge."""
import os


def limit(name: str, default: int) -> int:
    value = int(os.environ.get(f"H5P_MCP_MAX_{name}", default))
    if value < 1:
        raise ValueError(f"Invalid limit {name}")
    return value
