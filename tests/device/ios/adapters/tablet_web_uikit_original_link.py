"""Read only the UIKit original graph across independent peer head changes.

Current peer bytes and inodes provide continuity, never peer/native authority.
The private reader expires before returning and cannot persist or query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import time

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as children,tablet_web_uikit_continuation as uikit
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import COMPONENTS
from ios.adapters.tablet_web_uikit_segment import TabletUIKitSegment


def forbidden(*_args,**_kwargs):need(False)


class _OriginalLinkPrefix(uikit.TabletUIKitClosedPrefix):
    """Complete own originals, with scoped current peer identity only."""
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,*,monotonic):
        self.alive=True;self.root=self.link_root=Path(root)
        self.expected=uikit.base.scope(binding,run,role,fixture_url,pid);self.lock,self.monotonic=lock,monotonic
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock');lock.assert_held()
        self.inventory=EmoteOriginalLease(root,[])
        self.store=PrivateFeatureState(self.root/children._name('uikit',self.expected));self.state=self.store.read()
        self.raw,self.old=uikit.decode(self.state,self.expected)
        head=PrivateFeatureState(self.root/('tabletweb-source-owner-'+run+'-'+role+'.json')).read()
        children.decode(head,self.expected);self.peers={}
        for child in head['children']:
            if child['component']=='uikit':continue
            raw,signature=children._raw(self.root/child['headerName'])
            self.peers[child['headerName']]=(signature,hashlib.sha256(raw).hexdigest())
        # Do not call the live constructor: its DOM proof and literal seven
        # sibling descriptors are admission guards, outside this own graph.
        self.copies=OriginalFrameStore(root,binding,run,role,self.guard,forbidden,
            namespace='tabletweb-uikit-closed',schema_prefix='tabletWebClosedHeader',monotonic=monotonic)
        self.records=OriginalFrameStore(root,binding,run,role,self.guard,forbidden,
            namespace='tabletweb-uikit-packets',schema_prefix='tabletWebSourcePacket',monotonic=monotonic)
        self.guard()

    def guard(self):
        need(self.alive and self.root==self.link_root);self.lock.assert_held();self.inventory.guard()
        need(same(self.store.read(),self.state));raw,old=uikit.decode(self.state,self.expected)
        need(raw==self.raw and same(old,self.old));expected=self.expected
        path=self.root/('tabletweb-source-owner-'+expected['runId']+'-'+expected['role']+'.json')
        raw,signature=children._raw(path)
        need(signature==self.state['parent']['signature'] and hashlib.sha256(raw).hexdigest()==self.state['parent']['sha256'])
        parent=PrivateFeatureState(path).read();children.decode(parent,expected);reference=parent['copyIntent']
        need(reference is not None and reference['phase'] in ('opened','saved'))
        def locked():self.lock.assert_held();return True
        copies=OriginalFrameStore(self.root,expected['binding'],expected['runId'],expected['role'],locked,forbidden,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=self.monotonic)
        need(same(copies.read(reference),children.copy_body(parent,expected)))
        for child in parent['children']:
            if child['component']=='uikit':
                need(child['signature']==self.state['previousHeader']['signature']
                    and child['sha256']==self.state['previousHeader']['sha256']
                    and child['lastRecord']==self.old['records'][-1] and child['nextRaw']==self.old['nextRaw'])
            else:
                actual,identity=children._raw(self.root/child['headerName']);prior,sha=self.peers[child['headerName']]
                need(identity==prior and hashlib.sha256(actual).hexdigest()==sha)
        self.inventory.guard();return True

    save=intent=copy=index=bind_successor=forbidden


def read(root,binding,run,role,fixture_url,pid,lock,*,monotonic=time.monotonic):
    """Return an original UIKit tail, with no exported reader or authority."""
    prefix=object.__new__(_OriginalLinkPrefix)
    try:
        prefix.__init__(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        version=prefix.state['tabletWebUIKitContinuationVersion']
        if version==uikit.FENCE_VERSION:result=prefix.history()
        elif version==uikit.BOUND_VERSION:result=prefix.adopted()
        else:
            need(version in (uikit.ACTIVE_VERSION,uikit.VERSION))
            reader=object.__new__(TabletUIKitSegment);reader.root=Path(root);reader.binding=deepcopy(binding)
            reader.run,reader.role,reader.fixture,reader.pid=run,role,fixture_url,pid
            reader.lock,reader._current_guard,reader._pinned_guard=lock,forbidden,forbidden
            reader.monotonic,reader.epoch_ms,reader.historical,reader.clock=monotonic,forbidden,True,None
            reader.component,reader.module='uikit',COMPONENTS['uikit']
            reader.closed=prefix;reader.store=prefix.store;reader.state=deepcopy(prefix.state['active']);reader.saved=deepcopy(reader.state)
            reader.guard=reader.storage_guard=reader._bound;reader._original_storage();packets=reader.history()
            need(not reader.blocked and packets and reader.state['pending'] is reader.state['recordIntent'] is reader.state['recordInspection'] is None)
            result=dict(historicalOnly=True,phase='rotating',globalIndex=reader._next_index()-1,nextIndex=reader._next_index(),
                nextRaw=reader.state['nextRaw'],nativeFloor=deepcopy(packets[-1]))
        prefix.guard()
        return dict(result,component='uikit',subgraphOnly=True,peerAuthority=False)
    finally:prefix.alive=False
