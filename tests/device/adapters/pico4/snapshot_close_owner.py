"""Normal checked-control restoration and Tablet Close; retained originals.

Only original mode/format UI values were admitted before this run's input.
This component does not invent the missing thirteen-key settings baseline.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,need,integer,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_return_image import PicoSnapshotReturnImage
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals
from adapters.pico4.snapshot_upload_owner import sha,provider_phase,quiet_indices
from adapters.pico4.snapshot_upload_frame import validate as frame_packet,clocks
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
from adapters.pico4.snapshot import MODES,FORMATS
from adapters.pico4.navigation import identifier
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.script_journey.history import pack,unpack,canonical
from feature_journeys.contract import typed_equal,json_document
from feature_journeys.phase_fixture import validate as phase_packet
from openxr_input.controller_protocol import validate_envelope

VERSION=1
STAGES=('prepare-issued','prepared','restore-issued','restored','close-issued','closed','quiet-issued','partial-closed')


class SnapshotCloseOriginals(SnapshotUploadOriginals):
    VERSION_KEY='snapshotCloseOriginalsVersion'
    VERBS=('close',)


class PicoSnapshotCloseOwner:
    def __init__(self,parent,path):
        need(isinstance(parent,PicoSnapshotReturnImage) and parent.role=='primary')
        self.parent,self.bg,self.run,self.binding,self.lock,self.source=parent,parent.parent,parent.run,deepcopy(parent.binding),parent.lock,parent.source
        self.store=PrivateFeatureState(path);need(self.store.path==self.lock.path.with_name('snapshot-close-owner.json'))
        self.disk=self.state=self.state_sha=self.anchor=None;self.current=False;self.controller_anchor=self.controller_envelope=None
        with self.lock.held():
            parent.load();need(parent.state['phase']=='complete');self.parent_disk=deepcopy(parent.disk);self.parent_sha=sha(self.parent_disk)
            need(self.bg.status()['foreground']);self.upload=self.bg.live();self.base=self.upload.base
            need(isinstance(self.base,PicoSnapshotCancelOwner) and self.base.lock is self.lock and self.base.binding==self.binding)
            self.snapshot,self.native,self.session=self.base.snapshot,self.base.native,self.base.session
            _store,header,originals=self.bg.ancestors[0];rows=unpack(header['payload']);need(len(rows)==1);cancel=originals.decode(rows[0])
            need(typed_equal(cancel,self.base.state));self.session_basis=deepcopy(cancel['sessionOrigin'])
            deliveries=[row['command'] for row in cancel['deliveries'] if row['kind']=='controller'];need(deliveries)
            for value in deliveries:
                validate_envelope(value,self.session.profile);need(value['sessionNonce']==self.session_basis['sessionNonce'] and value['sequence']==self.session_basis['nextSequence']
                    and value['commands']==[dict(id='tablet-open-'+str(value['sequence']),operation='tablet.open',arguments=dict(holdMilliseconds=1000))])
                self.session_basis['nextSequence']+=1
            self.session_basis_sha=sha(self.session_basis)
            self.preference=deepcopy(self.snapshot._read());need(self.preference is not None);self.snapshot._validate(self.preference)
            for field,options in (('mode',MODES),('format',FORMATS)):
                value=self.preference['original'+field.title()];need(value in options)
                control='snapshot.'+field+'.'+value
                original=[row for row in cancel['deliveries'] if row['stage']=='open-issued' and row['kind']=='qml' and row['command']['controlId']==control]
                need(len(original)==1);ui=cancel['frames'][original[0]['frame']]['ui'];choice=self.snapshot.ui.control(ui,control)
                need(choice is not None and choice['checked'] is True)
            self.preference_sha=sha(self.preference);self.originals=SnapshotCloseOriginals(self.lock.path.with_name('snapshot-close-originals.json'),self.run,self.binding,'close')
            self.load();self.session_binding();self.base.bind_close_owner(self)

    def bound(self):
        self.parent.bound();need(sha(self.parent_disk)==self.parent_sha and typed_equal(self.parent.store.read(),self.parent_disk)
            and sha(self.preference)==self.preference_sha and typed_equal(self.snapshot._read(),self.preference)
            and sha(self.session_basis)==self.session_basis_sha and typed_equal(self.session_basis,json_document(canonical(self.session_basis))))
        if self.state is not None:
            need(typed_equal(self.store.read(),self.disk) and sha(self.state)==self.state_sha and typed_equal(self.state,json_document(canonical(self.state))));self.originals.verify()
        now=self.native.monotonic();need(number(now,0,1e15));return now

    def session_binding(self):
        # Host-only cursor admission outside the original Session callback.
        # An uncertain grant remains readable but never authorizes a resend.
        self.bound()
        with self.session._lock():current=self.session._load()
        need(current is not None and all(typed_equal(current[key],self.session_basis[key]) for key in ('schemaVersion','sessionNonce','processIdentity')))
        sequences={self.session_basis['nextSequence']}
        if self.state is not None and self.state['controller'] is not None and self.state['controller']['envelope'] is not None:
            sequences.add(self.session_basis['nextSequence']+1)
            if self.state['stage'] in ('closed','quiet-issued','partial-closed'):sequences.remove(self.session_basis['nextSequence'])
        need(current['nextSequence'] in sequences)

    def phase(self,value):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        previous=self.bg.state['source'];need(value['active'] and all(typed_equal(value[key],previous[key]) for key in ('instance','createdEpochMs'))
            and typed_equal(value['activations'][:-1],previous['activations']) and value['activations'][-1]['stimulus']==dict(verb='close',inputs={}))

    def frame(self,row,state):
        self.bg.stable_frame(row,returned=True);provider_phase(row['provider'],state['source']);ui=row['base']['ui'];old=self.bg.origin['base']['ui']
        need(ui['bridgeId']==old['bridgeId'])
        if ui['open']:
            need(ui['ready'] and ui['generation']==old['generation'] and ui['picoSnapshotReview']['present'])
            current,original=ui['picoSnapshotReview']['review'],old['picoSnapshotReview']['review']
            need(all(typed_equal(current[key],original[key]) for key in original if key not in ('mode','format')))
        else:
            need(not ui['ready'] and not ui['controls'] and ui['generation']!=old['generation'])
            if ui['picoSnapshotReview']['present']:
                current,original=ui['picoSnapshotReview']['review'],old['picoSnapshotReview']['review']
                need(all(typed_equal(current[key],original[key]) for key in original if key not in ('mode','format','visible'))
                    and current['mode']==MODES.index(self.preference['originalMode']) and current['format']==self.preference['originalFormat'])
            if state['closedGeneration'] is not None:need(ui['generation']==state['closedGeneration'])
        return ui

    def restored(self,row):
        ui=row['base']['ui'];review=ui['picoSnapshotReview'];need(ui['open'] and ui['ready'] and review['present'])
        value=review['review'];return (value['mode']==MODES.index(self.preference['originalMode']) and value['format']==self.preference['originalFormat']
            and not any(control['id'].startswith(('snapshot.mode.','snapshot.format.')) for control in ui['controls']))

    def validate(self,state):
        exact(state,{'stage','source','parentSha256','frames','steps','restoration','controller','neutral','neutrals','closedGeneration','quiet','received'})
        need(state['stage'] in STAGES and state['parentSha256']==self.parent_sha and state['received'] is None
            and type(state['frames']) is list and len(state['frames'])<=96 and type(state['steps']) is list and len(state['steps'])<=4)
        self.phase(state['source']);previous=None;closed=False
        for row in state['frames']:
            self.frame(row,state)
            need(not closed or not row['base']['ui']['open']);closed=closed or not row['base']['ui']['open']
            if previous is not None:
                need(row['hostMonotonic']>=previous['hostMonotonic'])
                old=frame_packet(previous,self.run,self.bg.pid,self.binding['sessionId']);new=frame_packet(row,self.run,self.bg.pid,self.binding['sessionId'])
                from adapters.pico4.snapshot_originals import accept
                from adapters.pico4.snapshot_script_originals import accept as script_accept
                from adapters.pico4.snapshot_capture_source import continuity as files_accept
                from adapters.pico4.snapshot_upload_source import continuity as upload_accept
                from adapters.native_account_observation import accept as account_accept
                from adapters.pico4.snapshot_upload_fixture import validate as provider_packet
                accept(old[0],new[0]);script_accept(old[1],new[1]);files_accept(old[2],new[2]);upload_accept(old[3],new[3]);account_accept(old[4]['account']['observation'],new[4]['account'])
                need(new[4]['instance']==old[4]['instance'] and new[4]['sequence']>old[4]['sequence'] and new[4]['requestId']!=old[4]['requestId'])
                provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'],previous=previous['provider'])
            previous=row
        ids=set();commands=set();last_after=-1
        for index,step in enumerate(state['steps']):
            exact(step,{'id','before','command','after'});control=step['id'];need(control not in ids and control in ('snapshot.mode','snapshot.format',
                'snapshot.mode.'+self.preference['originalMode'],'snapshot.format.'+self.preference['originalFormat']));ids.add(control)
            need(integer(step['before'],0,len(state['frames'])-1) and step['before']>last_after and state['frames'][step['before']]['base']['ui']['open'])
            field='mode' if control.startswith('snapshot.mode') else 'format'
            if control!='snapshot.'+field:need(index>0 and state['steps'][index-1]['id']=='snapshot.'+field and state['steps'][index-1]['after'] is not None)
            if step['command'] is not None:
                self.qml(step['command'],state['frames'][step['before']],control);need(step['command']['commandId'] not in commands);commands.add(step['command']['commandId'])
            if step['after'] is not None:
                need(step['command'] is not None and integer(step['after'],step['before']+1,len(state['frames'])-1));self.effect(step,state['frames'][step['after']]);last_after=step['after']
            else:need(index==len(state['steps'])-1 and state['stage']=='restore-issued')
        previous_sequence=self.bg.origin['base']['ui']['lastCommandSequence']
        for index,row in enumerate(state['frames']):
            issued=[step for step in state['steps'] if step['command'] is not None and step['before']<index]
            maximum=self.bg.origin['base']['ui']['lastCommandSequence']+len(issued);sequence=row['base']['ui']['lastCommandSequence']
            need(previous_sequence<=sequence<=maximum);previous_sequence=sequence
        if state['restoration'] is not None:need(integer(state['restoration'],0,len(state['frames'])-1) and state['restoration']>last_after and self.restored(state['frames'][state['restoration']]))
        if state['stage'] in ('restored','close-issued','closed','quiet-issued','partial-closed'):need(state['restoration'] is not None and all(step['after'] is not None for step in state['steps']))
        controller=state['controller'];closing=state['stage'] in ('close-issued','closed','quiet-issued','partial-closed')
        need((controller is not None)==closing)
        if not closing:need(state['neutral'] is None and not state['neutrals'] and state['closedGeneration'] is None and not closed)
        if controller is not None:
            exact(controller,{'before','envelope'});need(integer(controller['before'],0,len(state['frames'])-1) and state['restoration'] is not None and controller['before']>state['restoration'] and self.restored(state['frames'][controller['before']]))
            if controller['envelope'] is not None:self.envelope(controller['envelope'])
        need(type(state['neutrals']) is list and len(state['neutrals'])<=len(state['frames']));last=-1
        for row in state['neutrals']:
            exact(row,{'frame','value'});index=row['frame'];need(integer(index,last+1,len(state['frames'])-1) and not state['frames'][index]['base']['ui']['open']
                and controller is not None and controller['envelope'] is not None)
            PicoLifecycleBack.neutral(row['value'],controller['envelope'],max(clocks(state['frames'][index])[1:])-1500)
            need(row['value']['updatedEpochMs']<=max(clocks(state['frames'][index])[1:])+250);last=index
        need((state['neutral'] is None)==(not state['neutrals']))
        if state['neutral'] is not None:need(typed_equal(state['neutral'],state['neutrals'][-1]['value']))
        if state['stage'] in ('closed','quiet-issued','partial-closed'):
            need(controller is not None and controller['envelope'] is not None and state['neutral'] is not None
                and state['closedGeneration'] is not None and state['frames'] and not state['frames'][-1]['base']['ui']['open']
                and [row['frame'] for row in state['neutrals']]==[index for index,row in enumerate(state['frames']) if not row['base']['ui']['open']])
        need(type(state['quiet']) is list and len(state['quiet'])<=1 and bool(state['quiet'])==(state['stage']=='partial-closed'))
        for window in state['quiet']:
            exact(window,{'indices'});indices=window['indices'];quiet_indices(indices,len(state['frames']));start=previous=signature=None
            for index in indices:
                row=state['frames'][index];need(not row['base']['ui']['open']);value=self.quiet_clocks(row,state,index);key=self.signature(row)
                if start is None:start=value;signature=key
                else:need(key==signature and all(0<=b-a<=500 for a,b in zip(previous,value)))
                previous=value
            need(all(b-a>=3000 for a,b in zip(start,previous)))

    def load(self):
        self.bound();disk=self.store.read();need(self.disk is None or typed_equal(self.disk,disk))
        if disk is None:need(self.state is None);self.originals.verify();return
        exact(disk,{'snapshotCloseOwnerVersion','runId','binding','fixtureUrl','preference','payload'})
        need(type(disk['snapshotCloseOwnerVersion']) is int and disk['snapshotCloseOwnerVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url and typed_equal(disk['preference'],self.preference))
        rows=unpack(disk['payload']);need(len(rows)==1);state=self.originals.decode(rows[0]);self.validate(state);self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def save(self,state,*,host_only=False):
        self.bound();need(typed_equal(self.store.read(),self.disk));self.validate(state)
        disk=dict(snapshotCloseOwnerVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,preference=self.preference,payload=pack([self.originals.encode(state,host_only=host_only)]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state;self.state_sha=sha(state);self.bound()

    def observe(self):
        need(self.bg.status()['foreground']);started=self.bound();requested=self.native.clock_ms()
        neutral=self.session.require_owned_neutral(self.binding['processIdentity'],self.state['controller']['envelope']) if self.state['stage'] in ('close-issued','closed','quiet-issued','partial-closed') and self.state['controller']['envelope'] is not None else None
        row=self.upload.read_frame();self.frame(row,self.state)
        state=deepcopy(self.state);state['frames'].append(row)
        if neutral is not None and not row['base']['ui']['open']:state['neutrals'].append(dict(frame=len(state['frames'])-1,value=deepcopy(neutral)));state['neutral']=deepcopy(neutral)
        self.save(state);need(self.native.guard() is not False);epoch=self.native.clock_ms();completed=self.bound();captured=min(clocks(row)[1:])
        need(-250<=epoch-captured and max(epoch-captured,requested-captured+(completed-started)*1000)<=1500);self.anchor=(started,requested,captured);return row

    def fence(self):
        need(self.anchor is not None);started,requested,captured=self.anchor;self.bound();need(self.native.guard() is not False)
        phase_started=self.bound();phase_requested=self.source.epoch_ms();value=self.source.status(self.state['source'])
        need(value['active'] and all(typed_equal(value[key],self.state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        epoch=self.native.clock_ms();fixture_epoch=self.source.epoch_ms();completed=self.bound()
        age=max(epoch-captured,requested-captured+(completed-started)*1000,fixture_epoch-value['capturedEpochMs'],phase_requested-value['capturedEpochMs']+(completed-phase_started)*1000)
        need(number(epoch,1,1e15) and number(fixture_epoch,phase_requested,1e15) and -250<=epoch-captured and -250<=fixture_epoch-value['capturedEpochMs'] and age<=1500);return completed,age

    def qml(self,command,row,control):
        exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'})
        ui=row['base']['ui'];choice=self.snapshot.ui.control(ui,control)
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and identifier(command['commandId']) and command['controlId']==control
            and command['bridgeId']==self.binding['sessionId'] and command['generation']==ui['generation'] and command['action']=='activate'
            and integer(command['sequence'],1) and command['sequence']==ui['lastCommandSequence']+1 and integer(command['observedElapsedMs'])
            and 0<=ui['elapsedMs']-command['observedElapsedMs']<=1500 and choice is not None and choice['token']==command['controlToken'])

    def effect(self,step,row):
        ui=row['base']['ui'];need(ui['open'] and ui['lastCommandSequence']==step['command']['sequence'])
        field='mode' if step['id'].startswith('snapshot.mode') else 'format';value=self.preference['original'+field.title()]
        if step['id']=='snapshot.'+field:need(self.snapshot.ui.control(ui,'snapshot.'+field+'.'+value) is not None)
        else:
            review=ui['picoSnapshotReview']['review'];need(review[field]==(MODES.index(value) if field=='mode' else value)
                and not any(control['id'].startswith('snapshot.'+field+'.') for control in ui['controls']))

    def before_qml(self,command):
        self.lock.assert_held();need(self.current and self.state['stage']=='restore-issued');self.session_binding();step=self.state['steps'][-1]
        need(step['command'] is None and step['after'] is None);row=self.observe();self.qml(command,row,step['id'])
        state=deepcopy(self.state);state['steps'][-1].update(before=len(state['frames'])-1,command=deepcopy(command));self.save(state);self.fence()

    def envelope(self,value):
        validate_envelope(value,self.session.profile);need(value['sessionNonce']==self.session_basis['sessionNonce'] and value['sequence']==self.session_basis['nextSequence'] and len(value['commands'])==1
            and value['commands'][0]==dict(id='tablet-close-'+str(value['sequence']),operation='tablet.close',arguments=dict(holdMilliseconds=1000)))

    def before_controller(self,operation):
        self.lock.assert_held();need(self.current and operation=='tablet.close' and self.state['stage']=='close-issued' and self.state['controller']['envelope'] is None);self.session_binding()
        row=self.observe();need(self.restored(row));state=deepcopy(self.state);state['controller']['before']=len(state['frames'])-1;self.save(state)
        self.controller_anchor=self.fence();self.controller_envelope=None

    def controller_intent(self,envelope):
        # This original Session callback performs only host validation/CAS.
        # No phase/native query, guard or Session re-entry is allowed here.
        self.lock.assert_held();need(self.current and self.state['stage']=='close-issued' and self.state['controller']['envelope'] is None
            and self.controller_anchor is not None and self.controller_envelope is None);self.envelope(envelope)
        state=deepcopy(self.state);state['controller']['envelope']=deepcopy(envelope);self.save(state,host_only=True)
        self.controller_envelope=deepcopy(envelope);self.before_publish(envelope)

    def before_publish(self,envelope):
        self.lock.assert_held();need(self.current and self.state['stage']=='close-issued' and typed_equal(envelope,self.state['controller']['envelope'])
            and self.controller_anchor is not None and typed_equal(envelope,self.controller_envelope));started,age=self.controller_anchor;now=self.native.monotonic()
        need(number(now,started,1e15) and age+(now-started)*1000<=1500)

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None or self.state['stage']=='prepare-issued')
            if self.state is None:
                value=self.source.status(self.bg.state['source']);self.phase(value)
                self.save(dict(stage='prepare-issued',source=value,parentSha256=self.parent_sha,frames=[],steps=[],restoration=None,controller=None,neutral=None,neutrals=[],closedGeneration=None,quiet=[],received=None))
            row=self.observe();need(row['base']['ui']['open']);state=deepcopy(self.state);state['stage']='prepared';self.save(state);result=self.report();self.fence();return result

    def restore(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('prepared','restore-issued'))
            if self.state['stage']=='restore-issued':return self.reconcile()
            for field,options in (('mode',MODES),('format',FORMATS)):
                row=self.observe();value=self.preference['original'+field.title()];current=row['base']['ui']['picoSnapshotReview']['review'][field]
                if current==(MODES.index(value) if field=='mode' else value) and not any(control['id'].startswith('snapshot.'+field+'.') for control in row['base']['ui']['controls']):continue
                for control in ('snapshot.'+field,'snapshot.'+field+'.'+value):
                    previous=[step for step in self.state['steps'] if step['id']==control]
                    if previous:
                        need(len(previous)==1 and previous[0]['after'] is not None);continue
                    row=self.observe()
                    state=deepcopy(self.state);state['stage']='restore-issued';state['steps'].append(dict(id=control,before=len(state['frames'])-1,command=None,after=None));self.save(state);self.fence()
                    self.current=True
                    try:self.snapshot.click(control)
                    finally:self.current=False
                    self.reconcile();need(self.state['stage']=='prepared')
            row=self.observe();need(self.restored(row));state=deepcopy(self.state);state.update(stage='restored',restoration=len(state['frames'])-1);self.save(state);result=self.report();self.fence();return result

    def close(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='restored');row=self.observe();need(self.restored(row))
            state=deepcopy(self.state);state.update(stage='close-issued',controller=dict(before=len(state['frames'])-1,envelope=None));self.save(state);self.fence();self.current=True
            try:self.snapshot.ui.controller('tablet.close')
            finally:self.current=False
            return self.reconcile()

    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('restore-issued','close-issued','closed','quiet-issued','partial-closed'))
            if self.state['stage']=='close-issued':
                need(self.state['controller']['envelope'] is not None)
            row=self.observe();state=deepcopy(self.state)
            if state['stage']=='restore-issued':
                step=state['steps'][-1];need(step['command'] is not None);self.effect(step,row);step['after']=len(state['frames'])-1;state['stage']='prepared'
            elif state['stage']=='close-issued':
                need(not row['base']['ui']['open']);need(state['neutrals'] and state['neutrals'][-1]['frame']==len(state['frames'])-1);state.update(stage='closed',closedGeneration=row['base']['ui']['generation'])
            self.save(state);result=self.report();self.fence();return result

    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('closed','quiet-issued'));state=deepcopy(self.state);state['stage']='quiet-issued';self.save(state)
            start=previous=signature=None;indices=[]
            for attempt in range(65):
                row=self.observe();need(not row['base']['ui']['open']);value=self.quiet_clocks(row,self.state,len(self.state['frames'])-1);key=self.signature(row)
                if start is None or any(b-a>500 for a,b in zip(previous,value)):start=value;signature=key;indices=[]
                need(key==signature);previous=value;indices.append(len(self.state['frames'])-1);self.fence()
                if all(b-a>=3000 for a,b in zip(start,value)):
                    state=deepcopy(self.state);state.update(stage='partial-closed',quiet=[dict(indices=indices)]);self.save(state);result=self.report();self.fence();return result
                need(attempt<64);self.native.sleep(.25)

    @staticmethod
    def quiet_clocks(row,state,index):
        values=[sample['value'] for sample in state['neutrals'] if sample['frame']==index];need(len(values)==1)
        return (*clocks(row),values[0]['updatedEpochMs'])

    def signature(self,row):
        return sha(dict(work=self.base.scoped_work(row['base']),review=row['base']['ui']['picoSnapshotReview'],generation=row['base']['ui']['generation'],provider=row['provider']['requests']))

    def report(self):
        return dict(qualification='PICO_SNAPSHOT_NORMAL_CLOSE_COMPONENT_ONLY',stage=self.state['stage'],fullSnapshotRecipe=False,deviceAcceptance=False,
            checkedModeFormatRestored=self.state['restoration'] is not None,tabletClosed=self.state['stage'] in ('closed','quiet-issued','partial-closed'),
            originalControllerNeutral=self.state['neutral'] is not None,completeSettingsBaseline=False,qtObjectsRetired=False,globalExportExecutorRetired=False,journalRetained=True)
