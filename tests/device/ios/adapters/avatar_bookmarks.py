"""Exact real AvatarBookmarks persistence bytes, separate from loaded/UI rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode, exact, need
from adapters.normal_ui import NativeUIError
from ios.adapters.location_bookmarks import original_bytes as stable_file

VERSION = 1
SOURCE = 'avatar-bookmarks-persistence'


def original_bytes(value):
    need(type(value) is dict and value.get('source') == SOURCE)
    # The existing bounded regular-file/content grammar is common. Its fixed
    # location source is only a parser selector, never retained as provenance.
    validated = deepcopy(value); validated['source'] = 'app-local-data/bookmarks.json'
    try: return stable_file(validated)
    except (ValueError, TypeError, UnicodeError):
        raise NativeUIError('Original Avatar bookmark bytes are invalid') from None


def entries(value):
    raw = original_bytes(value)
    if raw is None: return dict(status=value['status'], entries=None)
    try:
        loaded = decode(raw.decode('utf-8')); need(type(loaded) is dict)
    except (ValueError, UnicodeError, RuntimeError): return dict(status='invalid-json', entries=None)
    return dict(status='ready', entries=loaded)


def persisted(value, loaded):
    """Original file bytes must actually match the independently loaded map."""
    exact(loaded, {'source', 'entries', 'loadError'})
    need(loaded['source'] == 'AvatarBookmarks.getBookmarks' and loaded['loadError'] is False
         and type(loaded['entries']) is dict)
    actual = entries(value)
    need(actual['status'] == 'ready' and actual['entries'] == loaded['entries'])
    return deepcopy(actual['entries'])


def owned(value, loaded, name, baseline, *, saved=None):
    need(type(name) is str and name and type(baseline) is dict and name not in baseline)
    current = persisted(value, loaded)
    need({key: entry for key, entry in current.items() if key != name} == baseline)
    if name not in current: return False
    if saved is not None: need(current[name] == saved)
    return True
