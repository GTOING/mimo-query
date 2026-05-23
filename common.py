#!/usr/bin/env python3
"""Shared helpers for MiMo Query tools."""

MIMO_ORIGIN = "https://platform.xiaomimimo.com"

COOKIE_FIELDS = [
    "api-platform_slh",
    "api-platform_ph",
    "api-platform_serviceToken",
    "userId",
]


def parse_cookie_string(raw):
    """Extract MiMo cookie fields from a Cookie header or Chrome DevTools table copy."""
    pairs = {}
    raw = raw or ""
    if "\t" in raw:
        for line in raw.strip().splitlines():
            cols = line.split("\t")
            if len(cols) >= 2:
                name = cols[0].strip()
                value = cols[1].strip().strip('"')
                if name:
                    pairs[name] = value
    else:
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                pairs[key.strip()] = value.strip()

    return {field: pairs[field].strip() for field in COOKIE_FIELDS if pairs.get(field, "").strip()}


def build_cookie(fields):
    """Build a Cookie header string preserving MiMo COOKIE_FIELDS order first."""
    ordered = []
    for field in COOKIE_FIELDS:
        if field in fields and fields[field]:
            ordered.append((field, fields[field]))
    for key, value in fields.items():
        if key not in COOKIE_FIELDS and value:
            ordered.append((key, value))
    return "; ".join(f"{key}={value}" for key, value in ordered)


def mask_secret(value, visible_start=3, visible_end=4):
    """Mask a secret while keeping a small preview useful for identification."""
    value = value or ""
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return f"{value[:visible_start]}****{value[-visible_end:]}"


def mask_email(value):
    """Mask an email address while preserving the domain."""
    value = value or ""
    if "@" not in value:
        return mask_secret(value)
    local, domain = value.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "***"
    else:
        masked_local = f"{local[:1]}***{local[-1:]}"
    return f"{masked_local}@{domain}"
