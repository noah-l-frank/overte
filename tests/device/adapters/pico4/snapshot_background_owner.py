"""One-send Snapshot HOME/return using existing Pico OS and lifecycle sources.

The frozen Phone b62 Snapshot background path supplies the lifecycle identity
join. No Chat-only history, Phone touch authority or foreground bypass is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals,SnapshotBackgroundOriginals
from adapters.pico4.snapshot_save_originals import SnapshotSaveOriginals
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_upload_frame import validate as frame_packet,clocks
from adapters.pico4.snapshot_upload_owner import sha,provider_phase,mutation_scope,quiet_indices
from adapters.pico4.snapshot_upload_source import continuity as upload_continuity,require_retired
from adapters.pico4.snapshot_upload_fixture import validate as provider_packet
from adapters.pico4.snapshot_upload_fixture import join
from adapters.native_account_observation import accept as account_accept
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
from adapters.pico4.snapshot_script_originals import accept as script_accept
from adapters.pico4.snapshot_capture_source import continuity as files_accept
from adapters.pico4.snapshot_originals import accept as native_accept
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.contract import typed_equal,json_document
from adapters.script_journey.history import canonical

VERSION=1
STAGES=('prepare-issued','prepared','home-issued','background-observed','resume-issued','returned','quiet-issued','partial-ready')


class PicoSnapshotBackgroundOwner:
    def __init__(self,path,run,binding,lock,source,os_status,os_input,runtime,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(lock,ScriptSourceLock) and isinstance(source,PhaseFixtureReader) and source.run==run and source.area=='snapshots'
            and all(callable(value) for value in (os_status,os_input,runtime,monotonic,sleep)))
        self.store=PrivateFeatureState(path);need(self.store.path==lock.path.with_name('snapshot-background-owner.json'))
        self.run,self.binding,self.lock,self.source=run,deepcopy(context(binding)),lock,source;self.pid=int(binding['processIdentity'].split(':')[0]);self.binding_sha=sha(self.binding)
        self.os_status,self.os_input,self.runtime,self.monotonic,self.sleep=os_status,os_input,runtime,monotonic,sleep
        self.disk=self.state=self.anchor=None
        with lock.held():
            self.parent_store=PrivateFeatureState(lock.path.with_name('snapshot-upload-owner.json'));self.parent_disk=self.parent_store.read()
            need(self.parent_disk is not None and self.parent_disk['runId']==run and typed_equal(self.parent_disk['binding'],self.binding)
                and self.parent_disk['verb']=='upload' and self.parent_disk['snapshotUploadOwnerVersion']==1 and self.parent_disk['fixtureUrl']==source.fixture_url)
            self.parent_originals=SnapshotUploadOriginals(lock.path.with_name('snapshot-upload-originals.json'),run,binding,'upload')
            self.ancestors=[]
            for name,kind,verb in (('snapshot-cancel',SnapshotCancelOriginals,None),('snapshot-save',SnapshotSaveOriginals,None),('snapshot-upload-fail',SnapshotUploadOriginals,'upload-fail')):
                store=PrivateFeatureState(lock.path.with_name(name+'-owner.json'));header=store.read();need(header is not None and header['runId']==run and typed_equal(header['binding'],self.binding))
                original=kind(lock.path.with_name(name+'-originals.json'),run,binding,*(() if verb is None else (verb,)))
                payload=unpack(header['payload']);need(len(payload)==1);original.decode(payload[0]);self.ancestors.append((store,deepcopy(header),original))
            rows=unpack(self.parent_disk['payload']);need(len(rows)==1);self.parent=self.parent_originals.decode(rows[0]);need(self.parent['stage']=='partial-ready')
            self.parent_disk_sha=sha(self.parent_disk);self.parent_sha=sha(self.parent);self.origin=self.parent['frames'][-1];frame_packet(self.origin,run,self.pid,self.binding['sessionId'])
            self.parent_closure()
            self.originals=SnapshotBackgroundOriginals(lock.path.with_name('snapshot-background-originals.json'),run,binding,'background');self.load()

    def parent_closure(self):
        """Cold input admission reopens actual closure data, never a ready label."""
        state=self.parent
        exact(state,{'stage','source','parentSha256','failureSha256','frames','deliveries','job','proof','readId','received','artifacts','artifactRoot','scope','quiet'})
        need(state['scope']==self.run and state['received'] is not None and len(state['deliveries'])==1 and len(state['quiet'])==1)
        need(sha(PrivateFeatureState(self.lock.path.with_name('snapshot-save-owner.json')).read())==state['parentSha256']
            and sha(PrivateFeatureState(self.lock.path.with_name('snapshot-upload-fail-owner.json')).read())==state['failureSha256'])
        phase_packet(state['source'],run=self.run,area='snapshots',request=state['source']['requestId'],epoch=state['source']['capturedEpochMs'])
        need(state['source']['active'] and state['source']['activations'][-1]['stimulus']==dict(verb='upload',inputs={}))
        exact(state['proof'],{'frame'});need(integer(state['proof']['frame'],0,len(state['frames'])-1))
        row=state['frames'][state['proof']['frame']];parts=frame_packet(row,self.run,self.pid,self.binding['sessionId'])
        files=parts[2]['source']['rows'];need(len(files)==1);capture=files[0]
        proof=join(parts[3]['source'],row['provider'],state['job'],ticket=state['source']['activations'][-1]['ticket'],
            image_bytes=capture['bytes'],image_sha256=capture['sha256'],path=capture['path'],success=True)
        exact(state['quiet'][0],{'indices'});indices=state['quiet'][0]['indices'];quiet_indices(indices,len(state['frames']))
        previous=start=None;signature=None
        for index in indices:
            row=state['frames'][index];frame_packet(row,self.run,self.pid,self.binding['sessionId']);self.frame(row,returned=False,historical=True)
            provider_phase(row['provider'],state['source']);mutation_scope(row['provider'],state['frames'][0]['provider'],proof['requests'])
            current=clocks(row);key=self.signature(row)
            if start is None:start=current;signature=key
            else:need(key==signature and all(0<=b-a<=500 for a,b in zip(previous,current)))
            previous=current
        need(all(b-a>=3000 for a,b in zip(start,previous)))

    def bound(self):
        self.lock.assert_held();context(self.binding)
        for value,digest in ((self.binding,self.binding_sha),(self.parent,self.parent_sha),(self.parent_disk,self.parent_disk_sha)):
            raw=canonical(value);need(hashlib.sha256(raw).hexdigest()==digest and typed_equal(value,json_document(raw)))
        need(typed_equal(self.parent_store.read(),self.parent_disk) and self.source.run==self.run and self.source.area=='snapshots'
            and self.source.fixture_url==self.parent_disk['fixtureUrl']);self.parent_originals.verify()
        for store,header,original in self.ancestors:need(typed_equal(store.read(),header));original.verify()
        now=self.monotonic();need(number(now,0,1e15))
        if self.state is not None:
            need(all(now>=row['hostMonotonic'] for row in self.state['frames']) and all(now>=row['hostMonotonic'] for row in self.state['os']))
        return now

    def phase(self,value):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        old=self.parent['source'];need(value['active'] and all(value[key]==old[key] for key in ('instance','createdEpochMs'))
            and typed_equal(value['activations'][:-1],old['activations'])
            and value['activations'][-1]['stimulus']==dict(verb='background-resume',inputs={}))

    def status(self):
        self.bound();row=self.os_status(deepcopy(self.binding));exact(row,{'binding','foreground','running'})
        need(typed_equal(row['binding'],self.binding) and type(row['foreground']) is bool and row['running'] is True);self.bound();return deepcopy(row)

    def stable_frame(self,row,*,returned,historical=False):
        native,script,files,upload,account=frame_packet(row,self.run,self.pid,self.binding['sessionId'])
        before=frame_packet(self.origin,self.run,self.pid,self.binding['sessionId']);old_native,old_script,old_files,old_upload,old_account=before
        if not historical:
            native_accept(old_native,native);script_accept(old_script,script);files_accept(old_files,files);upload_continuity(old_upload,upload);account_accept(old_account['account']['observation'],account['account'])
        need(typed_equal(native['requests'],old_native['requests']) and typed_equal(script['history'],old_script['history'])
            and typed_equal(script['captureContext']['entries'],old_script['captureContext']['entries'])
            and script['captureContext']['instance']==old_script['captureContext']['instance']
            and typed_equal(files['source']['rows'],old_files['source']['rows'])
            and all(typed_equal(row['base']['inventory'][key],self.origin['base']['inventory'][key]) for key in ('files','rows'))
            and typed_equal(upload['source']['jobs'],old_upload['source']['jobs']) and typed_equal(upload['source']['events'],old_upload['source']['events']))
        lifecycle,old=account['lifecycle'],old_account['lifecycle']
        need(account['instance']==old_account['instance'] and lifecycle['launches']==old['launches']
            and all(typed_equal(account['account'][key],old_account['account'][key]) for key in ('loggedIn','principalSha256'))
            and all(typed_equal(account['account']['observation'][key],old_account['account']['observation'][key]) for key in
                ('credentialGeneration','credentialActive','endpointPresent','endpointSha256','tokenPresent','tokenValid')))
        if returned:need(lifecycle['backgrounds']>old['backgrounds'] and lifecycle['activations']>old['activations'])
        else:need(typed_equal(lifecycle,old))
        require_retired(upload['source']);work=PicoSnapshotCancelOwner.scoped_work(row['base'])
        need(not work['evaluating'] and not work['timers'] and not work['unknownTimers'] and all(work[key]==0 for key in
            ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
        provider=row['provider'];mutation_scope(provider,self.origin['provider'],[])
        need(provider['uploads']==self.origin['provider']['uploads'] and provider['stories']==self.origin['provider']['stories']==1
            and not provider['inflight'] and not provider['held'])
        return account

    def frame(self,row,*,returned,historical=False):
        account=self.stable_frame(row,returned=returned,historical=historical)
        ui,old_ui=row['base']['ui'],self.origin['base']['ui'];need(ui['open'] and ui['ready'] and ui['generation']==old_ui['generation']
            and typed_equal(ui['picoSnapshotReview'],old_ui['picoSnapshotReview']))
        return account

    def validate(self,state):
        exact(state,{'stage','source','parentSha256','frames','before','after','os','quiet','received'})
        need(state['stage'] in STAGES and state['parentSha256']==sha(self.parent_disk) and state['received'] is None
            and type(state['frames']) is list and 0<=len(state['frames'])<=65 and type(state['os']) is list and len(state['os'])<=64)
        self.phase(state['source']);need((state['before'] is None or integer(state['before'],0,len(state['frames'])-1)) and (state['after'] is None or integer(state['after'],1,len(state['frames'])-1)))
        for index,row in enumerate(state['frames']):
            self.frame(row,returned=state['after'] is not None and index>=state['after']);provider_phase(row['provider'],state['source'])
            if state['after'] is not None and index>=state['after']:
                need(typed_equal(decode(row['account']['raw'])['lifecycle'],decode(state['frames'][state['after']]['account']['raw'])['lifecycle']))
            if index:
                previous=state['frames'][index-1];need(row['hostMonotonic']>=previous['hostMonotonic'])
                old=frame_packet(previous,self.run,self.pid,self.binding['sessionId']);new=frame_packet(row,self.run,self.pid,self.binding['sessionId'])
                native_accept(old[0],new[0]);script_accept(old[1],new[1]);files_accept(old[2],new[2]);upload_continuity(old[3],new[3])
                need(new[4]['instance']==old[4]['instance'] and new[4]['sequence']>old[4]['sequence'] and new[4]['requestId']!=old[4]['requestId'])
                account_accept(old[4]['account']['observation'],new[4]['account']);provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'],previous=previous['provider'])
        if state['before'] is None:need(not state['frames'] and state['stage']=='prepare-issued')
        else:need(state['frames'])
        if STAGES.index(state['stage'])>=STAGES.index('returned'):need(state['after'] is not None)
        for row in state['os']:
            exact(row,{'status','hostMonotonic'});exact(row['status'],{'binding','foreground','running'})
            need(typed_equal(row['status']['binding'],self.binding) and type(row['status']['foreground']) is bool and row['status']['running'] is True and number(row['hostMonotonic'],0,1e15))
        if STAGES.index(state['stage'])>=STAGES.index('background-observed'):
            bg=[row for row in state['os'] if not row['status']['foreground']];need(len(bg)>=2 and bg[-1]['hostMonotonic']-bg[0]['hostMonotonic']>=.25
                and all(0<=b['hostMonotonic']-a['hostMonotonic']<=.5 for a,b in zip(bg,bg[1:])))
        need(type(state['quiet']) is list and len(state['quiet'])<=1 and (bool(state['quiet'])==(state['stage']=='partial-ready')))
        for window in state['quiet']:
            exact(window,{'indices'});indices=window['indices'];quiet_indices(indices,len(state['frames']));need(indices[0]>=state['after'])
            start=previous=None;signature=None
            for index in indices:
                row=state['frames'][index];current=clocks(row);key=self.signature(row)
                if start is None:start=current;signature=key
                else:need(key==signature and all(0<=b-a<=500 for a,b in zip(previous,current)))
                previous=current
            need(all(b-a>=3000 for a,b in zip(start,previous)))

    def load(self):
        self.bound();disk=self.store.read()
        if self.disk is not None:need(typed_equal(disk,self.disk))
        if disk is None:need(self.state is None);self.originals.verify();return
        exact(disk,{'snapshotBackgroundOwnerVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['snapshotBackgroundOwnerVersion']) is int and disk['snapshotBackgroundOwnerVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url)
        rows=unpack(disk['payload']);need(len(rows)==1);state=self.originals.decode(rows[0]);self.validate(state);self.disk,self.state=deepcopy(disk),state

    def save(self,state):
        self.bound();need(typed_equal(self.store.read(),self.disk));self.validate(state)
        disk=dict(snapshotBackgroundOwnerVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,payload=pack([self.originals.encode(state)]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state

    def live(self):
        from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner
        owner=self.runtime();need(isinstance(owner,PicoSnapshotUploadOwner) and owner.lock is self.lock and owner.run==self.run
            and typed_equal(owner.binding,self.binding) and typed_equal(owner.store.read(),self.parent_disk));return owner

    def fence(self,anchor,*,owner=None):
        started,requested=anchor;self.bound()
        if owner is not None:need(owner.native.guard() is not False)
        current=self.source.status(self.state['source']);need(current['active'] and all(typed_equal(current[key],self.state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        epoch=self.source.epoch_ms()
        native=owner.native.clock_ms() if owner is not None else None
        completed=self.bound()
        if owner is not None:
            need(self.anchor is not None);frame_started,frame_requested,captured=self.anchor
            need(number(native,1,1e15) and -250<=native-captured and max(native-captured,frame_requested-captured+(completed-frame_started)*1000)<=1500)
        need(number(epoch,requested,1e15) and 0<=completed-started<=1.5
            and -250<=epoch-current['capturedEpochMs'] and max(epoch-current['capturedEpochMs'],requested-current['capturedEpochMs']+(completed-started)*1000)<=1500)

    def observe(self,*,returned):
        owner=self.live();started=self.bound();requested=owner.native.clock_ms();row=owner.read_frame();self.frame(row,returned=returned)
        state=deepcopy(self.state);state['frames'].append(row)
        if not returned:need(state['after'] is None);state['before']=len(state['frames'])-1
        elif state['after'] is None:state['after']=len(state['frames'])-1
        self.save(state);need(owner.native.guard() is not False);epoch=owner.native.clock_ms();completed=self.bound();captured=min(clocks(row)[1:])
        need(-250<=epoch-captured and max(epoch-captured,requested-captured+(completed-started)*1000)<=1500);self.anchor=(started,requested,captured);return owner,row

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None or self.state['stage']=='prepare-issued')
            if self.state is None:
                source=self.source.status(self.parent['source']);self.phase(source)
                self.save(dict(stage='prepare-issued',source=source,parentSha256=sha(self.parent_disk),frames=[],before=None,after=None,os=[],quiet=[],received=None))
            need(self.status()['foreground']);owner,row=self.observe(returned=False);state=deepcopy(self.state);state['stage']='prepared';self.save(state)
            result=self.report();self.fence((self.bound(),self.source.epoch_ms()),owner=owner);return result

    def home(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='prepared' and self.status()['foreground']);owner,row=self.observe(returned=False);anchor=(self.bound(),self.source.epoch_ms())
            state=deepcopy(self.state);state['stage']='home-issued';self.save(state)
            self.os_input('lifecycle.background',deepcopy(self.binding),before_input=lambda:self.fence(anchor,owner=owner));return self.background()

    def background(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('home-issued','background-observed'));started=self.bound()
            for attempt in range(41):
                anchor=(self.bound(),self.source.epoch_ms());row=dict(status=self.status(),hostMonotonic=self.bound())
                if row['status']['foreground']:
                    need(not self.state['os'] and self.bound()-started<5 and attempt<40);self.fence(anchor);self.sleep(.125);continue
                state=deepcopy(self.state);state['os'].append(row)
                if len(state['os'])>=2 and state['os'][-1]['hostMonotonic']-state['os'][0]['hostMonotonic']>=.25:state['stage']='background-observed'
                self.save(state)
                if state['stage']=='background-observed':
                    result=self.report();self.fence(anchor);return result
                need(self.bound()-started<5 and attempt<40);self.sleep(.125)
            need(False)

    def resume(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='background-observed' and not self.status()['foreground']);anchor=(self.bound(),self.source.epoch_ms())
            state=deepcopy(self.state);state['stage']='resume-issued';self.save(state)
            self.os_input('app.launch',deepcopy(self.binding),before_input=lambda:self.fence(anchor));return self.reconcile()

    def reconcile(self):
        """Once Resume is issued, recovery only observes; no cold resend."""
        with self.lock.held():
            self.load();need(self.state['stage'] in ('resume-issued','returned','quiet-issued','partial-ready'));need(self.status()['foreground'])
            owner,row=self.observe(returned=True);state=deepcopy(self.state)
            if state['stage']=='resume-issued':state['stage']='returned';self.save(state)
            result=self.report();self.fence((self.bound(),self.source.epoch_ms()),owner=owner);return result

    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('returned','quiet-issued'))
            state=deepcopy(self.state);state['stage']='quiet-issued';self.save(state);start=previous=signature=None;indices=[]
            for attempt in range(65):
                need(self.status()['foreground']);owner,row=self.observe(returned=True);current=clocks(row);key=self.signature(row)
                if start is None or any(b-a>500 for a,b in zip(previous,current)):start=current;signature=key;indices=[]
                need(key==signature);previous=current;indices.append(len(self.state['frames'])-1)
                self.fence((self.bound(),self.source.epoch_ms()),owner=owner)
                if all(b-a>=3000 for a,b in zip(start,current)):
                    state=deepcopy(self.state);state['stage']='partial-ready';state['quiet']=[dict(indices=indices)];self.save(state)
                    result=self.report();self.fence((self.bound(),self.source.epoch_ms()),owner=owner);return result
                need(attempt<64);self.sleep(.25)
            need(False)

    @staticmethod
    def signature(row):
        work=PicoSnapshotCancelOwner.scoped_work(row['base'])
        account=deepcopy(decode(row['account']['raw'])['account']);account['observation'].pop('capturedEpochMs')
        return sha(dict(work=work,provider=row['provider']['requests'],account=account,
            ui=row['base']['ui']['picoSnapshotReview']))

    def report(self):
        return dict(qualification='PICO_SNAPSHOT_OS_RETURN_COMPONENT_ONLY',stage=self.state['stage'],fullSnapshotRecipe=False,
            journalRetained=True,ordinaryInputResendAllowed=False,independentAfterReturnPng=False,quietCompleted=self.state['stage']=='partial-ready')
