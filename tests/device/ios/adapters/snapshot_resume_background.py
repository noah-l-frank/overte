"""Durable once-only Snapshot Home/activation over the existing OS context.

Only foreground code obtains Page/input originals. Recovery in the background
opens actual historical files and the retained OS session. This component does
not establish post-resume pixels, an independent Actor or whole-feature End.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.lifecycle_background import LifecycleOSContext,os_original
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.adapters.snapshot_resume_page import SnapshotResumePage
from ios.adapters.snapshot_resume_inputs import SnapshotResumeInputsPacket
from ios.adapters.snapshot_resume_cursor import cursor
from ios.adapters.tablet_web_admission import installed_forward

NAME='ios-snapshot-resume-os-owner.json'
PHASES=('background-issued','background-observed','foreground-issued','foreground-observed','after-issued','complete')


class SnapshotResumeBackground:
    def __init__(self,store,os_context,run,lock,page_factory,review_factory,packet_factory,
                 *,epoch_ms,monotonic,sleep):
        need(type(store) is PrivateFeatureState and type(os_context) is LifecycleOSContext
            and isinstance(lock,ScriptSourceLock) and store.path.name==NAME
            and lock.path==store.path.with_name('script-feature-sources.lock')
            and all(callable(f) for f in (page_factory,review_factory,packet_factory,epoch_ms,monotonic,sleep)))
        self.store,self.os,self.run,self.lock=store,os_context,identifier(run),lock
        self.binding=deepcopy(context(os_context.binding))
        self.page_factory,self.review_factory,self.packet_factory=page_factory,review_factory,packet_factory
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.previous=store.read();self.state=None
        self.file_guard()
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosSnapshotResumeOSOwnerVersion=1,binding=self.binding,runId=self.run,state=deepcopy(state))

    def file_guard(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        self.os.runtime.adapter._candidate_guard()
        need(same(self.os.runtime.adapter.read_session(self.os.selector),self.os.session_state))
        return True

    def decode(self,value):
        exact(value,{'iosSnapshotResumeOSOwnerVersion','binding','runId','state'})
        state=value['state'];need(type(value['iosSnapshotResumeOSOwnerVersion']) is int
            and value['iosSnapshotResumeOSOwnerVersion']==1 and same(value,self.envelope(state)))
        exact(state,{'phase','ticket','reviewSha256','before','inputs','cursor','osBefore','background','foreground','after','result'})
        need(state['phase'] in PHASES);position=PHASES.index(state['phase']);identifier(state['ticket'])
        need(type(state['reviewSha256']) is str and len(state['reviewSha256'])==64
            and all(c in '0123456789abcdef' for c in state['reviewSha256'])
            and type(state['before']) is dict and integer(state['before']['index'],1,382)
            and type(state['inputs']) is int and state['inputs']==1 and type(state['cursor']) is dict)
        os_original(state['osBefore'],self.binding,self.os.gate.bundle)
        need(state['osBefore']['process']['foreground'])
        previous=state['osBefore']
        for key,foreground in (('background',False),('foreground',True)):
            current=state[key]
            if current is not None:
                os_original(current,self.binding,self.os.gate.bundle)
                need(current['process']['foreground'] is foreground and same(current['source'],previous['source'])
                    and current['hostBefore']['epochMs']>=previous['hostAfter']['epochMs']
                    and current['hostBefore']['monotonic']>=previous['hostAfter']['monotonic'])
                installed_forward(previous['installed'],current['installed']);previous=current
        need((state['background'] is not None)==(position>=1)
            and (state['foreground'] is not None)==(position>=3)
            and (state['after'] is not None)==(position==5)
            and (state['result'] is not None)==(position==5))
        if position==5:need(state['after']['index']==state['before']['index']+1)
        return deepcopy(state)

    def save(self):
        self.file_guard();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)

    def archive_page(self):
        page=SnapshotResumePage.archive(PrivateFeatureState(self.store.path.with_name('ios-snapshot-resume-page-owner.json')),
            self.lock,self.binding,self.run,self.review().page.fixture_url,combined=True)
        need(page.lock is self.lock and same(page.binding,self.binding) and page.run==self.run)
        return page

    def review(self):
        review=self.review_factory()
        need(type(review) is SnapshotCaptureReviewOwner and review.historical and review.lock is self.lock
            and same(review.binding,self.binding) and review.run==self.run and review.store.path.parent==self.store.path.parent)
        return review

    def original_before(self,page,review):
        need(type(page) is SnapshotResumePage and page.lock is self.lock and page.run==self.run
            and same(page.binding,self.binding) and page.store.path.parent==self.store.path.parent)
        need(page.state['ticket']==self.state['ticket'] and page.state['restored'] is None)
        before=page.original(self.state['before']);packet=self.packet_factory(page,self.state['inputs'],historical=True)
        need(type(packet) is SnapshotResumeInputsPacket and packet.lock is self.lock
            and same(packet.binding,self.binding) and packet.run==self.run)
        self.packet_membership(packet)
        need(same(cursor(before,packet.historical(),self.binding,self.run),self.state['cursor']))
        # The complete historical capture and original screen are reread here.
        # They are not replayed inside each intermediate WAL/file callback.
        proof=review.proof();need(digest(proof)==self.state['reviewSha256'])
        old=review.page_original(review.state['after']);old_phase=old['phaseAfter'];phase=before['phaseBefore']
        phase_packet(phase,run=self.run,area='snapshots',request=phase['requestId'],
            epoch=phase['capturedEpochMs'],previous=old_phase)
        need(len(phase['activations'])>len(old_phase['activations'])
            and phase['activations'][:len(old_phase['activations'])]==old_phase['activations'])
        follow_native(old['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
        need(old['clockJoin']['nativeAfter']['lifecycle']['launches']==before['clockJoin']['nativeBefore']['lifecycle']['launches'])
        need(old['originals']['ui']['instance']==before['originals']['ui']['instance'])
        controls=[r for r in before['originals']['ui']['controls'] if r['id']=='snapshot.capture']
        need(len(controls)==1 and controls[0]['snapshotRootId']==proof['renderedReview']['rootIdentity'])
        return before

    @staticmethod
    def packet_membership(packet):
        """Full closed namespace membership at a stable child boundary.

        This is deliberately not an intermediate child-write callback: a born
        inode must first be recorded by the child's existing durable intent.
        """
        expected={packet.store.path};files=packet.files().store;parts=packet.parts().store
        state=packet.state
        if state is not None:
            if state['storage'] is not None:expected.add(files.path(state['storage']))
            if state['rawParts'] is not None:
                packet.parts().inspect(state['rawParts'])
                expected.update(parts.path(ref) for ref in state['rawParts']['chunks'] if ref['phase']!='planned')
            if state['storage'] is not None and state['storage']['phase']=='planned':
                need(not os.path.lexists(files.path(state['storage'])))
        for index,path in enumerate(packet.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith((packet._store_prefix+'-primary-'+packet._name+'-',files.namespace+'-',parts.namespace+'-')):
                need(path in expected)

    def status(self):
        self.file_guard();value=self.os.status(self.epoch_ms,self.monotonic);self.file_guard();return value

    def wait(self,foreground):
        started=self.monotonic()
        for attempt in range(51):
            status=self.status()
            if status['process']['foreground'] is foreground:return status
            if self.monotonic()-started>=5 or attempt==50:break
            self.sleep(.1)
        need(False)

    def completed(self,page,before,after):
        need(page.route(after)['kind']=='snapshot'
            and same(before['phaseBefore']['activations'],after['phaseAfter']['activations']))
        first,last=before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'];follow_native(first,last)
        need(last['lifecycle']==dict(launches=first['lifecycle']['launches'],
            backgrounds=first['lifecycle']['backgrounds']+1,activations=first['lifecycle']['activations']+1))
        a,b=before['originals']['ui'],after['originals']['ui']
        need(a['instance']==b['instance'] and a['lastSequence']==b['lastSequence'])
        controls=[r for r in b['controls'] if r['id']=='snapshot.capture']
        need(len(controls)==1 and controls[0]['snapshotRootId']==self.state['cursor']['rootId'])
        need(self.state['osBefore']['hostBefore']['epochMs']>=before['clockJoin']['hostAfterEpochMs']
            and self.state['osBefore']['hostBefore']['monotonic']>=before['clockJoin']['hostAfterMonotonic']
            and after['clockJoin']['hostBeforeEpochMs']>=self.state['foreground']['hostAfter']['epochMs']
            and after['clockJoin']['hostBeforeMonotonic']>=self.state['foreground']['hostAfter']['monotonic'])
        return dict(iosSnapshotResumeOSBridgeVersion=1,runId=self.run,binding=deepcopy(self.binding),
            beforeOriginalSha256=digest(before),afterOriginalSha256=digest(after),
            originalOSStatesSha256=digest([self.state[k] for k in ('osBefore','background','foreground')]),
            completeInputPrefixSha256=digest(self.state['cursor']),sameProcessAndInputCursor=True,
            exactOneBackgroundAndActivation=True,originalOSBridgeRequired=False,renderedResumeRequired=True,
            independentActorSceneRequired=True,destinationCompositionRequired=True,pairedCleanupRequired=True,wholeFeatureRequired=True)

    @operation
    def act(self,ticket):
        identifier(ticket);self.file_guard()
        if self.state is None:
            need(self.status()['process']['foreground']);review=self.review();proof=review.proof()
            page=self.page_factory();page.prepare(ticket);need(page.state['observation'] is None)
            before=deepcopy(page.state['records'][-1]);frame=page.original(before)
            packet=self.packet_factory(page,1,historical=False)
            self.packet_membership(packet)
            if packet.state is None:packet.reserve()
            if packet.state['phase']=='reserved':packet.send()
            if packet.state['phase']=='issued':packet.retain()
            self.packet_membership(packet)
            anchor=cursor(frame,packet.historical(),self.binding,self.run);status=self.status();need(status['process']['foreground'])
            self.state=dict(phase='background-issued',ticket=ticket,reviewSha256=digest(proof),before=before,
                inputs=1,cursor=anchor,osBefore=status,background=None,foreground=None,after=None,result=None)
            self.original_before(page,review);self.save();self.os.background();self.file_guard()
        need(self.state['ticket']==ticket)
        # Reopening historical evidence is OS/background safe and creates no
        # live source, UI query, launch, SDK or screen request.
        review=self.review();page=self.archive_page();before=self.original_before(page,review)
        if self.state['phase']=='background-issued':
            self.state.update(phase='background-observed',background=self.wait(False));self.save()
        if self.state['phase']=='background-observed':
            need(not self.status()['process']['foreground']);self.state['phase']='foreground-issued';self.save()
            self.os.activate();self.file_guard()
        if self.state['phase']=='foreground-issued':
            self.state.update(phase='foreground-observed',foreground=self.wait(True));self.save()
        if self.state['phase']=='foreground-observed':
            self.state['phase']='after-issued';self.save()
        if self.state['phase']=='after-issued':
            self.os.probe(True);page=self.archive_page()
            count=self.state['before']['index']
            if len(page.state['records'])==count:
                pending=page.state['observation']
                if pending is not None and pending['wire'] is not None:
                    def foreground_guard():self.file_guard();self.os.probe(True);return True
                    page=SnapshotResumePage.adopt_saved_observation(page.store,self.lock,self.binding,self.run,
                        page.fixture_url,foreground_guard)
                else:
                    page=self.page_factory();page.recover_observation();page.observe()
            need(len(page.state['records'])==count+1)
            reference=deepcopy(page.state['records'][-1]);after=page.original(reference)
            result=self.completed(page,before,after)
            self.state.update(phase='complete',after=reference,result=result);self.save()
        need(self.state['phase']=='complete');page=self.archive_page();before=self.original_before(page,self.review())
        need(same(self.state['result'],self.completed(page,before,page.original(self.state['after']))))
        self.file_guard();return deepcopy(self.state['result'])
