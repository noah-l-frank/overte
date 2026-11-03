"""Explicit resumed SNAP Page3 originals; no normal navigation or OS action.

This retains independently acquired original UI/work on the existing snapshot
surface. A native lifecycle transition is only an unresolved bridge here; the
separate OS owner must prove actual background/foreground before any result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner


class SnapshotResumePage(IOSSnapshotPageOwner):
    def __init__(self,*args,**kwargs):
        need(kwargs.get('combined') is True);super().__init__(*args,**kwargs)

    def store_namespace(self):return 'ios-snapshot-resume-page'
    def frame_namespace(self):return self.store_namespace()
    def version(self):return 3

    @classmethod
    def adopt_saved_observation(cls,store,lock,binding,run,fixture_url,guard):
        """Finish only an existing complete original under an OS-safe guard.

        No live source factory, native/UI clock, phase reader, WDA or input
        authority is constructed. The existing original decoder/inode reader
        and parent CAS execute; unknown or partial bytes remain unresolved.
        """
        need(cls is SnapshotResumePage and callable(guard));lock.assert_held();need(guard() is not False)
        owner=cls.archive(store,lock,binding,run,fixture_url,combined=True)
        pending=owner.state['observation']
        need(pending is not None and pending['wire'] is not None and pending['wire']['phase'] in ('opened','saved'))
        owner.guard=guard;owner.historical=False
        try:owner.recover_observation();need(owner.state['observation'] is None)
        finally:owner.historical=True
        need(guard() is not False)
        return cls.archive(store,lock,binding,run,fixture_url,combined=True)

    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and value['activations'][-1]['stimulus']==dict(verb='background-resume',inputs={}))

    def frame(self,value,previous=None):
        # Keep the existing complete current Page decoder. Only the historical
        # cross-frame lifecycle rule has a separate explicit resumed profile.
        super().frame(value)
        if previous is not None:
            old,current=previous['originals'],value['originals']
            first,last=previous['clockJoin']['nativeAfter'],value['clockJoin']['nativeBefore']
            follow_native(first,last)
            need(value['clockJoin']['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs']
                and value['clockJoin']['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']
                and current['ui']['instance']==old['ui']['instance']
                and current['ui']['elapsedMs']>=old['ui']['elapsedMs']
                and current['ui']['lastSequence']==old['ui']['lastSequence'])
            a,b=first['lifecycle'],last['lifecycle']
            need(same(a,b) or b==dict(launches=a['launches'],backgrounds=a['backgrounds']+1,activations=a['activations']+1))
            source=self.work_source()
            source.validate(current['work'],dict(schemaVersion=1,commandId=current['work']['requestId'],action=source.ACTION,runId=self.run),
                int(self.binding['processIdentity']),previous=old['work'])
        return value

    def decode(self,value):
        state=super().decode(value)
        need(not state['actions'] and state['restored'] is None)
        return state

    @operation
    def prepare(self,ticket):
        self.bound();identifier(ticket);need(not self.historical)
        if self.state['ticket'] is None:
            status=self.phase.read();need(status['ticket']==ticket);self.phase_original(status['status'],ticket)
            self.state.update(ticket=ticket,phaseOriginal=status['status']);self.save()
        else:need(self.state['ticket']==ticket)
        self.active()
        if self.state['roots'] is None:
            self.state['roots']=self.runtime.roots(self);self.runtime_root();self.save()
        if self.state['initial'] is None:
            self.recover_observation()
            if not self.state['records']:self.observe()
            need(len(self.state['records'])==1)
            reference=self.state['records'][0];need(self.route(self.original(reference))['kind']=='snapshot')
            self.state['initial']=reference['index'];self.state['opened']=reference['index'];self.save()
        frame=self.record(self.state['opened']);need(self.route(frame)['kind']=='snapshot')
        return dict(iosSnapshotResumePagePreparedVersion=1,runId=self.run,binding=deepcopy(self.binding),
            originalReference=deepcopy(self.state['records'][self.state['opened']-1]),
            originalOSBridgeRequired=True,renderedReviewRequired=True,independentActorSceneRequired=True,
            pairedCleanupRequired=True,wholeFeatureRequired=True)

    def drive(self,*_args,**_kwargs):raise NativeUIError('Resume Page cannot issue navigation input')
    def open(self,*_args,**_kwargs):raise NativeUIError('Resume Page requires its explicit prepare operation')
    def capture(self,*_args,**_kwargs):raise NativeUIError('Resume Page cannot repeat a capture')
    def restore(self,*_args,**_kwargs):raise NativeUIError('Resume Page supplies no restoration or cleanup authority')
