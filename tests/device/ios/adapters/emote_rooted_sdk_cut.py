"""Closed paired original membership through Emote SDK deletion admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_rooted_fence import _current_metadata
from ios.adapters.emote_session_carriers import inventory


class IOSEmoteRootedSDKCut:
    def __init__(self,session):
        from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
        need(type(session) is IOSEmoteRootedSessionEnd and session.state['phase']=='prepared')
        self.session=session;self.expected=None
        processes=session.processes;archive=session.process.archive
        self.roots={root for process in processes.values() for root in (process.root,process.lock.path.parent)}
        leases=[EmoteOriginalLease(root,[]) for root in self.roots]
        self.mutable={session.store.path,session.os_store().path}
        with read_scope(fresh=True) as reads:
            session.bound();session.qualify();copies=archive.copies()
            for process in processes.values():
                copies.update({str(path):value for path,value in process.fence_validate()['metadata'].items()})
            _current_metadata(archive.paths,copies)
            found=inventory(self.roots);need(found<=reads)
        for lease in leases:lease.guard()
        self.paths=found-self.mutable;self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.guard_preparing()
    def guard_preparing(self):
        for process in self.session.processes.values():
            for lock in process.ownership.roles.locks.values():lock.assert_held()
        for path,signature in self.pins.items():need(EmoteOriginalLease.signature(path.lstat())==signature)
    def issued(self,reads):
        need(type(reads) is set and self.expected is None);self.guard_preparing()
        session=self.session;session.bound();need(session.state['phase']=='delete-issued')
        # The only newly admitted files are actual successful stage-one typed
        # OS reads. Old immutable originals retain their original file pins.
        found=inventory(self.roots);need(found<=self.paths|self.mutable|reads)
        self.paths=found-self.mutable;self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.expected=deepcopy(session.previous);self.os=deepcopy(session.os_store().read());self.guard()
    def guard(self):
        need(self.expected is not None);self.guard_preparing();session=self.session
        need(same(session.store.read(),self.expected) and same(session.previous,self.expected)
            and same(session.envelope(session.state),self.expected) and same(session.os_store().read(),self.os)
            and inventory(self.roots)-self.mutable==self.paths)
        return True
