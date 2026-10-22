"""Bounded memo of pure history validation after original-file verification.

No frame, input, native fact, freshness anchor or product result is cached.
Every caller first reopens all original manifests/files and checks their hashes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from collections import OrderedDict
import hashlib

from adapters.emote_admission import PINS as ADMISSION_PINS
from adapters.emote_source_profile import PINS as SOURCE_PINS,MANAGER_PINS
from overte_phone_script_history import canonical

# A complete primary/actor journey retains hundreds of distinct verified
# historical prefixes. Keep their digest-only proofs through reconstruction;
# the former 128-entry cache churned while final retirement replayed them.
# This bound stores no decoded frame or product fact (roughly 0.1 MiB of keys).
LIMIT=1024
_verified=OrderedDict()


def history(phase,header,state,validate):
    # Headers contain the immutable manifest hashes, original file identities,
    # binding, policy, role, run and artifact directory. Pending acquisition is
    # validated separately on every decode; it supplies no historical frame.
    identity={key:value for key,value in header.items() if key!='payload'}
    identity['history']={key:state[key] for key in ('revision','manifests')}
    identity['reviewedCatalogs']=[hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ADMISSION_PINS,SOURCE_PINS,MANAGER_PINS)]
    key=hashlib.sha256(canonical(identity)).digest()
    # Public calls reconstruct their PhaseFixtureReader. Only the digest of a
    # fully qualified immutable history may survive that reconstruction. The
    # caller still reopens/verifies every original file before reaching here;
    # neither phase authority nor any fresh/native result is reused.
    if key in _verified:
        _verified.move_to_end(key);return
    validate() # Failed or partial replay never enters the memo.
    _verified[key]=None
    if len(_verified)>LIMIT:_verified.popitem(last=False)
