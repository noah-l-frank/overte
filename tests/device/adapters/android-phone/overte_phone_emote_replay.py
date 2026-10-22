"""Bounded memo of pure history validation after original-file verification.

No frame, input, native fact, freshness anchor or product result is cached.
Every caller first reopens all original manifests/files and checks their hashes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import OrderedDict
import hashlib
from weakref import WeakKeyDictionary

from adapters.emote_admission import PINS as ADMISSION_PINS
from adapters.emote_source_profile import PINS as SOURCE_PINS,MANAGER_PINS
from overte_phone_script_history import canonical

LIMIT=128
_verified=WeakKeyDictionary()


def history(phase,header,state,validate):
    # Headers contain the immutable manifest hashes, original file identities,
    # binding, policy, role, run and artifact directory. Pending acquisition is
    # validated separately on every decode; it supplies no historical frame.
    identity={key:value for key,value in header.items() if key!='payload'}
    identity['history']={key:state[key] for key in ('revision','manifests')}
    identity['reviewedCatalogs']=[hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ADMISSION_PINS,SOURCE_PINS,MANAGER_PINS)]
    key=hashlib.sha256(canonical(identity)).digest()
    rows=_verified.setdefault(phase,OrderedDict())
    if key in rows:
        rows.move_to_end(key);return
    validate() # Failed or partial replay never enters the memo.
    rows[key]=None
    if len(rows)>LIMIT:rows.popitem(last=False)
