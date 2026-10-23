"""Normal existing Pico Upload with independent native/TLS/file originals.

Private fail/success components retain all predecessors and resources. They do
not qualify the preceding system Share or the remaining Resume/Close/cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import uuid
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate as account_packet
from adapters.native_account_observation import accept as account_accept
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
from adapters.pico4.snapshot_cancel_owner import original
from adapters.pico4.snapshot_capture_files import PicoSnapshotCaptureFiles
from adapters.pico4.snapshot_export_controls import metadata as control_metadata
from adapters.pico4.snapshot_context import original as context_value
from adapters.pico4.snapshot_upload_source import PicoSnapshotUploadSource,validate as upload_packet,continuity as upload_continuity,require_retired
from adapters.pico4.snapshot_upload_fixture import SnapshotUploadFixtureReader,validate as provider_packet,join
from adapters.pico4.snapshot_upload_bytes import PicoSnapshotUploadBytes
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals
from adapters.pico4 import snapshot_originals as native_source
from adapters.pico4.snapshot_script_originals import accept as script_accept
from adapters.pico4.snapshot_capture_source import continuity as files_accept
from adapters.pico4.navigation import identifier
from adapters.script_journey.history import canonical,pack,unpack
from feature_journeys.contract import typed_equal
from snapshot_observation import inspect_snapshot,MAX_BYTES

VERSION=1
STAGES=('prepare-issued','prepared','input-issued','observed','read-issued','acquired','quiet-issued','partial-ready')


def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


class PicoSnapshotUploadOwner:
    host_path=PicoSnapshotCaptureFiles.host_path
    artifact_root=PicoSnapshotCaptureFiles.artifact_root
    host_read=PicoSnapshotCaptureFiles.host_read
    publish=PicoSnapshotCaptureFiles.publish

    def __init__(self,path,parent,uploads,fixture,bytes_source,account,verb,*,failure=None):
        need(isinstance(parent,PicoSnapshotSaveOwner) and isinstance(uploads,PicoSnapshotUploadSource)
            and isinstance(fixture,SnapshotUploadFixtureReader) and isinstance(bytes_source,PicoSnapshotUploadBytes)
            and isinstance(account,NativeFeatureObservation) and verb in ('upload-fail','upload')
            and uploads.lock is parent.lock and uploads.pid==account.pid==parent.native.pid
            and bytes_source.fixture is fixture and fixture.run==parent.run and fixture.client is parent.source.client)
        need(failure is None if verb=='upload-fail' else isinstance(failure,PicoSnapshotUploadOwner)
            and failure.verb=='upload-fail' and failure.parent is parent and failure.lock is parent.lock)
        self.parent,self.base,self.uploads,self.fixture,self.bytes_source,self.account=parent,parent.parent,uploads,fixture,bytes_source,account
        self.verb,self.failure,self.run,self.binding,self.lock=verb,failure,parent.run,deepcopy(parent.binding),parent.lock
        self.binding_sha=sha(self.binding)
        self.native,self.source,self.transport=self.base.native,self.base.source,parent.transport
        self.store=PrivateFeatureState(path);need(self.store.path==self.lock.path.with_name('snapshot-'+verb+'-owner.json'))
        self.disk=self.state=self.anchor=None;self.current=False
        with self.lock.held():
            parent.load();need(parent.state['stage']=='partial-ready')
            self.parent_disk=deepcopy(parent.disk);self.parent_sha=sha(self.parent_disk)
            self.parent_state=deepcopy(parent.state);self.base_state=deepcopy(self.base.state);self.parent_state_sha=sha(self.parent_state);self.base_state_sha=sha(self.base_state)
            self.failure_disk=self.failure_state=None
            if failure is not None:
                failure.load();need(failure.state['stage']=='partial-ready');self.failure_disk=deepcopy(failure.disk);self.failure_state=deepcopy(failure.state)
            self.originals=SnapshotUploadOriginals(self.store.path.with_name('snapshot-'+verb+'-originals.json'),self.run,self.binding,verb)
            self.load()
        parent.bind_upload_owner(self)

    def pin(self):
        self.lock.assert_held();need(sha(self.binding)==self.binding_sha and typed_equal(self.parent.binding,self.binding)
            and sha(self.parent_state)==self.parent_state_sha and sha(self.base_state)==self.base_state_sha
            and typed_equal(self.parent.state,self.parent_state) and typed_equal(self.base.state,self.base_state)
            and typed_equal(self.parent.store.read(),self.parent_disk));self.parent.pin();self.parent.originals.verify()
        if self.failure is not None:
            need(typed_equal(self.failure.store.read(),self.failure_disk) and typed_equal(self.failure.state,self.failure_state));self.failure.originals.verify()
        captured=self.base.state['capture'];need(self.base.files.host_read(captured['artifactRecord'])==self.parent.host_read(self.parent.state['artifacts'][self.parent.state['saved']['file']['copy']]))

    def phase(self,value):
        self.base.phase(value);previous=self.parent_state['source'] if self.failure is None else self.failure_state['source']
        need(all(typed_equal(value[key],previous[key]) for key in ('instance','createdEpochMs'))
            and typed_equal(value['activations'][:len(previous['activations'])],previous['activations']))
        remaining=[row['stimulus'] for row in value['activations'][len(previous['activations']):]]
        # These are original input metadata only. No Share effect is inferred.
        verbs=['share-open','share-cancel','share-open','share-select-owned','upload-fail'] if self.failure is None else ['upload']
        need(remaining==[dict(verb=verb,inputs={}) for verb in verbs]);return value

    def frame(self,row):
        exact(row,{'base','upload','provider','account','hostMonotonic'});native,script,files=self.base.frame(row['base'])
        upload=original({key:row['upload'][key] for key in ('raw','sha256')},262144)
        exact(row['upload'],{'raw','sha256','request'});upload_packet(upload,row['upload']['request'],self.native.pid,upload['capturedEpochMs']);need(upload['runId']==self.run)
        provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'])
        account=original(row['account'],262144);account_packet(account,account['requestId'],self.native.pid,account['capturedEpochMs'],require_account=True)
        need(upload['instance']==files['instance']==account['instance'])
        need(number(row['hostMonotonic'],0,1e15) and max(self.clocks(row)[1:])-min(self.clocks(row)[1:])<=1500)
        self.stable_capture(row);self.account_original(account,row['provider']);self.capture_context(row)
        return native,script,files,upload,account

    def stable_capture(self,row):
        native,script,files=self.base.frame(row['base']);old_native,old_script,old_files=self.base.frame(self.base.state['frames'][-1])
        need(typed_equal(native['requests'],old_native['requests']) and typed_equal(script['history'],old_script['history'])
            and typed_equal(files['source']['rows'],old_files['source']['rows'])
            and native['resources']['activeRequests']==native['resources']['projectionImagesBytes']==0
            and not any(native['resources'][key] for key in ('taking360','waitingOnSnapshot','projectionTimerActive'))
            and {key:value for key,value in row['base']['inventory'].items() if key!='capturedEpochMs'}==
                {key:value for key,value in self.base.state['frames'][-1]['inventory'].items() if key!='capturedEpochMs'})
        ui=row['base']['ui'];review=ui.get('picoSnapshotReview');path=self.base.state['capture']['file']['path']
        need(ui['open'] and ui['ready'] and review is not None and review['present'] and review['review']['visible']
            and review['review']['loggedIn'] and review['review']['canShare']
            and not any(review['review'][key] for key in ('capturing','processing','exportBusy','exportTicket'))
            and any(image['path']==path for image in review['review']['images']))

    def capture_context(self,row):
        script=decode(row['base']['script']['raw']);need(script['snapshotScriptOriginalsVersion']==3)
        original_script=self.base.frame(self.base.state['frames'][self.base.state['capture']['frame']])[1]
        need(original_script['history']['snapshotScriptHistoryVersion']==2)
        events=[event for event in original_script['history']['events'] if event['kind']=='pending' and event['id']==self.base.state['capture']['requestId']]
        need(len(events)==1);pending=events[0]['context'];current=script['captureContext']
        need(current['instance']==pending['instance'] and all(current['entries'][key]==pending['entries'][key] for key in ('previousSnapshotDomainID','previousSnapshotHref'))
            and context_value(current,'previousSnapshotDomainID')=='{'+row['provider']['domainId']+'}'
            and context_value(current,'previousStillSnapPath')==self.base.state['capture']['file']['path']
            and current['normalizedHref']==pending['normalizedHref'] and bool(current['normalizedHref']))
        return current

    def account_original(self,packet,provider):
        account=packet['account'];body=account['observation']
        need(account['loggedIn'] and account['principalSha256']==hashlib.sha256(('e2e-'+self.run).encode()).hexdigest()
            and body['credentialActive'] and body['endpointPresent'] and body['endpointSha256']==hashlib.sha256(provider['origin'].encode()).hexdigest()
            and body['tokenPresent'] and body['tokenValid'] and not body['transportRejected'] and not body['loginPending'] and not body['refreshPending'])

    def clocks(self,row):
        upload=decode(row['upload']['raw']);account=decode(row['account']['raw'])
        return (row['hostMonotonic']*1000,)+self.base.clocks(row['base'])[1:]+(upload['capturedEpochMs'],upload['source']['capturedEpochMs'],
            account['capturedEpochMs'],account['account']['observation']['capturedEpochMs'],row['provider']['capturedEpochMs'])

    def validate(self,state):
        exact(state,{'stage','source','parentSha256','failureSha256','frames','deliveries','job','proof','readId','received','artifacts','artifactRoot','scope','quiet'})
        need(state['stage'] in STAGES and state['parentSha256']==self.parent_sha and state['failureSha256']==(None if self.failure_disk is None else sha(self.failure_disk))
            and state['scope']==self.run and type(state['frames']) is list and len(state['frames'])<=127 and (state['frames'] or state['stage']=='prepare-issued')
            and type(state['deliveries']) is list and len(state['deliveries'])<=1 and type(state['artifacts']) is dict and len(state['artifacts'])<=1
            and type(state['quiet']) is list and len(state['quiet'])<=1 and (state['job']=='' or native_source.nonce(state['job']))
            and (state['readId']=='' or native_source.nonce(state['readId'])))
        self.phase(state['source']);exact(state['artifactRoot'],{'device','inode'});need(integer(state['artifactRoot']['device']) and integer(state['artifactRoot']['inode'],1) and state['artifactRoot']==self.artifact_root());previous_upload=previous_provider=previous_account=None;previous_native=previous_script=previous_files=None;clock=0
        for row in state['frames']:
            native,script,files,upload,account=self.frame(row)
            if previous_upload is None and self.failure_state is not None:
                old=self.failure_state['frames'][-1];upload_continuity(decode(old['upload']['raw']),upload)
                provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'],previous=old['provider'])
                previous_account=decode(old['account']['raw'])['account']['observation']
            if previous_upload is not None:
                upload_continuity(previous_upload,upload);provider_packet(row['provider'],self.run,row['provider']['requestId'],row['provider']['capturedEpochMs'],previous=previous_provider)
                native_source.accept(previous_native,native);script_accept(previous_script,script);files_accept(previous_files,files)
            previous_upload,previous_provider,previous_native,previous_script,previous_files=upload,row['provider'],native,script,files
            previous_account=account_accept(previous_account,account['account']);need(row['hostMonotonic']>=clock);clock=row['hostMonotonic']
        for delivery in state['deliveries']:
            exact(delivery,{'command','frame'});need(integer(delivery['frame'],0,len(state['frames'])-1));self.qml(delivery['command'],state['frames'][delivery['frame']]);self.before_input(state['frames'][delivery['frame']],state)
        if state['stage'] in ('prepare-issued','prepared'):need(not state['deliveries'] and not state['job'] and state['proof'] is None)
        if state['stage'] in ('observed','read-issued','acquired','quiet-issued','partial-ready'):
            need(len(state['deliveries'])==1 and state['proof'] is not None and native_source.nonce(state['job']));self.proof(state)
        if self.verb=='upload-fail':need(not state['readId'] and state['received'] is None and not state['artifacts'])
        elif state['stage'] in ('read-issued','acquired','quiet-issued','partial-ready'):need(native_source.nonce(state['readId']))
        if state['stage'] in ('prepare-issued','prepared','input-issued','observed'):need(not state['readId'] and state['received'] is None and not state['artifacts'])
        for id,record in state['artifacts'].items():
            need(id==state['readId']);exact(record,{'name','bytes','sha256','phase','file','removeIntent'})
            capture=self.base.state['capture']['file'];need(record['name']=='snapshot-owned-'+self.run+'-'+id+'.bin'
                and all(record[key]==capture[key] for key in ('bytes','sha256')) and record['phase'] in ('planned','opened','saved') and record['removeIntent'] is False)
            if record['phase']=='planned':need(record['file'] is None)
            else:exact(record['file'],{'device','inode'});need(integer(record['file']['device']) and integer(record['file']['inode'],1))
        if state['received'] is not None:self.received_proof(state)
        if self.verb=='upload' and state['stage'] in ('acquired','quiet-issued','partial-ready'):need(state['received'] is not None)
        if state['stage']!='partial-ready':need(not state['quiet'])
        for window in state['quiet']:
            exact(window,{'indices'});indices=window['indices'];need(type(indices) is list and len(indices)>=2 and indices==sorted(set(indices)) and all(integer(index,0,len(state['frames'])-1) for index in indices))
            first=previous=None;fingerprint=None
            for index in indices:
                row=state['frames'][index];self.idle(row,state);current=self.clocks(row)
                if first is None:first=current;fingerprint=self.signature(row)
                else:need(all(0<=b-a<=500 for a,b in zip(previous,current)) and self.signature(row)==fingerprint)
                previous=current
            need(all(b-a>=3000 for a,b in zip(first,previous)))
        if state['stage']=='partial-ready':need(state['quiet'])

    def load(self):
        self.pin();disk=self.store.read()
        if self.disk is not None:need(typed_equal(disk,self.disk))
        if disk is None:need(self.state is None and self.originals.disk is None);self.originals.verify();return
        exact(disk,{'snapshotUploadOwnerVersion','runId','binding','fixtureUrl','verb','payload'})
        need(type(disk['snapshotUploadOwnerVersion']) is int and disk['snapshotUploadOwnerVersion']==VERSION and disk['runId']==self.run
            and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url and disk['verb']==self.verb)
        rows=unpack(disk['payload']);need(len(rows)==1);state=self.originals.decode(rows[0]);self.validate(state)
        if state['frames'] and self.uploads.last is None:
            row=state['frames'][-1]['upload'];self.uploads.restore(decode(row['raw']),row['request'],row['raw'])
        self.disk,self.state=deepcopy(disk),state

    def save(self,state=None):
        self.lock.assert_held();state=self.state if state is None else state;need(typed_equal(self.store.read(),self.disk));self.validate(state)
        disk=dict(snapshotUploadOwnerVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,verb=self.verb,payload=pack([self.originals.encode(state)]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state

    def read_frame(self):
        started=self.base.now();requested=self.native.clock_ms();base=self.base.read_frame()
        self.uploads.read(self.run);account=self.account.read(self.account.sequence,require_account=True)
        raw=self.account.original();need(typed_equal(decode(raw),account));provider=self.fixture.provider()
        row=dict(base=base,upload=self.uploads.original(),provider=provider,account=dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest()),hostMonotonic=self.base.now())
        self.frame(row);self.anchor=(started,requested,min(self.clocks(row)[1:]));return row

    def append(self):
        row=self.read_frame();state=deepcopy(self.state);state['frames'].append(row);self.save(state);return row

    def fence(self):
        need(self.anchor is not None);started,requested,captured=self.anchor;self.pin();need(self.native.guard() is not False)
        phase_started=self.base.now();phase_epoch=self.source.epoch_ms();current=self.source.status(self.state['source'])
        need(current['active'] and all(typed_equal(current[key],self.state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        native=self.native.clock_ms();fixture=self.source.epoch_ms();completed=self.base.now()
        need(number(native,1,1e15) and number(fixture,phase_epoch,1e15) and -250<=native-captured and -250<=fixture-current['capturedEpochMs']
            and max(native-captured,requested-captured+(completed-started)*1000,fixture-current['capturedEpochMs'],phase_epoch-current['capturedEpochMs']+(completed-phase_started)*1000)<=1500)

    def qml(self,command,row):
        exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'})
        ui=row['base']['ui'];path=self.base.state['capture']['file']['path'];control='snapshot.upload.'+hashlib.sha256(path.encode()).hexdigest()
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and identifier(command['commandId']) and command['bridgeId']==self.binding['sessionId']==ui['bridgeId']
            and command['generation']==ui['generation'] and command['controlId']==control and command['action']=='activate'
            and integer(command['sequence'],1) and command['sequence']==ui['lastCommandSequence']+1 and integer(command['observedElapsedMs'])
            and 0<=ui['elapsedMs']-command['observedElapsedMs']<=1500 and ui.get('snapshotExportControlsVersion')==1)
        selected=self.base.snapshot.ui.control(ui,control);need(selected is not None);control_metadata(selected)
        need(selected['inputReady'] and selected['path']==path and selected['token']==command['controlToken'])

    def before_input(self,row,state):
        baseline=state['frames'][0];old=decode(baseline['upload']['raw'])['source'];current=decode(row['upload']['raw'])['source']
        need(typed_equal(old['events'],current['events']) and typed_equal(old['jobs'],current['jobs']))
        first,provider=baseline['provider'],row['provider'];need(typed_equal(first['requests'],provider['requests'])
            and provider['inflight']==0 and not provider['held'] and provider['stories']==0 and provider['uploads']==first['uploads'])
        self.base.still_idle(row['base'],self.base.state);require_retired(current)

    def before_qml(self,command):
        self.lock.assert_held();need(self.current and self.state['stage']=='input-issued' and not self.state['deliveries'])
        row=self.append();self.qml(command,row);self.before_input(row,self.state)
        state=deepcopy(self.state);state['deliveries']=[dict(command=deepcopy(command),frame=len(state['frames'])-1)];self.save(state);self.fence()

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None or self.state['stage']=='prepare-issued')
            if self.state is None:
                source=self.phase(self.source.status(self.parent.state['source'] if self.failure is None else self.failure.state['source']))
                state=dict(stage='prepare-issued',source=source,parentSha256=self.parent_sha,failureSha256=None if self.failure_disk is None else sha(self.failure_disk),
                    frames=[],deliveries=[],job='',proof=None,readId='',received=None,artifacts={},artifactRoot=self.artifact_root(),scope=self.run,quiet=[]);self.save(state)
            row=self.append();self.before_input(row,self.state);state=deepcopy(self.state);state['stage']='prepared';self.save(state);result=self.report();self.fence();return result

    def send(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='prepared');row=self.append();self.before_input(row,self.state);self.fence()
            state=deepcopy(self.state);state['stage']='input-issued';self.save(state)
            control='snapshot.upload.'+hashlib.sha256(self.base.state['capture']['file']['path'].encode()).hexdigest()
            selected=self.base.snapshot.ui.control(row['base']['ui'],control);need(selected is not None);self.current=True
            try:self.base.snapshot.ui.input(control,token=selected['token'])
            finally:self.current=False
            return self.reconcile()

    def proof(self,state):
        proof=state['proof'];exact(proof,{'frame'});need(integer(proof['frame'],0,len(state['frames'])-1));row=state['frames'][proof['frame']]
        native=decode(row['upload']['raw'])['source'];baseline=decode(state['frames'][0]['upload']['raw'])['source'];old_ids={job['id'] for job in baseline['jobs']}
        need(state['job'] not in old_ids and {job['id'] for job in native['jobs']}-old_ids=={state['job']})
        deliveries=state['deliveries'];need(len(deliveries)==1);before=state['frames'][deliveries[0]['frame']]
        born=[event for event in native['events'] if event['jobId']==state['job'] and event['kind']=='begin'];need(len(born)==1
            and born[0]['capturedEpochMs']>=max(state['source']['activations'][-1]['activatedEpochMs'],decode(before['upload']['raw'])['capturedEpochMs']))
        capture=self.base.state['capture']['file'];job=next(item for item in native['jobs'] if item['id']==state['job'])
        original_files=self.base.frame(self.base.state['frames'][self.base.state['capture']['frame']])[2]['source']['rows']
        original_file=next(item for item in original_files if item['id']==capture['fileId'])
        need(job['href']==self.capture_context(row)['normalizedHref'])
        need(job['file'] and int(job['file']['device'])==capture['device']==original_file['device']
            and int(job['file']['inode'])==capture['inode']==original_file['inode']
            and all(job['file'][key]==original_file[key] for key in ('uid','links')))
        proof=join(native,row['provider'],state['job'],ticket=state['source']['activations'][-1]['ticket'],
            image_bytes=capture['bytes'],image_sha256=capture['sha256'],path=capture['path'],success=self.verb=='upload')
        if self.verb=='upload-fail':need(proof['offline'] is True)
        return proof

    def reconcile(self):
        """Query originals only; an uncertain ordinary Upload is never resent."""
        with self.lock.held():
            self.load();need(self.state['stage'] in ('input-issued','observed','read-issued','acquired','quiet-issued','partial-ready'));row=self.append()
            if self.state['stage']=='input-issued':
                old={job['id'] for job in decode(self.state['frames'][0]['upload']['raw'])['source']['jobs']}
                jobs=[job for job in decode(row['upload']['raw'])['source']['jobs'] if job['id'] not in old]
                need(len(jobs)<=1)
                if jobs and jobs[0]['terminal']:
                    state=deepcopy(self.state);state['job']=jobs[0]['id'];state['proof']=dict(frame=len(state['frames'])-1);state['stage']='observed';self.save(state)
            result=self.report();self.fence();return result

    def start_read(self):
        with self.lock.held():
            self.load();need(self.verb=='upload' and self.state['stage']=='observed');row=self.append();self.fence()
            state=deepcopy(self.state);state['readId']=uuid.uuid4().hex
            original_ids={item['id'] for item in self.base.frame(self.base.state['frames'][-1])[2]['source']['rows']}
            need(state['readId'] not in original_ids and state['readId'] not in self.parent.state['artifacts']);state['stage']='read-issued';self.save(state);self.fence()
            return self.acquire()

    def acquire(self):
        """Read-only backend acquisition may recover without any Upload input."""
        with self.lock.held():
            self.load();need(self.verb=='upload' and self.state['stage']=='read-issued');self.append();self.fence();proof=self.proof(self.state)
            request=proof['requests'][0]['requestId'];ticket=self.state['source']['activations'][-1]['ticket'];metadata,content=self.bytes_source.acquire(request,ticket)
            need(content==self.base.files.host_read(self.base.state['capture']['artifactRecord']));self.publish(self.state['readId'],content)
            self.append();state=deepcopy(self.state);state['received']=dict(metadata=metadata,frame=len(state['frames'])-1);state['stage']='acquired';self.save(state)
            result=self.report();self.fence();return result

    def received_proof(self,state):
        exact(state['received'],{'metadata','frame'});need(integer(state['received']['frame'],0,len(state['frames'])-1))
        value=state['received']['metadata'];exact(value,{'source','request','readId','bytes','sha256','capturedEpochMs','originalCompletedEpochMs','metadata','decoded'})
        meta=value['metadata'];exact(meta,{'snapshotUploadOriginalVersion','instance','runId','requestId','readId','ticket','capturedEpochMs','originalCompletedEpochMs','domainId','origin','body','image'})
        proof=self.proof(state);request=proof['requests'][0];capture=self.base.state['capture']['file'];provider=state['frames'][state['received']['frame']]['provider']
        need(type(meta['snapshotUploadOriginalVersion']) is int and meta['snapshotUploadOriginalVersion']==2
            and integer(value['capturedEpochMs'],1,provider['capturedEpochMs']) and value['capturedEpochMs']==meta['capturedEpochMs']
            and value['originalCompletedEpochMs']==meta['originalCompletedEpochMs']==request['completedEpochMs']
            and meta['domainId']==provider['domainId'] and meta['origin']==provider['origin'] and meta['requestId']==value['request'])
        need(value['source']=='snapshot-upload-original' and value['request']==request['requestId'] and native_source.nonce(value['readId'])
            and meta['readId']==value['readId'] and meta['runId']==self.run and meta['instance']==state['frames'][state['received']['frame']]['provider']['instance']
            and meta['ticket']==state['source']['activations'][-1]['ticket'] and typed_equal(meta['body'],request['body'])
            and meta['image']==request['image'] and all(value[key]==capture[key] for key in ('bytes','sha256')))
        artifact=state['artifacts'].get(state['readId']);need(artifact is not None and artifact['phase']=='saved')
        raw=self.host_read(artifact);need(raw==self.base.files.host_read(self.base.state['capture']['artifactRecord']) and value['decoded']==inspect_snapshot(raw,mode='still',file_format='png'))

    def idle(self,row,state):
        self.base.still_idle(row['base'],self.base.state);require_retired(decode(row['upload']['raw'])['source'])
        provider=row['provider'];need(provider['inflight']==0 and not provider['held'] and provider['stories']==(1 if self.verb=='upload' else 0))
        review=row['base']['ui']['picoSnapshotReview']['review'];need(not review['uploadPath'] and review['statusError']==(self.verb=='upload-fail'))
        if self.verb=='upload':need(any(image['path']==self.base.state['capture']['file']['path'] and image['storyPresent'] for image in review['images']))

    def signature(self,row):
        return sha(dict(upload=decode(row['upload']['raw'])['source']['events'],provider=row['provider']['requests'],
            work=self.base.scoped_work(row['base']),account=decode(row['account']['raw'])['account']['observation']['events']))

    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in (('observed','quiet-issued') if self.verb=='upload-fail' else ('acquired','quiet-issued')))
            state=deepcopy(self.state);state['stage']='quiet-issued';self.save(state);first=previous=fingerprint=None;indices=[]
            for _ in range(65):
                row=self.append();self.idle(row,self.state);clocks=self.clocks(row);current=self.signature(row)
                if first is None or any(b-a>500 for a,b in zip(previous,clocks)):first=clocks;indices=[];fingerprint=current
                need(current==fingerprint);previous=clocks;indices.append(len(self.state['frames'])-1);self.fence()
                if all(b-a>=3000 for a,b in zip(first,clocks)):
                    state=deepcopy(self.state);state['quiet']=[dict(indices=indices)];state['stage']='partial-ready';self.save(state);result=self.report();self.fence();return result
                self.native.sleep(.25)
            need(False)

    def report(self):
        return dict(qualification='PICO_NORMAL_UPLOAD_COMPONENT_ONLY',stage=self.state['stage'],verb=self.verb,
            fullSnapshotRecipe=False,deviceAcceptance=False,journalRetained=True,ordinaryUploadResendAllowed=False,
            precedingShareQualified=False,backendStoryRetained=self.verb=='upload' and self.state['proof'] is not None,
            productExportExecutorRetired=False)
