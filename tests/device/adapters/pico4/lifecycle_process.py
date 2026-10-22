"""OS-proven retirement of original process-owned Lifecycle sources.

No old weak QObject flag is rewritten. This component preserves all journals;
full peer/stale/restore resource closure remains a separate journey verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,number,validate as validate_native
from adapters.native_process_presence import NativeProcessPresence,validate as validate_presence
from adapters.native_chat_observation import NativeChatObservation,validate as validate_chat
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_world import PicoLifecycleWorld,LifecycleWorldHistory,neutral
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin,LifecycleXHistory
from adapters.pico4.lifecycle_back import frame
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.restart_inputs import RestartInputs,native as birth,validate_native_restart
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
FILES=('lifecycle-world-owner.json','lifecycle-x-back-owner.json','lifecycle-x-join.json')


def archived(disk):
    """Keep embedded raw transcripts under one bounded compression layer."""
    value=deepcopy(disk);value['payload']=unpack(value['payload']);return value


def original_snapshot(value):
    disk=deepcopy(value);disk['payload']=pack(disk['payload']);return disk


def owner_snapshots(shutdown):return [original_snapshot(shutdown[key]) for key in ('world','back','join')]


def identity(binding):
    context(binding);value=binding['processIdentity'];need(re.fullmatch('[1-9][0-9]{0,9}:[1-9][0-9]{0,19}',value))
    pid,start=map(int,value.split(':'));need(integer(pid,1,2147483647));return pid,start


def native(value,pid):
    need(ui.nonce(value.get('requestId')));validate_native(value,value['requestId'],pid,value['capturedEpochMs']);return value


def native_birth(value):return birth(dict(pid=value['processId'],instance=value['instance'],lifecycle=deepcopy(value['lifecycle'])))


def settings(value):
    return dict(graphics=deepcopy(value['graphics']),audio={key:value['audio'][key] for key in ('recording','muted')},
        loggedIn=value['account']['loggedIn'])


def domain(value,run,pid):
    request=dict(schemaVersion=1,commandId=value['commandId'],action='feature-chat-observe',operation='inspect',runId=run)
    validate_chat(value,request,pid,value['capturedEpochMs']);need(value['chatVersion']==2)
    source=value['source'];need(not source['scopePresent'] and not source['retired'] and source['mixerPresent'])
    session=source['session'];need(session['connected'] and session['mixerActive']);return value


class PicoLifecycleDomain:
    """Read the existing original native inspect operation; never open its cache."""
    def __init__(self,reader,source_lock):
        need(isinstance(reader,NativeChatObservation) and isinstance(source_lock,ScriptSourceLock))
        self.native,self.source_lock,self.pid,self.guard=reader,source_lock,reader.pid,reader.guard
    def read(self,run):
        with self.source_lock.held():
            value=self.native.perform(run,'inspect');domain(value,run,self.pid);return value


def restored(original,current):
    a,b=original['source'],current['source']
    need(a['sceneUrl']==b['sceneUrl'] and a['modelScale']==b['modelScale']
        and math.sqrt(sum((x-y)**2 for x,y in zip(a['feetPosition'],b['feetPosition'])))<=.025
        and math.sqrt(sum((x-y)**2 for x,y in zip(a['bodyPosition'],b['bodyPosition'])))<=.025
        and abs(sum(x*y for x,y in zip(a['orientation'],b['orientation'])))>=.999
        and all(abs(x-y)<=.025 for x,y in zip(a['sensorToWorld'],b['sensorToWorld'])))
    for key in ('advancedMovement','actionEnabled','scriptedEnabled','scriptedTimescale'):need(a['motors'][key]==b['motors'][key])


def closed(packet):
    source=packet['source'];need(not source['tabletShown'] and ui.current_editor(packet) is None
        and measured_keyboard(source['keyboard']) is False and not any(row['focused'] for row in source['editors']))


class PicoLifecycleProcessRetirement:
    def __init__(self,path,run,profile,guard,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(ui.nonce(run) and isinstance(source_lock,ScriptSourceLock) and all(callable(f) for f in (guard,monotonic,sleep)))
        self.store,self.run,self.profile,self.guard=PrivateFeatureState(path),run,profile,guard
        need(self.store.path.name=='lifecycle-process-owner.json' and source_lock.path==self.store.path.with_name('script-sources.lock'))
        self.lock,self.monotonic,self.sleep=source_lock,monotonic,sleep
        self.owners=[PrivateFeatureState(self.store.path.with_name(name)) for name in FILES]
        self.inputs=RestartInputs(PrivateFeatureState(self.store.path.with_name('lifecycle-restart-inputs.json')),self.owners,monotonic=monotonic)
        self.disk=self.state=None;self.last_clock=None
        with self.lock.held():self.load()

    def now(self):
        need(self.guard() is not False);now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock))
        self.last_clock=now;return now

    def history(self,disk,binding):
        pid,_start=identity(binding);history=LifecycleWorldHistory(self.run,binding,pid,self.profile);history.validate(original_snapshot(disk));return history

    def validate(self,state):
        exact(state,{'phase','binding','originalWorld','originalNative','originalDomain','shutdown','next'})
        need(state['phase'] in ('begun','prepared','process-retired'));binding=context(state['binding']);pid,_start=identity(binding)
        original=self.history(state['originalWorld'],binding);need(not original.state['attempts'])
        native(state['originalNative'],pid);domain(state['originalDomain'],self.run,pid);need(state['originalNative']['audio']['recording'] is False)
        if state['phase']=='begun':need(state['shutdown'] is None and state['next'] is None);return
        shutdown=state['shutdown'];exact(shutdown,{'world','back','join','native','domain','quiet','freshness'})
        history=self.history(shutdown['world'],binding);attempts=history.state['attempts']
        need(len(attempts)==2 and all(row['phase']=='quiet' for row in attempts)
            and history.state['frames'][:len(original.state['frames'])]==original.state['frames'])
        history.attempts(history.state,history.originals(history.state['frames'][-1])['gesture'])
        joined=shutdown['join'];exact(joined,{'lifecycleXJoinVersion','runId','binding','payload'})
        need(type(joined['lifecycleXJoinVersion']) is int and joined['lifecycleXJoinVersion']==1 and joined['runId']==self.run and joined['binding']==binding)
        payload=joined['payload'];need(type(payload) is list);need(len(payload)==1 and payload[0]['phase']=='observed')
        LifecycleXHistory(history,self.profile,original_snapshot(shutdown['back'])).validate(payload[0])
        native(shutdown['native'],pid);need(shutdown['native']['instance']==state['originalNative']['instance']
            and shutdown['native']['sequence']>state['originalNative']['sequence']
            and settings(shutdown['native'])==settings(state['originalNative'])
            and shutdown['native']['lifecycle']['launches']==state['originalNative']['lifecycle']['launches'])
        domain(shutdown['domain'],self.run,pid)
        need(shutdown['domain']['instance']==state['originalDomain']['instance']
            and shutdown['domain']['sequence']>state['originalDomain']['sequence']
            and shutdown['domain']['source']==state['originalDomain']['source'])
        fresh=shutdown['freshness'];exact(fresh,{'started','requestedEpochMs'})
        need(number(fresh['started'],0,1e15) and integer(fresh['requestedEpochMs'],1)
            and fresh['started']<=history.state['frames'][-1]['hostMonotonic'])
        first,last=shutdown['quiet']['first'],shutdown['quiet']['last'];exact(shutdown['quiet'],{'first','last'})
        need(integer(first,0,len(history.state['frames'])-1) and integer(last,first+1,len(history.state['frames'])-1))
        anchor=drive.AvatarDisplacement(original.originals(original.state['frames'][0])['drive']);quiet=drive.AvatarReleaseWindow(anchor)
        for row in history.state['frames'][first:last+1]:
            current=history.originals(row);closed(current['ui']);neutral(current['gesture']);restored(anchor.original,current['drive'])
            okay=quiet.observe(current['drive'],row['hostMonotonic'])
        need(okay)
        if state['phase']=='prepared':need(state['next'] is None);return
        target=state['next'];exact(target,{'binding','frames'});new=target['binding'];new_pid,new_start=identity(new)
        need(new_pid!=pid and new_start>identity(binding)[1] and new['sessionId']!=binding['sessionId']
            and new['generation']>=binding['generation'] and all(new[key]==binding[key] for key in ('sourceRevision','artifactSha256','targetFingerprint')))
        need(type(target['frames']) is list and 2<=len(target['frames'])<=64)
        previous=None;quiet=None;seen={key:set() for key in ('ui','gesture','drive','native','presence','domain')};old_current=history.originals(history.state['frames'][-1])
        for row in target['frames']:
            current=self.new_frame(row,state,new,old_current)
            for key in seen:
                packet=current[key] if key in current else row[key];nonce_key='requestId' if key=='native' else 'commandId'
                need(packet[nonce_key] not in seen[key]);seen[key].add(packet[nonce_key])
            if previous:
                ui.accept(ui.summary(previous['ui']),ui.summary(current['ui']));gesture.accept(previous['gesture'],current['gesture'])
                drive.continuity(previous['drive'],current['drive'])
                need(row['native']['instance']==prior['native']['instance'] and row['native']['sequence']>prior['native']['sequence']
                    and row['presence']['sequence']>prior['presence']['sequence'] and row['hostMonotonic']>=prior['hostMonotonic']
                    and row['domain']['instance']==prior['domain']['instance'] and row['domain']['sequence']>prior['domain']['sequence']
                    and row['domain']['source']==prior['domain']['source'])
                for key,nonce_key in (('native','requestId'),('presence','commandId'),('domain','commandId')):
                    need(row[key][nonce_key]!=prior[key][nonce_key] and row[key]['capturedEpochMs']>=prior[key]['capturedEpochMs'])
            else:quiet=drive.AvatarReleaseWindow(drive.AvatarDisplacement(current['drive']))
            okay=quiet.observe(current['drive'],row['hostMonotonic']);previous=current;prior=row
        need(okay)

    def new_frame(self,row,state,binding,old_current):
        exact(row,{'ui','gesture','drive','native','presence','domain','hostMonotonic','requestedEpochMs','durationSeconds'})
        pid,_start=identity(binding);helper=LifecycleWorldHistory(self.run,binding,pid,self.profile)
        current=helper.originals({key:row[key] for key in ('ui','gesture','drive','hostMonotonic')});closed(current['ui']);neutral(current['gesture'])
        for key in ('ui','gesture','drive'):need(current[key]['instance']!=old_current[key]['instance'])
        need(current['ui']['source']['keyboard']['instance']!=old_current['ui']['source']['keyboard']['instance'])
        need(not any(event['kind']=='started' for event in current['gesture']['source']['events']))
        native(row['native'],pid);validate_native_restart(native_birth(state['shutdown']['native']),native_birth(row['native']))
        need(settings(row['native'])==settings(state['originalNative']))
        original=self.history(state['originalWorld'],state['binding']);restored(original.originals(original.state['frames'][0])['drive'],current['drive'])
        domain(row['domain'],self.run,pid);old_domain=state['shutdown']['domain'];new_domain=row['domain']
        a,b=old_domain['source']['session'],new_domain['source']['session']
        need(new_domain['instance']!=old_domain['instance'] and b['instance']!=a['instance'] and b['connectionBirth']!=a['connectionBirth']
            and b['domainSha256']==a['domainSha256'] and b['connectedEpochMs']>state['shutdown']['native']['capturedEpochMs']
            and new_domain['source']['mixerSha256']==old_domain['source']['mixerSha256'])
        receipt=row['presence'];request=dict(schemaVersion=1,commandId=receipt['commandId'],action='feature-process-presence',queryProcessId=identity(state['binding'])[0])
        need(ui.nonce(receipt['commandId']));validate_presence(receipt,request,pid,receipt['capturedEpochMs']);need(receipt['presence']=='absent' and receipt['instance']==row['native']['instance'])
        stamps=[packet['capturedEpochMs'] for packet in current.values()]+[receipt['capturedEpochMs'],row['native']['capturedEpochMs'],row['domain']['capturedEpochMs'],current['gesture']['source']['frameEpochMs']]
        need(integer(row['requestedEpochMs'],1) and number(row['durationSeconds'],0,1.5)
            and all(stamp>=row['requestedEpochMs']-250 for stamp in stamps)
            and row['requestedEpochMs']-min(stamps)+row['durationSeconds']*1000<=1500)
        return current

    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleProcessOwnerVersion','runId','payload'})
        need(type(disk['lifecycleProcessOwnerVersion']) is int and disk['lifecycleProcessOwnerVersion']==VERSION and disk['runId']==self.run)
        payload=unpack(disk['payload']);need(len(payload)==1);self.validate(payload[0]);self.disk,self.state=deepcopy(disk),deepcopy(payload[0])

    def save(self,state):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(state)
        disk=dict(lifecycleProcessOwnerVersion=VERSION,runId=self.run,payload=pack([state]));self.store.write(disk,self.disk)
        need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)

    def begin(self,world,source,domain_source):
        with self.lock.held():
            self.load();need(self.state is None and isinstance(world,PicoLifecycleWorld) and world.lock is self.lock
                and world.store.path==self.owners[0].path and isinstance(source,NativeFeatureObservation) and source.pid==world.pid
                and isinstance(domain_source,PicoLifecycleDomain) and domain_source.pid==world.pid and domain_source.source_lock is self.lock)
            world.load();need(world.state is not None and not world.state['attempts']);started=self.now();requested=source.clock_ms()
            packets=world.current();closed(packets['ui']);neutral(packets['gesture']);restored(world.anchor.original,packets['drive'])
            receipt=source.read(source.sequence);native(receipt,world.pid);connected=domain_source.read(self.run);world.now();world.fresh_current();need(self.now()-started<=1.5 and receipt['capturedEpochMs']>=requested)
            self.save(dict(phase='begun',binding=deepcopy(world.binding),originalWorld=archived(world.disk),originalNative=deepcopy(receipt),originalDomain=deepcopy(connected),shutdown=None,next=None))
            need(self.now()-started<=1.5);world.fresh_current();return deepcopy(receipt)

    def prepare(self,joined,source,domain_source):
        try:
            with self.lock.held():
                self.load();need(self.state is not None and self.state['phase'] in ('begun','prepared') and isinstance(joined,PicoLifecycleXJoin)
                    and joined.world.lock is self.lock and isinstance(source,NativeFeatureObservation)
                    and isinstance(domain_source,PicoLifecycleDomain) and domain_source.source_lock is self.lock)
                if self.state['phase']=='prepared':
                    need([owner.read() for owner in self.owners]==owner_snapshots(self.state['shutdown']))
                    need(self.inputs.store.read() is None or self.inputs.read()['phase']=='prepared')
                world=joined.world;joined.load();need(joined.state is not None and joined.state['phase']=='observed' and world.binding==self.state['binding']
                    and len(world.state['attempts'])==2 and world.state['attempts'][-1]['phase']=='quiet' and source.pid==domain_source.pid==world.pid)
                quiet=drive.AvatarReleaseWindow(world.anchor);first=len(world.state['frames']);started=self.now()
                for index in range(41):
                    packets=world.current();closed(packets['ui']);neutral(packets['gesture']);restored(world.anchor.original,packets['drive'])
                    receipt=source.read(source.sequence);connected=domain_source.read(self.run)
                    need(settings(receipt)==settings(self.state['originalNative']) and connected['source']==self.state['originalDomain']['source'])
                    world.attempts(world.state,packets['gesture'])
                    now=self.now();world.fresh_current();need(now-started<20)
                    if quiet.observe(packets['drive'],world.state['frames'][-1]['hostMonotonic']):
                        snapshots=[owner.read() for owner in self.owners]
                        need(snapshots==[world.disk,joined.back.disk,joined.disk])
                        state=deepcopy(self.state);state.update(phase='prepared',shutdown=dict(world=archived(snapshots[0]),back=archived(snapshots[1]),join=archived(snapshots[2]),
                            native=deepcopy(receipt),domain=deepcopy(connected),quiet=dict(first=first,last=len(world.state['frames'])-1),
                            freshness=dict(started=world.fresh_anchor[0],requestedEpochMs=world.fresh_anchor[1])))
                        self.save(state);world.now();world.fresh_current();return deepcopy(receipt)
                    need(index<40);self.sleep(.25)
        except Exception:raise NativeUIError('Lifecycle shutdown preparation unresolved; originals retained') from None

    def prepare_inputs(self,source):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='prepared' and isinstance(source,NativeFeatureObservation)
                and source.pid==identity(self.state['binding'])[0])
            need([owner.read() for owner in self.owners]==owner_snapshots(self.state['shutdown']))
            if self.inputs.store.read() is None:self.inputs.capture(self.state['binding'],source)
            value=self.inputs.read();need(value['oldBinding']==self.state['binding'] and value['oldNative']==native_birth(self.state['shutdown']['native']))
            return deepcopy(value)

    def require_stop_ready(self,source):
        """Final current-age guard inside RestartInputs' one-send callback."""
        self.lock.assert_held();self.load();need(self.state is not None and self.state['phase']=='prepared')
        need(isinstance(source,NativeFeatureObservation) and source.pid==identity(self.state['binding'])[0])
        history=self.history(self.state['shutdown']['world'],self.state['binding'])
        row=history.state['frames'][-1];packets=history.originals(row)
        fresh=self.state['shutdown']['freshness'];elapsed=self.now()-fresh['started'];epoch=source.clock_ms()
        stamps=[packet['capturedEpochMs'] for packet in packets.values()]
        stamps.extend(self.state['shutdown'][key]['capturedEpochMs'] for key in ('native','domain'))
        stamps.append(packets['gesture']['source']['frameEpochMs'])
        need(0<=elapsed<=1.5 and max(epoch-min(stamps),fresh['requestedEpochMs']-min(stamps)+elapsed*1000)<=1500)
        need([owner.read() for owner in self.owners]==owner_snapshots(self.state['shutdown']))
        need(source.guard() is not False);need(self.now()-fresh['started']<=1.5)

    def observe(self,binding,source,presence,domain_source,ui_source,axes,avatar):
        try:
            with self.lock.held():
                self.load();need(self.state is not None and self.state['phase'] in ('prepared','process-retired')
                    and isinstance(source,NativeFeatureObservation) and isinstance(presence,NativeProcessPresence)
                    and isinstance(domain_source,PicoLifecycleDomain) and domain_source.source_lock is self.lock
                    and isinstance(ui_source,ui.PicoLifecycleSource) and isinstance(axes,gesture.PicoLifecycleGesture) and isinstance(avatar,drive.PicoLifecycleDrive))
                pid,start=identity(binding);old_pid,old_start=identity(self.state['binding'])
                need(pid!=old_pid and start>old_start and binding['sessionId']!=self.state['binding']['sessionId']
                    and binding['generation']>=self.state['binding']['generation']
                    and all(binding[key]==self.state['binding'][key] for key in ('sourceRevision','artifactSha256','targetFingerprint')))
                need(source.pid==presence.pid==domain_source.pid==ui_source.pid==axes.pid==avatar.pid==pid)
                for reader in (ui_source,axes,avatar):need(reader.source_lock is self.lock)
                original=self.inputs.read();need(original['phase'] in ('launch-issued','observed') and original['oldBinding']==self.state['binding'])
                self.inputs.observe(binding,source)
                history=self.history(self.state['shutdown']['world'],self.state['binding']);old=history.originals(history.state['frames'][-1])
                rows=[];quiet=None;started=self.now()
                for index in range(41):
                    before=self.now();requested=source.clock_ms();receipt=source.read(source.sequence)
                    exited=presence.require_absent(identity(self.state['binding'])[0]);connected=domain_source.read(self.run);row={}
                    for name,reader in (('gesture',axes),('drive',avatar),('ui',ui_source)):
                        reader.capture(self.run);row[name]=frame(reader.last_raw);need(row[name]['sha256']==reader.last_sha256)
                    for reader in (source,presence,domain_source,ui_source,axes,avatar):need(reader.guard() is not False)
                    now=self.now();need(now-started<20)
                    row.update(native=deepcopy(receipt),presence=deepcopy(exited),domain=deepcopy(connected),hostMonotonic=now,requestedEpochMs=requested,durationSeconds=now-before)
                    current=self.new_frame(row,self.state,binding,old)
                    if quiet is None:quiet=drive.AvatarReleaseWindow(drive.AvatarDisplacement(current['drive']))
                    rows.append(row)
                    if quiet.observe(current['drive'],now):
                        need([owner.read() for owner in self.owners]==owner_snapshots(self.state['shutdown']))
                        state=deepcopy(self.state);state.update(phase='process-retired',next=dict(binding=deepcopy(binding),frames=rows));self.save(state)
                        final=self.now();stamps=[row[key]['capturedEpochMs'] for key in ('native','presence','domain')]
                        stamps.extend(value['capturedEpochMs'] for value in current.values());stamps.append(current['gesture']['source']['frameEpochMs'])
                        need(final-before<=1.5 and row['requestedEpochMs']-min(stamps)+(final-before)*1000<=1500)
                        return dict(processOwnedScopesRetired=True,originalProcessId=identity(state['binding'])[0],
                            currentProcessId=pid,worldAttempts=2,originalWeakFlagsPreserved=True,journalsRetained=True)
                    need(index<40);self.sleep(.25)
        except Exception:raise NativeUIError('Lifecycle process retirement unresolved; original scopes retained') from None


def run_lifecycle_restart(owner,prepare,source,stop,stopped,launch,recover,observe):
    """Use existing one-send app inputs; issued stop/launch are never repeated.

    prepare rechecks actual restored quiet while the original process is alive.
    recover only obtains a current binding; observe supplies OS/native proof.
    """
    need(isinstance(owner,PicoLifecycleProcessRetirement)
        and all(callable(callback) for callback in (prepare,source,stop,stopped,launch,recover,observe)))
    with owner.lock.held():
        owner.load();need(owner.state is not None and owner.state['phase'] in ('begun','prepared','process-retired'))
        value=None if owner.inputs.store.read() is None else owner.inputs.read()
        if value is None or value['phase']=='prepared':
            prepare();native_source=source();owner.prepare_inputs(native_source)
            def deliver():
                owner.require_stop_ready(native_source)
                return stop()
            owner.inputs.stop(deliver)
        value=owner.inputs.read()
        if value['phase']=='stop-issued':owner.inputs.launch(stopped,launch)
        if owner.inputs.read()['phase']=='launch-issued':
            recover()  # Read-only recovery after an uncertain launch, never resend.
        return observe()
