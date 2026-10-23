"""Private browser VM transactions on original compilation and QObject sources.

Reuses the existing immutable original-frame container; no input or public
capability is provided. Service/table absence never retires a live Qt object.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import re
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_observation import NativeScriptObservation,validate as script_packet
from adapters.native_script_object_lifetimes import NativeScriptObjectLifetimes,validate as object_packet,selected,ACTION
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import MAX_FRAMES,canonical,same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.browser_source import fixture
from adapters.pico4.browser_measurements import browser_status
from feature_journeys.contract import identifier
from feature_journeys.fixtures import pinned_resource

VERSION=1


def reviewed():
    raw=pinned_resource('web-source/tablet-feature-client.js');units=raw.decode('utf-8').encode('utf-16le')
    return dict(encoding='utf-16le-code-units',codeUnits=len(units)//2,sha256=hashlib.sha256(units).hexdigest()),raw


def original_identity(scripts,url):
    source=scripts['source'];pins,_raw=reviewed()
    need(source.get('sourceIdentityVersion')==source.get('membershipSourceVersion')==source.get('compiledSourceVersion')==1
        and source.get('loadSourceVersion')==source.get('effectSourceVersion')==1 and source['loads']['complete']
        and source['membership']['complete'])
    assigned=[row for row in source['membership']['managers'] if row['assigned'] and row['url']==url]
    engines=[row for row in source['engines'] if row['url']==url]
    need(len(assigned)==len(engines)==1)
    member,engine=assigned[0],engines[0]
    need(engine['running'] and not engine['stopping'] and not engine['finished']
        and engine['required']['instance']==member['instance'] and engine['code']['submitted']
        and all(engine['code'][key]==value for key,value in pins.items()) and engine['compiled']['complete'])
    compiled=[row for row in engine['compiled']['compilations'] if row['resourceName']==url]
    need(len(compiled)==1 and all(compiled[0][key]==value for key,value in pins.items())
        and member['assignedEpochMs']<=engine['code']['submittedEpochMs']<=compiled[0]['compiledEpochMs'])
    return dict(manager=member['instance'],membership=deepcopy(member),code=deepcopy(engine['code']),compilation=deepcopy(compiled[0]))


def join(frame,url,pid,*,origin=None):
    exact(frame,{'objectsBefore','scripts','objectsAfter','http','hostMonotonic'})
    need(number(frame['hostMonotonic'],0,1e15))
    before,scripts,after=frame['objectsBefore'],frame['scripts'],frame['objectsAfter'];epoch=after['capturedEpochMs']
    for packet in (before,after):object_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=ACTION),pid,epoch)
    object_packet(after,dict(schemaVersion=1,commandId=after['commandId'],action=ACTION),pid,epoch,previous=before)
    script_packet(scripts,scripts['requestId'],pid,epoch)
    need(before['instance']==scripts['instance']==after['instance']
        and before['requestedEpochMs']<=before['capturedEpochMs']<=scripts['requestedEpochMs']
        <=scripts['capturedEpochMs']<=after['requestedEpochMs']<=epoch and epoch-before['requestedEpochMs']<=1500)
    source=scripts['source'];pins,raw=reviewed()
    need(source.get('sourceIdentityVersion')==source.get('membershipSourceVersion')==source.get('compiledSourceVersion')==1
        and source.get('loadSourceVersion')==source.get('effectSourceVersion')==1 and source['loads']['complete']
        and source['membership']['complete'])
    if origin is None:origin=original_identity(scripts,url)
    exact(origin,{'manager','membership','code','compilation'})
    identifier(origin['manager'])
    life_before=selected(before,origin['manager']);life_after=selected(after,origin['manager'])
    need(life_before['registeredEpochMs']<=origin['membership']['assignedEpochMs']
        and life_before['workerCreated'] and life_before['workerCreatedEpochMs']<=origin['code']['submittedEpochMs'])
    members=[row for row in source['membership']['managers'] if row['instance']==origin['manager'] or row['assigned'] and row['url']==url]
    need(len(members)<=1 and (not members or members[0]==origin['membership']))
    engines=[]
    for engine in source['engines']:
        need(engine['compiled']['complete'])
        own=engine['required']['instance']==origin['manager']
        if own:
            engines.append(engine)
            need(engine['url']==url and engine['code']==origin['code']
                and [row for row in engine['compiled']['compilations'] if row['resourceName']==url]==[origin['compilation']])
        else:
            need(engine['url']!=url and engine['code']['sha256']!=pins['sha256']
                and not any(row['resourceName']==url or row['sha256']==pins['sha256'] for row in engine['compiled']['compilations']))
    need(len(engines)<=1)
    if not any(life_before[key] for key in ('managerAlive','engineAlive','workerAlive')):need(not members and not engines)
    status=browser_status(frame['http']);ticket=url.rsplit('/',2)[-2]
    receipts=[row for row in status['responses'] if row['ticket']==ticket and row['resource']=='client.js' and row['origin']=='primary']
    need(len(receipts)==1 and receipts[0]['status']==200 and receipts[0]['sha256']==hashlib.sha256(raw).hexdigest()
        and receipts[0]['bytes']==len(raw) and receipts[0]['capturedEpochMs']<=origin['code']['submittedEpochMs']+250)
    retired=not members and not engines and not any(row[key] for row in (life_before,life_after)
        for key in ('managerAlive','engineAlive','workerAlive'))
    return deepcopy(origin),dict(retired=retired,running=bool(engines and engines[0]['running'] and not engines[0]['stopping'] and not engines[0]['finished']))


class PicoBrowserVm:
    def __init__(self,run,url,script_url,role,binding,scripts,objects,store,lock,http):
        fixture(run,url);identifier(run);context(binding)
        need(role in ('primary','actor') and type(script_url) is str and script_url.startswith(url+'tickets/')
            and re.fullmatch('[0-9a-f]{32}/client\\.js',script_url[len(url+'tickets/'):])
            and isinstance(scripts,NativeScriptObservation) and not scripts.ios and isinstance(objects,NativeScriptObjectLifetimes)
            and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(http)
            and scripts.pid==objects.pid==int(binding['processIdentity'].split(':',1)[0])
            and scripts.instance is None and objects.last is None)
        lock.assert_held();self.scripts,self.objects,self.store,self.lock,self.http=scripts,objects,store,lock,http
        self.scope=dict(picoBrowserVmVersion=VERSION,runId=run,fixtureUrl=url,scriptUrl=script_url,role=role,binding=deepcopy(binding))
        self.chunks=ChatSourceChunks(store,self.scope);self.previous=store.read();self._frames=();self._frame_hashes=();self._sealed_frames=self._frames;self._sealed_hashes=self._frame_hashes
        self.origin=None;self.failed=False;self.windows=[]
        if self.previous is None:self.chunks.inventory(0)
        else:
            exact(self.previous,set(self.scope)|{'phase','revision','chunks','quiet'})
            need(all(same(self.previous[key],value) for key,value in self.scope.items()) and self.previous['phase']=='ready')
            self.windows=deepcopy(self.previous['quiet']);need(type(self.windows) is list and len(self.windows)<=16)
            frames=self.chunks.load(self.previous['chunks']);need(self.previous['revision']==2*len(frames)+len(self.windows))
            for index,frame in enumerate(frames):
                self.validate(frame,frames[index-1:index] if index else [])
                self._append_cache(canonical(frame),json_digest(frame))
            for window in self.windows:
                exact(window,{'first','last','afterEpochMs'});need(self.window(window['first'],window['last'],window['afterEpochMs']))
            scripts.restore_history([row['scripts'] for row in frames])
            if frames:objects.restore(frames[-1]['objectsAfter'])
        self.cached_digest=self.cache_digest()

    @property
    def frames(self):
        """Inspection copies; original VM transactions remain immutable bytes."""
        return [json.loads(raw) for raw in self._frames]

    @property
    def frame_count(self):return len(self._frames)

    def frame(self,index):
        need(self._frames is self._sealed_frames and type(index) is int and -len(self._frames)<=index<len(self._frames))
        return json.loads(self._frames[index])

    def frame_hash(self,index):
        need(self._frame_hashes is self._sealed_hashes and type(index) is int and -len(self._frame_hashes)<=index<len(self._frame_hashes))
        return self._frame_hashes[index]

    def _append_cache(self,raw,sha256):
        # Only a fully validated new/cold original may enter this immutable
        # prefix. Fresh capture performs this work before its last clock fence.
        need(type(raw) is bytes and hashlib.sha256(raw).hexdigest()==sha256)
        self._frames=self._frames+(raw,);self._frame_hashes=self._frame_hashes+(sha256,)
        self._sealed_frames,self._sealed_hashes=self._frames,self._frame_hashes

    def cache_digest(self):return json_digest(dict(scope=self.scope,frames=list(self._frame_hashes),origin=self.origin,quiet=self.windows))

    def verify(self):
        self.lock.assert_held();need(not self.failed and self._frames is self._sealed_frames and self._frame_hashes is self._sealed_hashes
            and same(self.store.read(),self.previous) and self.cache_digest()==self.cached_digest);self.chunks.verify()

    def validate(self,frame,previous):
        from adapters.pico4.browser_vm_grammar import validate_frame
        self.origin,facts=validate_frame(frame,previous,self.origin,self.scope['scriptUrl'],self.scripts.pid)
        return facts

    def write(self,phase,chunks,*,windows=None):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        value={**self.scope,'phase':phase,'revision':(self.previous['revision'] if self.previous else 0)+1,'chunks':chunks,
            'quiet':deepcopy(self.windows if windows is None else windows)}
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def capture(self):
        self.lock.assert_held();need(not self.failed and self.frame_count<MAX_FRAMES)
        started=self.objects.monotonic();barrier=self.objects.clock_ms();need(number(started,0,1e15) and integer(barrier,1))
        def final(earliest):
            need(self.scripts.guard() is not False and self.objects.guard() is not False)
            measured=self.objects.monotonic();epoch=self.objects.clock_ms();ended=self.objects.monotonic()
            need(number(measured,started,started+1.5) and number(ended,measured,started+1.5) and integer(epoch,barrier))
            fresh(earliest,epoch);need(max(epoch-earliest+math.ceil((ended-measured)*1000),barrier-earliest+math.ceil((ended-started)*1000))<=1500)
        try:
            self.verify();manifest=[] if self.previous is None else self.previous['chunks']
            self.write('reading',manifest);final(barrier)
            before=self.objects.read(0 if self.objects.last is None else self.objects.last['sequence'])
            scripts=self.scripts.read(self.scripts.sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
            after=self.objects.read(before['sequence']);http=self.http()
            frame=dict(objectsBefore=before,scripts=scripts,objectsAfter=after,http=http,hostMonotonic=self.objects.monotonic())
            facts=self.validate(frame,[] if self.frame_count==0 else [self.frame(-1)])
            sha256=json_digest(frame);candidate=canonical(frame);result=deepcopy(facts)
            self.write('ready',self.chunks.append(frame,manifest));self.chunks.verify();final(before['requestedEpochMs'])
            self._append_cache(candidate,sha256);self.cached_digest=self.cache_digest();return result
        except Exception:
            self.failed=True;raise NativeUIError('Original browser VM ownership is retained; source transaction did not complete') from None

    def window(self,first,last,after_epoch):
        from adapters.pico4.browser_vm_grammar import window
        return window(self.frame_count,self.frame,first,last,after_epoch,self.origin,self.scope['scriptUrl'],self.scripts.pid)

    def quiet(self,after_epoch):
        """Record an exact complete suffix once; later reads retain its originals."""
        self.verify();need(integer(after_epoch,1))
        for window in self.windows:
            if window['afterEpochMs']==after_epoch:return self.window(window['first'],window['last'],after_epoch)
        rows=[]
        for index in reversed(range(self.frame_count)):
            frame=self.frame(index)
            _origin,facts=join(frame,self.scope['scriptUrl'],self.scripts.pid,origin=self.origin)
            if not facts['retired'] or min(frame['objectsBefore']['requestedEpochMs'],frame['scripts']['requestedEpochMs'],
                    frame['objectsAfter']['requestedEpochMs'])<after_epoch:break
            rows.insert(0,frame)
        if not rows:return False
        first,last=self.frame_count-len(rows),self.frame_count-1
        if not self.window(first,last,after_epoch):return False
        need(len(self.windows)<16);started=self.objects.monotonic()
        windows=self.windows+[dict(first=first,last=last,afterEpochMs=after_epoch)]
        self.write('ready',self.previous['chunks'],windows=windows);self.windows=deepcopy(windows)
        self.cached_digest=self.cache_digest()
        need(self.scripts.guard() is not False and self.objects.guard() is not False)
        measured=self.objects.monotonic();epoch=self.objects.clock_ms();ended=self.objects.monotonic()
        captured=self.frame(-1)['objectsBefore']['source']['capturedEpochMs']
        need(number(measured,started,started+1.5) and number(ended,measured,started+1.5))
        fresh(captured,epoch);need(epoch-captured+math.ceil((ended-measured)*1000)<=1500)
        return True
