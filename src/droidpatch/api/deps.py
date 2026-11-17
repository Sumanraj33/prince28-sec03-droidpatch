"""Dependency helpers for routes."""

from fastapi import Request


def get_records(request: Request) -> list[dict]:
    """Return the loaded records from application state."""
    return request.app.state.records
