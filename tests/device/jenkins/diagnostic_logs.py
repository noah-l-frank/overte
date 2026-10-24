"""Publish complete redacted diagnostic text without publishing private originals.

This opt-in debugging utility does not change test verdicts, timeouts, or cleanup.
The caller supplies actual private selectors and credentials from its owned inputs.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat


class DiagnosticPrivacyError(ValueError):
    pass


def _require(value, code):
    if not value:
        raise DiagnosticPrivacyError(code)


def _stamp(value):
    return (value.st_dev, value.st_ino, value.st_uid, value.st_gid,
            value.st_mode, value.st_nlink, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _private_read(path):
    path = Path(path)
    _require(path.is_absolute() and path.resolve() == path,
             'DIAGNOSTIC_PRIVATE_PATH_REQUIRED')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
                 and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1,
                 'DIAGNOSTIC_PRIVATE_FILE_REQUIRED')
        raw = stream.read()
        _require(_stamp(before) == _stamp(os.fstat(stream.fileno()))
                 == _stamp(path.lstat()), 'DIAGNOSTIC_ORIGINAL_CHANGED')
    return raw, _stamp(before)


_PRIVATE_FIELD = re.compile(
    r'''(?ix)["']?(?:password|passwd|access[_-]?token|control[_-]?token|
    refresh[_-]?token|token|nonce|authorization|secret|ownerToken|deviceSerial|androidSerial|
    udid|selector|reservationKey)["']?\s*[:=]\s*
    (?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;\}\]\r\n]+)''')
_URL = re.compile(r'''[a-z][a-z0-9+.-]*://[^\s<>"']+''', re.I)
_UUID = re.compile(r'(?i)\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b')
_IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
_IPV6 = re.compile(r'(?<![\w:])[0-9a-fA-F]*:[0-9a-fA-F:]+(?:%[\w.-]+)?(?![\w:])')
_MAC = re.compile(r'(?i)(?<![\w:])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![\w:])')
_BEARER = re.compile(r'(?i)\b(?:bearer|basic)\s+[a-z0-9+/=_~.:-]+')
_ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
# The same forbidden categories as tests/device/audit_artifacts.py. Apply to
# every output chunk; that command intentionally skips files larger than 4 MiB.
_AUDIT = (
    re.compile(r'''(?i)["'](?:password|passwd|access[_-]?token|control[_-]?token|authorization|secret)["']\s*[:=]'''),
    re.compile(r'[a-z][a-z0-9+.-]*://[^/@\s:]+:[^/@\s]+@', re.I),
    re.compile(r'''(?i)["'](?:deviceSerial|udid|androidSerial)["']\s*:'''),
)


def sanitize(text, private_values):
    _require(type(text) is str and '\0' not in text,
             'DIAGNOSTIC_TEXT_REQUIRED')
    _require(isinstance(private_values, (set, frozenset, list, tuple))
             and all(type(v) is str and len(v) >= 4 for v in private_values),
             'DIAGNOSTIC_ACTUAL_PRIVATE_VALUES_REQUIRED')
    # Whole-text replacement precedes chunking, including multiline secrets.
    for value in sorted(set(private_values), key=len, reverse=True):
        text = text.replace(value, '<private>')
    text = _ANSI.sub('', text)
    text = _BEARER.sub('<private-auth>', text)
    text = _PRIVATE_FIELD.sub('<private-field>', text)
    text = _URL.sub('<private-url>', text)
    text = _UUID.sub('<private-id>', text)
    text = _MAC.sub('<private-address>', text)

    def address(match):
        try:
            ipaddress.ip_address(match.group().split('%', 1)[0])
        except ValueError:
            return match.group()
        return '<private-address>'

    text = _IPV4.sub(address, text)
    text = _IPV6.sub(address, text)
    _require(not any(v in text for v in private_values)
             and not any(p.search(text) for p in _AUDIT),
             'DIAGNOSTIC_PUBLIC_PRIVACY_REJECTED')
    return text


def _write(directory, name, raw):
    path = directory / name
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                          | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'name': name, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def publish_log(path, out, private_values, chunk_bytes=1024 * 1024):
    """Keep all original lines; publish no original path or private value.

    Returns the manifest also written as index.json. The caller must publish
    only a completely validated generation, never a partially written directory.
    """
    _require(type(chunk_bytes) is int and 128 <= chunk_bytes <= 1024 * 1024,
             'DIAGNOSTIC_CHUNK_BOUND_REQUIRED')
    path, out = Path(path), Path(out)
    _require(out.is_absolute() and out.resolve() == out and not out.exists()
             and out.parent.is_dir(), 'DIAGNOSTIC_FRESH_PUBLIC_ROOT_REQUIRED')
    original, pin = _private_read(path)
    try:
        decoded = original.decode('utf-8')
    except UnicodeDecodeError:
        # Keep exact original privately. Public representation explicitly records
        # replacement characters instead of silently claiming byte equivalence.
        decoded = original.decode('utf-8', errors='replace')
    public = sanitize(decoded, private_values).encode('utf-8')
    _require(_stamp(path.lstat()) == pin, 'DIAGNOSTIC_ORIGINAL_CHANGED')
    chunks = []
    remaining = public
    while remaining:
        end = min(chunk_bytes, len(remaining))
        while end < len(remaining) and remaining[end] & 0xc0 == 0x80:
            end -= 1
        chunks.append(remaining[:end])
        remaining = remaining[end:]
    # Validate each chunk and the complete stream before creating output.
    for raw in chunks:
        text = raw.decode('utf-8')
        _require(not any(p.search(text) for p in _AUDIT),
                 'DIAGNOSTIC_PUBLIC_PRIVACY_REJECTED')
    out.mkdir(mode=0o700)
    files = [_write(out, f'part-{number:05d}.log', raw)
             for number, raw in enumerate(chunks, 1)]
    result = {
        'schemaVersion': 1, 'scope': 'REDACTED_DIAGNOSTIC_NOT_TEST_ACCEPTANCE',
        'originalBytes': len(original),
        'originalSha256': hashlib.sha256(original).hexdigest(),
        'originalLines': len(original.splitlines()),
        'originalUtf8Valid': decoded.encode('utf-8') == original,
        'publicBytes': len(public), 'publicSha256': hashlib.sha256(public).hexdigest(),
        'publicLines': len(public.splitlines()), 'truncated': False,
        'originalRetained': True, 'privacyAudit': 'passed', 'parts': files,
    }
    _require(_stamp(path.lstat()) == pin, 'DIAGNOSTIC_ORIGINAL_CHANGED')
    _write(out, 'index.json', (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    return result
