"""Original configured Chat assignment and V8 compilation, without input.

The fixed Phone Chat selection is reused with Pico's normalized engine keys and
complete original manager membership. A name or expected hash is never sent to
the native observation getter.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import time

from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.independent_chat_receiver import binding_pid
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_observation import NativeScriptObservation,validate as script_packet
from adapters.native_script_roots import NativeScriptRoots,root_url,validate as roots_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import MAX_FRAMES,same
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1
SOURCE_PATH='scripts/communityScripts/armored-chat/armored_chat.js'
PINS=Path(__file__).resolve().parents[2]/'feature_journeys/chat-script-source.v1.json'


def pins():
    """Reviewed Chat bytes only; the different Pico peer script is not adopted."""
    value=json.loads(PINS.read_text())
    exact(value,{'chatScriptSourceVersion','path','encoding','codeUnits','utf8Sha256','sha256'})
    need(type(value['chatScriptSourceVersion']) is int and value['chatScriptSourceVersion']==VERSION
        and value['path']==SOURCE_PATH and value['encoding']=='utf-16le-code-units'
        and integer(value['codeUnits'],1,4194304)
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('utf8Sha256','sha256')))
    raw=(PINS.parents[3]/SOURCE_PATH).read_bytes();units=raw.decode('utf-8').encode('utf-16le')
    need(hashlib.sha256(raw).hexdigest()==value['utf8Sha256'] and len(units)//2==value['codeUnits']
        and hashlib.sha256(units).hexdigest()==value['sha256'])
    return value


def identity(before,scripts,after,*,pid,epoch):
    """Recompute a root/script/root original transaction, never feature success."""
    for packet in (before,after):
        need(type(packet) is dict)
        roots_packet(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),
            action='feature-script-roots-observe'),pid,epoch)
    roots_packet(after,dict(schemaVersion=1,commandId=after['commandId'],action='feature-script-roots-observe'),
        pid,epoch,previous=before)
    need(type(scripts) is dict)
    script_packet(scripts,scripts.get('requestId'),pid,epoch)
    need(before['instance']==scripts['instance']==after['instance']
        and before['requestedEpochMs']<=before['capturedEpochMs']<=scripts['requestedEpochMs']
        <=scripts['capturedEpochMs']<=after['requestedEpochMs']<=after['capturedEpochMs']
        and after['capturedEpochMs']-before['requestedEpochMs']<=1500)
    fresh(before['requestedEpochMs'],epoch)
    reviewed=pins();root=root_url(before['source']['defaultScriptsUrl'])
    physical=root+SOURCE_PATH[len('scripts/'):]
    names={physical}
    if root.startswith('file:'):names.add('file:///~//'+SOURCE_PATH[len('scripts/'):])
    source=scripts['source']
    need(source.get('sourceIdentityVersion')==source.get('membershipSourceVersion')==source.get('compiledSourceVersion')==1
        and source['membership']['complete'])
    # Include assigned managers which have not appeared in the running table;
    # a second pending load of this actual physical Chat is not absence.
    assigned=[row for row in source['membership']['managers'] if row['assigned'] and row['url']==physical]
    engines=[row for row in source['engines'] if row['running'] and not row['stopping'] and not row['finished']]
    selected=[row for row in engines if row['url'] in names]
    need(len(assigned)==len(selected)==1)
    engine=selected[0];manager=assigned[0];code=engine['code'];compiled=engine['compiled']
    need(manager['instance']==engine['required']['instance'] and manager['assignedEpochMs']<=code['submittedEpochMs']
        and code['submitted'] and all(code[key]==reviewed[key] for key in ('encoding','codeUnits','sha256'))
        and compiled['complete'])
    matches=[row for row in compiled['compilations'] if row['resourceName'] in names]
    need(len(matches)==1 and matches[0]['compiledEpochMs']>=code['submittedEpochMs']
        and all(matches[0][key]==code[key] for key in ('encoding','codeUnits','sha256')))
    for other in engines:
        need(other['compiled']['complete'])
        if other is engine:continue
        # A second compiled copy in another actual manager cannot masquerade
        # as an unrelated script merely by changing its public table URL.
        need(not any(row['resourceName'] in names or row['sha256']==reviewed['sha256']
            for row in other['compiled']['compilations']))
    return deepcopy(dict(url=engine['url'],assignedUrl=physical,manager=manager['instance'],
        loadGeneration=manager['loadGeneration'],assignedEpochMs=manager['assignedEpochMs'],
        code=code,compilation=matches[0]))


class ChatScriptSource:
    """Durable passive source transactions, serialized by the parent lock.

    Interrupted reads and orphan chunks are retained. Reconstruction replays
    only fully committed originals; every new capture still queries natively.
    """
    def __init__(self,run,role,binding,roots,scripts,store,source_lock,*,monotonic=time.monotonic):
        identifier(run)
        need(role in ('primary','actor') and isinstance(roots,NativeScriptRoots)
            and isinstance(scripts,NativeScriptObservation) and not roots.ios and not scripts.ios
            and isinstance(store,PrivateFeatureState) and isinstance(source_lock,ScriptSourceLock)
            and source_lock.path==store.path.with_name('script-sources.lock') and callable(monotonic))
        self.binding=deepcopy(context(binding));need(roots.pid==scripts.pid==binding_pid(binding))
        need(roots.last is None and scripts.instance is None and scripts.sequence==0)
        source_lock.assert_held()
        self.run,self.role,self.roots,self.scripts,self.store,self.lock,self.monotonic=run,role,roots,scripts,store,source_lock,monotonic
        self.failed=False;self.frames=[]
        self.base=dict(chatScriptObservationVersion=VERSION,runId=run,role=role,binding=self.binding,
            phase='ready',revision=0,chunks=[])
        self.history=ChatSourceChunks(store,{key:value for key,value in self.base.items() if key not in ('phase','revision','chunks')})
        self.previous=store.read()
        if self.previous is None:self.history.inventory(0)
        else:
            exact(self.previous,set(self.base))
            need(all(same(self.previous[key],self.base[key]) for key in set(self.base)-{'phase','revision','chunks'})
                and self.previous['phase']=='ready' and integer(self.previous['revision'],0,2*MAX_FRAMES))
            self.frames=self.history.load(self.previous['chunks']);need(self.previous['revision']==2*len(self.frames))
            for index,frame in enumerate(self.frames):self._validate(frame,self.frames[:index])
            if self.frames:
                roots.restore(self.frames[-1]['after'])
                scripts.restore_history([frame['scripts'] for frame in self.frames])
            self.base=deepcopy(self.previous)

    def _validate(self,frame,previous):
        exact(frame,{'ticket','afterEpochMs','before','scripts','after'})
        identifier(frame['ticket']);need(integer(frame['afterEpochMs'],1)
            and frame['before']['requestedEpochMs']>=frame['afterEpochMs'])
        selected=identity(frame['before'],frame['scripts'],frame['after'],pid=self.roots.pid,epoch=frame['after']['capturedEpochMs'])
        if previous:
            old=previous[-1]
            need(all(frame['ticket']!=row['ticket'] for row in previous)
                and selected==identity(old['before'],old['scripts'],old['after'],pid=self.roots.pid,epoch=old['after']['capturedEpochMs']))
            roots_packet(frame['before'],dict(schemaVersion=1,commandId=frame['before']['commandId'],
                action='feature-script-roots-observe'),self.roots.pid,frame['after']['capturedEpochMs'],previous=old['after'])
            need(frame['scripts']['sequence']>old['scripts']['sequence'] and frame['scripts']['requestId']!=old['scripts']['requestId'])
        return selected

    def _write(self,value):
        need(same(self.store.read(),self.previous));self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=self.base=deepcopy(value)

    def capture(self,ticket,after_epoch):
        started=last=self.monotonic();need(number(started,0,1e15))
        barrier=None
        def check():
            nonlocal last
            self.lock.assert_held()
            need(self.roots.guard() is not False and self.scripts.guard() is not False)
            now=self.monotonic();need(number(now,last,started+1.5));last=now
        try:
            identifier(ticket);need(not self.failed and integer(after_epoch,1))
            with self.lock.held():
                check();self.history.verify();need(self.base['phase']=='ready' and len(self.frames)<MAX_FRAMES)
                barrier=self.roots.clock_ms();need(integer(barrier,after_epoch));check()
                self._write({**self.base,'phase':'reading','revision':self.base['revision']+1});check()
                before=self.roots.read(0 if self.roots.last is None else self.roots.last['sequence']);check()
                scripts=self.scripts.read(self.scripts.sequence,require_effects=True,require_code_identity=True,
                    require_load_history=True,require_membership=True);check()
                after=self.roots.read(before['sequence']);check()
                frame=dict(ticket=ticket,afterEpochMs=after_epoch,before=before,scripts=scripts,after=after)
                selected=self._validate(frame,self.frames);candidate=deepcopy(frame);result=deepcopy(selected)
                self._write({**self.base,'phase':'ready','revision':self.base['revision']+1,
                    'chunks':self.history.append(frame,self.base['chunks'])})
                self.history.verify();check()
                measured=self.monotonic();need(number(measured,last,started+1.5))
                epoch=self.roots.clock_ms();need(integer(epoch,barrier));fresh(before['requestedEpochMs'],epoch)
                final=self.monotonic();need(number(final,measured,started+1.5)
                    and max(epoch-before['requestedEpochMs']+math.ceil((final-measured)*1000),
                        barrier-before['requestedEpochMs']+math.ceil((final-started)*1000))<=1500)
                self.frames.append(candidate);return result
        except Exception:
            self.failed=True
            raise NativeUIError('Original compiled Chat source is unavailable; interrupted source history is retained') from None
