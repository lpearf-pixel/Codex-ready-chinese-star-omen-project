from __future__ import annotations


def validate(instance, schema):
    required = schema.get("required", [])
    for key in required:
        if key not in instance:
            raise ValueError(f"Missing required field: {key}")
