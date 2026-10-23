"""Normal existing Pico Save -> original provider -> independent PNG component.

The unchanged v16 MediaStore branch follows the owned normal Cancel/Still
prefix. Journals, product executor, original capture and UI remain obligations
for Share/Upload/Resume/final cleanup. No Snapshot capability is advertised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner,original
from adapters.pico4.snapshot_capture_files import PicoSnapshotCaptureFiles
from adapters.pico4.snapshot_exports import PicoSnapshotExports,components,validate as export_packet,continuity as export_continuity
from adapters.pico4.snapshot_export_readbacks import command as export_command
from adapters.pico4.snapshot_export_controls import metadata as export_control
from adapters.pico4.snapshot_saved_files import PicoSnapshotSavedFiles,original_stat
from adapters.pico4.snapshot_save_originals import SnapshotSaveOriginals
from adapters.pico4.snapshot_platform import profile as platform_profile
from adapters.pico4 import snapshot_originals as native_source
from adapters.pico4.snapshot_script_originals import accept as script_accept
from adapters.pico4.snapshot_capture_source import continuity as file_continuity
from adapters.pico4.navigation import identifier
from adapters.script_journey.history import pack,unpack,canonical
from feature_journeys.contract import typed_equal
from snapshot_observation import inspect_snapshot,MAX_BYTES

VERSION=1
STAGES=('prepare-issued','prepared','input-issued','exported','read-issued','acquired','quiet-issued','partial-ready')


def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


class PicoSnapshotSaveOwner:
    # Reuse the exact existing exclusive planned/opened/saved host publication,
    # inode-bound recovery and full stat reader; no second file writer.
    host_path=PicoSnapshotCaptureFiles.host_path
    artifact_root=PicoSnapshotCaptureFiles.artifact_root
    host_read=PicoSnapshotCaptureFiles.host_read
    publish=PicoSnapshotCaptureFiles.publish

    def __init__(self,path,parent,exports,saved):
        need(isinstance(parent,PicoSnapshotCancelOwner) and isinstance(exports,PicoSnapshotExports)
            and isinstance(saved,PicoSnapshotSavedFiles) and exports.lock is parent.lock
            and exports.pid==parent.native.pid and not exports.read_only and saved.readbacks is exports and saved.run==parent.run)
        self.parent,self.exports,self.transport=parent,exports,saved
        self.lock,self.run,self.binding,self.source=parent.lock,parent.run,parent.binding,parent.source
        self.native=parent.native;self.store=PrivateFeatureState(path)
        need(self.store.path==self.lock.path.with_name('snapshot-save-owner.json') and saved.artifacts==parent.files.transport.artifacts
            and saved.context=={key:self.binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')})
        self.disk=self.state=self.anchor=None;self.current=False;self.decoded={};self.upload_owner=None
        with self.lock.held():
            parent.load();need(parent.encoding_version==2 and parent.state['stage']=='still-ready')
            self.parent_disk=deepcopy(parent.disk);self.parent_digest=sha(self.parent_disk)
            self.originals=SnapshotSaveOriginals(self.store.path.with_name('snapshot-save-originals.json'),self.run,self.binding)
            self.load()
        parent.bind_save_owner(self)

    def pin(self):
        self.lock.assert_held();need(typed_equal(self.parent.store.read(),self.parent_disk))
        self.parent.originals.verify();self.parent.capture_proof(self.parent.state)

    def phase(self,value):
        self.parent.phase(value);before=self.parent.state['source']
        need(all(value[key]==before[key] for key in ('instance','createdEpochMs'))
            and value['activations'][:-1]==before['activations']
            and value['activations'][-1]['stimulus']==dict(verb='save',inputs={}))
        return value

    frame=PicoSnapshotCancelOwner.frame

    def frame_context(self):
        return dict(PicoSnapshotCancelOwner.frame_context(self),
            parent=self.parent.frame_context(),
            platform=self.parent.state['platform']['original']['source'])

    def original_frame(self,row):
        exact(row,{'base','exports','platform','copy','hostMonotonic'})
        native,script,files=self.parent.frame(row['base'])
        exact(row['exports'],{'raw','sha256','request'});packet=original({key:row['exports'][key] for key in ('raw','sha256')},262144)
        export_packet(packet,row['exports']['request'],self.native.pid,packet['capturedEpochMs']);need(packet['runId']==self.run)
        platform=row['platform'];exact(platform,{'requestedEpochMs','capturedEpochMs','source'});exact(platform['source'],{'snapshotAndroidPlatformVersion','sdk','saveBackend','savePermission'})
        need(integer(platform['requestedEpochMs'],1) and integer(platform['capturedEpochMs'],platform['requestedEpochMs'])
            and platform['capturedEpochMs']-platform['requestedEpochMs']<=1500
            and platform['source']==platform_profile(str(platform['source']['sdk']))
            and platform['source']==self.parent.state['platform']['original']['source']
            and platform['source']['saveBackend']=='media-store' and number(row['hostMonotonic'],0,1e15))
        if row['copy'] is not None:
            exact(row['copy'],{'id','metadata'});metadata=row['copy']['metadata'];exact(metadata,{'device','inode','bytes','sha256','originalStat'})
            need(native_source.nonce(row['copy']['id']) and original_stat(metadata['originalStat'],metadata['bytes'],metadata['device'],metadata['inode']))
            copied=[item for item in components(packet)[1]['source'].get('files',[]) if item['id']==row['copy']['id']]
            need(len(copied)==1 and all(copied[0][key]==metadata[key] for key in ('bytes','sha256')))
        clocks=self.clocks(row)[1:];need(max(clocks)-min(clocks)<=1500)
        return native,script,files,packet

    def clocks(self,row):
        value=decode(row['exports']['raw']);events,copies=components(value)
        return (row['hostMonotonic']*1000,)+self.parent.clocks(row['base'])[1:]+(value['capturedEpochMs'],events['capturedEpochMs'],
            copies['source'].get('capturedEpochMs',value['capturedEpochMs']),row['platform']['capturedEpochMs'])

    def stable_capture(self,row):
        native,script,_files,_exports=self.frame(row);baseline=self.parent.state['frames'][-1]
        original_native,original_script,_packet=self.parent.frame(baseline)
        need(typed_equal(native['requests'],original_native['requests']) and typed_equal(script['history'],original_script['history'])
            and script['activeUploads']==0 and row['base']['inventory']==dict(self.parent.state['frames'][-1]['inventory'],
                capturedEpochMs=row['base']['inventory']['capturedEpochMs']))
        need(native['resources']['activeRequests']==native['resources']['projectionImagesBytes']==0
            and not any(native['resources'][key] for key in ('taking360','waitingOnSnapshot','projectionTimerActive')))
        review=row['base']['ui'].get('picoSnapshotReview');capture=self.parent.state['capture']['file']
        need(type(review) is dict and review['present'] and review['review']['visible'] and row['base']['ui']['open'] and row['base']['ui']['ready']
            and any(image['path']==capture['path'] for image in review['review']['images']))

    def validate(self,state):
        exact(state,{'stage','source','parentSha256','frames','deliveries','requests','export','readId','saved','artifacts','artifactRoot','scope','quiet','inspection','completedInspections'})
        need(state['stage'] in STAGES and state['parentSha256']==self.parent_digest and state['scope']==self.run
            and type(state['frames']) is list and len(state['frames'])<=128 and (state['frames'] or state['stage']=='prepare-issued')
            and type(state['deliveries']) is list and len(state['deliveries'])<=128 and type(state['requests']) is list and len(state['requests'])<=66
            and type(state['artifacts']) is dict and len(state['artifacts'])<=1 and type(state['quiet']) is list and len(state['quiet'])<=1)
        self.phase(state['source']);exact(state['artifactRoot'],{'device','inode'});need(integer(state['artifactRoot']['device']) and integer(state['artifactRoot']['inode'],1) and state['artifactRoot']==self.artifact_root())
        previous_native,previous_script,previous_files=self.parent.frame(self.parent.state['frames'][-1]);previous_exports=None;clock=0
        # The immutable parent's native file ledger is the original identity
        # authority. A fresh file-owner object's optional warm cache is None;
        # that is never an empty ownership inventory or a collision exemption.
        parent_file_ids={row['id'] for row in previous_files['source']['rows']}
        need(self.parent.state['capture']['file']['fileId'] in parent_file_ids)
        for row in state['frames']:
            native,script,files,value=self.frame(row);self.stable_capture(row)
            previous_native=native_source.accept(previous_native,native);previous_script=script_accept(previous_script,script)
            file_continuity(previous_files,files);previous_files=files
            if previous_exports is not None:export_continuity(previous_exports,value)
            previous_exports=value;need(row['hostMonotonic']>=clock);clock=row['hostMonotonic']
            first_lease=decode(state['frames'][0]['exports']['raw'])['lease']
            need(first_lease['present'] and value['lease']['present'] and value['lease']['native']['handle']==first_lease['native']['handle'])
        qml=0;nonces=set()
        for row in state['deliveries']:
            exact(row,{'kind','command','frame'});need(integer(row['frame'],0,len(state['frames'])-1))
            if row['kind']=='qml':self.qml(row['command'],state['frames'][row['frame']]);self.before_export(state['frames'][row['frame']],state);qml+=1
            else:
                need(row['kind']=='readback');export_command(row['command'])
                need(row['command']['runId']==self.run and any(typed_equal(row['command'],request) for request in state['requests']))
            need(row['command']['commandId'] not in nonces);nonces.add(row['command']['commandId'])
        need(qml<=1 and len({request['commandId'] for request in state['requests']})==len(state['requests'])
            and len({request['resourceId'] for request in state['requests']})==len(state['requests']))
        reads=0
        for request in state['requests']:
            export_command(request);need(request['runId']==self.run and state['export'] is not None)
            if request['operation']=='read':
                reads+=1;need(request['resourceId']==state['readId'] and request['exportRequest']==state['export']['identity']['request'])
            else:need(request['operation']=='inspect-destinations' and not request['exportRequest'])
        need(type(state['completedInspections']) is dict and len(state['completedInspections'])<=65)
        need(reads<=1 and (state['inspection']=='' or native_source.nonce(state['inspection'])
            and any(request['operation']=='inspect-destinations' and request['resourceId']==state['inspection'] for request in state['requests'])))
        for id,index in state['completedInspections'].items():
            need(native_source.nonce(id) and integer(index,0,len(state['frames'])-1)
                and self.inspection_done(state['frames'][index],id,state))
        for request in state['requests']:
            if request['operation']=='inspect-destinations':need(request['resourceId'] in state['completedInspections']
                or request is state['requests'][-1] and state['inspection']==request['resourceId'])
        if state['stage']=='partial-ready':need(not state['inspection'])
        if state['stage'] in ('prepare-issued','prepared'):
            need(not state['deliveries'] and not state['requests'] and state['export'] is state['saved'] is None and not state['readId'] and not state['artifacts'])
        if state['stage']=='input-issued':need(state['export'] is state['saved'] is None and not state['readId'] and not state['requests'] and not state['artifacts'])
        if state['stage']=='exported':need(qml==1 and state['saved'] is None and not state['readId'] and not state['requests'] and not state['artifacts'])
        if state['stage'] in ('read-issued','acquired','quiet-issued','partial-ready'):need(qml==1 and reads==1 and native_source.nonce(state['readId']))
        if state['stage']=='read-issued':need(state['saved'] is None)
        if state['stage']!='partial-ready':need(not state['quiet'])
        if state['export'] is not None:self.export_proof(state)
        if state['stage'] in ('exported','read-issued','acquired','quiet-issued','partial-ready'):need(state['export'] is not None)
        need(state['readId']=='' or native_source.nonce(state['readId']))
        for id,row in state['artifacts'].items():
            need(id not in parent_file_ids and native_source.nonce(id) and (state['saved'] is None or id==state['saved']['file']['copy']))
            exact(row,{'name','bytes','sha256','phase','file','removeIntent'})
            need(row['name']=='snapshot-owned-'+self.run+'-'+id+'.bin' and integer(row['bytes'],1,MAX_BYTES)
                and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) and row['phase'] in ('planned','opened','saved') and row['removeIntent'] is False)
            if row['phase']=='planned':need(row['file'] is None)
            else:
                exact(row['file'],{'device','inode'});need(integer(row['file']['device']) and integer(row['file']['inode'],1))
        if state['saved'] is not None:self.saved_proof(state)
        if state['stage'] in ('acquired','quiet-issued','partial-ready'):need(state['saved'] is not None)
        for window in state['quiet']:
            exact(window,{'indices'});indices=window['indices'];need(type(indices) is list and 2<=len(indices)<=65
                and all(integer(index,0,len(state['frames'])-1) for index in indices) and indices==sorted(set(indices)))
            rows=[state['frames'][index] for index in indices];first=self.quiet_clocks(rows[0],state);previous=first;signature=None
            for row in rows:
                current=self.quiet_clocks(row,state);self.idle(row,state)
                need(all(0<=b-a<=500 for a,b in zip(previous,current)));previous=current
                observed=self.quiet_signature(row)
                if signature is None:signature=observed
                else:need(signature==observed)
            need(all(b-a>=3000 for a,b in zip(first,previous)))
        if state['stage']=='partial-ready':need(state['quiet'])

    def load(self):
        self.lock.assert_held();self.pin();disk=self.store.read()
        if self.disk is not None:need(typed_equal(disk,self.disk))
        if disk is None:need(self.state is None and self.originals.disk is None);self.originals.verify();return
        exact(disk,{'snapshotSaveOwnerVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['snapshotSaveOwnerVersion']) is int and disk['snapshotSaveOwnerVersion']==VERSION
            and disk['runId']==self.run and typed_equal(disk['binding'],self.binding) and disk['fixtureUrl']==self.source.fixture_url)
        rows=unpack(disk['payload']);need(len(rows)==1);state=self.originals.decode(rows[0]);self.validate(state)
        if state['frames']:
            value=decode(state['frames'][-1]['exports']['raw'])
            if self.exports.last is None:self.exports.restore(value,state['frames'][-1]['exports']['request'])
        self.disk,self.state=deepcopy(disk),deepcopy(state)

    def save(self,state=None):
        self.lock.assert_held();state=self.state if state is None else state;need(typed_equal(self.store.read(),self.disk));self.validate(state)
        encoded=self.originals.encode(state);disk=dict(snapshotSaveOwnerVersion=VERSION,runId=self.run,binding=self.binding,
            fixtureUrl=self.source.fixture_url,payload=pack([encoded]))
        self.store.write(disk,self.disk);need(typed_equal(self.store.read(),disk));self.disk,self.state=deepcopy(disk),state

    def read_frame(self):
        started=self.parent.now();requested=self.native.clock_ms();base=self.parent.read_frame()
        copy=None
        if self.state is not None and self.state['saved'] is not None:
            # current() already performs the same fresh original export query
            # and guards. Archive that query; do not issue a discarded duplicate.
            id=self.state['saved']['file']['copy'];_packet,_original,_job,parts=self.transport.current(id,historical=True)
            copy=dict(id=id,metadata=self.transport.metadata(parts))
        else:self.exports.request(self.run)
        platform=self.parent.platform.read()
        row=dict(base=base,exports=self.exports.original(),platform=deepcopy(platform),copy=copy,hostMonotonic=self.parent.now());self.frame(row)
        self.anchor=(started,requested,min(self.clocks(row)[1:]));return row

    def append(self):
        row=self.read_frame();state=deepcopy(self.state);state['frames'].append(row);self.save(state);return row

    def fence(self):
        need(self.anchor is not None);started,requested,captured=self.anchor;self.pin();need(self.native.guard() is not False)
        native_epoch=self.native.clock_ms();phase_started=self.parent.now();phase_epoch=self.source.epoch_ms();phase=self.source.status(self.state['source'])
        need(phase['active'] and all(typed_equal(phase[key],self.state['source'][key]) for key in ('instance','createdEpochMs','activations')))
        final_native=self.native.clock_ms();final_phase=self.source.epoch_ms();completed=self.parent.now()
        need(number(final_native,native_epoch,1e15) and number(final_phase,phase_epoch,1e15)
            and -250<=final_native-captured and -250<=final_phase-phase['capturedEpochMs']
            and max(final_native-captured,requested-captured+(completed-started)*1000,
                final_phase-phase['capturedEpochMs'],phase_epoch-phase['capturedEpochMs']+(completed-phase_started)*1000)<=1500)

    def qml(self,command,row):
        exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'})
        ui=row['base']['ui'];path=self.parent.state['capture']['file']['path'];control='snapshot.save.'+hashlib.sha256(path.encode()).hexdigest()
        need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and identifier(command['commandId'])
            and command['bridgeId']==self.binding['sessionId']==ui['bridgeId'] and command['generation']==ui['generation']
            and command['action']=='activate' and command['controlId']==control and integer(command['sequence'],1)
            and command['sequence']==ui['lastCommandSequence']+1 and integer(command['observedElapsedMs'])
            and 0<=ui['elapsedMs']-command['observedElapsedMs']<=1500 and ui.get('snapshotExportControlsVersion')==1)
        selected=self.parent.snapshot.ui.control(ui,control);need(selected is not None);export_control(selected)
        need(selected['inputReady'] and selected['path']==path and selected['token']==command['controlToken'])

    def bind_upload_owner(self,owner):
        from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner
        need(isinstance(owner,PicoSnapshotUploadOwner) and owner.parent is self and owner.lock is self.lock
            and (self.upload_owner is None or self.upload_owner is owner
                or self.upload_owner.verb=='upload-fail' and self.upload_owner.state['stage']=='partial-ready' and owner.failure is self.upload_owner))
        self.upload_owner=owner

    def before_qml(self,command):
        self.lock.assert_held()
        if self.state['stage']=='partial-ready' and self.upload_owner is not None:
            self.upload_owner.before_qml(command);return
        need(self.current and self.state['stage']=='input-issued' and not any(row['kind']=='qml' for row in self.state['deliveries']))
        row=self.append();self.qml(command,row);self.before_export(row,self.state);self.parent.still_idle(row['base'],self.parent.state)
        state=deepcopy(self.state);state['deliveries'].append(dict(kind='qml',command=deepcopy(command),frame=len(state['frames'])-1));self.save(state);self.fence()

    def before_source_send(self,command):
        export_command(command)
        if command['operation']=='observe':return
        self.lock.assert_held();need(self.current and typed_equal(command,self.state['requests'][-1])
            and (self.state['stage']=='read-issued' and command['operation']=='read'
                or self.state['stage']=='quiet-issued' and command['operation']=='inspect-destinations')
            and not any(row['command']['commandId']==command['commandId'] for row in self.state['deliveries']))
        # The pre-read original frame is already durable. Never query this
        # same source recursively from its final publisher callback.
        state=deepcopy(self.state);state['deliveries'].append(dict(kind='readback',command=deepcopy(command),frame=len(state['frames'])-1));self.save(state);self.fence()

    def prepare(self):
        """Read-only recovery may finish an original interrupted preparation."""
        with self.lock.held():
            self.load();need(self.state is None or self.state['stage']=='prepare-issued')
            if self.state is None:
                phase=self.phase(self.source.status(self.parent.state['source']))
                # The actual SDK chooses v16's existing backend branch.
                # Documents ownership fails before any new ordinary input.
                need(self.parent.platform.read()['source']['saveBackend']=='media-store')
                state=dict(stage='prepare-issued',source=deepcopy(phase),parentSha256=self.parent_digest,frames=[],deliveries=[],requests=[],
                    export=None,readId='',saved=None,artifacts={},artifactRoot=self.artifact_root(),scope=self.run,quiet=[],inspection='',completedInspections={})
                self.save(state)
            row=self.append();self.parent.still_idle(row['base'],self.parent.state)
            # If an earlier original baseline reached disk, it remains the
            # baseline. Recovery cannot adopt intervening export/IO effects.
            self.before_export(row,self.state)
            value=decode(row['exports']['raw']);need(value['lease']['present'] and not value['lease']['native']['busy'])
            events,_copies=components(value);need(not events['activeRequest'] and not events['pendingIo'])
            state=deepcopy(self.state);state['stage']='prepared';self.save(state);result=self.report();self.fence();return result

    def send(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='prepared');self.append();self.fence()
            state=deepcopy(self.state);state['stage']='input-issued';self.save(state)
            path=self.parent.state['capture']['file']['path'];control='snapshot.save.'+hashlib.sha256(path.encode()).hexdigest()
            selected=self.parent.snapshot.ui.control(self.state['frames'][-1]['base']['ui'],control);need(selected is not None)
            self.current=True
            try:self.parent.snapshot.ui.input(control,token=selected['token'])
            finally:self.current=False
            return self.reconcile()

    def export_proof(self,state):
        record=state['export'];exact(record,{'frame','identity','uri','destination'})
        need(integer(record['frame'],0,len(state['frames'])-1));value=decode(state['frames'][record['frame']]['exports']['raw'])
        events,copies=components(value);baseline=components(decode(state['frames'][0]['exports']['raw']))[0]
        identity=record['identity'];exact(identity,{'request','handle','ticket','generation','action','source'})
        before=decode(state['frames'][0]['exports']['raw']);file=self.parent.state['capture']['file']
        need(before['lease']['present'] and identity['handle']==before['lease']['native']['handle']
            and identity['action']=='save' and identity['source']==file['path'])
        owned=[row for row in events['events'][baseline['sequence']:] if all(row[key]==identity[key] for key in identity)]
        delivery=[item for item in state['deliveries'] if item['kind']=='qml'];need(len(delivery)==1)
        before_frame=state['frames'][delivery[0]['frame']]
        need(owned and owned[0]['kind']=='request-active' and owned[0]['capturedEpochMs']>=max(state['source']['activations'][-1]['activatedEpochMs'],decode(before_frame['exports']['raw'])['capturedEpochMs'])
            and len({row['request'] for row in events['events'][baseline['sequence']:]})==1
            and len([row for row in state['deliveries'] if row['kind']=='qml'])==1)
        for kind in ('destination-created','destination-copied','destination-published'):
            rows=[row for row in owned if row['kind']==kind];need(len(rows)==1 and rows[0]['value']==record['uri'])
        for kind in ('result-ready','delivered'):
            rows=[row for row in owned if row['kind']==kind];need(len(rows)==1 and rows[0]['value']=='success' and rows[0]['auxiliary']=='')
        body=copies['source'];need(body.get('snapshotExportReadbacksVersion')==2 and 'initialized' not in body and body['osDestinations']['snapshotOsDestinationsVersion']==3)
        targets=[row for row in body['osDestinations']['rows'] if row['request']==identity['request']];need(len(targets)==1 and targets[0]==record['destination'])
        captured=self.parent.state['capture'];native_files=self.parent.frame(self.parent.state['frames'][captured['frame']])[2]['source']['rows']
        original_file=[item for item in native_files if item['id']==file['fileId']];need(len(original_file)==1)
        destination=targets[0];need(destination['identity']['providerUid']!=original_file[0]['uid'] and destination['acquiredEpochMs']>=max(decode(before_frame['exports']['raw'])['capturedEpochMs'],next(item['capturedEpochMs'] for item in owned if item['kind']=='destination-published')) and destination['phase']=='qualified' and destination['inserted'] and not destination['deleteIssued']
            and destination['identity']['ownerPackage']=='org.overte.pico' and destination['identity']['uri']==record['uri']
            and destination['identity']['displayName']==Path(file['path']).name
            and (destination['identity']['device'],destination['identity']['inode'])!=(file['device'],file['inode'])
            and destination['original']=={key:file[key] for key in ('bytes','sha256')})

    def saved_proof(self,state):
        saved=state['saved'];exact(saved,{'frame','file','decoded'})
        need(integer(saved['frame'],0,len(state['frames'])-1));file=saved['file']
        exact(file,{'artifact','bytes','sha256','capturedEpochMs','originalCompletedEpochMs','request','job','copy','source','snapshotSavedOriginalVersion','device','inode','originalStat'})
        need(type(file['snapshotSavedOriginalVersion']) is int and file['snapshotSavedOriginalVersion']==1 and file['source']=='pico-snapshot-saved-original'
            and file['request']==state['export']['identity']['request'] and file['job']==state['readId'] and native_source.nonce(file['copy'])
            and integer(file['capturedEpochMs'],1) and integer(file['originalCompletedEpochMs'],1,file['capturedEpochMs'])
            and original_stat(file['originalStat'],file['bytes'],file['device'],file['inode']))
        body=components(decode(state['frames'][saved['frame']]['exports']['raw']))[1]['source']
        jobs=[row for row in body['jobs'] if row['id']==state['readId']];need(len(jobs)==1 and jobs[0]['phase']=='complete')
        delivery=[item for item in state['deliveries'] if item['kind']=='readback' and item['command']['operation']=='read']
        need(len(delivery)==1);before=state['frames'][delivery[0]['frame']]
        job=jobs[0];need(job['startedEpochMs']>=max(state['source']['activations'][-1]['activatedEpochMs'],decode(before['exports']['raw'])['capturedEpochMs']) and job['completedEpochMs']==file['originalCompletedEpochMs'] and job['original']['id']==file['copy']
            and job['original']['request']==file['request'] and all(job['original'][key]==file[key] for key in ('bytes','sha256')))
        captured=self.parent.state['capture'];need(all(file[key]==captured['file'][key] for key in ('bytes','sha256')))
        artifact=state['artifacts'].get(file['copy']);need(artifact is not None and artifact['phase']=='saved' and artifact['name']==file['artifact'])
        raw=self.host_read(artifact);original_png=self.parent.files.host_read(captured['artifactRecord']);need(raw==original_png)
        key=(artifact['file']['device'],artifact['file']['inode'],file['sha256'])
        if key not in self.decoded:self.decoded[key]=inspect_snapshot(raw,mode='still',file_format='png')
        need(saved['decoded']==self.decoded[key]==captured['decoded'])

    def reconcile(self):
        """Read original events only; uncertain Save/read inputs are never resent."""
        with self.lock.held():
            self.load();need(self.state['stage'] in ('input-issued','exported','read-issued','acquired','quiet-issued','partial-ready'))
            row=self.append();value=decode(row['exports']['raw']);events,copies=components(value)
            if self.state['stage']=='input-issued':
                before=components(decode(self.state['frames'][0]['exports']['raw']))[0]
                entries=[event for event in events['events'][before['sequence']:] if event['kind']=='request-active']
                if entries:
                    need(len(entries)==1);identity={key:entries[0][key] for key in ('request','handle','ticket','generation','action','source')}
                    published=[event for event in events['events'] if event['request']==identity['request'] and event['kind']=='destination-published']
                    destinations=copies['source'].get('osDestinations',{}).get('rows',[])
                    targets=[item for item in destinations if item['request']==identity['request'] and item['phase']=='qualified']
                    success=all(any(event['request']==identity['request'] and event['kind']==kind and event['value']=='success' and not event['auxiliary'] for event in events['events']) for kind in ('result-ready','delivered'))
                    if published and targets and success:
                        need(len(published)==len(targets)==1);state=deepcopy(self.state)
                        state['export']=dict(frame=len(state['frames'])-1,identity=identity,uri=published[0]['value'],destination=deepcopy(targets[0]))
                        state['stage']='exported';self.save(state)
            if self.state['stage']=='read-issued':
                jobs=[job for job in copies['source'].get('jobs',[]) if job['id']==self.state['readId']]
                if jobs and jobs[0]['phase']=='complete':
                    need(len(jobs)==1);file=self.transport.acquire_current(jobs[0]['original']['id']);self.append();state=deepcopy(self.state)
                    raw=self.host_read(state['artifacts'][file['copy']]);state['saved']=dict(frame=len(state['frames'])-1,file=file,decoded=inspect_snapshot(raw,mode='still',file_format='png'))
                    state['stage']='acquired';self.save(state)
            result=self.report();self.fence();return result

    def start_read(self):
        with self.lock.held():
            self.load();need(self.state['stage']=='exported');self.append();state=deepcopy(self.state)
            state['readId']=uuid.uuid4().hex;need(all(job['id']!=state['readId'] for job in components(decode(state['frames'][-1]['exports']['raw']))[1]['source']['jobs']));request=self.exports.envelope(self.run,'read',export_request=state['export']['identity']['request'],resource_id=state['readId'])
            state['requests'].append(deepcopy(request));state['stage']='read-issued';self.save(state);self.current=True
            try:self.exports.request_original(request)
            finally:self.current=False
            return self.reconcile()

    def before_export(self,row,state):
        first=decode(state['frames'][0]['exports']['raw']);current=decode(row['exports']['raw'])
        old,old_copies=components(first);new,copies=components(current)
        need(current['lease']['present'] and current['lease']['native']['handle']==first['lease']['native']['handle']
            and not current['lease']['native']['busy'] and new['events']==old['events'] and not new['activeRequest'] and not new['pendingIo'])
        def inventory(value):return {key:item for key,item in value['source'].items() if key not in ('sequence','capturedEpochMs','elapsedMs')}
        need(inventory(old_copies)==inventory(copies))

    def inspection_done(self,row,id,state):
        value=decode(row['exports']['raw']);body=components(value)[1]['source'];os=body.get('osDestinations')
        if type(os) is not dict or os['pending'] or os['checkId']!=id:return False
        need(os['snapshotOsDestinationsVersion']==3)
        issued=[delivery for delivery in state['deliveries'] if delivery['kind']=='readback'
            and delivery['command']['operation']=='inspect-destinations' and delivery['command']['resourceId']==id]
        need(len(issued)==1);before=state['frames'][issued[0]['frame']]
        need(os['checkedEpochMs']>=decode(before['exports']['raw'])['capturedEpochMs'])
        current=[item for item in os['rows'] if item['request']==state['export']['identity']['request']]
        need(len(current)==1 and current[0]['verifiedEpochMs']>=decode(before['exports']['raw'])['capturedEpochMs'])
        return True

    def resolve_inspection(self):
        id=self.state['inspection'];need(native_source.nonce(id))
        for _ in range(31):
            row=self.append()
            if self.inspection_done(row,id,self.state):
                state=deepcopy(self.state);state['completedInspections'][id]=len(state['frames'])-1;state['inspection']='';self.save(state);return row
            self.fence();self.native.sleep(.1)
        need(False)

    def inspect_provider(self):
        # Recovery first resolves an already-issued inspection read-only. An
        # unknown publication is never retired or replaced by another send.
        if self.state['inspection']:self.resolve_inspection()
        self.append();state=deepcopy(self.state);id=uuid.uuid4().hex
        current=components(decode(state['frames'][-1]['exports']['raw']))[1]['source']['osDestinations']
        need(current['checkId']!=id and all(request['resourceId']!=id for request in state['requests']))
        request=self.exports.envelope(self.run,'inspect-destinations',resource_id=id)
        state['requests'].append(request);state['inspection']=id;self.save(state);self.current=True
        try:self.exports.request_original(request)
        finally:self.current=False
        return self.resolve_inspection()

    def idle(self,row,state):
        self.parent.still_idle(row['base'],self.parent.state);review=row['base']['ui']['picoSnapshotReview']['review'];need(not review['exportError'] and not review['statusError']);value=decode(row['exports']['raw']);events,copies=components(value)
        need(value['lease']['present'] and value['lease']['native']['handle']==state['export']['identity']['handle'] and not value['lease']['native']['busy']
            and not events['activeRequest'] and not events['pendingIo'] and 'initialized' not in copies['source']
            and not copies['source']['copiesRetired'] and all(job['phase'] in ('complete','failed') for job in copies['source']['jobs']))
        os=copies['source']['osDestinations'];need(self.inspection_done(row,os['checkId'],state))
        current=[item for item in os['rows'] if item['request']==state['export']['identity']['request']];need(len(current)==1)
        observed=dict(current[0]);original=state['export']['destination']
        need({key:item for key,item in observed.items() if key not in ('checkedEpochMs','verifiedEpochMs')}==
            {key:item for key,item in original.items() if key not in ('checkedEpochMs','verifiedEpochMs')})
        issued=next(delivery for delivery in state['deliveries'] if delivery['kind']=='readback' and delivery['command']['resourceId']==os['checkId'])
        before=state['frames'][issued['frame']];verified=observed['verifiedEpochMs'];epoch=value['capturedEpochMs']
        need(-250<=epoch-verified and max(epoch-verified,decode(before['exports']['raw'])['capturedEpochMs']-verified+
            (row['hostMonotonic']-before['hostMonotonic'])*1000)<=1500)
        copied=row['copy'];saved=state['saved']['file'];need(copied is not None and copied['id']==saved['copy']
            and all(copied['metadata'][key]==saved[key] for key in ('bytes','sha256','device','inode','originalStat')))

    def quiet_clocks(self,row,state):
        events,copies=components(decode(row['exports']['raw']));os=copies['source']['osDestinations']
        return self.clocks(row)+(events['elapsedMs'],copies['source']['elapsedMs'],os['checkedEpochMs'],
            next(item['verifiedEpochMs'] for item in os['rows'] if item['request']==state['export']['identity']['request']))

    def quiet_signature(self,row):
        value=decode(row['exports']['raw']);events,copies=components(value);work=self.parent.scoped_work(row['base']);os=deepcopy(copies['source'].get('osDestinations'))
        if os is not None:
            for key in ('checkedEpochMs','checkId'):os.pop(key)
            for item in os['rows']:
                for key in ('checkedEpochMs','verifiedEpochMs'):item.pop(key)
        return dict(lease=value['lease'],events=events['events'],pendingIo=events['pendingIo'],jobs=copies['source'].get('jobs'),files=copies['source'].get('files'),
            destinations=copies['source'].get('destinations'),os=os,grants=copies['source'].get('shareGrants'),copy=row['copy'],
            work={key:work[key] for key in ('signalInvocations','timerInvocations','timerRegistrations')})

    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['stage'] in ('acquired','quiet-issued'));state=deepcopy(self.state);state['stage']='quiet-issued';self.save(state)
            first=previous=signature=None;indices=[]
            for _ in range(65):
                row=self.inspect_provider();self.idle(row,self.state);clocks=self.quiet_clocks(row,self.state);observed=self.quiet_signature(row)
                if first is None or previous is not None and any(b-a>500 for a,b in zip(previous,clocks)):first=(len(self.state['frames'])-1,clocks);signature=observed;indices=[]
                indices.append(len(self.state['frames'])-1)
                need(observed==signature);previous=clocks;self.fence()
                if all(b-a>=3000 for a,b in zip(first[1],clocks)):
                    state=deepcopy(self.state);state['quiet']=[dict(indices=deepcopy(indices))];state['stage']='partial-ready';self.save(state)
                    result=self.report();self.fence();return result
                self.native.sleep(.25)
            need(False)

    def report(self):
        return dict(qualification='PICO_NORMAL_SNAPSHOT_SAVE_COMPONENT_ONLY',stage=self.state['stage'],fullSnapshotRecipe=False,
            deviceAcceptance=False,journalRetained=True,ordinarySaveResendAllowed=False,originalCaptureRetained=True,
            productExportExecutorRetired=False,savedPng=None if self.state['saved'] is None else deepcopy(self.state['saved']['decoded']))
