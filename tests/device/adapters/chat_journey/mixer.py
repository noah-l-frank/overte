"""One owned mixer removal/restoration, joined to independent native originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
import uuid
from adapters.chat_journey.samples import ChatSamples,transition_ready
from adapters.chat_journey.mixer_control import FixtureMixerControl,validate as control_packet
from fixture.messages_mixer import valid_control_command
from adapters.native_chat_observation import identity
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack

VERSION=1


class ChatMixerOwner:
    def __init__(self,controls,roles,store,*,monotonic=time.monotonic,sleep=time.sleep):
        need(type(controls) is tuple and len(controls)==2 and all(isinstance(source,FixtureMixerControl) for source in controls)
            and controls[0] is not controls[1] and not controls[0].readonly and controls[1].readonly
            and controls[0].identity==controls[1].identity and type(roles) is tuple and len(roles)==2
            and all(isinstance(role,ChatSamples) for role in roles) and roles[0].role=='primary' and roles[1].role=='actor'
            and roles[0] is not roles[1] and roles[0].run==roles[1].run and roles[0].binding==roles[1].binding
            and roles[0].peer_binding==roles[1].peer_binding and roles[0].store.path!=roles[1].store.path
            and store.path not in (roles[0].store.path,roles[1].store.path) and callable(monotonic) and callable(sleep)
            and all(source.previous is None for source in controls))
        self.controls,self.roles,self.store=controls,roles,store;self.monotonic,self.sleep=monotonic,sleep
        self.previous=store.read();self.frames=[];self.last_clock=None;self.deadline=None
        self.base=dict(chatMixerOwnerVersion=VERSION,runId=roles[0].run,binding=roles[0].binding,peerBinding=roles[0].peer_binding,
            controlIdentity=controls[0].identity,transcripts=[role.store.path.name for role in roles],
            phase='new',commands=[],recoverySources=[],offlineObserved=False,original=None,transcript=pack([]))
        if self.previous is not None:
            exact(self.previous,set(self.base));need(all(self.previous[key]==self.base[key] for key in set(self.base)-{'phase','commands','recoverySources','offlineObserved','original','transcript'}))
            need(self.previous['phase'] in ('new','baseline','issuing-offline','offline','issuing-online','online','recovering','recovery-observed'))
            commands=self.previous['commands'];need(type(commands) is list and len(commands)<=2)
            need(all(valid_control_command(row) and row['runId']==roles[0].run for row in commands)
                and len({row['action'] for row in commands})==len(commands)
                and len({row['commandId'] for row in commands})==len(commands)
                and (not commands or commands[0]['action']=='offline'))
            need(type(self.previous['offlineObserved']) is bool)
            self.base=deepcopy(self.previous)
            self.frames=unpack(self.previous['transcript'])
            need(type(self.previous['recoverySources']) is list and len(self.previous['recoverySources'])<=2)
            for frame in self.frames+self.previous['recoverySources']:
                exact(frame,{'controls','roles','transition','controlOnly'})
                need(type(frame['transition']) is bool and type(frame['controls']) is list and len(frame['controls'])==2)
                for source,value in zip(controls,frame['controls']):
                    control_packet(value,value['capturedEpochMs']);need(value['mixerControlVersion']==2);source.accept(value)
                self.join(frame)
            if self.previous['original'] is not None:
                original=self.previous['original'];exact(original,{'control','nativeMixer'})
                need(any(not frame['controlOnly'] and not frame['transition'] and frame['controls'][0]==original['control']
                    and roles[0].frames[frame['roles'][0]['index']]['primary']['source']['mixerSha256']==original['nativeMixer']
                    for frame in self.frames))
                need(all(command['instance']==original['control']['instance'] for command in commands))
            self.base=deepcopy(self.previous)

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def budget(self):
        need(self.deadline is not None and self.now()<=self.deadline)

    def write(self,phase,**values):
        need(self.store.read()==self.previous)
        value={**self.base,**values,'phase':phase,'transcript':pack(self.frames)}
        self.store.write(value,self.previous);need(self.store.read()==value);self.previous=self.base=deepcopy(value)

    def append(self,frame,*,recovery=False):
        if recovery:
            need(len(self.base['recoverySources'])<2)
            self.write(self.base['phase'],recoverySources=self.base['recoverySources']+[deepcopy(frame)])
        else:
            original=self.frames;self.frames=self.frames+[deepcopy(frame)]
            try:self.write(self.base['phase'])
            except Exception:
                # An uncommitted read cannot enlarge the next input journal.
                # A lost write receipt still fails the original CAS guard.
                self.frames=original;raise

    def reference(self):
        return [dict(index=len(role.frames)-1,ticket=role.frames[-1]['ticket'],
            epochs=[role.frames[-1][key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')],
            queries=[role.frames[-1][key].get('commandId',role.frames[-1][key].get('requestId')) for key in ('primary','peer','view','lifecycle')]) for role in self.roles]

    def join(self,frame):
        first,last=frame['controls']
        need(all(first[key]==last[key] for key in ('instance','domainId','stackGeneration','processes','mixer','mixerIdentity',
            'runId','offlineFenced','commands')) and first['sequence']<last['sequence']
            and first['capturedEpochMs']<=last['capturedEpochMs'] and first['mixerControlVersion']==last['mixerControlVersion']==2
            and first['runId'] in (None,self.roles[0].run))
        for row in first['commands']:
            matches=[command for command in self.base['commands'] if command['commandId']==row['commandId']]
            need(len(matches)==1 and matches[0]['instance']==first['instance'] and matches[0]['runId']==first['runId']
                and all(matches[0][key]==row[key] for key in ('action','observedGeneration')))
        need(type(frame['controlOnly']) is bool and type(frame['transition']) is bool and type(frame['roles']) is list)
        if frame['controlOnly']:
            need(frame['transition'] and frame['roles']==[]);return frame
        need(len(frame['roles'])==2)
        expected=identity(self.roles[0].run,first['domainId'])
        for role,reference in zip(self.roles,frame['roles']):
            exact(reference,{'index','ticket','epochs','queries'})
            need(integer(reference['index'],0,len(role.frames)-1))
            native=role.frames[reference['index']]
            need(reference['ticket']==native['ticket']
                and reference['epochs']==[native[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')]
                and reference['queries']==[native[key].get('commandId',native[key].get('requestId')) for key in ('primary','peer','view','lifecycle')]
                and frame['transition']==native.get('transition',False))
            for key in ('primary','peer'):
                value=native[key];need(value['chatVersion']==2)
                session=value['source']['session'];need(session['connected'] and session['domainSha256']==expected)
        return frame

    def measure_control(self,*,recovery=False):
        # Recovery must still fence/restore the owned mixer when native client
        # observation is unavailable. This frame emits no Chat state/resources.
        self.budget();started=self.now();packets=[source.state() for source in self.controls]
        frame=dict(controls=deepcopy(packets),roles=[],transition=True,controlOnly=True)
        self.join(frame);self.append(frame,recovery=recovery)
        clocks=[]
        for source,value in zip(self.controls,packets):
            measured=self.now();epoch=source.clock_ms();fresh(value['capturedEpochMs'],epoch)
            need(source.guard() is not False);clocks.append((measured,epoch,value['capturedEpochMs']))
        finished=self.now();need(number(finished,started,started+1.5)
            and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))
        self.budget();return frame

    def measure(self,after_epoch,*,transition):
        self.budget();started=self.now();first=self.controls[0].state()
        observed=[(role.read_transition if transition else role.read)(uuid.uuid4().hex,after_epoch) for role in self.roles]
        last=self.controls[1].state();packets=[first,last]
        frame=dict(controls=deepcopy(packets),roles=self.reference(),transition=transition,controlOnly=False)
        self.join(frame)
        self.append(frame)
        clocks=[]
        for role in self.roles:
            native=role.frames[-1]
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
            for reader,oldest in ((role.primary,min(native[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),
                                  (role.peer,native['peer']['capturedEpochMs'])):
                measured=self.now();epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
        for source,value in zip(self.controls,packets):
            measured=self.now();epoch=source.clock_ms();fresh(value['capturedEpochMs'],epoch);need(source.guard() is not False)
            clocks.append((measured,epoch,value['capturedEpochMs']))
        finished=self.now();need(number(finished,started,started+1.5)
            and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))
        if not transition:need(observed[0]['state']==observed[1]['state'])
        self.budget();return observed,frame

    def goal(self,frame,running):
        if not all(value['mixer']['running']==running and not value['mixer']['pending'] for value in frame['controls']):return False
        source=frame['controls'][0]
        commands=self.base['commands']
        if commands:
            actual={row['commandId']:row for row in source['commands']}
            # Online is an actual admission fence, never an ACK-derived fact.
            required=commands[-1]
            row=actual.get(required['commandId'])
            if row is None or row['action']!=required['action'] or row['status']=='pending':return False
            if running and not source['offlineFenced']:return False
        original=self.base['original']
        if original is not None:
            need(all(source[key]==original['control'][key] for key in ('instance','domainId','stackGeneration','processes')))
            expected_generation=original['control']['mixer']['generation']+(2 if running else 1)
            if source['mixer']['generation']!=expected_generation:return False
            if running:need(source['mixerIdentity']!=original['control']['mixerIdentity'])
        for role in self.roles:
            for key in ('primary','peer'):
                native=role.frames[-1][key]['source']
                if native['mixerPresent']!=running or native['session']['mixerActive']!=running:return False
                if original is not None and running:need(native['mixerSha256']!=original['nativeMixer'])
        return True

    def await_ready(self,after_epoch,running):
        started=self.now()
        for _attempt in range(42):
            _observed,frame=self.measure(after_epoch,transition=True)
            if self.goal(frame,running) and all(transition_ready(role) for role in self.roles):
                # New independent full queries are mandatory. Raw qualification
                # never becomes a cached/current shared-state result.
                observed,full=self.measure(after_epoch,transition=False)
                need(self.goal(full,running));return observed,full
            need(self.now()-started<20);self.sleep(.5)
        need(False)

    def quiet(self,after_epoch,running,initial):
        baseline=deepcopy(initial[0][0]['state']);first=None;previous=None;started=self.now();quiet_started=None;previous_host=None
        native_events=[[deepcopy(role.frames[-1][key]['source']['events']) for key in ('primary','peer')] for role in self.roles]
        for _attempt in range(202):
            observed,frame=self.measure(after_epoch,transition=False);need(self.goal(frame,running))
            need(all(value['state']==baseline for value in observed))
            for role,events in zip(self.roles,native_events):
                need([role.frames[-1][key]['source']['events'] for key in ('primary','peer')]==events)
            epochs=[epoch for role in frame['roles'] for epoch in role['epochs']]+[value['capturedEpochMs'] for value in frame['controls']]
            now=self.now()
            if first is None:first=epochs;quiet_started=now
            else:need(all(0<current-old<=1500 for current,old in zip(epochs,previous)) and now-previous_host<=1.5)
            previous=epochs;previous_host=now
            if now-quiet_started>=3 and all(end-begin>=3000 for end,begin in zip(epochs,first)):return observed
            need(now-started<20);self.sleep(.1)
        need(False)

    def issue(self,action,after_epoch,*,recovery=False):
        need(action in ('offline','online') and action not in [row['action'] for row in self.base['commands']])
        # New passive original sources choose the admission generation. They
        # cannot resend/complete a prior input; the full request is durable first.
        need(integer(after_epoch,1));frame=self.measure_control(recovery=recovery);actual=frame['controls'][1]
        need(actual['runId'] in (None,self.roles[0].run))
        request=dict(schemaVersion=2,commandId=uuid.uuid4().hex,runId=self.roles[0].run,
            instance=actual['instance'],observedGeneration=actual['mixer']['generation'],action=action)
        self.write('issuing-'+action,commands=self.base['commands']+[request])
        self.budget();self.controls[0].command(request) # Receipt is never used as a node fact.

    def remove(self,after_epoch):
        admitted=False
        try:
            need(integer(after_epoch,1) and self.previous is None)
            admitted=True;self.deadline=self.now()+20;self.write('baseline');observed,frame=self.await_ready(after_epoch,True)
            need(frame['controls'][0]['runId'] is None and not frame['controls'][0]['commands'])
            original=dict(control=deepcopy(frame['controls'][0]),nativeMixer=self.roles[0].frames[-1]['primary']['source']['mixerSha256'])
            self.write('baseline',original=original);self.issue('offline',after_epoch)
            current=self.await_ready(after_epoch,False);observed=self.quiet(after_epoch,False,current)
            self.write('offline',offlineObserved=True);return observed
        except Exception:
            if admitted:self.recover(after_epoch)
            raise NativeUIError('Chat mixer removal is unresolved; original sources and input intent remain') from None

    def restore(self,after_epoch):
        try:
            need(integer(after_epoch,1) and self.base['original'] is not None
                and [row['action'] for row in self.base['commands']]==['offline'] and self.base['phase']=='offline')
            self.deadline=self.now()+20;self.issue('online',after_epoch)
            return self.inspect_restored(after_epoch)
        except Exception:
            raise NativeUIError('Chat mixer restoration is unresolved; no uncertain command is resent') from None

    def inspect_restored(self,after_epoch):
        # Passive completion after an uncertain online response. The original
        # command cannot be retried, even after reconstruction or a timeout.
        need(integer(after_epoch,1) and self.base['original'] is not None and self.base['offlineObserved']
            and [row['action'] for row in self.base['commands']]==['offline','online'])
        if self.deadline is None:self.deadline=self.now()+20
        current=self.await_ready(after_epoch,True);observed=self.quiet(after_epoch,True,current)
        self.write('online');return observed

    def recover(self,after_epoch):
        # The opposite restoration command may run once after uncertain removal.
        # An online-first source admission fences a delayed offline HTTP input.
        if self.previous is None or 'offline' not in [row['action'] for row in self.base['commands']] or 'online' in [row['action'] for row in self.base['commands']]:return
        try:
            self.deadline=self.now()+20;self.write('recovering');self.issue('online',after_epoch,recovery=True)
            frame=self.measure_control(recovery=True);first=frame['controls'][0]
            need(first['mixer']['running'] and not first['mixer']['pending'] and first['offlineFenced']
                and all(row['status']!='pending' for row in first['commands']))
            # This narrower process recovery does not claim an observed outage,
            # native recovery, quiet interval or full feature completion.
            self.write('recovery-observed')
        except Exception:pass
