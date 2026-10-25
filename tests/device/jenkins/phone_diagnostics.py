"""Strengthen Phone account privacy around the reviewed complete-log publisher."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from types import ModuleType

# Keep the existing stream/hash/chunk implementation and its original license
# and authorship. Import its reviewed exact bytes from this source directory,
# rather than a similarly named module on a session's inherited Python path.
_BASE_SHA256 = '2ceeeb3570e902a7bc8ada6a0078600bb4cf968e16c813ff1456d089e3875bb7'
_path = Path(__file__).with_name('diagnostic_logs.py')
if not _path.is_absolute() or _path.resolve() != _path:
    raise ValueError('PHONE_DIAGNOSTIC_SOURCE_ALIAS')
_raw = _path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != _BASE_SHA256:
    raise ValueError('PHONE_DIAGNOSTIC_SOURCE_CHANGED')
_base = ModuleType('_phone_bound_diagnostic_logs')
_base.__file__ = str(_path)
exec(compile(_raw, str(_path), 'exec'), _base.__dict__)
_original_sanitize = _base.sanitize
DiagnosticPrivacyError = _base.DiagnosticPrivacyError
_require = _base._require

# Native messages interpolate unquoted names at varying positions. Retain one
# placeholder per original line rather than guessing account-value boundaries.
_ACCOUNT_LINE = re.compile(
    r'(?i)\b(?:(?:domain[_-]?)?user(?:[_-]?name)?(?:[_-]?(?:id|signature))?|'
    r'account(?:[_-]?(?:id|name|email))?|display[_-]?name|e-?mail|login|logged\s+in|'
    r'(?:public|private)[ _-]?key(?:[_-]?(?:data|pem|bytes|id))?|'
    r'signature(?:[_-]?(?:data|bytes))?|ssh-(?:rsa|ed25519))\b')
_PEM = re.compile(r'-----BEGIN [A-Z0-9 ]*(?:KEY|CERTIFICATE)-----'
                  r'[\s\S]*?(?:-----END [A-Z0-9 ]*(?:KEY|CERTIFICATE)-----|\Z)')
_EMAIL = re.compile(r'''(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@'''
                    r'''[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?![\w.-])''')
_HOME = re.compile(r'''(?<![\w])/(?:home/[^/\s"'<>]+|Users/[^/\s"'<>]+|root)'''
                   r'''(?:/[^\s"'<>]*)?''')
# Bare DER/base64 or hex signatures can lack field names. Source hashes remain
# available in sealed metadata; exact original log bytes stay private.
_ENCODED = re.compile(r'(?<![A-Za-z0-9+/_=-])[A-Za-z0-9+/_=-]{64,}(?![A-Za-z0-9+/_=-])')


def _hide_lines(value, label):
    return re.sub(r'[^\r\n]+', label, value)


def sanitize(text, private_values):
    _require(type(text) is str and '\0' not in text, 'DIAGNOSTIC_TEXT_REQUIRED')
    _require(isinstance(private_values, (set, frozenset, list, tuple))
             and all(type(value) is str and len(value) >= 4 for value in private_values),
             'DIAGNOSTIC_ACTUAL_PRIVATE_VALUES_REQUIRED')
    # Preserve the original line count even when a supplied secret spans lines.
    for value in sorted(set(private_values), key=len, reverse=True):
        text = text.replace(value, _hide_lines(value, '<private>'))
    text = _base._ANSI.sub('', text)
    text = _PEM.sub(lambda match: _hide_lines(match.group(), '<private-key-material>'), text)
    lines = []
    for line in text.splitlines(keepends=True):
        if _ACCOUNT_LINE.search(line):
            category = ('<private-auth-signature-rejected>' if re.search(
                r'(?i)signature.*(?:fail|denying|decrypt|invalid)|(?:decrypt|invalid).*signature', line)
                else '<private-account-diagnostic>')
            line = _hide_lines(line, category)
        lines.append(line)
    text = ''.join(lines)
    text = _EMAIL.sub('<private-email>', text)
    text = _HOME.sub('<private-home-path>', text)
    text = _ENCODED.sub('<private-key-material>', text)
    text = _original_sanitize(text, ())
    _require(not any(value in text for value in private_values)
             and not any(pattern.search(text) for pattern in (_EMAIL, _HOME, _ENCODED, _PEM)),
             'DIAGNOSTIC_PUBLIC_PRIVACY_REJECTED')
    return text


def publish_log(path, out, private_values, chunk_bytes=1024 * 1024):
    """Reuse original private-file, UTF8, chunk, hash and mutation checks."""
    original = _base.sanitize
    _base.sanitize = sanitize
    try:
        return _base.publish_log(path, out, private_values, chunk_bytes)
    finally:
        _base.sanitize = original
