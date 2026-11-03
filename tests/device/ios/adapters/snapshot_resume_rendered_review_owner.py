"""Actual OS resume plus retained original PNG and newly bracketed WDA pixels.

The existing capture-review WAL/child discipline is reused. This explicit new
profile uses Resume Page3, a distinct image namespace, the completed original
OS bridge and the already owned still PNG. Actor/scene/End remain required.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner,PHASES
from ios.adapters.snapshot_resume_background import SnapshotResumeBackground
from ios.adapters.snapshot_resume_page import SnapshotResumePage
from ios.adapters.snapshot_resume_review_images import SnapshotResumeReviewImages


class SnapshotResumeRenderedReviewOwner(SnapshotCaptureReviewOwner):
    def __init__(self,page,capture,images,os_bridge,*,monotonic):
        need(type(page) is SnapshotResumePage and page.combined_profile() and not page.historical
            and type(capture) is IOSSnapshotCaptureOwner and capture.combined and capture.historical
            and type(images) is SnapshotResumeReviewImages and not images.historical
            and type(os_bridge) is SnapshotResumeBackground and os_bridge.state['phase']=='complete'
            and callable(monotonic))
        self.page,self.capture,self.images,self.os_bridge,self.monotonic=page,capture,images,os_bridge,monotonic
        self.historical=False;self.lock=page.lock;self.binding=deepcopy(context(page.binding));self.run=page.run
        need(capture.lock is images.lock is os_bridge.lock is self.lock
            and same(capture.binding,self.binding) and same(images.binding,self.binding) and same(os_bridge.binding,self.binding)
            and capture.run==images.run==os_bridge.run==self.run and images.role=='primary' and images.stage==1
            and page.fixture_url==capture.phase.fixture_url and capture.store.path.parent==page.store.path.parent
            and images.store.path==page.store.path.with_name('ios-snapshot-resume-review-screens.json')
            and images.root==page.store.path.parent)
        self.store=PrivateFeatureState(page.store.path.with_name('ios-snapshot-resume-rendered-review-owner.json'))
        self.previous=self.store.read()
        self.state=dict(phase='new',ticket=None,capture=None,beforeCount=None,before=None,
            screenPrefix=None,screenNonce=None,afterCount=None,after=None,result=None)
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)
        self.inventory()

    @classmethod
    def archive(cls,*_args,**_kwargs):
        # The parent OS-safe context remains mandatory for this new profile;
        # the old Capture1 archive cannot relabel this new owner.
        need(False)

    def envelope(self,state):
        return dict(iosSnapshotResumeRenderedReviewOwnerVersion=1,binding=self.binding,runId=self.run,
            fixtureUrl=self.page.fixture_url,pageStore=self.page.store.path.name,
            captureStore=self.capture.store.path.name,imagesStore=self.images.store.path.name,payload=pack([state]))

    def bound(self):
        self.os_bridge.file_guard();need(self.os_bridge.state['phase']=='complete')
        return super().bound()

    def inventory(self):
        self.bound();self.images._load()
        expected={self.images._path(row) for row in self.images.rows if row['file'] is not None and row['phase']!='removed'}
        for index,path in enumerate(self.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith('snapshot-resume-review-'):need(path in expected)
            if path.name.startswith('ios-snapshot-resume-rendered-review-'):need(path==self.store.path)

    def page_original(self,reference):
        self.bound();need(reference in self.page.state['records'])
        frame=self.page.original(reference);need(self.page.route(frame)['kind']=='snapshot'
            and same(frame['phaseBefore']['activations'],self.page.state['phaseOriginal']['activations'])
            and frame['phaseBefore']['instance']==self.page.state['phaseOriginal']['instance'])
        return frame

    def decode(self,value):
        exact(value,{'iosSnapshotResumeRenderedReviewOwnerVersion','binding','runId','fixtureUrl','pageStore','captureStore','imagesStore','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosSnapshotResumeRenderedReviewOwnerVersion']) is int
            and value['iosSnapshotResumeRenderedReviewOwnerVersion']==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','ticket','capture','beforeCount','before','screenPrefix','screenNonce','afterCount','after','result'})
        need(state['phase'] in PHASES);position=PHASES.index(state['phase'])
        if position==0:need(all(state[key] is None for key in state if key!='phase'));return deepcopy(state)
        identifier(state['ticket']);need(type(state['capture']) is dict)
        exact(state['capture'],{'resultSha256','artifactSha256','artifactIndex','phaseSha256','captureInput','rootsSha256'})
        for key in ('resultSha256','artifactSha256','phaseSha256','rootsSha256'):
            token=state['capture'][key];need(type(token) is str and len(token)==64 and all(c in '0123456789abcdef' for c in token))
        need(integer(state['capture']['artifactIndex'],1,128) and integer(state['capture']['captureInput'],1,128)
            and integer(state['beforeCount'],1,383))
        need((state['before'] is not None)==(position>=2))
        if position>=2:need(state['before']['index']==state['beforeCount']+1)
        need((state['screenPrefix'] is not None)==(position>=3))
        if position>=3:
            need(type(state['screenPrefix']) is list and len(state['screenPrefix'])<=96)
            seen=set()
            for row in state['screenPrefix']:
                exact(row,{'nonce','name','ticket','phase','file','capture'});identifier(row['nonce'])
                need(row['nonce'] not in seen and row['phase'] in ('saved','removed'));seen.add(row['nonce'])
        need((state['screenNonce'] is not None)==(position>=4))
        if position>=4:identifier(state['screenNonce'])
        need((state['afterCount'] is not None)==(position>=5))
        if position>=5:need(state['afterCount']==state['beforeCount']+1)
        need((state['after'] is not None)==(position>=6))
        if position>=6:need(state['after']['index']==state['afterCount']+1)
        need((state['result'] is not None)==(position==7))
        return deepcopy(state)

    @operation
    def acquire(self,ticket):
        identifier(ticket);self.bound()
        if self.state['phase']=='complete':need(self.state['ticket']==ticket);return self.proof()
        need(self.page.state['ticket']==self.os_bridge.state['ticket']==ticket
            and self.page.state['opened'] is not None and self.page.state['restored'] is None
            and self.capture.state['phase']=='copied')
        self.page.active();descriptor,_result,_fact,_raw=self.captured()
        if self.state['phase']=='new':
            self.state.update(phase='before-issued',ticket=ticket,capture=descriptor,beforeCount=len(self.page.state['records']));self.save()
        need(self.state['ticket']==ticket)
        if self.state['phase']=='before-issued':self.observation('before','beforeCount')
        if self.state['phase']=='before-saved':
            self.images._load();need(all(row['phase'] in ('saved','removed') for row in self.images.rows))
            self.state.update(phase='screen-issued',screenPrefix=deepcopy(self.images.rows));self.save()
        if self.state['phase']=='screen-issued':self.screen()
        if self.state['phase']=='screen-saved':
            need(len(self.page.state['records'])==self.state['before']['index'])
            self.state.update(phase='after-issued',afterCount=len(self.page.state['records']));self.save()
        if self.state['phase']=='after-issued':self.observation('after','afterCount')
        need(self.state['phase']=='after-saved');result=self.derived()
        self.state.update(phase='complete',result=deepcopy(result));self.save();return self.proof()

    def derived(self):
        result=super().derived()
        bridge=self.os_bridge.act(self.state['ticket'])
        need(bridge['originalOSBridgeRequired'] is False)
        os_page=self.os_bridge.archive_page();after_os=os_page.original(self.os_bridge.state['after'])
        before=self.page_original(self.state['before']);after=self.page_original(self.state['after'])
        follow_native(after_os['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
        need(after_os['clockJoin']['nativeAfter']['lifecycle']==before['clockJoin']['nativeBefore']['lifecycle']
            and after['clockJoin']['nativeAfter']['lifecycle']==before['clockJoin']['nativeBefore']['lifecycle']
            and after_os['originals']['ui']['instance']==before['originals']['ui']['instance']
            and after_os['originals']['ui']['lastSequence']==before['originals']['ui']['lastSequence'])
        result.pop('iosSnapshotCaptureRenderedReviewVersion')
        result.update(iosSnapshotResumeRenderedReviewVersion=1,stage='background-resume-still-png',
            backgroundResumeReviewRequired=False,originalOSBridgeRequired=False,renderedResumeRequired=False)
        result['pins'].update(originalOSBridgeSha256=digest(bridge),afterOSPageSha256=digest(after_os))
        return result
