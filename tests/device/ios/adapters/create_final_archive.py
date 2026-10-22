"""Seal actual qualified Create originals after the fixture becomes inactive.

Original PNGs, exports and private proof carriers remain real files. This
archive records their actual inode/bytes after a pure whole-proof decoder has
accepted the same unchanged closure. Later verification requires no SDK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit
import stat

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters.graphics_configuration import settings as image_settings

VERSION=1
MAX_BYTES=64*1024*1024


def file_original(path):
    path=Path(path);PrivateFeatureState(path)._parent()
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(descriptor,'rb') as stream:
        before=os.fstat(stream.fileno());current=path.lstat()
        for row in (before,current):
            need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_uid==os.geteuid()
                and stat.S_IMODE(row.st_mode)==0o600 and 0<=row.st_size<=MAX_BYTES)
        need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino))
        sha=hashlib.sha256()
        while True:
            chunk=stream.read(1024*1024)
            if not chunk:break
            sha.update(chunk)
        after=os.fstat(stream.fileno());end=path.lstat()
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
            ==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
            ==(end.st_dev,end.st_ino,end.st_size,end.st_mtime_ns,end.st_ctime_ns))
    return dict(path=str(path),device=before.st_dev,inode=before.st_ino,bytes=before.st_size,sha256=sha.hexdigest())


class CreateFinalArchive:
    def __init__(self,store,root,binding,run,role,lock):
        self.store,self.root,self.binding,self.run,self.role,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        need(isinstance(store,PrivateFeatureState) and role in ('primary','actor')
            and store.path.name=='ios-create-'+role+'-'+run+'-final.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        lock.assert_held();self.previous=store.read();self.state=deepcopy(self.previous)
        self.frames=OriginalFrameStore(self.root,self.binding,run,role,lambda:True,self.intent,namespace='ios-create-final',schema_prefix='iosCreateFinal')
        if self.state is not None:self.decode(self.state)

    def decode(self,value):
        exact(value,{'iosCreateFinalArchiveVersion','binding','runId','role','phase','frameSha256','record','pending'})
        need(type(value['iosCreateFinalArchiveVersion']) is int and value['iosCreateFinalArchiveVersion']==VERSION
            and same(context(value['binding']),self.binding) and value['runId']==self.run and value['role']==self.role
            and value['phase'] in ('writing','complete') and type(value['frameSha256']) is str and len(value['frameSha256'])==64)
        if value['record'] is not None:self.frames.expand(value['record'])
        if value['pending'] is not None:self.frames.original(value['pending'])
        if value['phase']=='complete':need(value['record'] is not None and value['pending'] is None)
        return deepcopy(value)

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));self.decode(self.state)
        self.store.write(self.state,self.previous);self.previous=deepcopy(self.state)

    def intent(self,kind,value):
        need(kind=='original' and self.state is not None and self.state['phase']=='writing' and value['index']==1)
        self.state['pending']=deepcopy(value);self.save()

    @staticmethod
    def closure(directories,extra,excluded):
        need(type(directories) is list and type(extra) is list and type(excluded) is list)
        excluded={str(Path(path)) for path in excluded};paths={Path(path) for path in extra}
        for directory in directories:
            directory=Path(directory);PrivateFeatureState(directory/'boundary')._parent()
            # All retained Create state, immutable source records and component
            # carriers are included. Coordinator/final journals are excluded
            # explicitly because their terminal transition follows this seal.
            paths.update(path for path in directory.iterdir() if path.name.startswith('ios-create-') and path.name.endswith('.json'))
        paths={path for path in paths if str(path) not in excluded}
        need(0<len(paths)<=4096);return [file_original(path) for path in sorted(paths)]

    def coordinator(self,value):
        if value is None:return
        exact(value,{'iosCreateFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy'})
        need(type(value['iosCreateFeatureVersion']) is int and value['iosCreateFeatureVersion']==1
            and value['runId']==self.run and value['role']==self.role and value['artifactRoot']==str(self.root))
        image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
        url=urlsplit(value['fixtureUrl'])
        need(url.scheme in ('http','https') and url.hostname and not url.username and not url.password
            and not url.query and not url.fragment and url.path.endswith('/runs/'+self.run+'/'))

    def seal(self,*,phase_original,feature,original,validate,paired,directories,extra,excluded,coordinator_header=None):
        self.lock.assert_held();need(callable(validate) and type(feature) is dict and type(paired) is dict)
        if self.state is not None:
            if self.state['phase']=='writing':self.recover()
            return self.verify()
        phase_packet(phase_original,run=self.run,area='create',request=phase_original['requestId'],epoch=phase_original['capturedEpochMs'])
        need(phase_original['active'] is False and phase_original['runId']==self.run and phase_original['area']=='create'
            and phase_original['activations'] and phase_original['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={})
            and feature['phase'] in ('paired','cleaned') and feature['binding']==self.binding and feature['phaseInstance']==phase_original['instance'])
        self.coordinator(coordinator_header)
        before=self.closure(directories,extra,excluded);measured=validate(original)
        need(measured['public']['resources']==[] and measured['public']['artifacts']==[]
            and measured['ticket']==phase_original['activations'][-1]['ticket']
            and measured['acquisition']['hostAfterEpochMs']<=phase_original['retiredEpochMs']
            and measured['retirement']['originalSha256']==paired['localSha256']==digest(original))
        self.paired(feature,paired,validate,measured)
        after=self.closure(directories,extra,excluded);need(same(before,after))
        frame=dict(iosCreateFinalProofVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            phaseOriginal=deepcopy(phase_original),feature=deepcopy(feature),coordinatorHeader=deepcopy(coordinator_header),original=deepcopy(original),
            measured=deepcopy(measured),paired=deepcopy(paired),files=before)
        self.state=dict(iosCreateFinalArchiveVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            phase='writing',frameSha256=digest(frame),record=None,pending=None);self.save()
        reference=self.frames.write(1,frame);self.state.update(record=reference,pending=None,phase='complete');self.save()
        return self.verify()

    def paired(self,feature,paired,validate,measured):
        """Rederive the original publication/reader, never a caller's ACK."""
        from ios.adapters.create_retirement import CreateRetirement
        from ios.adapters.peer_admission import validate as admitted
        decoder=getattr(validate,'__self__',None)
        need(isinstance(decoder,CreateRetirement) and decoder.binding==self.binding and decoder.run==self.run and decoder.role==self.role
            and feature['retirement'] is not None and paired['localSha256']==feature['retirement']['localSha256'])
        if self.role=='actor':
            exact(paired,{'localSha256','publication','publisherOriginal'})
            store=PrivateFeatureState(self.store.path.with_name('phase-retirement-create-'+self.run+'-actor.json'))
            need(same(store.read(),paired['publisherOriginal']))
            archived=PhaseRetirementPublisher.archive(paired['publisherOriginal'],store=store,binding=self.binding,run=self.run,area='create',
                fixture_url=decoder.source.phase.client.url,phase_instance=feature['phaseInstance'],validate_original=validate)
            need(archived['pending'] is None and archived['records'])
            checker=object.__new__(PhaseRetirementPublisher);checker.store=store;checker.binding=self.binding;checker.run=self.run;checker.area='create'
            checker.url=decoder.source.phase.client.url;checker.instance=feature['phaseInstance'];checker.validate_original=validate
            latest=checker.load(archived['records'][-1]);need(same(latest,paired['publication']) and latest['mode']=='published'
                and latest['intent']['body']['originalSha256']==paired['localSha256'])
        else:
            exact(paired,{'localSha256','peerReceipt','readerOriginal'})
            peer=admitted(feature['actorAdmission'],self.binding)
            checker=object.__new__(PhaseRetirementReader);checker.stage='complete';checker.binding=self.binding;checker.run=self.run;checker.area='create'
            checker.instance=feature['phaseInstance'];checker.url=decoder.source.phase.client.url;checker.admitted_original=feature['actorAdmission']
            checker.actor=binding_from_context(peer)
            store=PrivateFeatureState(self.store.path.with_name('ios-create-primary-peer-retirement.json'))
            need(same(store.read(),paired['readerOriginal']));archived=checker.decode(paired['readerOriginal'])
            need(archived['records'] and same(archived['records'][-1],paired['peerReceipt']))
            receipt=paired['peerReceipt'];need(measured['acquisition']['hostBeforeEpochMs']>=receipt['acquisition']['hostAfterEpochMs']
                and measured['acquisition']['hostBeforeMonotonic']>=receipt['acquisition']['hostAfterMonotonic'])

    def recover(self):
        self.lock.assert_held();need(self.state is not None and self.state['phase']=='writing')
        pending=self.state['pending'];need(pending is not None and pending['phase'] in ('opened','saved'))
        frame=self.frames.read(pending);need(digest(frame)==self.state['frameSha256'])
        complete=dict(pending,phase='saved');self.state.update(record=self.frames.compact(complete),pending=None,phase='complete');self.save()

    def verify(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));state=self.decode(self.previous);need(state['phase']=='complete')
        frame=self.frames.read(self.frames.expand(state['record']));need(digest(frame)==state['frameSha256'])
        exact(frame,{'iosCreateFinalProofVersion','binding','runId','role','phaseOriginal','feature','coordinatorHeader','original','measured','paired','files'})
        need(type(frame['iosCreateFinalProofVersion']) is int and frame['iosCreateFinalProofVersion']==VERSION
            and frame['binding']==self.binding and frame['runId']==self.run and frame['role']==self.role
            and frame['phaseOriginal']['active'] is False and frame['measured']['public']['resources']==[]
            and frame['measured']['public']['artifacts']==[] and type(frame['files']) is list and 0<len(frame['files'])<=4096)
        self.coordinator(frame['coordinatorHeader'])
        phase=frame['phaseOriginal'];phase_packet(phase,run=self.run,area='create',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={})
            and frame['measured']['ticket']==phase['activations'][-1]['ticket']
            and frame['measured']['acquisition']['hostAfterEpochMs']<=phase['retiredEpochMs']
            and frame['paired']['localSha256']==frame['measured']['retirement']['originalSha256']==digest(frame['original']))
        paths=[]
        for row in frame['files']:
            exact(row,{'path','device','inode','bytes','sha256'});need(integer(row['bytes'],0,MAX_BYTES))
            need(same(file_original(row['path']),row));paths.append(row['path'])
        need(paths==sorted(set(paths)));return deepcopy(frame)
