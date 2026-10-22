"""Independent Snapshot originals, including passive Android handoff sources.

The role never issues a functional input. All effects are projected by the
closed source reducer; immutable receipts retain their original timestamps.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import os
import stat

from adapters.native_feature_observation import exact,fresh,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_phone_touch_state import released as touch_released
from adapters.world_render_evidence import original_pixels
from feature_journeys.contract import result
from feature_journeys.evidence import image_observation
from feature_journeys.scenarios import VERSION
from overte_phone_create_role import PhoneCreateRole
from overte_phone_create_marker import ready as marker_ready,retired as marker_retired
from overte_phone_graphics_samples import restore_native
from overte_phone_script_history import pack,unpack,same
from overte_phone_snapshot_handoff import script_advance
from overte_phone_snapshot_source import continuity as snapshot_continuity
from overte_phone_snapshot_capture_source import continuity as files_continuity
from overte_phone_snapshot_readbacks import PhoneSnapshotReadbacks,continuity as readbacks_continuity
from overte_phone_snapshot_upload_source import continuity as upload_continuity
from overte_phone_snapshot_consumer import continuity as consumer_continuity
from overte_phone_snapshot_upload_bytes import PhoneSnapshotUploadBytes
from overte_phone_snapshot_saved_files import PhoneSnapshotSavedFiles
from adapters.native_account_observation import accept as account_accept
from adapters.native_script_work import scope as script_scope
from overte_phone_snapshots_evidence import SnapshotsOriginals,SnapshotsImages,SnapshotsBinary
from overte_phone_snapshots_measurements import state as measured_state,SnapshotPending,export_requests


def distinct(rows):
    """Remove adjacent identical historical floors only, never a transition."""
    result=[]
    for row in rows:
        if not result or not same(result[-1],row):result.append(deepcopy(row))
    return result


class PassiveReadbacks(PhoneSnapshotReadbacks):
    """Use the original readback transport against fresh passive batches only."""
    def __init__(self,handoff):
        self.handoff,self.pid,self.clock_ms,self.last=handoff,handoff.owner['processId'],handoff.clock_ms,None
    def request(self,run,operation='observe',export_request='',resource_id='',**_kwargs):
        need(run==self.handoff.owner['runId'] and operation=='observe' and export_request==resource_id=='')
        packet=self.handoff.read()['readbacks']
        if self.last is not None:readbacks_continuity(self.last,packet)
        self.last=deepcopy(packet);return deepcopy(packet)


class PhoneSnapshotsRole(PhoneCreateRole):
    def __init__(self,feature,role):
        need(role in ('primary','actor'));feature.lock.assert_held()
        self.feature,self.role=feature,role
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-'+role+'-originals.json'))
        self.previous=self.store.read();self.state=dict(phase='ready',sequence=0,manifests=[],pending=None)
        self.originals=SnapshotsOriginals(feature.root,feature.binding,feature.run,role,self.bound,self.storage_intent,kind='snapshots')
        if self.previous is not None:
            exact(self.previous,{'snapshotsRoleVersion','runId','binding','role','payload'})
            need(type(self.previous['snapshotsRoleVersion']) is int and self.previous['snapshotsRoleVersion']==1
                and self.previous['runId']==feature.run and self.previous['role']==role and same(self.previous['binding'],feature.binding))
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,{'phase','sequence','manifests','pending'})
            need(self.state['phase'] in ('ready','reading','retired') and integer(self.state['sequence'],0,256))
        self.frames=self.restore_originals()
        self.system=feature.state['handoff'] is not None
        self.measurements=self.native=self.avatar=self.world=self.touch=self.marker=None
        self.handoff=None;self.files=None;self.readbacks=self.upload=None
        baseline=feature.original();self.baseline=baseline
        history=self.history()
        if self.system:
            h=feature.state['handoff']
            self.handoff=feature.adapter._snapshot_handoff_source(feature.selector,feature.binding,h['resolution'],feature.header_authority,h['binding'])
            originals=[row for frame in history for row in frame.get('handoffOriginals',[]) if row['source']['handoffId']==h['id']]
            if originals:self.handoff.restore_history(distinct(originals))
            read=self.handoff.read
            def tracked_read():
                value=read()
                if self.state['phase']=='reading':
                    pending=self.state['pending']['work'];rows=pending.setdefault('handoffOriginals',[])
                    need(len(rows)<128);rows.append(deepcopy(self.handoff.last));self.save()
                return value
            self.handoff.read=tracked_read
            self.platform=feature.adapter._snapshot_system_platform(feature.selector,feature.binding,h['resolution'],feature.header_authority)
        else:
            self.measurements=feature.adapter._snapshot_measurements(feature.selector)
            self.native=feature.adapter._native_feature_observer(feature.selector,read_only=True)
            self.avatar=feature.adapter._avatar_render_observer(feature.selector,read_only=True)
            self.world=feature.adapter._graphics_subject_observer(feature.selector,read_only=True)
            self.touch=feature.adapter._touch_state_observer(feature.selector,read_only=True)
            self.marker=feature.adapter._create_fixture_observer(feature.selector,read_only=True)
            self.readbacks=feature.adapter._snapshot_readbacks(feature.selector,read_only=True)
            self.upload=feature.adapter._snapshot_upload_source(feature.selector)
            self.platform=feature.adapter._snapshot_platform(feature.selector)
            previous=next((row['nativeAfter'] for row in reversed(history) if row.get('nativeAfter') is not None),None)
            if previous is not None:restore_native(self.native,previous)
            else:restore_native(self.native,baseline['native'])
            groups=[group for frame in history for group in ([row['source']['source']['group'] for row in frame['handoffOriginals']] if frame.get('handoffOriginals') else frame.get('groups',([frame['measurement']['group']] if frame.get('measurement') is not None else [])))]
            groups=[baseline['group'],*groups]
            scripts=None
            for group in distinct(groups):scripts=script_advance(scripts,group['script'])
            # Pure replay restores the actual script engine/manager lifetime set.
            for key,value in scripts.__dict__.items():
                if key in ('instance','sequence','engines','active','retired','effect_rows','absent_effects','effects_required','code_required','compilations_required','loads','membership','retired_managers','captured_epoch'):
                    setattr(self.measurements.scripts,key,deepcopy(value))
            self.measurements.roots.last=deepcopy(groups[-1]['rootsAfter'])
            self.measurements.snapshot.last=deepcopy(groups[-1]['snapshot'])
            previous=next((row['avatarAfter'] for row in reversed(history) if row.get('avatarAfter') is not None),baseline['avatar'])
            self.avatar.restore([previous])
            for key,reader in (('touch',self.touch),('world',self.world),('marker',self.marker)):
                previous=next((frame[key] for frame in reversed(history) if frame.get(key) is not None),baseline.get(key))
                if previous is not None:
                    if key in ('touch','marker'):reader.restore([previous])
                    else:reader.last=deepcopy(previous)
            self.settings=feature.settings(read_only=True)
            previous=next((frame['measurement']['settings'] for frame in reversed(history) if frame.get('measurement') is not None and frame['measurement']['settings'] is not None),None)
            if previous is not None:self.settings.last=deepcopy(previous)
            for key,reader in (('readbacksPacket',self.readbacks),('uploadPacket',self.upload)):
                previous=next((row[key] for row in reversed(history) if row.get(key) is not None),None)
                if previous is not None:reader.last=deepcopy(previous)
        # A resumed foreground reader retains lifecycle/account floors from
        # every passive original, including intermediate body transfer reads.
        if self.native is not None:
            last_native=max((index for index,frame in enumerate(history) if frame.get('nativeAfter') is not None),default=-1)
            contexts=[row['source']['source']['context'] for frame in history[last_native+1:] for row in frame.get('handoffOriginals',[])]
            for current in contexts:
                need(all(current['lifecycle'][key]>=value for key,value in self.native.lifecycle.items()))
                self.native.lifecycle=deepcopy(current['lifecycle'])
                self.native.account_history=account_accept(self.native.account_history,current['account'])
        self.platform.original=deepcopy(baseline['platform']['source'])
        self.work=None
        if not self.system and (feature.state['cancelJobs'] or feature.state['phase'] in ('cleaned','retiring')):
            self.work=feature.adapter._script_work(feature.selector,read_only=True)
            rows=[row for frame in history for row in frame.get('workOriginals',([frame['scriptWork']] if frame.get('scriptWork') is not None else []))]
            if rows:self.work.restore(distinct(rows))
            self.track(self.work,'read','workOriginals')
        self.documents=feature.documents(read_only=True) if feature.state['docArm'] is not None else None
        if self.documents is not None:
            floor=feature.state['docBinding']['floor']
            rows=[row for frame in history for row in frame.get('documentOriginals',([frame['measurement']['documents']] if frame.get('measurement') is not None and frame['measurement']['documents'] is not None else []))]
            self.documents.restore_history(distinct([floor,*rows]));self.track(self.documents,'observe','documentOriginals')
        self.consumer=feature.consumer(read_only=True) if feature.state['consumerArm'] is not None else None
        if self.consumer is not None:
            previous=next((row for frame in reversed(history) for row in reversed(frame.get('consumerOriginals',([frame['measurement']['consumer']] if frame.get('measurement') is not None and frame['measurement']['consumer'] is not None else [])))),None)
            if previous is not None:self.consumer.last=deepcopy(previous)
            self.track(self.consumer,'observe','consumerOriginals')
        if self.previous is None:self.save()

    def track(self,reader,method,key):
        original=getattr(reader,method)
        def acquire(*args,**kwargs):
            value=original(*args,**kwargs)
            if self.state['phase']=='reading':
                rows=self.state['pending']['work'].get(key,[]);need(len(rows)<128)
                self.checkpoint(**{key:[*rows,deepcopy(value)]})
            return value
        setattr(reader,method,acquire)

    def history(self):
        rows=list(self.frames)
        if self.state['pending'] is not None:rows.append(self.state['pending'].get('work',{}))
        return rows

    def save(self):
        self.bound();value=dict(snapshotsRoleVersion=1,runId=self.feature.run,binding=self.feature.binding,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def storage_intent(self,kind,value):
        super().storage_intent(kind,value)
        if kind=='original' and value['phase']=='saved':
            self.state['pending']['frame']=None;self.state['pending']['work']={};self.save()
        return True

    def image_engine(self,index=None):
        f=self.feature
        return SnapshotsImages(f.root,f.binding,f.run,self.role,index or self.state['sequence']+1,self.bound,self.image_intent)

    def binary_engine(self,index=None):
        f=self.feature
        return SnapshotsBinary(f.root,f.binding,f.run,self.role,index or self.state['sequence']+1,self.bound,self.binary_intent)

    def binary_intent(self,value):
        need(self.state['phase']=='reading');rows=self.state['pending']['binaries'];old=next((row for row in rows if row['name']==value['name']),None)
        if old is None:need(value['phase']=='planned');rows.append(deepcopy(value))
        else:
            need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and same({k:v for k,v in old.items() if k not in ('phase','file')},{k:v for k,v in value.items() if k not in ('phase','file')}))
            rows[rows.index(old)]=deepcopy(value)
        self.save();return True

    def files_owner(self):
        if self.files is None:self.files=self.feature.observer_files(self.role,handoff_source=self.handoff)
        return self.files

    def batch(self):
        f=self.feature
        if self.system:
            batch=self.handoff.read()
            groups=self.state['pending']['work'].get('groups',[])
            self.checkpoint(groups=[*groups,deepcopy(batch['group'])]);return batch
        group,self.selected=self.measurements.read(f.run)
        readbacks=self.readbacks.request(f.run);upload=self.upload.read(f.run)
        self.checkpoint(group=group,groups=[*self.state['pending']['work'].get('groups',[]),deepcopy(group)],readbacksPacket=readbacks,uploadPacket=upload)
        return dict(group=group,readbacks=readbacks,captureFiles=None,upload=upload)

    def body(self,acquisition):
        """Read only this owner's actual immutable intermediate inode."""
        owner=self.files_owner()
        with owner.held():
            row=owner.state['artifacts'][acquisition['fileId']]
            need(row['name']==acquisition['artifact']);return owner.host_read(row)

    def binary(self,ticket,acquisition,raw):
        image_observation(raw,self.feature.run,self.feature.state['captureTicket'] or ticket,self.feature.config['fileImagePolicy'])
        value=self.binary_engine().write(ticket,acquisition,raw)
        self.checkpoint(acquisitions=[*self.state['pending']['work'].get('acquisitions',[]),deepcopy(acquisition)])
        return value

    def capture_bodies(self,ticket,packet):
        owner=self.files_owner();records=[]
        for row in packet['source']['rows']:
            if row['runId']!=self.feature.run or row['absent']:continue
            if not row['closed']:raise SnapshotPending()
            value=owner.acquire(row['path'],row['captureId']);raw=self.body(value)
            records.append(self.binary(ticket,value,raw))
        return records

    def system_ui(self):
        f=self.feature;handoff=f.state['handoff'];resolution=handoff['resolution'] if handoff is not None else self.baseline['resolution']
        factory=f.adapter._snapshot_document_ui if handoff is not None and handoff['kind']=='document' else f.adapter._snapshot_share_ui
        ui=factory(f.selector,f.binding,resolution,lambda *_:need(False),f.header_authority)
        return ui.capture(),resolution

    def independent_exports(self,ticket,group,readbacks,upload,provider,captured):
        f=self.feature;records=[];requests=export_requests(group['snapshot'],self.baseline['group']['snapshot'])
        if readbacks.get('initialized') is not False:
            for destination in readbacks['destinations']:
                owned=next(row for row in readbacks['osDestinations']['rows'] if row['request']==destination['request'])
                if destination['published'] and owned['phase']!='retired':
                    jobs=[job for job in readbacks['jobs'] if job['request']==destination['request'] and job['phase']=='complete']
                    if not jobs:raise SnapshotPending()
                    need(len(jobs)==1 and jobs[0]['original'] is not None)
                    # Existing transport does actual URI/copy reads; a dedicated
                    # private per-acquisition directory cannot adopt old files.
                    root=f.root/('snapshots-'+self.role+'-transfer-'+str(self.state['sequence']+1))
                    need(not root.exists() and not root.is_symlink());self.checkpoint(transfer=dict(name=root.name,phase='planned',root=None,files=[]))
                    root.mkdir(mode=0o700);info=root.lstat()
                    self.checkpoint(transfer=dict(name=root.name,phase='created',root=dict(device=info.st_dev,inode=info.st_ino),files=[]))
                    if self.system:
                        source=self.files_owner().transport
                        reader=PhoneSnapshotSavedFiles(source.adb,source.selector,source.package,source.context,source.check_continuity,root,PassiveReadbacks(self.handoff),f.run)
                    else:reader=f.adapter._snapshot_saved_files(f.selector,f.run,root)
                    value=reader.acquire_current(jobs[0]['original']['id']);need(type(value['artifact']) is str and Path(value['artifact']).name==value['artifact'])
                    path=root/value['artifact'];need(path.parent==root)
                    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                    with os.fdopen(fd,'rb') as stream:
                        info=os.fstat(stream.fileno());current=path.lstat()
                        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
                            and (info.st_dev,info.st_ino)==(current.st_dev,current.st_ino))
                        raw=stream.read(SnapshotsBinary.LIMIT+1);need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
                    transfer=dict(name=root.name,phase='owned',root=deepcopy(self.state['pending']['work']['transfer']['root']),files=[dict(name=path.name,device=info.st_dev,inode=info.st_ino,bytes=len(raw),sha256=value['sha256'])])
                    self.checkpoint(transfer=transfer);records.append(self.binary(ticket,value,raw));self.retire_transfer(transfer)
            if self.consumer is not None:
                consumed=self.consumer.observe()
                if consumed['phase']=='complete' and not consumed['retired']:
                    grant=next(row for row in readbacks['shareGrants']['rows'] if row['request'] in requests and row['component']==consumed['identity']['component'])
                    value,raw=self.consumer.acquire_current(grant,captured);records.append(self.binary(ticket,value,raw))
        if self.documents is not None:
            documents=self.documents.observe()
            for row in documents['documents']:
                if row['absent'] or not row['writeClosedEpochMs']:continue
                owned=next(item for item in readbacks['osDestinations']['rows'] if item['identity'] is not None and item['identity'].get('documentId')==row['documentId'])
                uid=f.adapter._snapshot_phone_uid(f.selector,f.binding,(f.state['handoff'] or {}).get('resolution',self.baseline['documentResolution']),f.header_authority)
                value,raw=self.documents.acquire(row['documentId'],owned['identity'],captured,uid['uid'],self.baseline['documentResolution'])
                records.append(self.binary(ticket,value,raw))
        for job in upload['jobs']:
            if job['terminal']=='success':
                original=next(row for row in provider['requests'] if row['response'] is not None and any(request['stage']=='image' and request['responseId']==row['response']['responseId'] for request in job['requests']))
                reader=PhoneSnapshotUploadBytes(f.phase,self.bound,f.phase.epoch_ms,monotonic=f.monotonic)
                value,raw=reader.acquire(original['requestId'],original['ticket']);records.append(self.binary(ticket,value,raw))
        return records

    def retire_transfer(self,transfer):
        f=self.feature;root=f.root/transfer['name'];need(root.parent==f.root and root.name.startswith('snapshots-'+self.role+'-transfer-'))
        need(transfer['phase'] in ('created','owned','deleting','removed'))
        if transfer['phase']=='removed':need(not root.exists() and not root.is_symlink());return
        if not root.exists():
            need(not root.is_symlink() and transfer['phase']=='deleting')
            self.checkpoint(transfer=dict(transfer,phase='removed'));return
        info=root.lstat();need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700
            and (info.st_dev,info.st_ino)==(transfer['root']['device'],transfer['root']['inode']))
        actual={p.name for p in root.iterdir()};expected={row['name'] for row in transfer['files']}
        need(actual<=expected if transfer['phase']=='deleting' else actual==expected)
        transfer=deepcopy(transfer);transfer['phase']='deleting';self.checkpoint(transfer=transfer)
        for row in transfer['files']:
            path=root/row['name'];need(path.parent==root)
            try:info=path.lstat()
            except FileNotFoundError:continue
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
                and (info.st_dev,info.st_ino)==(row['device'],row['inode']) and info.st_size==row['bytes']
                and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']);path.unlink();need(not path.exists() and not path.is_symlink())
        info=root.lstat();need((info.st_dev,info.st_ino)==(transfer['root']['device'],transfer['root']['inode']))
        root.rmdir();need(not root.exists() and not root.is_symlink());transfer['phase']='removed';self.checkpoint(transfer=transfer)

    def reacquire_binary(self,record):
        """Resume only from the same independently observed original owner."""
        f=self.feature;source=record['acquisition'];kind=source['source']
        if kind=='snapshot-capture-original':
            value=self.files_owner().acquire(source['path'],source['captureId'])
            need(all(value[key]==source[key] for key in ('fileId','captureId','path','device','inode','bytes','sha256','nativeClosedEpochMs')))
            return self.body(value)
        batch=self.batch();readbacks=batch['readbacks']['source']['source']
        captures=[row['acquisition'] for row in self.state['pending']['binaries'] if row['acquisition']['source']=='snapshot-capture-original']
        need(len(captures)==1);captured=captures[0]
        if kind=='snapshot-saved-original':
            transfer=self.state['pending']['work'].get('transfer');need(transfer is not None and transfer['phase']=='owned' and len(transfer['files'])==1)
            row=transfer['files'][0];path=f.root/transfer['name']/row['name'];info=path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1
                and (info.st_dev,info.st_ino)==(row['device'],row['inode']))
            # A saved transfer is read only while a fresh original readback
            # still owns the same job/copy; no current completion is invented.
            need(any(job['id']==source['job'] and job['phase']=='complete' and job['original'] is not None and job['original']['id']==source['copy'] for job in readbacks['jobs']))
            return path.read_bytes()
        if kind=='snapshot-receiver-original':
            need(self.consumer is not None)
            grant=next(row for row in readbacks['shareGrants']['rows'] if row['request']==source['request'])
            value,raw=self.consumer.acquire_current(grant,captured);need(value['copy']==source['copy']);return raw
        if kind=='snapshot-upload-original':
            reader=PhoneSnapshotUploadBytes(f.phase,self.bound,f.phase.epoch_ms,monotonic=f.monotonic)
            value,raw=reader.acquire(source['request'],source['metadata']['ticket']);return raw
        need(kind=='snapshot-document-original' and self.documents is not None)
        owner=next(row for row in readbacks['osDestinations']['rows'] if row['identity'] is not None and row['identity'].get('documentId')==source['documentId'])
        uid=f.adapter._snapshot_phone_uid(f.selector,f.binding,(f.state['handoff'] or {}).get('resolution',self.baseline['documentResolution']),f.header_authority)
        value,raw=self.documents.acquire(source['documentId'],owner['identity'],captured,uid['uid'],self.baseline['documentResolution']);return raw

    def recover(self):
        self.bound();need(self.state['phase']=='reading');pending=self.state['pending'];f=self.feature
        for record in list(pending['binaries']):
            if record['phase']=='saved':self.binary_engine().read(record)
            else:self.binary_engine().resume(record,self.reacquire_binary(record))
        transfer=pending['work'].get('transfer')
        if transfer is not None:
            if transfer['phase']=='planned':need(not (f.root/transfer['name']).exists())
            else:self.retire_transfer(transfer)
        image=pending['image']
        if image is not None or pending.get('capture') is not None:
            need(not self.system)
            owned=f.adapter._world_render_capture(f.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
            if image is not None and image['phase']!='saved':
                if owned.owner.store.read() is not None:
                    capture=pending['work']['capture'];need(owned.owner.owned()['capture']['commandId']==capture['requestId']);owned.storage.bind(capture)
                    self.image_engine().resume(image,owned.storage.read(capture['source']['image']['name']))
                else:need(image['phase']=='planned' and self.image_engine().absent(image))
            if owned.owner.store.read() is not None:self.release_capture(owned)
        if pending['frame'] is not None:frame=pending['frame']
        elif pending['original'] is not None and pending['original']['phase']=='saved':frame=self.originals.read(pending['original'])
        else:frame=dict(pending['work'],diagnostic=True,image=pending['image'],binaries=pending['binaries'],retirement=pending['retirement'])
        self.finish_archive(frame)

    def read(self,after_sequence):
        try:return self.acquire(after_sequence)
        except SnapshotPending:self.recover();raise

    def acquire(self,after_sequence):
        f=self.feature;self.bound();need(self.state['phase'] in ('ready','retired') and integer(after_sequence,0,self.state['sequence']) and self.state['sequence']<256)
        self.state.update(phase='reading',pending=dict(original=None,manifest=None,image=None,binaries=[],retirement=None,frame=None,work={}));self.save()
        phase_before=f.phase.status();need(phase_before['activations']);ticket=phase_before['activations'][-1]['ticket']
        need(phase_before['active'] or f.state['phase'] in ('cleaned','retiring'));self.checkpoint(ticket=ticket,phaseBefore=phase_before)
        native_before=avatar_before=world=touch=marker=capture=image=retirement=None;image_ready=False
        if not self.system:
            native_before=self.native.read(self.native.sequence,require_account=True);avatar_before=self.avatar.read()
            self.checkpoint(nativeBefore=native_before,avatarBefore=avatar_before)
        closing=f.state['phase'] in ('cleaned','retiring')
        owner=self.files_owner();binaries=[]
        if not closing:
            batch=self.batch();self.checkpoint(group=batch['group'])
            inventory=owner.inventory();packet=owner.source.last;need(packet is not None)
            binaries=self.capture_bodies(ticket,packet)
            acquired=self.state['pending']['work'].get('acquisitions',[]);captured=next((row for row in acquired if row['source']=='snapshot-capture-original'),None)
            if captured is not None:
                provider=f.phase.provider();binaries.extend(self.independent_exports(ticket,batch['group'],batch['readbacks']['source']['source'],batch['upload']['source'],provider,captured))
        # Closure needs no new body publication. Its complete fresh VM group,
        # real namespace scan and every owner are still acquired below; any
        # live/late file makes the strict reducer fail rather than becoming a
        # fictional empty inventory. Avoid duplicate native groups/scans here.
        if not self.system:
            if f.state['marker'] is not None and f.state['marker']['operation']=='prepare':
                marker=self.marker.read(f.run)
                # The original private capture keeps its own capture ticket.
                # Save/Share phases need no new world image, and cannot claim
                # one by retiming a marker left by the earlier capture.
                if marker['source']['originalInput']['ticket']==ticket:
                    marker_ready(marker,avatar_before)
                    owned=f.adapter._world_render_capture(f.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
                    need(owned.owner.store.read() is None)
                    captures=[row['capture'] for row in self.frames if row.get('capture') is not None]
                    if captures:
                        previous=captures[-1];reader=owned.capture;reader.instance,reader.sequence=previous['instance'],previous['sequence']
                        reader.acquisition,reader.captured=previous['source']['acquisitionSequence'],previous['source']['capturedEpochMs'];reader.frames={row['source']['renderTrace']['frameId'] for row in captures}
                    capture,raw=owned.read(owned.capture.sequence);self.checkpoint(capture=capture);self.state['pending']['capture']=deepcopy(owned.owner.owned());self.save()
                    original_pixels(capture,raw);image_observation(raw,f.run,ticket,f.policy)
                    need(capture['source']['targetExtent']==f.config['imageExtent']);image=self.image_engine().write(ticket,capture,raw)
                    retirement=self.release_capture(owned);image_ready=True
            elif f.state['marker'] is not None:
                marker=self.marker.read(f.run);marker_retired(marker)
            world=self.world.read(f.run,require_avatar=True);touch=self.touch.read()
        # Read all current effect owners after body acquisition. Historical
        # completion timestamps remain in the immutable acquisition receipts.
        batch=self.batch();inventory=owner.inventory();packet=owner.source.last
        batch=self.batch() if self.system else batch
        platform=self.platform.read();system,resolution=self.system_ui()
        documents=self.documents.observe() if self.documents is not None else None
        consumer=self.consumer.observe() if self.consumer is not None else None
        phone_uid=f.adapter._snapshot_phone_uid(f.selector,f.binding,(f.state['handoff'] or {}).get('resolution',self.baseline['documentResolution']),f.header_authority) if documents is not None else None
        settings=None if self.system else self.settings.request(f.run,'observe')
        cancels=[]
        if f.state['cancelJobs']:
            originals=f.inputs.restore(f.state['inputs'],f.state['inputSequence'])
            reader=None if self.system else f.adapter._snapshot_cancel(f.selector,read_only=True)
            if reader is not None:
                previous=[packet for frame in self.history() if frame.get('measurement') is not None for packet in frame['measurement']['cancels']]
                for packet_ in previous:reader.jobs[packet_['source']['job']]=deepcopy(packet_['source'])
                if previous:reader.last=deepcopy(previous[-1])
            for job in f.state['cancelJobs']:
                need(integer(job['sourceIndex'],1,len(originals)))
                if self.system:
                    index=job['retirementIndex'] or job['sourceIndex']
                    key='snapshotCancelRetired' if job['retirementIndex'] else 'snapshotCancel'
                    cancels.append(deepcopy(originals[index-1][key]))
                else:
                    request=None
                    if not batch['group']['snapshot']['source']['review']['present']:
                        work=self.work.read(self.selected['manager']['instance'],0 if self.work.last is None else self.work.last['sequence'])
                        selected=script_scope(work,self.selected['compilation'])
                        need(not selected['evaluating'] and not selected['timers'] and not selected['unknownTimers']
                            and all(selected[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
                        request=work['requestId']
                    cancels.append(reader.request(f.run,job['id'],'observe',closed_read_work_request_id=request))
        native_after=avatar_after=script_work=None
        if not self.system:
            native_after=self.native.read(self.native.sequence,require_account=True);avatar_after=self.avatar.read()
            self.checkpoint(nativeAfter=native_after,avatarAfter=avatar_after)
            if f.state['phase'] in ('cleaned','retiring'):
                script_work=self.work.read(self.selected['manager']['instance'],0 if self.work.last is None else self.work.last['sequence'])
                scope=script_scope(script_work,self.selected['compilation'])
                need(not scope['evaluating'] and not scope['timers'] and not scope['unknownTimers']
                    and all(scope[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
                self.checkpoint(scriptWork=script_work)
        phase_after=f.phase.status(phase_before);provider=f.phase.provider();epoch=f.phase.epoch_ms()
        need(same(phase_before['activations'],phase_after['activations']) and phase_before['active']==phase_after['active'])
        measurement=dict(group=batch['group'],captureFiles=packet['source'],inventory=inventory,readbacks=batch['readbacks']['source']['source'],upload=batch['upload']['source'],provider=provider,
            platform=platform,system=system,resolution=resolution,consumer=consumer,consumerBinding=deepcopy(f.state['consumerBinding']),
            acquisitions=deepcopy(self.state['pending']['work'].get('acquisitions',[])),cancels=cancels,settings=settings,
            documents=documents,documentsBinding=deepcopy(f.state['docBinding']),phoneUid=phone_uid,documentResolution=self.baseline['documentResolution'])
        account=native_after['account'] if native_after is not None else batch['context']['account']
        f.validate_account(account,phase_after['activations'][-1]['stimulus']['verb'],epoch)
        measured=measured_state(measurement,self.baseline['group'],run=f.run,pid=f.pid,epoch=epoch)
        observer_retirement=None
        if f.state['phase'] in ('cleaned','retiring'):
            need(settings is not None and settings['source']['retired'])
            with owner.held():already_retired=owner.state['retired']
            if not already_retired:owner.retire()
            observer_retirement=owner.require_retired();self.checkpoint(observerFilesRetirement=observer_retirement)
        for packet_ in (native_before,native_after):
            if packet_ is not None:native_packet(packet_,packet_['requestId'],f.pid,epoch)
        captured_epoch=min(batch['group']['rootsBefore']['requestedEpochMs'],platform['requestedEpochMs'],system['requestedEpochMs'],provider['capturedEpochMs'])
        fresh(captured_epoch,epoch)
        frame=dict(ticket=ticket,phaseBefore=phase_before,phaseAfter=phase_after,measurement=measurement,state=measured,epochMs=epoch,
            nativeBefore=native_before,nativeAfter=native_after,scriptWork=script_work,observerFilesRetirement=observer_retirement,avatarBefore=avatar_before,avatarAfter=avatar_after,world=world,touch=touch,marker=marker,
            capture=capture,image=image,imageReady=image_ready,retirement=retirement,transfer=deepcopy(self.state['pending']['work'].get('transfer')),binaries=deepcopy(self.state['pending']['binaries']),
            workOriginals=deepcopy(self.state['pending']['work'].get('workOriginals',[])),documentOriginals=deepcopy(self.state['pending']['work'].get('documentOriginals',[])),consumerOriginals=deepcopy(self.state['pending']['work'].get('consumerOriginals',[])),
            groups=deepcopy(self.state['pending']['work'].get('groups',[])),handoffOriginals=deepcopy(self.state['pending']['work'].get('handoffOriginals',[])),readbacksPacket=batch['readbacks'],uploadPacket=batch['upload'])
        self.finish_archive(frame);self.bound();artifacts=[]
        if image_ready:artifacts.append(dict(kind='image',source='world-render-target',name=image['name'],sequence=self.state['sequence'],capturedEpochMs=capture['source']['capturedEpochMs'],ticket=ticket))
        source={'capture':'snapshot-capture-original','save':'snapshot-saved-original','share-select-owned':'snapshot-receiver-original','upload':'snapshot-upload-original'}.get(phase_before['activations'][-1]['stimulus']['verb'])
        selected=[row for row in binaries if row['acquisition']['source']==source]
        if selected:
            value=selected[-1];artifacts.append(dict(kind='file',source='snapshot-private-original' if source=='snapshot-capture-original' else source,name=value['name'],sequence=self.state['sequence'],capturedEpochMs=value['acquisition']['capturedEpochMs'],ticket=ticket))
        resources=[]
        for key in ('open','pending','saveSheet','shareSheet'):
            if measured[key]:resources.append('panel:snapshots-'+key.lower())
        if measured['files']:resources.append('file:snapshots-originals')
        if measurement['readbacks'].get('initialized') is not False:
            if not measurement['readbacks']['copiesRetired']:resources.append('file:snapshots-readbacks')
            if any(not row['absent'] for row in measurement['readbacks']['osDestinations']['rows']):resources.append('file:snapshots-os-destinations')
            if any(row['granted'] or row['chooserGranted'] for row in measurement['readbacks']['shareGrants']['rows']):resources.append('connection:snapshots-grants')
        if consumer is not None and not consumer['retired']:resources.append('connection:snapshots-consumer')
        # Arming the independent E2E provider is baseline measurement setup.
        # Every actual plan/document/FD remains a responsibility until its real
        # retirement; retain the full raw source even for an empty preflight.
        if documents is not None and not documents['retired'] and any(documents[key] for key in ('plans','documents','fdLifetimes')):
            resources.append('connection:snapshots-documents')
        if any(job['uploaderAlive'] or job['fileAlive'] or job['multipartAlive'] for job in measurement['upload']['jobs']):resources.append('connection:snapshots-upload')
        lifecycle=native_after['lifecycle'] if native_after is not None else batch['context']['lifecycle']
        return result('feature.snapshots.observe',dict(schemaVersion=1,contractVersion=VERSION,runId=f.run,sequence=self.state['sequence'],capturedEpochMs=captured_epoch,state=measured,artifacts=artifacts,resources=sorted(resources),lifecycle=lifecycle))

    def history_authority(self):
        """Only historical host IO; never a target/input/transfer guard."""
        self.feature.lock.assert_held();self.feature.header_authority()
        need(same(self.store.read(),self.previous));return True

    def restore_originals(self):
        self.bound()
        f=self.feature
        host=SnapshotsOriginals(f.root,f.binding,f.run,self.role,self.history_authority,lambda *_:need(False),kind='snapshots')
        frames=host.restore(self.state['manifests'],self.state['sequence'])
        self.validate_files(frames=frames,historical=True)
        self.bound();return frames

    def validate_files(self,*,frames=None,historical=False):
        """A retained JSON receipt cannot hide a missing or replaced original."""
        f=self.feature
        for index,frame in enumerate(self.frames if frames is None else frames,1):
            image_engine=(SnapshotsImages(f.root,f.binding,f.run,self.role,index,self.history_authority,lambda *_:need(False))
                if historical else self.image_engine(index))
            binary_engine=(SnapshotsBinary(f.root,f.binding,f.run,self.role,index,self.history_authority,lambda *_:need(False))
                if historical else self.binary_engine(index))
            image=frame.get('image')
            if image is not None:
                if image['phase']=='planned':need(frame.get('diagnostic') is True and image_engine.absent(image))
                else:need(image['phase']=='saved');image_engine.read(image)
            for row in frame.get('binaries',[]):need(row['phase']=='saved');binary_engine.read(row)

    def retire(self):
        """Validate every original inode before handing journal removal to owner."""
        self.bound();need(self.state['phase'] in ('ready','retired') and self.state['pending'] is None)
        self.frames=self.restore_originals()
        need(not any(self.feature.root.glob('snapshots-'+self.role+'-transfer-*')))
        self.files_owner().retire();self.files_owner().require_retired()
        self.state['phase']='retired';self.save();return True
