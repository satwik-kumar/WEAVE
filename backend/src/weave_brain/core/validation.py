"""Canonical ID validation usable outside HTTP modules."""

import re

from fastapi import HTTPException


def canonical(value: str, service: bool = False) -> str:
    pattern = r"(?:person|team|service|repository|file|document|decision|ticket|incident|test|project):[a-z0-9][a-z0-9./:_-]*"
    if (
        not re.fullmatch(pattern, value)
        or len(value) > 500
        or (service and not value.startswith("service:"))
    ):
        raise HTTPException(400, "Invalid canonical entity ID.")
    return value
