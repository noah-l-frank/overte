"""Independent Audio originals and once-only existing PC recorder admission.

Long PC receive calls and waits run outside both original source locks. This
owner never invokes a normal Pico input or uses its Parent's observed facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import hashlib
import os
import stat
import threading
import time
import uuid

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.host_process_identity import host_identity
from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.native_fd_owner import require_directory
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state as original_state
from adapters.pico4.audio_pc_source import accept as source_accept
from adapters.pico4.audio_peer import PicoAudioPeer,configuration
from adapters.recorded_preview_history import measured_state,accept_history
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import pack,canonical
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import projection
from voice_peer.preview_source import producer_sha256

VERSION=2


def original(store):
    value,raw,physical=original_state(store)
    return dict(path=str(store.path),sha256=hashlib.sha256(raw).hexdigest(),physical=physical)


def require_original(reference):
    exact(reference,{'path','sha256','physical'})
    store=PrivateFeatureState(reference['path']);need(original(store)==reference)
    return store.read()


class PicoAudioPCActor:
    def __init__(self,recipe,phase_source,peer_factory,native,settings,pages,os_status,*,monotonic=time.monotonic,sleep=time.sleep):
        from adapters.pico4.audio_recipe import PicoAudioRecipe
        need(type(recipe) is PicoAudioRecipe and isinstance(phase_source,PhaseFixtureReader)
            and phase_source.run==recipe.run and phase_source.area=='audio' and phase_source.fixture_url==recipe.source.fixture_url
            and not isinstance(phase_source.client,AdapterFixtureClient) and phase_source.client.token!=recipe.source.client.token
            and all(callable(value) for value in (peer_factory,os_status,monotonic,sleep)))
        need(native.pid==settings.pid==pages.pid==int(recipe.binding['processIdentity'].split(':')[0])
            and settings.source_lock is pages.source_lock is recipe.lock and pages.bridge==recipe.binding['sessionId']
            and native.instance is None and native.sequence==0 and settings.previous is pages.previous is None)
        self.recipe,self.source,self.native,self.settings,self.pages=recipe,phase_source,native,settings,pages
        self._phase_source,self._phase_client=phase_source,phase_source.client
        self.peer_factory,self.os_status,self.monotonic,self.sleep=peer_factory,os_status,monotonic,sleep
        self._peer_factory=peer_factory
        self.store=PrivateFeatureState(recipe.store.path.with_name('audio-recipe-pc-actor.json'))
        self.header=PrivateFeatureState(recipe.store.path.with_name('audio-recipe-pc-actor-header.json'))
        self.lock=ScriptSourceLock(recipe.lock.path.with_name('audio-recipe-pc-actor.lock'))
        with recipe.lock.held():
            need(all(path==self.lock.path for path in recipe.store.path.parent.glob('audio-recipe-pc-*')))
        self.host=host_identity();self.peer_template=peer_factory();need(type(self.peer_template) is PicoAudioPeer)
        self.config=configuration(self.peer_template.config);self.session=self.peer_template.session_hash
        self.session_original=original(PrivateFeatureState(Path(self.config['peerState'])/'session.json'))
        self.producer_sha=producer_sha256()
        self.raw_scope=dict(audioPCActorVersion=VERSION,runId=recipe.run,binding=deepcopy(recipe.binding),
            fixtureUrl=recipe.source.fixture_url,actorCredentialSha256=hashlib.sha256(phase_source.client.token.encode()).hexdigest(),hostProcessIdentity=self.host)
        self.raw_scope_sha=json_digest(self.raw_scope);self.raws=None;self.raw_getters={}
        self.disk=self.pin=self.state=None;self.frames=[];self.frames_sha=json_digest([])
        from adapters.pico4.audio_raw_archive import AudioRawArchive,AudioRawSourceLock
        self.raw_lock=AudioRawSourceLock(ScriptSourceLock(self.store.path.with_name('audio-recipe-pc-raw.lock')))
        self.raws=AudioRawArchive(self.store.path.with_name('audio-recipe-pc-raw.json'),self.raw_scope,self.raw_lock,
            self.raw_identity,self.raw_bill,monotonic)
        self.peer_template.bind_literal_source(self.literal_source())
        self.pc_baseline=self.peer_template.status();need(self.pc_baseline['client'].get('muted') is True)
        self.scope=dict(audioPCActorVersion=VERSION,runId=recipe.run,binding=deepcopy(recipe.binding),fixtureUrl=recipe.source.fixture_url,
            recipe=str(recipe.store.path),hostProcessIdentity=self.host,configuration=self.config,peerSessionHash=self.session,
            peerSessionOriginal=deepcopy(self.session_original),producerSha256=self.producer_sha,peerBaseline=deepcopy(self.pc_baseline),
            actorCredentialSha256=hashlib.sha256(phase_source.client.token.encode()).hexdigest())
        self.scope_sha=json_digest(self.scope)
        self.history=ChatSourceChunks(self.store,self.scope);self.frames=[];self.frames_sha=json_digest([])
        self.disk=self.pin=None;self.jobs={};self.executor=None;self.state=None;self.raw_hooks={}
        with self.held():
            need(all(path==self.lock.path or path.name.startswith('audio-recipe-pc-raw.json') or path.name=='audio-recipe-pc-raw.lock' for path in recipe.store.path.parent.glob('audio-recipe-pc-*')))
            self.header.write(deepcopy(self.scope),None);self.header_ref=original(self.header)
            self.header_expected=canonical(self.scope)+b'\n'
            self.header_original=ClosedOriginalFile(self.header.path,0o600,
                lambda:require_directory(self.raws.directory,self.store.path.parent))
            self.header_bytes()
            self._save(dict(jobs=[],pending=None,sequence=0,lastObservation=None,publication=None,quiet=None,quietWindows=[]),chunks=[])
        for label,reader,attribute in (('native',native,'original'),('settings',settings,'original'),('pages',pages,'read')):
            need(not hasattr(reader,'_pico_audio_pc_actor'));reader._pico_audio_pc_actor=self
            callback=getattr(reader,attribute)
            def hook(callback=callback,label=label):
                token=self.raw_getters.pop(label,None)
                if token is None:token=self.reserve_raw(label,dict(operation='original-getter'),256*1024)
                else:self.dispatch_identity()
                raw=callback();reference=self.raws.retain(token,raw);self._raw(label,reference);return raw
            self.raw_hooks[label]=(reader,attribute,hook);setattr(reader,attribute,hook)
            if label!='pages':
                send=reader.send
                def before(command,send=send,label=label):
                    need(label not in self.raw_getters)
                    token=self.reserve_raw(label,command,256*1024);self.raw_getters[label]=token
                    return send(command)
                self.raw_hooks[label+'-send']=(reader,'send',before);reader.send=before

    def header_bytes(self):
        with self.raw_lock.held():return self._header_bytes()

    def _header_bytes(self):
        need(self.header_original.path==self.header.path==Path(self.header_ref['path'])
            and self.header_expected==canonical(self.scope)+b'\n' and json_digest(self.scope)==self.scope_sha)
        raw,physical=self.header_original.read()
        need(raw==self.header_expected and physical==self.header_ref['physical'] and hashlib.sha256(raw).hexdigest()==self.header_ref['sha256'])
        return raw

    def dispatch_identity(self):
        # Fresh role/header authority gates EVERY new source dispatch/getter.
        # It does not revoke already issued responses' archival reservations.
        try:
            need(not self.raws.stopped and host_identity()==self.host
                and self.source is self._phase_source and self.source.client is self._phase_client
                and hashlib.sha256(self.source.client.token.encode()).hexdigest()==self.raw_scope['actorCredentialSha256'])
            if hasattr(self,'header_ref'):self.header_bytes()
        except BaseException:
            self.raws.stopped=True
            raise

    def reserve_raw(self,role,command,limit,*,side_bytes=0):
        self.dispatch_identity()
        token=self.raws.reserve(role,command,limit,side_bytes=side_bytes)
        self.dispatch_identity()
        return token

    def raw_identity(self):
        # Only original archival authority: the held raw root/directory/OFD and
        # this original host/scope. A late lost Actor header or role credential
        # cannot destroy bytes already received for an issued reservation.
        self.raw_lock.assert_held()
        need(host_identity()==self.host and self.raw_scope_sha==json_digest(self.raw_scope))

    def raw_bill(self):
        # One aggregate family: every existing Recipe/Actor/history part and
        # all actual host artifact bytes, including PC WAVs/sidecars. The raw
        # journal contributes its own parts/metadata exactly once separately.
        peer_root=Path(self.peer_template.config['peerState']);paths={};stack=[self.store.path.parent]
        while stack:
            directory=stack.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    path=Path(entry.path)
                    if path==peer_root:continue
                    info=entry.stat(follow_symlinks=False);need(not stat.S_ISLNK(info.st_mode))
                    if stat.S_ISDIR(info.st_mode):stack.append(path)
                    else:
                        need(stat.S_ISREG(info.st_mode))
                        if not entry.name.startswith(('audio-recipe-pc-raw.json','feature-input.')):paths[path]=info.st_size
        # Live temporary PCM/WAV is already guaranteed by the issued receive
        # reservation; all actually retained PC originals are fresh-stat charged.
        with os.scandir(peer_root) as entries:
            for entry in entries:
                info=entry.stat(follow_symlinks=False);need(not stat.S_ISLNK(info.st_mode))
                if stat.S_ISREG(info.st_mode):paths[Path(entry.path)]=info.st_size
        stored=sum(paths.values());parts=sum('.frame-' in path.name for path in paths)
        decoded=getattr(getattr(self,'history',None),'raw_bytes',0)+self.recipe.sources.raw_bytes
        decoded+=len(canonical(self.state)) if self.state is not None else 0
        # Encoded source fields/native/PCM copies remain in their original
        # owners; actual retained artifact bytes are charged conservatively too.
        return dict(parts=parts,decodedBytes=decoded+stored,storedBytes=stored)

    def literal_source(self):
        actor=self
        class Literal:
            def before(self,action,fields):
                # Actual AudioRoutes capture:48kHz stereo PCM16, raw+WAV,
                # <=11seconds under its unchanged existing file geometry.
                side=2*(11*48000*2*2+44) if action=='receive-preview-owned' else 0
                return actor.reserve_raw('pc-'+action,dict(action=action,fields=deepcopy(fields)),1024*1024,side_bytes=side)
            def after(self,token,raw):return actor.raws.retain(token,raw)
            def rejected(self,token):actor.raws.stopped=True
            def uncertain(self,token,raw):
                if type(raw) is bytes:actor.raws.retain(token,raw)
                actor.raws.failed=True
        return Literal()

    def encode_frame(self,value):
        # Source literals are the sole history original. Typed reconstruction
        # uses their exact decoder and cannot generate an expected observation.
        result=deepcopy(value)
        for key,label in (('native','native'),('settings','settings'),('pages','pages')):
            if key in result:
                refs=[row['rawReference'] for row in result['raws'] if row['label']==label];need(refs)
                reference=refs[-1];raw=self.raws.literal(reference)
                from adapters.native_feature_observation import decode
                need(json_digest(decode(raw))==json_digest(result.pop(key)))
                result[key+'Raw']=deepcopy(reference)
        if 'packet' in result:
            refs=[row['rawReference'] for row in result.get('raws',[]) if row['label']=='pc-reply'];need(refs)
            reference=refs[-1];raw=self.raws.literal(reference)
            from adapters.native_feature_observation import decode
            need(json_digest(decode(raw.decode('utf-8')))==json_digest(result.pop('packet')))
            result['packetRaw']=deepcopy(reference)
        return result

    def held(self):
        held=ExitStack()
        try:
            for lock in sorted((self.lock,self.recipe.lock),key=lambda value:str(value.path)):held.enter_context(lock.held())
            return held
        except BaseException:held.close();raise

    def unlocked(self):
        need(self.lock._owner is None and self.recipe.lock._owner is None)

    def bound(self):
        self.lock.assert_held();self.recipe.lock.assert_held()
        self.authority()
        for reader,attribute,hook in self.raw_hooks.values():need(getattr(reader,attribute) is hook and reader._pico_audio_pc_actor is self)

    def authority(self):
        """Exact durable role authority, safe under the Primary source lock."""
        need(not self.raws.stopped)
        self.recipe.lock.assert_held()
        self.header_bytes()
        need(host_identity()==self.host and json_digest(self.scope)==self.scope_sha
            and self.store.read()==self.disk and (self.pin is None or original(self.store)==self.pin)
            and json_digest(self.state)==self.state_sha and json_digest(self.frames)==self.frames_sha
            and self.peer_factory is self._peer_factory and producer_sha256()==self.producer_sha
            and self.source is self._phase_source and self.source.client is self._phase_client
            and not isinstance(self.source.client,AdapterFixtureClient)
            and hashlib.sha256(self.source.client.token.encode()).hexdigest()==self.scope['actorCredentialSha256'])
        require_original(self.scope['peerSessionOriginal'])
        self.history.verify();self.raws.verify()
        from adapters.pico4.audio_capture_owner import read_original_file
        for frame in self.frames:
            if frame['kind']=='pc-file-original':
                base=Path(self.config['peerState'])/'audio-owner.json'
                read_original_file(base,frame['file'])
                metadata=frame['metadata'];raw=read_original_file(base,{key:value for key,value in metadata.items() if key!='raw'})
                need(raw==metadata['raw'].encode())

    def _save(self,value,*,chunks=None,phase=None):
        self.lock.assert_held();self.recipe.lock.assert_held()
        need(self.store.read()==self.disk and (self.pin is None or original(self.store)==self.pin))
        body=dict(audioPCActorVersion=VERSION,scope=deepcopy(self.scope),phase=phase or ('reading' if value['pending'] is not None else 'ready'),
            chunks=chunks if chunks is not None else self.disk['chunks'],payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.pin=original(self.store)
        self.state=deepcopy(value);self.state_sha=json_digest(self.state)

    def _begin(self,kind,ticket):
        self.bound();need(self.state['pending'] is None)
        value=deepcopy(self.state);value['pending']=dict(kind=kind,ticket=ticket,raws=[],started=self.monotonic());self._save(value)

    def _append(self,value):
        need(self.state['pending'] is not None)
        encoded=self.encode_frame(value);bill=self.raw_bill();raw=self.raws.bill()
        need(bill['parts']+raw['parts']+1<=512 and bill['decodedBytes']+raw['decodedBytes']+len(canonical(encoded))<=16*1024*1024
            and bill['storedBytes']+raw['storedBytes']+3*65536<=16*1024*1024)
        manifest=self.history.append(encoded,self.disk['chunks'])
        self.frames.append(deepcopy(value));self.frames_sha=json_digest(self.frames);self._save(deepcopy(self.state),chunks=manifest)
        return len(self.frames)-1

    def _raw(self,label,reference):
        try:
            self.lock.assert_held();self.recipe.lock.assert_held()
            value=deepcopy(self.state);need(value['pending'] is not None and len(value['pending']['raws'])<64)
            value['pending']['raws'].append(dict(label=label,rawReference=reference,hostMonotonic=self.monotonic()));self._save(value)
        except BaseException:
            self.raws.stopped=True
            raise

    def peer(self,observer=None):
        peer=self.peer_factory();need(type(peer) is PicoAudioPeer and peer.config==self.config and peer.session_hash==self.session)
        peer.bind_literal_source(self.literal_source())
        if observer is not None:
            if getattr(observer,'__self__',None) is self and getattr(observer,'__func__',None) is PicoAudioPCActor._pc_reply:
                peer.bind_reply_observer(lambda action,value:self._pc_reply(action,value,peer.last_raw_reference))
            else:peer.bind_reply_observer(observer)
        return peer

    def _pc_reply(self,action,value,reference):
        need(reference is not None)
        state=deepcopy(self.state);need(state['pending'] is not None and len(state['pending']['raws'])<64)
        state['pending']['raws'].append(dict(label='pc-reply',action=action,rawReference=reference,hostMonotonic=self.monotonic()));self._save(state)

    def job(self,ticket):
        rows=[row for row in self.state['jobs'] if row['ticket']==ticket];need(len(rows)==1);return rows[0]

    def _source(self,ticket):
        self._begin('pc-source',ticket)
        packet=self.peer(self._pc_reply).source(ticket);job=self.job(ticket)
        previous=job['provider'] if job['last'] is None else self.frames[job['last']]['packet']
        source_accept(previous,packet)
        need(packet['instance']==job['provider']['instance'] and packet['provider']==job['provider']['provider'])
        if packet['source'] is not None:need(packet['source']['armRequestId']==job['request'] and packet['source']['seconds']==job['seconds'])
        index=self._append(dict(kind='pc-source',packet=deepcopy(packet),raws=deepcopy(self.state['pending']['raws']),hostMonotonic=self.monotonic()))
        value=deepcopy(self.state);row=next(row for row in value['jobs'] if row['ticket']==ticket);row['last']=index
        value['pending']=None;self._save(value);self.bound();return packet

    def arm(self,ticket,seconds):
        self.unlocked()
        # Serialize prior complete operations without holding either source lock.
        for other,future in tuple(self.jobs.items()):
            if other!=ticket:
                self.wait_saved(other)
                try:future.result(timeout=15)
                except Exception:pass # Only the actual source below can resolve effects.
        with self.held():
            self.bound();need(self.state['pending'] is None)
            existing=[row for row in self.state['jobs'] if row['ticket']==ticket]
            if not existing:
                need(len(self.state['jobs'])<16)
                self._begin('pc-admission',ticket);before=self.peer(self._pc_reply).source(ticket)
                need(before['source'] is None and before['producerSha256']==self.producer_sha)
                request=uuid.uuid4().hex;admission=PrivateFeatureState(self.store.path.with_name('audio-recipe-pc-job-'+ticket+'.json'))
                admission.write(dict(scope=deepcopy(self.scope),ticket=ticket,request=request,seconds=seconds,provider=before),None)
                value=deepcopy(self.state);value['jobs'].append(dict(ticket=ticket,request=request,seconds=seconds,provider=before,
                    admission=original(admission),last=None,ready=None,retired=False));value['pending']=None;self._save(value)
                issue=True
            else:issue=False;request=existing[0]['request']
        if issue:
            self.unlocked()
            if self.executor is None:self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='owned-pico-pc-preview')
            self.jobs[ticket]=self.executor.submit(self.peer().receive_owned,self.recipe.run,ticket,seconds,request)
        started=self.monotonic()
        for attempt in range(51):
            with self.held():
                packet=self._source(ticket);source=packet['source'];job=self.job(ticket)
                if source is not None and source['state']=='capturing':
                    path=PrivateFeatureState(self.store.path.with_name('audio-recipe-pc-ready-'+ticket+'.json'))
                    value=dict(scope=deepcopy(self.scope),admission=deepcopy(job['admission']),packet=deepcopy(packet))
                    if job['ready'] is None:
                        path.write(value,None);state=deepcopy(self.state);next(row for row in state['jobs'] if row['ticket']==ticket)['ready']=original(path);self._save(state)
                    else:require_original(job['ready'])
                    return deepcopy(self.job(ticket)['ready'])
                need(source is None or source['state'] in ('issued','starting'))
                need(ticket in self.jobs and not self.jobs[ticket].done())
            self.unlocked();need(self.monotonic()-started<5 and attempt<50);self.sleep(.1)
        need(False)

    def check_ready(self,reference,observer=None):
        # Called under the Primary lock: immutable exact file reads, never the
        # Actor lock, sampler, future wait or a second capture command.
        self.recipe.lock.assert_held();header=require_original(self.header_ref);value=require_original(reference)
        need(header==self.scope and value['scope']==header);admission=require_original(value['admission'])
        need(admission['scope']==header);old=value['packet'];packet=self.peer(observer).source(admission['ticket']);source_accept(old,packet)
        need(packet['source'] is not None and packet['source']['state']=='capturing'
            and packet['source']['armRequestId']==admission['request'] and packet['source']['seconds']==admission['seconds'])
        need(require_original(reference)==value and require_original(value['admission'])==admission and require_original(self.header_ref)==header)
        return packet

    def wait_saved(self,ticket):
        self.unlocked();started=self.monotonic()
        for attempt in range(151):
            with self.held():
                packet=self._source(ticket);source=packet['source']
                if source is not None and source['state']=='completed':return packet
                need(source is not None and source['state'] in ('issued','starting','capturing','closed'))
            self.unlocked();need(self.monotonic()-started<15 and attempt<150);self.sleep(.1)
        need(False)

    def _observe_native(self):
        self._begin('native-observation',None);started=self.state['pending']['started']
        before=self.source.status();native=self.native.read(self.native.sequence,require_recorded_history=True)
        settings=self.settings.capture(self.recipe.run);pages=self.pages.capture();after=self.source.status(before)
        need(before['activations']==after['activations'] and before['active'] and after['active']
            and settings['source']['native']['muted']==native['audio']['muted']
            and settings['source']['native']['previewCycle']==native['audio']['recordedVoice']['cycle'])
        actual=measured_state(native);actual['open']=bool(pages['picoAudioPages']['current'])
        previous=self.state['lastObservation']
        if previous is not None:accept_history(self.frames[previous]['native']['audio']['recordedVoice'],native['audio']['recordedVoice'])
        from adapters.pico4.audio_settings_source import CLOCKS
        captured=min(native['capturedEpochMs'],native['requestedEpochMs'],settings['capturedEpochMs'],
            pages['picoAudioPages']['capturedEpochMs'],before['capturedEpochMs'],
            *(settings['source'][key] for key in CLOCKS))
        frame=dict(kind='observation',before=before,after=after,native=native,settings=settings,pages=pages,actual=actual,
            capturedEpochMs=captured,raws=deepcopy(self.state['pending']['raws']),startedMonotonic=started,hostMonotonic=self.monotonic())
        index=self._append(frame);value=deepcopy(self.state);value.update(pending=None,lastObservation=index,sequence=value['sequence']+1);self._save(value)
        self.native.guard();self.settings.guard();self.pages.guard();fresh(captured,self.native.clock_ms())
        need(0<=self.monotonic()-started<=1.5);self.bound();return deepcopy(frame)

    def observe(self):
        with self.held():
            self._begin('os-status',None);os_state=self.os_status(deepcopy(self.recipe.binding))
            self._append(dict(kind='os-status',value=deepcopy(os_state),hostMonotonic=self.monotonic()))
            exact(os_state,{'binding','running','foreground'})
            need(os_state['binding']==self.recipe.binding and os_state['running'] is True and type(os_state['foreground']) is bool)
            value=deepcopy(self.state);value['pending']=None;self._save(value)
            result=self._observe_native() if os_state['foreground'] else None
        if result is None:
            from feature_journeys.phase_fixture import PhasePending
            raise PhasePending('Original Audio process is backgrounded; no Qt/native source was acquired')
        need(0<=self.monotonic()-result['startedMonotonic']<=1.5);return result

    def _publication_receipt(self):
        packet=deepcopy(self.state['publication']);need(packet is not None)
        self._begin('publication-return',packet['ticket'])
        journal=self.source.client.request('/runs/'+self.recipe.run)
        self._append(dict(kind='publication-return',journal=deepcopy(journal),hostMonotonic=self.monotonic()))
        need(journal['runId']==self.recipe.run and journal['area']=='audio')
        rows=[row for row in journal['entries'] if row['actorSequence']==packet['actorSequence']]
        need(len(rows)==1 and all(rows[0][key]==item for key,item in packet.items()))
        value=deepcopy(self.state);value.update(pending=None,publication=None);self._save(value);self.bound()

    def publish(self):
        with self.held():
            self.bound()
            if self.state['publication'] is not None:self._publication_receipt()
        frame=self.observe()
        with self.held():
            self.bound();need(self.state['publication'] is None)
            packet=dict(ticket=frame['after']['activations'][-1]['ticket'],actor='owned-observer',actorSequence=self.state['sequence'],
                capturedEpochMs=frame['capturedEpochMs'],facts=projection('audio',frame['actual']))
            value=deepcopy(self.state);value['publication']=packet;self._save(value)
            self.source.client.request('/runs/'+self.recipe.run+'/samples',deepcopy(packet))
            self._publication_receipt();fresh(packet['capturedEpochMs'],self.native.clock_ms())
            need(0<=self.monotonic()-frame['startedMonotonic']<=1.5);self.bound()
            return deepcopy(packet)

    def _finish_retirement(self,ticket,packet):
        job=self.job(ticket);previous=job['provider'] if job['last'] is None else self.frames[job['last']]['packet']
        source_accept(previous,packet)
        need(packet['source'] is not None and packet['source']['state']=='retired'
            and packet['source']['armRequestId']==job['request'] and packet['source']['exit'] is not None)
        index=self._append(dict(kind='pc-source',packet=deepcopy(packet),raws=deepcopy(self.state['pending']['raws']),hostMonotonic=self.monotonic()))
        value=deepcopy(self.state);row=next(row for row in value['jobs'] if row['ticket']==ticket)
        row.update(last=index,retired=True);value['pending']=None;self._save(value);self.bound()

    def retire_recorders(self):
        self.unlocked()
        for ticket in tuple(row['ticket'] for row in self.state['jobs']):
            with self.held():
                self.bound();pending=deepcopy(self.state['pending']);retired=self.job(ticket)['retired']
            if pending is not None:
                need(pending['kind']=='pc-retire')
                if pending['ticket']!=ticket:need(retired);continue
                # A lost reply resolves only from a new original query. Never
                # replay the earlier retirement command or receive operation.
                with self.held():self._finish_retirement(ticket,self.peer(self._pc_reply).source(ticket))
                continue
            if retired:
                with self.held():need(self._source(ticket)['source']['state']=='retired')
                continue
            self.wait_saved(ticket);future=self.jobs.get(ticket);need(future is not None and future.done())
            try:future.result()
            except Exception:pass # Completed original source + files, never the reply, qualify the effect.
            with self.held():
                self._begin('pc-retire',ticket);peer=self.peer(self._pc_reply);packet,raw=peer.original(self.recipe.run,ticket)
                source=self.frames[self.job(ticket)['last']]['packet']['source']
                need(raw is not None and packet['original']==source['original'])
                self._append(dict(kind='pc-file-original',packet=deepcopy(packet),file=deepcopy(peer.last_file),metadata=deepcopy(peer.last_metadata),
                    raws=deepcopy(self.state['pending']['raws']),hostMonotonic=self.monotonic()))
                self._finish_retirement(ticket,peer.retire_recorder(ticket))
        self.unlocked()
        if self.executor is not None:
            need(all(future.done() for future in self.jobs.values()));self.executor.shutdown(wait=True);self.executor=None

    def quiet(self):
        self.unlocked();first=last=None;started=None;first_pc=None;previous_pc=None
        from adapters.pico4.audio_settings_source import CLOCKS
        for attempt in range(41):
            frame=self.observe();packets={}
            for ticket in tuple(row['ticket'] for row in self.state['jobs']):
                with self.held():
                    packet=self._source(ticket);need(packet['source'] is not None and packet['source']['state']=='retired')
                    packets[ticket]=packet
            with self.held():
                self.bound();need(not frame['actual']['recording'] and not frame['actual']['preview'] and not frame['actual']['open'])
                baseline=next(row for row in self.frames if row['kind']=='observation')
                need(frame['actual']['muted']==baseline['actual']['muted'])
                peer_status=self.peer().status();need(peer_status['client'].get('muted') is True)
                key=json_digest(dict(actual=frame['actual'],voice=frame['native']['audio']['recordedVoice'],
                    instance=frame['native']['instance'],lifecycle=frame['native']['lifecycle'],
                    properties=frame['settings']['source']['properties'],native=frame['settings']['source']['native'],
                    gains=frame['settings']['source']['mixerGains'],peak=frame['settings']['source']['inputPeakValuesEnabled'],
                    lifetime=frame['settings']['source'].get('previewLifetime'),pages=frame['pages']['picoAudioPages']['originals']))
                stamps=[frame['native']['capturedEpochMs'],frame['pages']['picoAudioPages']['capturedEpochMs'],
                    *(frame['settings']['source'][name] for name in CLOCKS)]
                pc={ticket:packet['capturedEpochMs'] for ticket,packet in packets.items()};now=self.monotonic()
                if first is None:
                    first=list(stamps);started=now;first_pc=deepcopy(pc);digest=key
                else:
                    need(key==digest and all(new>=old for new,old in zip(stamps,last)) and all(pc[ticket]>=previous_pc[ticket] for ticket in pc))
                    # Quiet cannot bridge an unobserved long host/native gap.
                    if now-previous_host>.5 or any(new-old>500 for new,old in zip(stamps,last)) or any(pc[ticket]-previous_pc[ticket]>500 for ticket in pc):
                        value=deepcopy(self.state);need(len(value['quietWindows'])<8)
                        value['quietWindows'].append(deepcopy(value['quiet']));self._save(value)
                        first=list(stamps);started=now;first_pc=deepcopy(pc)
                complete=now-started>=3 and all(new-old>=3000 for new,old in zip(stamps,first)) and all(pc[ticket]-first_pc[ticket]>=3000 for ticket in pc)
                value=deepcopy(self.state);value['quiet']=dict(first=first,last=stamps,firstHost=started,lastHost=now,
                    firstPC=first_pc,lastPC=pc,key=digest,complete=complete);self._save(value);self.bound()
                self.native.guard();fresh(frame['capturedEpochMs'],self.native.clock_ms());need(0<=self.monotonic()-frame['startedMonotonic']<=1.5)
                last=list(stamps);previous_pc=deepcopy(pc);previous_host=now
            need(0<=self.monotonic()-frame['startedMonotonic']<=1.5)
            if complete:return dict(digitalRecorderLeasesRetired=True,originalFilesRetained=True,physicalAcousticObserved=False,fullAudioQualified=False)
            self.unlocked();need(attempt<40);self.sleep(.25)
        need(False)
