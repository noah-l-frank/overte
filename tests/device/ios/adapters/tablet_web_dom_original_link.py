"""Read only the DOM original subgraph while peer storage headers rotate.

Peer bytes/identities are continuity guards, never peer native authority.
Nothing from this helper enables a live guard, SourceReady or SDK teardown.
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
from ios.adapters import tablet_web_child_rotation as children,tablet_web_dom_continuation as dom
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_dom_segment import TabletDOMSegment
from ios.adapters.tablet_web_packets import COMPONENTS


def forbidden(*_args,**_kwargs):need(False)


class _OriginalLinkPrefix(dom.TabletDOMClosedPrefix):
    """Scoped private reader, without a mutable or peer-admission interface."""
    def _admit_current_uikit(self):
        # Own graph only, even when the live DOM4 constructor needs a known
        # UIKit proof. Captured current peer bytes/inodes remain continuity.
        return

    def _admit_current_native(self):
        # Own-only DOM5 also bypasses every generic peer proof. Current peer
        # header continuity never becomes independent peer/native authority.
        return

    def __init__(self,root,binding,run,role,fixture_url,pid,lock,*,monotonic):
        self.alive=True;self.link_root=Path(root)
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.link_root/'script-feature-sources.lock');lock.assert_held()
        self.inventory=EmoteOriginalLease(root,[])
        expected=dom.base.scope(binding,run,role,fixture_url,pid)
        head=PrivateFeatureState(self.link_root/('tabletweb-source-owner-'+run+'-'+role+'.json')).read()
        children.decode(head,expected);self.peers={}
        for child in head['children']:
            if child['component']=='dom':continue
            raw,signature=children._raw(self.link_root/child['headerName'])
            self.peers[child['headerName']]=(signature,hashlib.sha256(raw).hexdigest())
        super().__init__(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)

    def guard(self):
        need(self.alive and self.root==self.link_root);self.lock.assert_held();self.inventory.guard()
        need(same(self.store.read(),self.state));raw,old=dom.decode(self.state,self.expected)
        need(raw==self.raw and same(old,self.old))
        expected=self.expected;path=self.root/('tabletweb-source-owner-'+expected['runId']+'-'+expected['role']+'.json')
        raw,signature=children._raw(path)
        need(signature==self.state['parent']['signature'] and hashlib.sha256(raw).hexdigest()==self.state['parent']['sha256'])
        parent=PrivateFeatureState(path).read();children.decode(parent,expected)
        reference=parent['copyIntent'];need(reference is not None and reference['phase'] in ('opened','saved'))
        def locked():self.lock.assert_held();return True
        copies=OriginalFrameStore(self.root,expected['binding'],expected['runId'],expected['role'],locked,forbidden,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=self.monotonic)
        need(same(copies.read(reference),children.copy_body(parent,expected)))
        for child in parent['children']:
            if child['component']=='dom':
                need(child['signature']==self.state['previousHeader']['signature']
                    and child['sha256']==self.state['previousHeader']['sha256']
                    and child['lastRecord']==self.old['records'][-1] and child['nextRaw']==self.old['nextRaw'])
            else:
                actual,identity=children._raw(self.root/child['headerName']);prior,sha=self.peers[child['headerName']]
                need(identity==prior and hashlib.sha256(actual).hexdigest()==sha)
        self.inventory.guard();return True

    # Unlike the live prefix, this private subclass cannot persist any intent.
    save=intent=copy=index=bind_successor=forbidden


def read(root,binding,run,role,fixture_url,pid,lock,*,monotonic=time.monotonic):
    """Return only an original DOM tail; never expose the scoped reader."""
    prefix=object.__new__(_OriginalLinkPrefix)
    try:
        prefix.__init__(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        if prefix.state['tabletWebDOMContinuationVersion']==dom.FENCE_VERSION:
            result=prefix.adopted()
        else:
            need(prefix.state['tabletWebDOMContinuationVersion'] in (dom.ACTIVE_VERSION,)+dom.INITIAL_VERSIONS)
            # Build exactly the existing forced-historical segment. Its
            # prefix is private and scoped to this one complete original read;
            # no caller callback, reader or live guard escapes the function.
            reader=object.__new__(TabletDOMSegment);reader.root=Path(root);reader.binding=deepcopy(binding)
            reader.run,reader.role,reader.fixture,reader.pid=run,role,fixture_url,pid
            reader.lock,reader._current_guard,reader._pinned_guard=lock,forbidden,forbidden
            reader.monotonic,reader.epoch_ms,reader.historical,reader.clock=monotonic,forbidden,True,None
            reader.component,reader.module='dom',COMPONENTS['dom']
            reader.closed=prefix;reader.store=prefix.store;reader.state=deepcopy(prefix.state['active']);reader.saved=deepcopy(reader.state)
            reader.guard=reader.storage_guard=reader._bound;reader._original_storage();packets=reader.history()
            need(not reader.blocked and packets and reader.state['pending'] is reader.state['recordIntent'] is reader.state['recordInspection'] is None)
            result=dict(historicalOnly=True,phase='rotating',globalIndex=reader._next_index()-1,nextIndex=reader._next_index(),
                nextRaw=reader.state['nextRaw'],nativeFloor=deepcopy(packets[-1]))
        prefix.guard()
        return dict(result,component='dom',subgraphOnly=True,peerAuthority=False)
    finally:prefix.alive=False
