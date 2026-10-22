"""Avatar observation acquisition, immutable history and one-send publication.

Each role owns independent reads of both actual SDKs. Only the file-only
decoder normalizes originals. Interrupted reads retain their partial owners;
recovery abandons that acquisition before taking distinct passive samples.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy,copy
import hashlib
import os
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.original_frame_store import OriginalFrameStore
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_facts import IOSAvatarFacts,inside
from ios.adapters.avatar_observation import source_history
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.adapters.avatar_surface import IOSAvatarSurface
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=2
READS=(1,2)
PARTS=frozenset(('started','authorityBefore','baseline-primary','baseline-actor','surface-primary','surface-actor','primaryPeer','primary','actorBefore','actor','actorAfter','authorityAfter','image'))
ROLES=('primary','actor')


class IOSAvatarObserver:
    def __init__(self,store,sources,peers,surfaces,samples,authority,phase,*,role,guard,expected_code,
                 epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        exact(sources,set(ROLES));exact(peers,set(ROLES));exact(surfaces,set(ROLES))
        need(isinstance(store,PrivateFeatureState) and isinstance(samples,IOSAvatarSamples) and not samples.historical
            and isinstance(authority,AvatarAuthorityReader) and isinstance(phase,PhaseFixtureReader)
            and phase.area=='avatar-people' and role in ROLES and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.sources,self.peers,self.surfaces,self.samples,self.authority,self.phase=store,sources,peers,surfaces,samples,authority,phase
        self.role,self.run,self.binding,self.root,self.lock=role,identifier(phase.run),context(samples.binding),samples.root,samples.lock
        self.guard,self.epoch_ms,self.monotonic,self.expected_code=guard,epoch_ms,monotonic,deepcopy(expected_code)
        need(authority.run==self.run and authority.client.url==phase.client.url and samples.run==self.run and samples.role==role
            and store.path.name=='ios-avatar-'+role+'-observer.json' and store.path.parent==self.lock.path.parent)
        for subject in ROLES:
            source,peer,surface=sources[subject],peers[subject],surfaces[subject]
            need(isinstance(source,IOSAvatarSources) and not source.historical and source.role==role and source.run==self.run
                and isinstance(peer,IOSAvatarPeerSources) and not peer.historical and peer.role==role and peer.run==self.run
                and isinstance(surface,IOSAvatarSurface) and surface.sources is source and surface.subject_role==subject
                and same(source.binding,peer.binding))
            source.lock.assert_held();peer.lock.assert_held()
        need(same(self.binding,sources[role].binding));self.lock.assert_held();self.failed=False
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,role,guard,self.storage,
            namespace='avatar-observation',schema_prefix='avatarObservation',monotonic=monotonic)
        self.previous=store.read();self.schema_version=VERSION if self.previous is None or unpack(self.previous['payload'])[0]['pending'] is None else self.previous['iosAvatarObserverVersion']
        self.state=dict(rows=[],pending=None,baseline=None,authorityBarrier=None,phaseInstance=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state,version=None):
        version=getattr(self,'schema_version',VERSION) if version is None else version;state=deepcopy(state)
        if version>=2:
            for row in state['rows']:row.setdefault('staged',None)
        return dict(iosAvatarObserverVersion=version,binding=self.binding,runId=self.run,role=self.role,
            artifactRoot=str(self.root),fixtureUrl=self.phase.fixture_url,payload=pack([state]))

    def carrier(self,kind,*,live=False):
        need(kind in ('part','staged'))
        return OriginalFrameStore(self.root,self.binding,self.run,self.role,self.guard if live else lambda:True,
            (lambda name,value:self.carrier_storage(kind,name,value)) if live else lambda *_:need(False),
            namespace='avatar-observation-'+kind,schema_prefix='avatarObservation'+kind.title(),monotonic=getattr(self,'monotonic',time.monotonic))

    def absent_file(self,path):
        need(not os.path.lexists(path))
        if getattr(self,'record_absences',None) is not None:self.record_absences.add(path)

    def carrier_file(self,kind,value):
        store=self.carrier(kind);store.original(value);path=store.path(value)
        if value['phase']=='planned':self.absent_file(path);return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            store.file(path,stream.fileno(),value);raw=stream.read(value['bytes']+1);store.file(path,stream.fileno(),value)
        need(len(raw)<=value['bytes']);complete=len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
        if value['phase']=='saved':need(complete)
        from adapters.original_file_reads import record as read_original
        read_original(path)
        return dict(identity=value['file'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=complete)

    def carrier_storage(self,kind,name,value):
        self.bound();need(name=='original');p=self.state['pending'];need(p is not None);self.carrier(kind).original(value)
        need(value['index']==p['index'])
        if kind=='part':
            field=self.writing_part;need(field in PARTS);old=p['partial'].get(field)
        else:old=p['record']
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        if kind=='part':p['partial'][field]=deepcopy(value)
        else:p['record']=deepcopy(value)
        self.save()

    def partial_values(self,p,version=None,*,complete=False):
        version=getattr(self,'schema_version',VERSION) if version is None else version
        if version==1:return deepcopy(p['partial'])
        need(type(p['partial']) is dict and set(p['partial'])<=PARTS);result={}
        for name,ref in p['partial'].items():
            self.carrier('part').original(ref);need(ref['index']==p['index']);file=self.carrier_file('part',ref)
            ready=file is not None and file['complete']
            if complete:need(ready)
            if ready:
                value=self.carrier('part').read(ref);exact(value,{'name','value'});need(value['name']==name and type(value['value']) is dict);result[name]=value['value']
        return result

    def partial_files(self,p):
        return {name:self.carrier_file('part',ref) for name,ref in p['partial'].items()}

    def pending_record(self,p,version=None):
        version=getattr(self,'schema_version',VERSION) if version is None else version
        if p['record'] is None:return None
        if version==1:return deepcopy(p['record'])
        self.carrier('staged').original(p['record']);need(p['record']['index']==p['index'])
        file=self.carrier_file('staged',p['record'])
        return None if file is None or not file['complete'] else self.carrier('staged').read(p['record'])


    def decode(self,value):
        exact(value,{'iosAvatarObserverVersion','binding','runId','role','artifactRoot','fixtureUrl','payload'})
        rows=unpack(value['payload']);version=value['iosAvatarObserverVersion']
        need(type(version) is int and version in READS and len(rows)==1 and same(value,self.envelope(rows[0],version)))
        state=rows[0];exact(state,{'rows','pending','baseline','authorityBarrier','phaseInstance'})
        need(type(state['rows']) is list and len(state['rows'])<=512)
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','status','ticket','original'}|({'staged'} if version>=2 else set()));need(type(row['index']) is int and row['index']==index
                and row['status'] in ('observed','abandoned'));identifier(row['ticket']);self.originals.expand(row['original'])
            record=self.read_record(row);need(record['index']==index and record['ticket']==row['ticket'] and record['status']==row['status'])
        if state['baseline'] is not None:
            exact(state['baseline'],set(ROLES))
            for subject in ROLES:self.reference(self.sources[subject],state['baseline'][subject])
            need(number(state['authorityBarrier'],1,1e15));identifier(state['phaseInstance'])
        else:need(state['authorityBarrier'] is state['phaseInstance'] is None)
        if state['pending'] is not None:
            p=state['pending'];exact(p,{'index','ticket','partial','original','record','abandonedOriginal'})
            need(type(p['index']) is int and p['index']==len(state['rows'])+1 and type(p['partial']) is dict);identifier(p['ticket'])
            if p['original'] is not None:self.originals.original(p['original'])
            self.partial_values(p,version)
            staged=self.pending_record(p,version)
            if staged is not None:self.record(staged)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        for source in self.sources.values():source.lock.assert_held()
        for peer in self.peers.values():peer.lock.assert_held()

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def storage(self,kind,value):
        self.bound();p=self.state['pending'];need(kind=='original' and p is not None and p['record'] is not None)
        self.originals.original(value);need(value['index']==p['index']);old=p['original']
        need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        p['original']=deepcopy(value);self.save()

    def remember(self,name,value):
        self.bound();p=self.state['pending'];need(p is not None and name not in p['partial'])
        if getattr(self,'schema_version',VERSION)==1:p['partial'][name]=deepcopy(value);self.save();return value
        need(name in PARTS and type(value) is dict);self.writing_part=name
        try:self.carrier('part',live=True).write(p['index'],dict(name=name,value=deepcopy(value)))
        finally:self.writing_part=None
        return value

    @staticmethod
    def reference(owner,ref=None):
        if ref is None:
            need(owner.frames);return dict(index=len(owner.frames),sha256=digest(owner.frames[-1]))
        exact(ref,{'index','sha256'});need(integer(ref['index'],1,len(owner.frames))
            and digest(owner.frames[ref['index']-1])==ref['sha256']);return owner.frames[ref['index']-1]

    def partial_file(self,original):
        if original is None:return None
        self.originals.original(original);path=self.originals.path(original)
        if original['phase']=='planned':self.absent_file(path);return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes'])
        if original['phase']=='saved':need(len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256'])
        from adapters.original_file_reads import record as read_original
        read_original(path)
        return dict(identity=original['file'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def record(self,value,depth=0):
        need(integer(depth,0,8))
        version=value.get('iosAvatarObservationRecordVersion');need(type(version) is int and version in READS)
        exact(value,{'iosAvatarObservationRecordVersion','index','ticket','status','partial','components','facts','abandonment'}|({'parts','partFiles'} if version>=2 else set()))
        need(type(value['iosAvatarObservationRecordVersion']) is int and value['iosAvatarObservationRecordVersion'] in READS
            and integer(value['index'],1,512) and value['status'] in ('observed','abandoned')
            and type(value['partial']) is dict and type(value['components']) is dict)
        identifier(value['ticket']);exact(value['components'],{'sources','peers','samples'})
        if version>=2:
            parts=dict(index=value['index'],partial=value['parts'])
            need(same(self.partial_values(parts,version),value['partial']) and same(self.partial_files(parts),value['partFiles']))
        for kind in ('sources','peers'):
            exact(value['components'][kind],set(ROLES))
            for row in value['components'][kind].values():exact(row,{'owner','recovery'})
        if value['status']=='observed':
            need(type(value['facts']) is dict and value['abandonment'] is None)
            facts,partial=value['facts'],value['partial']
            need(facts['sequence']==value['index'] and facts['ticket']==value['ticket'])
            for field,part in (('primaryPeer','primaryPeer'),('actorBefore','actorBefore'),('actorAfter','actorAfter'),
                    ('provider','authorityAfter'),('image','image')):need(same(facts[field],partial[part]))
            need(same(facts['current'],{subject:partial[subject] for subject in ROLES})
                and all(same(facts['acquisition'][key],item) for key,item in partial['started'].items()))
        else:
            need(value['facts'] is None);abandoned=value['abandonment'];exact(abandoned,{'priorOwner','partialFile'}|({'stagedFile'} if version>=2 else set()))
            prior=abandoned['priorOwner'];exact(prior,{'iosAvatarObserverVersion','binding','runId','role','artifactRoot','fixtureUrl','payload'})
            rows=unpack(prior['payload']);version=prior['iosAvatarObserverVersion']
            need(type(version) is int and version in READS and len(rows)==1 and same(prior,self.envelope(rows[0],version)))
            pending=rows[0]['pending'];need(pending is not None and pending['index']==value['index'] and pending['ticket']==value['ticket']
                and same(self.partial_values(pending,version),value['partial']) and same(abandoned['partialFile'],self.partial_file(pending['original'])))
            if value['iosAvatarObservationRecordVersion']>=2:
                need(same(abandoned['stagedFile'],None if pending['record'] is None else self.carrier_file('staged',pending['record'])))
            staged=self.pending_record(pending,version)
            if staged is not None:self.record(staged,depth+1)
        return value

    def read_record(self,row):
        from ios.adapters.avatar_record_cache import AvatarRecordCache
        if not hasattr(self,'record_cache'):self.record_cache=AvatarRecordCache()
        def validate():
            previous=getattr(self,'record_absences',None);self.record_absences=set()
            try:return self._read_record(row)
            finally:self.last_record_absences=set(self.record_absences);self.record_absences=previous
        return self.record_cache.read(row,validate,absent=lambda:self.last_record_absences)

    def _read_record(self,row):
        reader=copy(self.originals);reader.guard=lambda:True;reader.intent=lambda *_:need(False)
        value=reader.read(reader.expand(row['original']));self.record(value)
        if row.get('staged') is not None:
            need(value['iosAvatarObservationRecordVersion']==2 and same(self.carrier('staged').read(row['staged']),value))
        elif value['iosAvatarObservationRecordVersion']==2:need(False)
        need(all(value[key]==row[key] for key in ('index','ticket','status')));return value

    def snapshot(self):
        self.bound();sources={};peers={}
        for subject in ROLES:
            source,peer=self.sources[subject],self.peers[subject]
            sources[subject]=dict(owner=deepcopy(source.previous),recovery=IOSAvatarSourceRecovery(source).store.read())
            peers[subject]=dict(owner=deepcopy(peer.previous),recovery=OriginalAvatarPeerRecovery(peer).store.read())
        return dict(sources=sources,peers=peers,samples=deepcopy(self.samples.previous))

    def decoder(self,record):
        components=record['components'];sources={};peers={}
        for subject in ROLES:
            actual=self.sources[subject];value=components['sources'][subject]
            sources[subject]=source_history(value['owner'],value['recovery'],store=actual.store,root=actual.root,
                binding=actual.binding,run=self.run,role=self.role,lock=actual.lock)
            live=PrivateFeatureState(actual.store.path.with_name('ios-avatar-'+self.role+'-source-recovery.json')).read()
            if live is not None:
                recovery=IOSAvatarSourceRecovery.archive(live,actual)
                known=[] if value['recovery'] is None else IOSAvatarSourceRecovery.archive(value['recovery'],sources[subject]).state['records']
                if record['facts'] is not None:
                    for ref in recovery.state['records']:
                        if recovery.attempt(recovery.record(ref))['revision']<record['facts']['current'][subject]['index']:need(ref in known)
            actual=self.peers[subject];value=components['peers'][subject]
            class Frozen(PrivateFeatureState):
                def read(_self,original=deepcopy(value['owner'])):return deepcopy(original)
                def write(_self,*_args):need(False)
                def discard(_self,*_args):need(False)
            peer=IOSAvatarPeerSources(Frozen(actual.store.path),actual.root,actual.binding,self.run,None,
                actual.lock,lambda:True,historical=True,role=self.role)
            need(peer.state['pending'] is None)
            if value['recovery'] is not None:
                recovery=OriginalAvatarPeerRecovery.archive(value['recovery'],peer);need(recovery.state['pending'] is None)
                for frame in peer.frames:recovery.follow(frame,historical=True)
            live=PrivateFeatureState(actual.store.path.with_name('ios-avatar-'+self.role+'-peer-recovery.json')).read()
            if live is not None:
                recovery=OriginalAvatarPeerRecovery.archive(live,actual)
                known=[] if value['recovery'] is None else OriginalAvatarPeerRecovery.archive(value['recovery'],peer).state['records']
                boundary=(record['facts']['primaryPeer'] if subject=='primary' else record['facts']['actorAfter']) if record['facts'] is not None else None
                for ref in recovery.state['records']:
                    if boundary is not None and recovery.attempt(recovery.record(ref))['revision']<boundary['index']:need(ref in known)
            peers[subject]=peer
        samples=IOSAvatarSamples.history(components['samples'],store=self.samples.store,root=self.root,binding=self.binding,
            run=self.run,role=self.role,policy=self.samples.policy,lock=self.lock)
        return IOSAvatarFacts(sources,peers,samples,self.authority,role=self.role,
            phase_instance=record['facts']['phaseInstance'],expected_code=self.expected_code)

    def validate_original(self,row):
        """Historical Publisher callback: original files only, no live guard."""
        self.lock.assert_held();record=self.read_record(row);need(record['status']=='observed')
        proof=self.decoder(record).derive(record['facts'])
        return {key:proof[key] for key in ('ticket','public','acquisition')}

    def finish(self,record):
        self.bound();p=self.state['pending'];need(p is not None and record['index']==p['index']);self.record(record)
        if p['record'] is None:
            if getattr(self,'schema_version',VERSION)==1:p['record']=deepcopy(record);self.save()
            else:self.carrier('staged',live=True).write(record['index'],record)
        else:need(same(record,self.pending_record(p)))
        if p['original'] is None:original=self.originals.write(record['index'],record)
        else:
            need(p['original']['phase']=='saved' and same(self.originals.read(p['original']),record))
            original=self.originals.compact(p['original'])
        row={key:record[key] for key in ('index','status','ticket')};row['original']=original
        if record['iosAvatarObservationRecordVersion']>=2:row['staged']=deepcopy(p['record'])
        self.state['rows'].append(row);self.state['pending']=None;self.schema_version=VERSION;self.save();return deepcopy(row)

    def recover(self):
        self.bound();p=self.state['pending']
        if p is None:return
        staged=self.pending_record(p)
        if staged is not None and (p['original'] is None or p['original']['phase']=='saved'):return self.finish(staged)
        # No native read is repeated. Each component keeps its actual partial
        # query, opened inode and native source prefix in its own recovery owner.
        for subject in ROLES:
            source=self.sources[subject];IOSAvatarSourceRecovery(source).recover()
            peer=self.peers[subject];OriginalAvatarPeerRecovery(peer).recover()
        self.samples.recover()
        # An interrupted immutable-file write remains owned and cannot be
        # overwritten by the abandonment record; its raw inode is retained.
        if p['abandonedOriginal'] is None or p['record'] is not None:
            p['abandonedOriginal']=dict(priorOwner=deepcopy(self.previous),partialFile=self.partial_file(p['original']))
            if self.schema_version>=2:p['abandonedOriginal']['stagedFile']=None if p['record'] is None else self.carrier_file('staged',p['record'])
            p['record']=None;p['original']=None;self.save()
        record=dict(iosAvatarObservationRecordVersion=self.schema_version,index=p['index'],ticket=p['ticket'],status='abandoned',
            partial=self.partial_values(p),components=self.snapshot(),facts=None,abandonment=deepcopy(p['abandonedOriginal']))
        if self.schema_version>=2:record.update(parts=deepcopy(p['partial']),partFiles=self.partial_files(p))
        p['record']=None;self.save();return self.finish(record)

    def provider(self):
        before=self.epoch_ms();started=self.monotonic();status=self.authority.read();after=self.epoch_ms();ended=self.monotonic()
        clock=dict(hostBeforeEpochMs=before,hostAfterEpochMs=after,hostBeforeMonotonic=started,hostAfterMonotonic=ended)
        PhaseWitnessPublisher.acquisition(clock);return dict(status=status,acquisition=clock)

    def observe(self,after_sequence=0):
        return self._observe(after_sequence,cleanup_checkpoint=False)

    def checkpoint(self,after_sequence=0):
        """Fresh live-resource cleanup admission, never final retirement."""
        return self._observe(after_sequence,cleanup_checkpoint=True)

    def _observe(self,after_sequence,*,cleanup_checkpoint):
        self.bound();need(integer(after_sequence,0,2**53-1));self.recover();phase=self.phase.read();ticket=phase['ticket']
        need((phase['verb']=='cleanup' if cleanup_checkpoint else phase['verb']!='cleanup') and len(self.state['rows'])<512
            and (not cleanup_checkpoint or self.state['baseline'] is not None))
        p=dict(index=len(self.state['rows'])+1,ticket=ticket,partial={},original=None,record=None,abandonedOriginal=None)
        self.state['pending']=p;self.save();started=self.monotonic();before=self.epoch_ms()
        self.remember('started',dict(hostBeforeEpochMs=before,hostBeforeMonotonic=started))
        initial=self.remember('authorityBefore',self.provider())
        if self.state['baseline'] is None:
            need(phase['verb']=='baseline');baselines={}
            for subject in ROLES:
                owner=self.sources[subject];IOSAvatarSourceRecovery(owner).recover();frame=owner.read()
                baselines[subject]=self.reference(owner);self.remember('baseline-'+subject,baselines[subject])
            self.state.update(baseline=baselines,authorityBarrier=initial['acquisition']['hostBeforeEpochMs'],
                phaseInstance=phase['status']['instance']);self.save()
        need(self.state['phaseInstance']==phase['status']['instance'])
        for subject in ROLES:self.surfaces[subject].prepare(ticket);self.remember('surface-'+subject,self.surfaces[subject].previous)
        for subject in ROLES:OriginalAvatarPeerRecovery(self.peers[subject]).recover()
        primary=self.peers['primary'];primary.read();ppeer=self.remember('primaryPeer',primary.reference())
        source=self.sources['primary'];IOSAvatarSourceRecovery(source).recover();source.read();pstate=self.remember('primary',self.reference(source))
        actor=self.peers['actor'];actor.read();abefore=self.remember('actorBefore',actor.reference())
        source=self.sources['actor'];IOSAvatarSourceRecovery(source).recover();source.read();astate=self.remember('actor',self.reference(source))
        actor.read();aafter=self.remember('actorAfter',actor.reference())
        provider=self.remember('authorityAfter',self.provider())
        previous=None
        for row in reversed(self.state['rows']):
            if row['status']=='observed':previous=self.read_record(row)['facts']['image'];break
        basis=None;loaded=self.sources['primary'].frames[-1]['originals']['state']['source']['geometryLoaded']
        if not loaded:
            for row in reversed(self.samples.state['rows']):
                if row['status']=='observed' and self.samples.archive(row)[2]['modelLoaded']:basis=row['index'];break
            need(basis is not None)
        self.samples.recover()
        avatar_id=(self.sources['primary'].frames[-1]['originals']['state']['source']['sessionId'] if self.role=='actor' else None)
        image=self.samples.capture(ticket,avatar_id=avatar_id,absence_basis=basis);self.remember('image',image)
        end=self.phase.read();need(end['ticket']==ticket)
        clock=dict(hostBeforeEpochMs=before,hostBeforeMonotonic=started,hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        PhaseWitnessPublisher.acquisition(clock)
        barriers={}
        for subject in ROLES:
            baseline=self.reference(self.sources[subject],self.state['baseline'][subject]);barriers[subject]=dict(
                nativeEpochMs=baseline['clockJoin']['nativeAfter']['capturedEpochMs'],providerEpochMs=self.state['authorityBarrier'],
                httpEvent=len(baseline['originals']['http']['events']))
        facts=dict(iosAvatarFactsOriginalVersion=1,runId=self.run,role=self.role,sequence=p['index'],ticket=ticket,
            phaseInstance=self.state['phaseInstance'],baseline=deepcopy(self.state['baseline']),current=dict(primary=pstate,actor=astate),
            primaryPeer=ppeer,actorBefore=abefore,actorAfter=aafter,provider=provider,barriers=barriers,image=image,
            imageBefore=previous if phase['verb'] in ('avatar-scale','wearable-add','avatar-bookmark-choose') else None,acquisition=clock)
        record=dict(iosAvatarObservationRecordVersion=self.schema_version,index=p['index'],ticket=ticket,status='observed',partial=self.partial_values(p,complete=True),
            components=self.snapshot(),facts=facts,abandonment=None)
        if self.schema_version>=2:record.update(parts=deepcopy(p['partial']),partFiles=self.partial_files(p))
        proof=self.decoder(record).derive(facts);row=self.finish(record);need(row['index']>after_sequence)
        # The original acquisition clocks are immutable. Include decoding and
        # private-file persistence in the return deadline without retiming any
        # source or saved original into this later instant.
        ended_epoch,ended_mono=self.epoch_ms(),self.monotonic()
        need(ended_epoch>=clock['hostAfterEpochMs'] and ended_mono>=clock['hostAfterMonotonic'])
        PhaseWitnessPublisher.acquisition(dict(hostBeforeEpochMs=before,hostBeforeMonotonic=started,
            hostAfterEpochMs=ended_epoch,hostAfterMonotonic=ended_mono))
        return proof['public']

    def publisher(self):
        need(self.role=='actor');return PhaseWitnessPublisher(
            PrivateFeatureState(self.store.path.with_name('phase-publication-avatar-people-'+self.run+'-actor.json')),self.binding,self.phase,self.lock,
            self.guard,self.validate_original,epoch_ms=self.epoch_ms,monotonic=self.monotonic)

    def publish_latest(self):
        self.bound();need(self.role=='actor' and self.state['rows'] and self.state['rows'][-1]['status']=='observed')
        return self.publisher().publish(self.state['rows'][-1])
