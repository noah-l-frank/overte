"""Capture-phase visible PNG join through existing Page and WDA owners.

Only complete, saved original child tails may repair a lost parent return.
Unknown screenshot delivery is retained and never retried. Actor/scene,
background resume, destinations, paired cleanup and whole End remain open.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_review_images import SnapshotReviewImages
from ios.adapters import snapshot_review

NAME='ios-snapshot-rendered-review-owner.json'
PHASES=('new','before-issued','before-saved','screen-issued','screen-saved','after-issued','after-saved','complete')


class SnapshotReviewPending(NativeUIError):pass


class SnapshotCaptureReviewOwner:
    def __init__(self,page,capture,images,*,monotonic):
        need(type(page) is IOSSnapshotPageOwner and page.combined_profile() and not page.historical
            and type(capture) is IOSSnapshotCaptureOwner and capture.combined and capture.historical
            and type(images) is SnapshotReviewImages and callable(monotonic))
        self.page,self.capture,self.images,self.monotonic=page,capture,images,monotonic
        self.lock=page.lock;self.binding=deepcopy(context(page.binding));self.run=page.run
        need(capture.lock is self.lock and images.lock is self.lock
            and same(capture.binding,self.binding) and same(images.binding,self.binding)
            and capture.run==images.run==self.run and images.role=='primary' and images.stage==0
            and page.fixture_url==capture.phase.fixture_url and capture.store.path.parent==page.store.path.parent
            and images.store.path==page.store.path.with_name('ios-snapshot-review-screens.json')
            and images.root==page.store.path.parent)
        self.store=PrivateFeatureState(page.store.path.with_name(NAME));self.previous=self.store.read()
        self.state=dict(phase='new',ticket=None,capture=None,beforeCount=None,before=None,
            screenPrefix=None,screenNonce=None,afterCount=None,after=None,result=None)
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)
        self.inventory()

    def envelope(self,state):
        return dict(iosSnapshotCaptureReviewOwnerVersion=1,binding=self.binding,runId=self.run,
            fixtureUrl=self.page.fixture_url,pageStore=self.page.store.path.name,
            captureStore=self.capture.store.path.name,imagesStore=self.images.store.path.name,payload=pack([state]))

    def bound(self):
        self.lock.assert_held();self.page.bound();self.capture.bound()
        need(same(self.store.read(),self.previous) and self.images.guard() is not False)
        return True

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def decode(self,value):
        exact(value,{'iosSnapshotCaptureReviewOwnerVersion','binding','runId','fixtureUrl','pageStore','captureStore','imagesStore','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosSnapshotCaptureReviewOwnerVersion']) is int
            and value['iosSnapshotCaptureReviewOwnerVersion']==1 and same(value,self.envelope(rows[0])))
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

    def inventory(self):
        self.bound();self.images._load()
        expected={self.images._path(row) for row in self.images.rows if row['file'] is not None and row['phase']!='removed'}
        for index,path in enumerate(self.store.path.parent.iterdir()):
            need(index<8192)
            if path.name.startswith('snapshot-review-'):need(path in expected)
            if path.name.startswith('ios-snapshot-rendered-review-'):need(path==self.store.path)

    def captured(self):
        self.bound();capture=self.capture
        need(capture.state['phase'] in ('copied','file-cleaned') and capture.state['result'] is not None)
        result=capture.result();need(same(result,capture.state['result']) and result['iosSnapshotDecodedCaptureVersion']==2
            and result['workProfile']=='combined' and result['capture']['mode']=='still' and result['capture']['format']=='png')
        artifact=capture.history('artifact',capture.state['artifact']);fact,original=artifact.originals()
        need(artifact.state['phase']=='copied' and artifact.read()==original and same(fact['file'],result['capture']['file']))
        descriptor=dict(resultSha256=digest(result),artifactSha256=digest(artifact.previous),artifactIndex=artifact.index,
            phaseSha256=digest(capture.state['phaseOriginal']),captureInput=capture.state['captureInput'],rootsSha256=digest(capture.state['roots']))
        if self.state['capture'] is not None:need(same(self.state['capture'],descriptor))
        return descriptor,result,fact,original

    def page_original(self,reference):
        self.bound();need(reference in self.page.state['records'])
        frame=self.page.original(reference);need(self.page.route(frame)['kind']=='snapshot')
        need(same(frame['phaseBefore']['activations'],self.capture.state['phaseOriginal']['activations'])
            and frame['phaseBefore']['instance']==self.capture.state['phaseOriginal']['instance'])
        return frame

    def observation(self,key,count_key):
        count=self.state[count_key];need(integer(count,1,383))
        # Saved Page originals can repair a lost parent CAS without a new GET.
        # An unfinished Page GET is handled only by its existing durable policy.
        self.page.recover_observation();records=self.page.state['records']
        if len(records)==count:
            self.page.observe();records=self.page.state['records']
        need(len(records)==count+1)
        reference=records[-1];self.page_original(reference);self.state[key]=deepcopy(reference)
        self.state['phase']='before-saved' if key=='before' else 'after-saved';self.save()

    def screen(self):
        self.bound();self.images._load();rows=self.images.rows;prefix=self.state['screenPrefix']
        need(same(rows[:len(prefix)],prefix))
        if len(rows)==len(prefix):
            self.images.capture(self.state['ticket']);self.images._load();rows=self.images.rows
        if len(rows)!=len(prefix)+1 or rows[-1]['phase']!='saved':
            raise SnapshotReviewPending('Original screen delivery is unresolved; no screenshot may be repeated')
        row=rows[-1];need(row['ticket']==self.state['ticket']);self.images.archive(row['nonce'])
        self.state['screenNonce']=row['nonce'];self.state['phase']='screen-saved';self.save()

    @operation
    def acquire(self,ticket):
        identifier(ticket);self.bound()
        if self.state['phase']=='complete':need(self.state['ticket']==ticket);return self.proof()
        need(self.page.state['ticket']==self.capture.state['ticket']==ticket
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
        self.bound();need(self.state['phase'] in ('after-saved','complete'))
        _descriptor,capture,fact,original=self.captured()
        before=self.page_original(self.state['before']);after=self.page_original(self.state['after'])
        need(after['clockJoin']['nativeBefore']['sequence']>before['clockJoin']['nativeAfter']['sequence']
            and after['clockJoin']['nativeBefore']['lifecycle']==before['clockJoin']['nativeAfter']['lifecycle'])
        before_ui,after_ui=before['originals']['ui'],after['originals']['ui']
        name=fact['file']['name'];screen=self.images.archive(self.state['screenNonce'])
        rows=[row for row in self.images.rows if row['nonce']==self.state['screenNonce']];need(len(rows)==1)
        row=rows[0];prefix=self.state['screenPrefix'];need(same(self.images.rows[:len(prefix)],prefix)
            and len(self.images.rows)==len(prefix)+1 and row['ticket']==self.state['ticket'] and row['phase']=='saved'
            and capture['capture']['completedNativeEpochMs']<=before_ui['sampleEpochMs'])
        result=snapshot_review.joined(before_ui,after_ui,row['capture'],original,screen,name,int(self.binding['processIdentity']))
        for value in (before_ui,after_ui):
            controls=[control for control in value['controls'] if control['id']=='snapshot.capture'];need(len(controls)==1)
            need(controls[0]['snapshotRootId']==result['rootIdentity'])
        result.update(originalUIAndScreenOwnershipRequired=False,originalCaptureCompletionRequired=False)
        return dict(iosSnapshotCaptureRenderedReviewVersion=1,runId=self.run,binding=deepcopy(self.binding),
            fixtureUrl=self.page.fixture_url,workProfile='combined',stage='capture-still-png',file=deepcopy(fact['file']),
            renderedReview=result,pins=dict(captureResultSha256=digest(capture),artifactSha256=self.state['capture']['artifactSha256'],
                beforePageOriginalSha256=digest(before),afterPageOriginalSha256=digest(after),
                screenRecordSha256=digest(row),screenOwnerSha256=digest(self.images.state)),
            captureAndRetainedPNGJoined=True,originalPageUIAndWDAJoined=True,hostOriginalRetained=True,
            independentActorSceneRequired=True,backgroundResumeReviewRequired=True,destinationCompositionRequired=True,
            pairedCleanupRequired=True,wholeFeatureRequired=True)

    @operation
    def proof(self):
        self.bound();need(self.state['phase']=='complete');self.inventory();result=self.derived()
        need(same(self.state['result'],result));return result
