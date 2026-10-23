"""Pre-input original settings lease for new runs, with no restore setter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need,number
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner,original
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_settings_originals import PicoSnapshotSettingsOriginals,validate,accept,LIMIT
from adapters.pico4.snapshot_upload_owner import sha
from adapters.script_journey.history import pack,unpack,canonical
from feature_journeys.contract import typed_equal,json_document
from feature_journeys.phase_fixture import validate as phase_packet
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class SnapshotSettingsBaselineOriginals(SnapshotCancelOriginals):
    def __init__(self,path,run,binding):
        self.root=PrivateFeatureState(path);self.scope=dict(snapshotSettingsBaselineOriginalsVersion=1,runId=run,binding=deepcopy(context(binding)),role='snapshot-preinput-settings')
        self.history=ChatSourceChunks(self.root,self.scope);self.disk=self.root.read();self.values=[];self.indices={}
        if self.disk is not None:
            exact(self.disk,set(self.scope)|{'phase','chunks'});need(self.disk['phase']=='reading' and all(typed_equal(self.disk[key],value) for key,value in self.scope.items()))
            self.values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        for index,value in enumerate(self.values):
            self.original(value);digest=self.digest(value);need(digest not in self.indices);self.indices[digest]=index

    @staticmethod
    def original(value):
        exact(value,{'kind','original'});need(value['kind']=='settings' and type(value['original']) is dict)


class PicoSnapshotSettingsBaseline:
    def __init__(self,parent,reader,path,*,may_capture):
        need(isinstance(parent,PicoSnapshotCancelOwner) and isinstance(reader,PicoSnapshotSettingsOriginals)
            and reader.lock is parent.lock and reader.pid==parent.native.pid and callable(may_capture))
        self.parent,self.reader,self.run,self.binding,self.lock,self.source=parent,reader,parent.run,deepcopy(parent.binding),parent.lock,parent.source
        self.store=PrivateFeatureState(path);need(self.store.path==self.lock.path.with_name('snapshot-settings-baseline.json'))
        self.may_capture=may_capture;self.disk=self.state=self.state_sha=None;self.anchor=None
        with self.lock.held():
            self.originals=SnapshotSettingsBaselineOriginals(self.lock.path.with_name('snapshot-settings-baseline-originals.json'),self.run,self.binding)
            self.load()
            if self.disk is None:
                need(parent.state is None and parent.snapshot.state is None and parent.snapshot.ui.state is None
                    and parent.originals.disk is None and self.originals.disk is None and may_capture())
            elif self.state['original'] is not None:
                self.reader.restore(self.packet(self.state['observations'][-1] if self.state['observations'] else self.state['admission'] or self.state['original']))
            parent.bind_settings_baseline(self)

    def bound(self):
        self.lock.assert_held()
        if self.disk is not None:need(typed_equal(self.store.read(),self.disk))
        self.originals.verify()
        if self.state is not None:need(sha(self.state)==self.state_sha and typed_equal(self.state,json_document(canonical(self.state))))
        now=self.parent.native.monotonic();need(number(now,0,1e15));return now

    def packet(self,reference):
        saved=self.originals.get('settings',reference);exact(saved,{'raw','sha256','anchor'});value=original({key:saved[key] for key in ('raw','sha256')},LIMIT)
        validate(value,self.run,value['commandId'],self.reader.pid,value['capturedEpochMs']);anchor=saved['anchor'];exact(anchor,{'hostMonotonic','nativeEpochMs'})
        need(number(anchor['hostMonotonic'],0,1e15) and integer(anchor['nativeEpochMs'],1) and value['capturedEpochMs']>=anchor['nativeEpochMs']);return value

    def validate(self,state):
        exact(state,{'stage','phase','original','admission','envelope','observations'})
        need(state['stage'] in ('capture-issued','captured','admitted','enveloped') and type(state['observations']) is list and len(state['observations'])<=32)
        phase=state['phase'];phase_packet(phase,run=self.run,area='snapshots',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['active'] and phase['activations'][-1]['stimulus']==dict(verb='baseline',inputs={}))
        if self.parent.state is not None:
            baseline=self.parent.state['baseline'];need(all(typed_equal(phase[key],baseline[key]) for key in ('instance','createdEpochMs','activations')))
        if state['original'] is None:need(state['stage']=='capture-issued' and state['admission'] is None and state['envelope'] is None and not state['observations']);return
        before=self.packet(state['original'])
        if state['admission'] is not None:
            current=self.packet(state['admission']);accept(before,current);need(typed_equal(current['source']['entries'],before['source']['entries'])
                and typed_equal(current['source']['formatCache'],before['source']['formatCache']) and current['source']['typedSha256']==before['source']['typedSha256'])
        if state['envelope'] is not None:
            validate_envelope(state['envelope'],self.parent.session.profile);origin=self.parent.state['sessionOrigin']
            need(state['admission'] is not None and state['envelope']['sessionNonce']==origin['sessionNonce'] and state['envelope']['sequence']==origin['nextSequence']
                and state['envelope']['commands']==[dict(id='tablet-open-'+str(origin['nextSequence']),operation='tablet.open',arguments=dict(holdMilliseconds=1000))]
                and any(delivery['kind']=='controller' and typed_equal(delivery['command'],state['envelope']) for delivery in self.parent.state['deliveries']))
        previous=self.packet(state['admission']) if state['admission'] is not None else before
        for reference in state['observations']:
            need(state['stage']=='enveloped');value=self.packet(reference);accept(previous,value);previous=value
        need((state['stage']=='captured')==(state['admission'] is None) and (state['stage']=='enveloped')==(state['envelope'] is not None))

    def load(self):
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None and self.originals.disk is None);return
        exact(disk,{'snapshotSettingsBaselineVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['snapshotSettingsBaselineVersion']) is int and disk['snapshotSettingsBaselineVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url)
        values=unpack(disk['payload']);need(len(values)==1);state=values[0];self.validate(state);self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def save(self,state):
        self.bound();self.validate(state)
        disk=dict(snapshotSettingsBaselineVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,payload=pack([state]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def identity(self):
        self.bound();need(self.state is not None and self.state['original'] is not None)
        return sha(dict(runId=self.run,binding=self.binding,phase=self.state['phase'],original=self.originals.get('settings',self.state['original'])))

    def capture(self):
        self.lock.assert_held();self.load();need(self.parent.state is None)
        if self.state is None:
            need(self.may_capture());phase=self.source.status(None)
            self.save(dict(stage='capture-issued',phase=phase,original=None,admission=None,envelope=None,observations=[]))
        need(self.state['stage'] in ('capture-issued','captured'))
        if self.state['stage']=='capture-issued':
            need(self.parent.snapshot.state is None and self.parent.snapshot.ui.state is None and self.parent.originals.disk is None)
            value=self.reader.capture(self.run);state=deepcopy(self.state);state.update(stage='captured',original=self.originals.put('settings',self.reader.original()));self.save(state)
            need(value==self.packet(state['original']))
        result=self.report();need(self.parent.native.guard() is not False);started=self.bound();requested=self.source.epoch_ms();phase=self.source.status(self.state['phase'])
        need(phase['active'] and all(typed_equal(phase[key],self.state['phase'][key]) for key in ('instance','createdEpochMs','activations')))
        epoch=self.source.epoch_ms();finished=self.bound();need(-250<=epoch-phase['capturedEpochMs'] and max(epoch-phase['capturedEpochMs'],requested-phase['capturedEpochMs']+(finished-started)*1000)<=1500)
        return result

    def before_input(self):
        self.lock.assert_held();self.load();need(self.state['stage'] in ('captured','admitted') and self.parent.state['stage']=='open-issued'
            and not self.parent.state['deliveries'] and self.parent.current)
        # SDK/queue work stays outside the Session lock. The parent's final
        # exact phase/clock fence follows this last source acquisition and CAS.
        value=self.reader.capture(self.run);before=self.packet(self.state['original']);need(value['source']['typedSha256']==before['source']['typedSha256']
            and typed_equal(value['source']['entries'],before['source']['entries']) and typed_equal(value['source']['formatCache'],before['source']['formatCache']))
        state=deepcopy(self.state);state.update(stage='admitted',admission=self.originals.put('settings',self.reader.original()));self.save(state)

    def input_intent(self,envelope):
        # Private host-only CAS under the original Session sequence lock.
        self.lock.assert_held();self.load();need(self.state['stage']=='admitted' and self.parent.current)
        state=deepcopy(self.state);state.update(stage='enveloped',envelope=deepcopy(envelope));self.save(state)

    def observe(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='enveloped' and len(self.state['observations'])<32)
            self.reader.capture(self.run);state=deepcopy(self.state);state['observations'].append(self.originals.put('settings',self.reader.original()));self.save(state)
            latest=self.packet(state['observations'][-1]);anchor=self.reader.anchor;oldest=min(latest['capturedEpochMs'],latest['source']['entriesEpochMs']);result=self.report()
            need(self.parent.native.guard() is not False);now=self.parent.native.clock_ms();completed=self.bound()
            need(number(completed,anchor['hostMonotonic'],1e15) and -250<=now-oldest and max(now-oldest,anchor['nativeEpochMs']-oldest+(completed-anchor['hostMonotonic'])*1000)<=1500)
            return result

    def report(self):
        match=None
        if self.state is not None and self.state['observations']:
            current=self.packet(self.state['observations'][-1]);before=self.packet(self.state['original']);match=current['source']['typedSha256']==before['source']['typedSha256'] and typed_equal(current['source']['entries'],before['source']['entries']) and typed_equal(current['source']['formatCache'],before['source']['formatCache'])
        return dict(qualification='PICO_SNAPSHOT_PREINPUT_SETTINGS_ORIGINAL_ONLY',baselineCaptured=self.state is not None and self.state['original'] is not None,
            originalInputBound=self.state is not None and self.state['envelope'] is not None,currentSettingsMatchOriginal=match,settingsRestored=False,journalRetained=True,fullSnapshotRecipe=False,deviceAcceptance=False)
