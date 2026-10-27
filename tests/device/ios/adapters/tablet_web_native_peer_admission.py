"""Known own-original proofs for explicit DOM/UIKit5 peer admission only.

An admitted header is pinned for one reader lifetime. These pins are neither
native freshness nor cached proof results, and cannot authorize a parent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
from types import MappingProxyType

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as children
from ios.adapters.emote_original_lease import EmoteOriginalLease


def admit(root,expected,parent_pin,lock,*,monotonic):
    """Read every changed native peer's original graph, with exact head fences."""
    # Import lazily: own links must bypass this entire admission path, and
    # generic own readers depend on those links without recursively admitting.
    from ios.adapters.tablet_web_native_child_continuation import KINDS,read_own
    root=Path(root)
    need(isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock')
    lock.assert_held();lease=EmoteOriginalLease(root,[])
    parent_path=root/('tabletweb-source-owner-'+expected['runId']+'-'+expected['role']+'.json')
    parent_raw,parent_signature=children._raw(parent_path)
    need(parent_signature==parent_pin['signature'] and hashlib.sha256(parent_raw).hexdigest()==parent_pin['sha256'])
    parent=PrivateFeatureState(parent_path).read();children.decode(parent,expected)
    pins={};pending=[]
    # Fence the full native peer set before any proof. A later proof must not
    # silently refresh a header already observed earlier in this same scope.
    for child in parent['children']:
        name=child['component']
        if name not in KINDS:continue
        actual,identity=children._raw(root/child['headerName']);digest=hashlib.sha256(actual).hexdigest()
        pins[name]=dict(signature=identity,sha256=digest)
        if identity!=child['signature'] or digest!=child['sha256']:
            pending.append((name,child['headerName'],actual,identity))
    need(set(pins)==set(KINDS))
    for name,filename,original,identity in pending:
        proof=read_own(root,expected['binding'],expected['runId'],expected['role'],expected['fixtureUrl'],
            expected['processId'],name,lock,monotonic=monotonic)
        need(proof['component']==name and proof['historicalOnly'] is True
            and proof['subgraphOnly'] is True and proof['peerAuthority'] is False)
        confirmed,confirmed_identity=children._raw(root/filename)
        need(confirmed==original and confirmed_identity==identity)
    lock.assert_held()
    confirmed,confirmed_identity=children._raw(parent_path)
    need(confirmed==parent_raw and confirmed_identity==parent_signature)
    for child in parent['children']:
        if child['component'] not in KINDS:continue
        actual,identity=children._raw(root/child['headerName']);pin=pins[child['component']]
        need(identity==pin['signature'] and hashlib.sha256(actual).hexdigest()==pin['sha256'])
    lease.guard()
    return MappingProxyType({name:MappingProxyType(dict(signature=MappingProxyType(dict(pin['signature'])),
        sha256=pin['sha256'])) for name,pin in pins.items()})
