"""One normal HOME/return, joined to original autonomous Qt/keyboard history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import math
import time
import uuid

from adapters.chat_journey.samples import ChatSamples,compose
from adapters.chat_journey.erase_restore import references
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.pico4.lifecycle_background_source import NativeLifecycleBackground,command,validate,accept
from adapters.pico4.lifecycle_source import LIVENESS
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import pack,unpack,same

VERSION=1
PHASES=('sampling','arm-issued','armed','background-issued','background-observed','foreground-issued',
    'foreground-observed','quiet','release-issued','observed','failed')


def original_packet(record,pid):
    exact(record,{'raw','sha256'});raw=record['raw']
    need(type(raw) is str and len(raw.encode())<=262144 and hashlib.sha256(raw.encode()).hexdigest()==record['sha256'])
    value=decode(raw);operation='observe'
    if value.get('performed'):operation='arm' if value.get('commandId')==value.get('armCommandId') else 'release'
    request=dict(schemaVersion=1,commandId=value['commandId'],action='feature-lifecycle-background',operation=operation,runId=value['runId'])
    if operation!='observe':request.update(ownerInstance=value['instance'],intentSequence=value['lastIntentSequence'])
    validate(value,request,pid,value['capturedEpochMs']);return value


def decode_owner(record):
    exact(record,{'chatBackgroundVersion','runId','binding','peerBinding','transcripts','payload'})
    need(type(record['chatBackgroundVersion']) is int and record['chatBackgroundVersion']==VERSION)
    context(record['binding']);context(record['peerBinding']);rows=unpack(record['payload']);need(len(rows)==1);state=rows[0]
    exact(state,{'phase','afterEpochMs','before','after','quiet','sourceInputs','sources','os'})
    need(state['phase'] in PHASES and integer(state['afterEpochMs'],1) and type(state['sourceInputs']) is list
        and len(state['sourceInputs'])<=2 and type(state['sources']) is list and len(state['sources'])<=16
        and type(state['os']) is list and len(state['os'])<=128 and type(state['quiet']) is list and len(state['quiet'])<=64)
    previous=None;pid=int(record['binding']['processIdentity'].split(':')[0])
    for index,request in enumerate(state['sourceInputs']):
        command(request);need(request['runId']==record['runId'] and request['operation']==('arm' if index==0 else 'release'))
        if index:need(request['ownerInstance']==state['sourceInputs'][0]['ownerInstance'] and request['intentSequence']==state['sourceInputs'][0]['intentSequence']+1)
    for source in state['sources']:
        value=original_packet(source,pid);need(value['runId']==record['runId']);accept(previous,value);previous=value
    for row in state['os']:
        exact(row,{'label','hostMonotonic','packet'});need(row['label'] in ('before-home','background','before-resume','foreground','recovery') and number(row['hostMonotonic'],0,1e15))
        status(row['packet'],record['binding'])
    return state


def status(packet,binding):
    exact(packet,{'binding','foreground','running'});need(same(packet['binding'],binding) and packet['running'] is True and type(packet['foreground']) is bool)
    return packet


class ChatBackground:
    """A restored timer is not Qt-object retirement or complete Chat cleanup."""
    def __init__(self,roles,source_factory,os_adapter,target,store,*,monotonic=time.monotonic,sleep=time.sleep):
        need(type(roles) is tuple and len(roles)==2 and all(isinstance(role,ChatSamples) and role.vr and not role.component_only for role in roles)
            and roles[0].role=='primary' and roles[1].role=='actor' and roles[0].run==roles[1].run
            and roles[0].binding==roles[1].binding and roles[0].peer_binding==roles[1].peer_binding
            and all(first is second for first,second in zip(roles[0].locks,roles[1].locks))
            and isinstance(os_adapter,PicoGraphicsBinding) and all(callable(f) for f in (source_factory,monotonic,sleep))
            and store.path not in {role.store.path for role in roles})
        self.roles,self.os,self.target,self.store=roles,os_adapter,target,store
        self.run_id,self.binding=roles[0].run,roles[0].binding
        self.monotonic,self.sleep=monotonic,sleep;self.last_clock=self.deadline=None;self.state=None
        self.scope=dict(chatBackgroundVersion=VERSION,runId=self.run_id,binding=self.binding,peerBinding=roles[0].peer_binding,transcripts=[role.store.path.name for role in roles])
        self.previous=store.read()
        if self.previous is not None:
            need(all(same(self.previous.get(key),value) for key,value in self.scope.items()))
            self.state=decode_owner(self.previous)
            for refs in ([self.state['before']] if self.state['before'] is not None else [])+([self.state['after']] if self.state['after'] is not None else []):self.frames(refs)
            for row in self.state['quiet']:
                exact(row,{'roles','hostMonotonic'});self.frames(row['roles']);need(number(row['hostMonotonic'],0,1e15))
        self.source=source_factory(self.intent)
        need(isinstance(self.source,NativeLifecycleBackground) and self.source.pid==roles[0].primary.pid
            and self.source.source_lock is roles[0].locks[0] and self.source.last is None)
        if self.state is not None and self.state['sources']:self.source.restore(self.state['sources'][-1]['raw'])
        if self.state is not None and self.state['phase']=='observed':self.closed_history()

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock)
            and (self.deadline is None or value<=self.deadline));self.last_clock=value;return value

    def save(self,phase=None):
        if phase is not None:self.state['phase']=phase
        need(same(self.store.read(),self.previous));value={**self.scope,'payload':pack([self.state])}
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,request):
        command(request);need(self.state is not None and request['runId']==self.run_id and len(self.state['sourceInputs'])<2
            and request['operation']==('arm' if not self.state['sourceInputs'] else 'release'))
        self.state['sourceInputs'].append(deepcopy(request));self.save(request['operation']+'-issued');self.now()

    def record_source(self,value,phase=None):
        need(same(value,self.source.last) and self.source.last_raw is not None and len(self.state['sources'])<16)
        self.state['sources'].append(dict(raw=self.source.last_raw,sha256=self.source.last_sha256));self.save(phase);self.now()

    def frames(self,refs):
        need(type(refs) is list and len(refs)==2);frames=[]
        for role,reference in zip(self.roles,refs):
            exact(reference,{'index','ticket','queries','epochs'});need(integer(reference['index'],0,len(role.frames)-1));frame=role.frames[reference['index']]
            need(reference['ticket']==frame['ticket'] and reference['queries']==[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')]
                and reference['epochs']==[frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')]
                and 'state' in compose(role.run,frame,role.primary.pid,role.peer.pid,vr=True))
            frames.append(frame)
        return frames

    def fresh_current(self,started,*,background=False):
        need(self.source.guard() is not False)
        for role in self.roles:
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
        clocks=[]
        for role in self.roles:
            frame=role.frames[-1]
            for reader,oldest in ((role.primary,min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),(role.peer,frame['peer']['capturedEpochMs'])):
                if background and reader is role.primary:oldest=min(oldest,self.source.last['capturedEpochMs'])
                measured=self.now();epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
        finished=self.now();need(finished-started<=1.5 and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))

    def pair(self):
        started=self.now();observed=[role.read(uuid.uuid4().hex,self.state['afterEpochMs']) for role in self.roles]
        need(observed[0]['state']==observed[1]['state']);self.fresh_current(started);self.fresh_started=started;return observed

    def os_status(self,label):
        started=self.now();packet=self.os._graphics_lifecycle_status(self.target,self.binding);status(packet,self.binding)
        need(self.now()-started<=1.5 and len(self.state['os'])<128)
        self.state['os'].append(dict(label=label,hostMonotonic=self.now(),packet=deepcopy(packet)));self.save();return packet

    def wait_os(self,foreground,label):
        started=self.now()
        for _index in range(51):
            value=self.os_status(label)
            if value['foreground'] is foreground:return value
            need(self.now()-started<5);self.sleep(.1)
        need(False)

    def stable(self,initial,current):
        for role,before,after in zip(self.roles,initial,current):
            a=compose(self.run_id,before,role.primary.pid,role.peer.pid,vr=True)['state'];b=compose(self.run_id,after,role.primary.pid,role.peer.pid,vr=True)['state']
            need(a['open'] and a['channel']=='domain' and a['draft']=='' and b=={**a,'focused':False,'keyboard':False}
                and after['view']['source']['ui']['generation']==before['view']['source']['ui']['generation'])
            for key in ('primary','peer'):need(after[key]['source']['events']==before[key]['source']['events'])
            first,last=before['lifecycle']['lifecycle'],after['lifecycle']['lifecycle']
            need(last['backgrounds']>=first['backgrounds']+1 and last['activations']>=first['activations']+1 and last['launches']==first['launches'])

    def history(self,packet):
        need(packet['available'] and not packet['expired'] and self.state['sourceInputs'])
        arm=self.state['sourceInputs'][0]
        need(packet['ownerRunId']==self.run_id and packet['instance']==arm['ownerInstance'] and packet['armCommandId']==arm['commandId'])
        frames=packet['frames'];need(len(frames)>=4)
        baseline=self.frames(self.state['before']);keyboards=[frame['view']['source']['keyboard'] for frame in baseline]
        first=frames[0];need(first['applicationState']=='active' and first['editor']['text']=='' and first['editor']['current'])
        need(all(first['keyboard']['instance']==keyboard['instance'] and first['keyboard']['sequence']>keyboard['sequence'] for keyboard in keyboards))
        for frame in frames:
            need(all(frame['editor'][key] for key in LIVENESS) and frame['editor']['text']==''
                and frame['keyboard']['created'] and frame['keyboard']['enabled'] and frame['keyboard']['keyCount']>0
                and all(frame['keyboard']['instance']==keyboard['instance'] and frame['keyboard']['keyCount']==len(keyboard['keys']) for keyboard in keyboards))
        clean=lambda frame:not frame['editor']['focused'] and frame['focusedEditors']==0 and not frame['keyboard']['visible'] and not frame['keyboard']['raised'] and frame['keyboard']['pressedKeys']==0
        hidden=[(index,frame) for index,frame in enumerate(frames) if frame['applicationState'] in ('hidden','suspended') and clean(frame)]
        need(len(hidden)>=2);start=hidden[0];finish=next(((index,frame) for index,frame in hidden[1:] if frame['elapsedMs']-start[1]['elapsedMs']>=250 and frame['capturedEpochMs']-start[1]['capturedEpochMs']>=250 and frame['cause']=='timer'),None);need(finish is not None)
        span=frames[start[0]:finish[0]+1];need(all(frame['applicationState'] in ('hidden','suspended') and clean(frame) for frame in span))
        need(all(0<=b['elapsedMs']-a['elapsedMs']<=500 for a,b in zip(span,span[1:])))
        tail=frames[finish[0]+1:];need(any(frame['applicationState']=='active' and frame['cause']=='application-state' for frame in tail))
        need(frames[-1]['applicationState']=='active' and frames[-1]['editor']['current'] and frames[-1]['editor']['visible'] and clean(frames[-1]))
        return packet

    def quiet(self):
        initial=self.frames(self.state['before']);started=None;epochs=None;previous=None;baseline=None
        for _index in range(64):
            observed=self.pair();current=[role.frames[-1] for role in self.roles];self.stable(initial,current);refs=references(self.roles);now=self.now()
            actual_epochs=[value for ref in refs for value in ref['epochs']]
            if started is None:started=now;epochs=actual_epochs;baseline=deepcopy(current)
            else:
                need(0<now-previous['hostMonotonic']<=1.5 and all(0<end-begin<=1500 for begin,end in zip(previous['epochs'],actual_epochs)))
                need(all(frame['lifecycle']['lifecycle']==old['lifecycle']['lifecycle'] for frame,old in zip(current,baseline)))
            self.state['quiet'].append(dict(roles=refs,hostMonotonic=now));self.state['after']=refs;self.save('quiet')
            previous=dict(hostMonotonic=now,epochs=actual_epochs)
            if now-started>=3 and all(end-begin>=3000 for begin,end in zip(epochs,actual_epochs)):return observed
            self.sleep(.1)
        need(False)

    def closed_history(self):
        need(self.state['before'] is not None and self.state['after'] is not None and len(self.state['sourceInputs'])==2 and self.state['sources'])
        packet=self.history(original_packet(self.state['sources'][-1],self.source.pid));release=self.state['sourceInputs'][1]
        need(packet['released'] and not packet['active'] and not packet['timerActive'] and packet['releaseCommandId']==release['commandId']
            and packet['lastIntentSequence']==release['intentSequence'])
        self.stable(self.frames(self.state['before']),self.frames(self.state['after']));rows=self.state['quiet'];need(len(rows)>=2)
        previous=None;original_lifecycle=None
        for row in rows:
            current_lifecycle=[frame['lifecycle']['lifecycle'] for frame in self.frames(row['roles'])]
            if original_lifecycle is None:original_lifecycle=current_lifecycle
            else:need(current_lifecycle==original_lifecycle)
            self.stable(self.frames(self.state['before']),self.frames(row['roles']))
            epochs=[epoch for ref in row['roles'] for epoch in ref['epochs']]
            if previous is not None:need(0<row['hostMonotonic']-previous['hostMonotonic']<=1.5 and all(0<end-begin<=1500 for begin,end in zip(previous['epochs'],epochs)))
            previous={**row,'epochs':epochs}
        need([frame['lifecycle']['lifecycle'] for frame in self.frames(self.state['after'])]==original_lifecycle)
        need(rows[-1]['hostMonotonic']-rows[0]['hostMonotonic']>=3
            and all(end-begin>=3000 for begin,end in zip([epoch for ref in rows[0]['roles'] for epoch in ref['epochs']],epochs)))
        osrows=self.state['os'];need(any(row['label']=='before-home' and row['packet']['foreground'] for row in osrows)
            and any(row['label']=='background' and not row['packet']['foreground'] for row in osrows)
            and any(row['label']=='before-resume' and not row['packet']['foreground'] for row in osrows)
            and any(row['label']=='foreground' and row['packet']['foreground'] for row in osrows))

    @staticmethod
    def recover_foreground(os_adapter,target,store,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        """Different normal Resume once, with OS originals while Qt guards sleep.

        This narrow recovery emits no Chat state, keyboard fact or timer release.
        It never creates a running process from an absent/replaced original.
        """
        need(isinstance(source_lock,ScriptSourceLock) and source_lock.path==store.path.with_name('script-sources.lock'))
        with source_lock.held():
            need(isinstance(os_adapter,PicoGraphicsBinding));old=store.read();need(old is not None);state=decode_owner(old)
            need(state['phase'] in ('background-issued','background-observed','foreground-issued','foreground-observed','failed') and state['sourceInputs'])
            binding=old['binding'];started=previous=monotonic();need(number(started,0,1e15))
            def save():
                nonlocal old
                value={**old,'payload':pack([state])};store.write(value,old);need(same(store.read(),value));old=deepcopy(value)
            def current(label='recovery'):
                nonlocal previous
                now=monotonic();need(number(now,previous,started+10));previous=now
                packet=status(os_adapter._graphics_lifecycle_status(target,binding),binding)
                finished=monotonic();need(number(finished,now,started+10) and finished-now<=1.5);previous=finished
                state['os'].append(dict(label=label,hostMonotonic=now,packet=deepcopy(packet)));need(len(state['os'])<=128);save();return packet
            with os_adapter.existing_input_session(target):
                packet=current()
                if not packet['foreground'] and state['phase'] in ('background-issued','background-observed'):
                    need(not current('background')['foreground']);state['phase']='background-observed';save()
                    sleep(.6);need(not current('before-resume')['foreground'])
                    state['phase']='foreground-issued';save();os_adapter._graphics_lifecycle_input(target,'app.launch',binding)
                for _index in range(51):
                    if current('foreground')['foreground']:return dict(foregroundRecovered=True,journalsRetained=True)
                    sleep(.1)
            need(False)

    def inspect_released(self):
        """Close a lost release result only through fresh originals, no input."""
        need(self.state is not None and len(self.state['sourceInputs'])==2 and len(self.state['quiet'])>=2)
        self.deadline=None;self.deadline=self.now()+20
        with ExitStack() as held:
            for lock in sorted(self.roles[0].locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
            packet=self.source.read(self.run_id);self.record_source(packet)
            release=self.state['sourceInputs'][1]
            need(packet['released'] and not packet['active'] and not packet['timerActive']
                and packet['releaseCommandId']==release['commandId'] and packet['lastIntentSequence']==release['intentSequence'])
            observed=self.pair();self.stable(self.frames(self.state['before']),[role.frames[-1] for role in self.roles])
            self.state['after']=references(self.roles);self.save('observed');self.closed_history()
            result=deepcopy(observed);self.fresh_current(self.fresh_started,background=True);return result

    def run(self,after_epoch):
        need(integer(after_epoch,1));self.deadline=None;self.deadline=self.now()+20
        try:
            with ExitStack() as held:
                for lock in sorted(self.roles[0].locks,key=lambda value:str(value.path)):held.enter_context(lock.held())
                with self.os.existing_input_session(self.target):
                    if self.state is None:
                        self.state=dict(phase='sampling',afterEpochMs=after_epoch,before=None,after=None,quiet=[],sourceInputs=[],sources=[],os=[]);self.save()
                        observed=self.pair();need(observed[0]['state']['open'] and observed[0]['state']['channel']=='domain' and observed[0]['state']['draft']=='')
                        self.state['before']=references(self.roles);self.save();self.record_source(self.source.read(self.run_id))
                        self.record_source(self.source.arm(self.run_id),'armed')
                    need(self.state['afterEpochMs']==after_epoch and self.state['phase'] not in ('observed','failed'))
                    if self.state['phase']=='arm-issued':
                        actual=self.source.read(self.run_id);arm=self.state['sourceInputs'][0]
                        need(actual['available'] and actual['active'] and actual['timerActive'] and actual['armCommandId']==arm['commandId'] and actual['instance']==arm['ownerInstance'])
                        self.record_source(actual,'armed')
                    if self.state['phase']=='armed':
                        need(self.os_status('before-home')['foreground']);self.save('background-issued')
                        self.os._graphics_lifecycle_input(self.target,'lifecycle.background',self.binding)
                    if self.state['phase']=='background-issued':self.wait_os(False,'background');self.save('background-observed')
                    if self.state['phase']=='background-observed':
                        self.sleep(.6);need(not self.os_status('before-resume')['foreground']);self.save('foreground-issued')
                        self.os._graphics_lifecycle_input(self.target,'app.launch',self.binding)
                    if self.state['phase']=='foreground-issued':self.wait_os(True,'foreground');self.save('foreground-observed')
                    need(self.state['phase'] in ('foreground-observed','quiet','release-issued'))
                    if self.state['phase']!='release-issued':
                        self.record_source(self.history(self.source.read(self.run_id)))
                        observed=self.quiet();self.record_source(self.history(self.source.read(self.run_id)))
                        self.record_source(self.source.release_owned(self.run_id,self.state['sourceInputs'][0]))
                    else:self.record_source(self.source.read(self.run_id))
                    packet=self.source.last;release=self.state['sourceInputs'][-1]
                    need(release['operation']=='release' and packet['released'] and not packet['active'] and not packet['timerActive']
                        and packet['releaseCommandId']==release['commandId'] and packet['lastIntentSequence']==release['intentSequence'])
                    observed=self.pair();self.stable(self.frames(self.state['before']),[role.frames[-1] for role in self.roles])
                    self.state['after']=references(self.roles);self.save('observed');self.closed_history()
                    result=deepcopy(observed);self.fresh_current(self.fresh_started,background=True);return result
        except Exception:
            # Recovery is separate input authority. Do not retry HOME, arm or a
            # recorded Resume/release, and do not retire any original journal.
            try:
                if self.state is not None and self.state['phase'] in ('background-issued','background-observed','foreground-issued'):
                    self.recover_foreground(self.os,self.target,self.store,self.roles[0].locks[0],monotonic=self.monotonic,sleep=self.sleep)
                    self.previous=self.store.read();self.state=decode_owner(self.previous)
                if self.state is not None and self.state['sourceInputs'] and len(self.state['sourceInputs'])==1:
                    current=self.source.read(self.run_id);arm=self.state['sourceInputs'][0]
                    if current['ownerRunId']==self.run_id and current['armCommandId']==arm['commandId']:
                        self.record_source(current);self.record_source(self.source.release_owned(self.run_id,arm))
                if self.state is not None:self.save('failed')
            except Exception:pass
            raise NativeUIError('Chat background/return is unresolved; original inputs and histories remain without replay') from None
