"""Closed paired original membership carried from frozen proof through Stop.

Only an independently decoded completed Actor end may replace its exact three
current WALs. Frozen copies never change. New local files require actual typed
read membership, and the process owner gets only its exact journal/fence paths.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same,unpack
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_rooted_fence import _current_metadata,_metadata_unchanged,_seal,inactive,inactive_prefixes
from ios.adapters.emote_rooted_fence_original import local,validate,phase_link
from ios.adapters.emote_session_carriers import inventory


class IOSEmoteRootedFenceCut:
    def __init__(self,end):
        from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
        need(type(end) is IOSEmoteRootedProcessEnd and end.state is not None and end.state['phase']=='prepared')
        self.end=end;end.bound();self.value=self.expected_issued=None
        self.archive_bound()
        roles=end.ownership.roles;self.roots={lock.path.parent for lock in roles.locks.values()}
        self.copies=deepcopy(roles.copies);self.copies[str(end.ownership.path)]=deepcopy(end.ownership.terminal)
        for role,lock in roles.locks.items():
            self.roots.add(Path(self.copies[str(lock.path.with_name('ios-emote-'+role+'-feature.json'))]['artifactRoot']))
        self.expected=deepcopy(self.copies)
        self.mutable={end.lock.path.with_name('ios-emote-'+end.role+'-'+tail+'.json') for tail in ('marker','keys','pointers')}
        leases=[EmoteOriginalLease(root,[]) for root in self.roots]
        with read_scope(fresh=True) as reads:
            need(same(end.archive.copies(),self.copies))
            self.proof,self.floor,self.phase_prefixes=end.ownership.read_with_retirement_context()
            _seal(self.proof,end.seal,run=end.run,role=end.role,binding=end.binding)
            feature=self.copies[str(end.lock.path.with_name('ios-emote-'+end.role+'-feature.json'))]
            state=unpack(feature['payload'])[0];need(same(state['binding'],end.binding))
            self.instance=state['phaseInstance']
            inactive(end.archive.state['phaseOriginal'],run=end.run,instance=self.instance,ticket=end.seal['description']['ticket'],after=self.floor)
            inactive_prefixes(end.archive.state['phaseOriginal'],self.phase_prefixes,run=end.run)
            self.read_peer()
            original=None
            if end.state['fence'] is not None:original=end.fence_original()
            elif end.state['pending'] is not None:
                need(end.state['pending']['phase'] in ('opened','saved'));original=end.frames.read(end.state['pending'])
            if original is not None:
                decoded=validate(original,end.ownership,end.archive,end.seal)
                self.expected.update({str(path):value for path,value in decoded['metadata'].items()})
            self.metadata_before()
            found=inventory(self.roots)
            archive_outputs={end.archive.store.path}|{end.archive.record_store(index).path for index in range(1,len(end.archive.paths)+1)}
            need(found<=reads|{store.path for store in end.archive.paths}|archive_outputs|end.outputs())
        for lease in leases:lease.guard()
        self.paths=found-end.outputs();self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.unchanged()

    def archive_bound(self):
        archive=self.end.archive
        need(archive.state is not None and archive.state['phase']=='validated'
            and same(archive.envelope(archive.state),archive.previous) and same(archive.store.read(),archive.previous))

    def check_authority(self,value):
        end=self.end
        self.archive_bound()
        # The retained pair was fully decoded before acquisition and remains
        # protected by its actual immutable file pins. Recheck its exact seal
        # and every original retired-phase/held operand on later admission.
        _seal(self.proof,end.seal,run=end.run,role=end.role,binding=end.binding)
        inactive_prefixes(end.archive.state['phaseOriginal'],self.phase_prefixes,run=end.run)
        phase_link(value,end.seal,run=end.run,role=end.role,binding=end.binding,instance=self.instance,floor=self.floor,
            retired=end.archive.state['phaseOriginal'],archive_sha=digest(end.archive.previous))

    def read_peer(self):
        end=self.end
        if end.peer is None:return
        peer=end.peer_identity();metadata=peer.overrides()
        expected={peer.lock.path.with_name('ios-emote-actor-'+tail+'.json') for tail in ('marker','keys','pointers')}
        need(set(metadata)==expected and expected<={Path(path) for path in self.copies})
        self.expected.update({str(path):deepcopy(value) for path,value in metadata.items()})

    def metadata_before(self):
        return _current_metadata(self.end.archive.paths,self.expected)

    def unchanged(self,*,acquiring=False):
        self.end.bound()
        for lock in self.end.ownership.roles.locks.values():lock.assert_held()
        signatures=_current_metadata(self.end.archive.paths,self.expected) if not acquiring else None
        for path,signature in self.pins.items():
            if not acquiring or path not in self.mutable:need(EmoteOriginalLease.signature(path.lstat())==signature)
        if signatures is not None:_metadata_unchanged(signatures)
        return True

    def acquired(self,value,reads):
        need(self.value is None and type(reads) is set);self.unchanged(acquiring=True)
        self.check_authority(value)
        end=self.end
        with read_scope(fresh=True) as decoded_reads:
            decoded=local(value,self.copies,root=end.root,binding=end.binding,run=end.run,role=end.role,lock=end.lock)
        found=inventory(self.roots)
        need(found<=self.paths|reads|decoded_reads|self.mutable|end.outputs())
        self.expected.update({str(path):deepcopy(item) for path,item in decoded['metadata'].items()})
        self.paths=found-end.outputs();self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.value=deepcopy(value);self.unchanged()

    def recovered(self,value):
        self.check_authority(value)
        decoded=validate(value,self.end.ownership,self.end.archive,self.end.seal)
        need(all(same(self.expected[str(path)],item) for path,item in decoded['metadata'].items()))
        self.value=deepcopy(value);self.unchanged()

    def freeze(self,value):
        end=self.end;self.unchanged()
        self.check_authority(value)
        need(self.value is not None and same(self.value,value) and same(end.fence_original(),value))
        need(inventory(self.roots)-end.outputs()==self.paths)
        self.expected_issued=end.envelope(dict(end.state,phase='stop-issued'))

    def guard(self):
        need(self.expected_issued is not None and same(self.end.previous,self.expected_issued))
        self.check_authority(self.value)
        self.unchanged();need(inventory(self.roots)-self.end.outputs()==self.paths)
        need(same(self.end.fence_original(),self.value));return True
