"""Normal Scripts and original pending-event continuation after Chat return.

Private partial owner: no live Actor, peer, image, final process retirement or
complete Lifecycle capability is manufactured from these retained originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import hashlib
import re
import uuid
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pending_commit_owner import NativePendingCommitOwner,command,validate as pending_validate,accept as pending_accept
from adapters.pico4 import lifecycle_source as ui,lifecycle_drive as drive
from adapters.pico4.lifecycle_back import BUTTON,PicoLifecycleBack,envelope,frame
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_pending_originals import LifecyclePendingOriginals
from adapters.pico4.lifecycle_world import PicoLifecycleWorld,neutral
from adapters.script_journey.history import canonical,pack,unpack
from adapters.token_script_ui import TokenScriptUI

VERSION=1
PHASES=('prepared','chat-x-issued','home','opening','opened','focus-issued','focused',
    'type-issued','typed','hold-issued','held','replace-x-issued','replacement-home',
    'reopening','reopened','attempt-issued','attempted','release-issued','released','quiet')
OPERATIONS={'focus-issued':'focus','type-issued':'type','hold-issued':'hold',
    'attempt-issued':'attempt','release-issued':'release'}


def current_return(method):
    """Keep nested calls in one twenty-second budget and check real lock exit."""
    @wraps(method)
    def call(owner,*args,**kwargs):
        started=owner.world.monotonic();need(number(started,0,1e15))
        previous=owner.deadline
        owner.deadline=started+20 if previous is None else previous
        try:
            result=method(owner,*args,**kwargs)
            owner.released_fresh()
            return result
        finally:owner.deadline=previous
    return call


class PicoLifecyclePending:
    def __init__(self,background,world,route,pending,path):
        need(type(background) is PicoLifecycleBackground and type(world) is PicoLifecycleWorld
            and type(route) is TokenScriptUI and type(pending) is NativePendingCommitOwner
            and background.lock is world.lock and background.run==world.run and background.binding==world.binding
            and pending.pid==world.pid and pending.intent is None)
        self.background,self.world,self.route,self.pending=background,world,route,pending
        self.run,self.binding,self.pid,self.lock=world.run,deepcopy(world.binding),world.pid,world.lock
        self.store=PrivateFeatureState(path);need(self.store.path==world.store.path.with_name('lifecycle-pending-owner.json'))
        self.disk=self.state=self.last_clock=self.anchor=self.deadline=None
        self.pending.intent=self.pending_intent
        self.pending_callback=self.pending_before_send;self.pending.bind_before_send(self.pending_callback)
        # This is the existing final normal QML publication boundary, after the
        # route's bind_input/current token/CAS checks. No new input channel.
        self.normal_callback=self.normal_intent
        self.route.io.navigation.io.bind_before_send(self.normal_callback)
        with self.lock.held():
            self.disk=self.store.read()
            self.originals=LifecyclePendingOriginals(self.store.path.with_name('lifecycle-pending-originals.json'),self.run,self.binding)
            need(self.store.read() is not None or self.originals.disk is None);self.load()

    def bound(self,*,host_only=False):
        self.lock.assert_held();now=self.world.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock))
        need(self.deadline is None or now<=self.deadline)
        self.last_clock=now;self.original_state()
        if not host_only:need(self.world.guard() is not False and self.pending.guard() is not False)
        return now

    def original_state(self):
        # Pure physical/metadata verification, also valid after actual lock
        # release. It cannot create a reader, refresh a source or acquire input.
        need(self.store.read()==self.disk and self.run==self.world.run==self.background.run
            and self.binding==self.world.binding==self.background.binding and self.pid==self.world.pid==self.pending.pid
            and self.lock is self.world.lock is self.background.lock
            and self.store.path==self.world.store.path.with_name('lifecycle-pending-owner.json'))
        self.originals.verify()
        if self.disk is not None:
            physical=self.disk['originalStamp'];need(type(physical) is list and len(physical)==8 and all(type(field) is int for field in physical))
        need((self.disk is None and self.originals.disk is None) or self.disk is not None
            and self.disk['originalChunks']==self.originals.manifest and self.disk['originalStamp']==list(self.originals.root_stamp))
        if self.state is not None:
            need(hashlib.sha256(canonical(self.background.store.read())).hexdigest()==self.state['backgroundSha256'])

    def fresh(self,*,host_only=False,already_guarded=False):
        now=self.bound(host_only=host_only or already_guarded);need(self.anchor is not None)
        start,requested,oldest=self.anchor
        if host_only:need(requested-oldest+(now-start)*1000<=1500);return
        # All copies, persistence and actual installed/process guards precede
        # both final native clocks; no fresh facts are inferred from the ACK.
        clocks=(self.world.axes.clock_ms(),self.pending.clock_ms());completed=self.world.monotonic()
        need(number(completed,now,1e15) and all(integer(epoch,1) and -250<=epoch-oldest
            and max(epoch-oldest,requested-oldest+(completed-start)*1000)<=1500 for epoch in clocks))
        self.last_clock=completed

    def released_fresh(self):
        # Actual context-manager exit has already run. Do not reacquire the
        # source lock or replay any source/input while checking original age.
        self.original_state()
        need(self.anchor is not None and self.world.guard() is not False and self.pending.guard() is not False)
        start,requested,oldest=self.anchor;epochs=(self.world.axes.clock_ms(),self.pending.clock_ms())
        completed=self.world.monotonic()
        need(number(completed,0,1e15) and completed>=self.last_clock
            and (self.deadline is None or completed<=self.deadline)
            and all(integer(epoch,1) and -250<=epoch-oldest
                and max(epoch-oldest,requested-oldest+(completed-start)*1000)<=1500 for epoch in epochs))
        self.last_clock=completed

    def pending_packet(self,row):
        exact(row,{'request','original'});command(row['request'])
        LifecyclePendingOriginals.original(row['original']);value=decode(row['original']['raw'])
        pending_validate(value,row['request'],self.pid,value['capturedEpochMs']);need(value['runId']==self.run)
        return value

    def packet(self,row):
        exact(row,{'world','pending','hostMonotonic'})
        need(number(row['hostMonotonic'],0,1e15));return self.world.originals(row['world']),self.pending_packet(row['pending'])

    def validate(self,state):
        exact(state,{'phase','backgroundSha256','frames','normal','mutations','backs','scriptId','replacementId','eventId','holdHost','quiet','cleanup'})
        need(state['phase'] in PHASES and type(state['backgroundSha256']) is str and re.fullmatch('[0-9a-f]{64}',state['backgroundSha256'])
            and type(state['frames']) is list and 1<=len(state['frames'])<=96
            and type(state['normal']) is list and len(state['normal'])<=48
            and type(state['mutations']) is list and len(state['mutations'])<=5
            and type(state['backs']) is list and len(state['backs'])<=2
            and type(state['quiet']) is list and len(state['quiet'])<=25)
        prior_ui=prior_pending=None;commands=set()
        for row in state['frames']:
            packets,pending=self.packet(row)
            prior_ui=ui.accept(prior_ui,ui.summary(packets['ui']));pending_accept(prior_pending,pending);prior_pending=pending
            need(pending['commandId'] not in commands);commands.add(pending['commandId'])
        first,_pending=self.packet(state['frames'][0]);current=ui.current_editor(first['ui'])
        need(current is not None and current['kind']=='chat' and not current['focused']
            and measured_keyboard(first['ui']['source']['keyboard']) is False)
        for row in state['normal']:self.normal_command(row)
        for before,after in zip(state['normal'],state['normal'][1:]):
            need(all(before[key]==after[key] for key in ('bridgeId','generation')) and after['sequence']==before['sequence']+1)
        initial_pending=self.packet(state['frames'][0])[1]
        for index,row in enumerate(state['mutations']):
            command(row);need(row['runId']==self.run and row['operation']==('focus','type','hold','attempt','release')[index]
                and row['ownerInstance']==initial_pending['instance'] and row['intentSequence']==initial_pending['lastIntentSequence']+index+1)
        for index,row in enumerate(state['backs']):
            exact(row,{'phase','originalId','envelope','neutral'})
            need(row['phase']==('chat-x-issued','replace-x-issued')[index] and ui.nonce(row['originalId']))
            if row['envelope'] is not None:
                envelope(row['envelope'],self.world.session.profile)
                if row['neutral'] is not None:PicoLifecycleBack.neutral(row['neutral'],row['envelope'],first['ui']['capturedEpochMs'])
            else:need(row['neutral'] is None)
        for name in ('scriptId','replacementId','eventId'):need(state[name] is None or ui.nonce(state[name]))
        if state['scriptId'] is not None:
            observed=[ui.current_editor(self.packet(row)[0]['ui']) for row in state['frames']]
            scripts=next((row for row in observed if row is not None and row['id']==state['scriptId']),None)
            need(scripts is not None and scripts['kind']=='scripts' and all(scripts[key]!=current[key] for key in ('id','fieldId','pageId','contextId')))
        if state['replacementId'] is not None:
            replacement=next((row for row in observed if row is not None and row['id']==state['replacementId']),None)
            need(replacement is not None and replacement['kind']=='scripts' and all(replacement[key]!=scripts[key] for key in ('id','fieldId','pageId','contextId')))
        if state['eventId'] is not None:
            need(number(state['holdHost'],0,1e15) and prior_pending['commit']
                and prior_pending['commit']['observation']['eventId']==state['eventId'] and len(state['mutations'])>=3
                and prior_pending['commit']['captureCommandId']==state['mutations'][2]['commandId'])
        else:need(state['holdHost'] is None)
        rank=PHASES.index(state['phase'])
        need(rank<2 or state['backs'] and state['backs'][0]['neutral'] is not None)
        need(rank<4 or state['scriptId'] is not None)
        for minimum,count in ((6,1),(8,2),(10,3),(16,4),(18,5)):
            need(rank<minimum or len(state['mutations'])>=count)
        need(rank<10 or state['eventId'] is not None)
        need(rank<12 or len(state['backs'])==2 and state['backs'][1]['neutral'] is not None)
        need(rank<14 or state['replacementId'] is not None)
        if rank>=16:
            terminal=prior_pending['commit']['observation']['events'][-1]
            need(not prior_pending['resources']['pendingRuns'] and not prior_pending['commit']['observation']['pending']
                and terminal['kind']=='rejected' and terminal['reason']=='context-retired')
        prior=None;window=None;complete=False
        for index in state['quiet']:
            need(integer(index,0,len(state['frames'])-1));row=state['frames'][index]
            packets=self.quiet_packet(state,row)
            if window is None:window=drive.AvatarReleaseWindow(drive.AvatarDisplacement(packets['drive']))
            complete=window.observe(packets['drive'],row['hostMonotonic'])
            if prior is not None:
                previous_packets=self.packet(prior)[0];a,b=previous_packets['ui'],packets['ui']
                need(0<b['capturedEpochMs']-a['capturedEpochMs']<=500 and 0<row['hostMonotonic']-prior['hostMonotonic']<=.5)
                need(previous_packets['gesture']['source']['events']==packets['gesture']['source']['events'])
            prior=row
        if state['phase']=='quiet':
            need(len(state['quiet'])>=2 and complete)
            a,b=(state['frames'][index] for index in (state['quiet'][0],state['quiet'][-1]))
            need(b['hostMonotonic']-a['hostMonotonic']>=3
                and self.packet(b)[0]['ui']['capturedEpochMs']-self.packet(a)[0]['ui']['capturedEpochMs']>=3000)
        cleanup=state['cleanup']
        if cleanup is not None:
            exact(cleanup,{'phase','eventId','request','frames'})
            need(cleanup['phase'] in ('issued','observed') and ui.nonce(cleanup['eventId'])
                and type(cleanup['frames']) is list and 1<=len(cleanup['frames'])<=8 and len(state['mutations'])>=3)
            previous=prior_pending
            for raw in cleanup['frames']:
                observed=self.pending_packet(raw);pending_accept(previous,observed);previous=observed
                need(observed['commit'] and observed['commit']['captureCommandId']==state['mutations'][2]['commandId']
                    and observed['commit']['observation']['eventId']==cleanup['eventId'])
            request=cleanup['request']
            if request is not None:
                command(request);need(request['operation']=='release' and request['runId']==self.run and request['eventId']==cleanup['eventId'])
            if cleanup['phase']=='observed':
                need(request is not None and previous['lastIntentSequence']==request['intentSequence']
                    and not previous['commit']['observation']['pending'] and not previous['resources']['pendingRuns'])

    def load(self):
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecyclePendingOwnerVersion','runId','binding','originalChunks','originalStamp','payload'})
        need(type(disk['lifecyclePendingOwnerVersion']) is int and disk['lifecyclePendingOwnerVersion']==VERSION
            and disk['runId']==self.run and disk['binding']==self.binding and disk['originalChunks']==self.originals.manifest)
        values=self.originals.decode(unpack(disk['payload']));need(len(values)==1);self.validate(values[0])
        self.disk,self.state=deepcopy(disk),deepcopy(values[0]);last=self.packet(self.state['frames'][-1])[1]
        if self.state['cleanup'] is not None:last=self.pending_packet(self.state['cleanup']['frames'][-1])
        if self.pending.last is None:self.pending.last=deepcopy(last)
        else:pending_accept(last,self.pending.last) if self.pending.last['sequence']!=last['sequence'] else need(last==self.pending.last)
        self.bound()

    def save(self,state,*,host_only=False):
        self.bound(host_only=host_only);self.validate(state)
        encoded=self.originals.encode([state]);disk=dict(lifecyclePendingOwnerVersion=VERSION,runId=self.run,
            binding=deepcopy(self.binding),originalChunks=self.originals.manifest,originalStamp=list(self.originals.root_stamp),payload=pack(encoded))
        self.store.write(disk,self.disk);need(self.store.read()==disk)
        self.disk,self.state=deepcopy(disk),deepcopy(state);self.bound(host_only=host_only)

    def capture(self):
        start=self.bound();requested=self.pending.clock_ms();packets=self.world.current()
        self.pending.read(self.run,self.state['eventId'] if self.state is not None and self.state['eventId'] else '')
        row=dict(world=deepcopy(self.world.state['frames'][-1]),pending=dict(request=deepcopy(self.pending.last_request),
            original=frame(self.pending.last_raw)),hostMonotonic=self.bound())
        self.anchor=start,requested,min(self.pending.last['capturedEpochMs'],*(packet['capturedEpochMs'] for packet in packets.values()))
        self.packet(row);self.fresh();return row

    @current_return
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);self.background.load()
            need(self.background.state is not None and self.background.state['phase']=='released')
            row=self.capture();packets,pending=self.packet(row);editor=ui.current_editor(packets['ui'])
            prior=self.background.packet(self.background.state['final'])['ui'];old=ui.current_editor(prior)
            ui.accept(ui.summary(prior),ui.summary(packets['ui']))
            need(editor is not None and editor['id']==old['id'] and editor['kind']=='chat' and not editor['focused']
                and editor['text']==old['text']
                and measured_keyboard(packets['ui']['source']['keyboard']) is False and not pending['commit'] and not pending['resources']['pendingRuns'])
            self.save(dict(phase='prepared',backgroundSha256=hashlib.sha256(canonical(self.background.disk)).hexdigest(),frames=[row],
                normal=[],mutations=[],backs=[],scriptId=None,replacementId=None,eventId=None,holdHost=None,quiet=[],cleanup=None));self.fresh()

    def append(self,row,**changes):
        state=deepcopy(self.state);state['frames'].append(row);state.update(changes);self.save(state);self.fresh()

    def normal_command(self,request):
        exact(request,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'})
        need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and str(uuid.UUID(request['commandId']))==request['commandId']
            and request['bridgeId']==self.binding['sessionId'] and ui.nonce(request['generation'])
            and integer(request['sequence'],1) and integer(request['observedElapsedMs']) and str(uuid.UUID(request['controlToken']))==request['controlToken']
            and request['action']=='activate' and (request['controlId'] in ('tablet.home','scripts.entry','scripts.menu','scripts.menu-edit','scripts.menu-running')
                or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',request['controlId'])))

    def normal_intent(self,request):
        self.bound();need(self.state['phase'] in ('opening','reopening'));self.normal_command(request)
        row=self.capture();state=deepcopy(self.state);state['frames'].append(row);state['normal'].append(deepcopy(request))
        self.save(state);self.fresh()

    def pending_intent(self,request):
        self.bound();command(request)
        if self.state['cleanup'] is not None:
            cleanup=self.state['cleanup'];need(cleanup['phase']=='issued' and cleanup['request'] is None
                and request['operation']=='release' and request['eventId']==cleanup['eventId'] and request['runId']==self.run)
            state=deepcopy(self.state);state['cleanup']['request']=deepcopy(request);self.save(state);self.fresh();return
        need(request['operation']==OPERATIONS[self.state['phase']] and request['runId']==self.run)
        # No pending-reader reentry inside its original exchange. Independently
        # requery current actual Qt/world ownership, then persist the envelope.
        packets=self.world.current();current=ui.current_editor(packets['ui'])
        need(current is not None and current['id']==(self.state['replacementId'] or self.state['scriptId']) and current['kind']=='scripts')
        state=deepcopy(self.state);state['mutations'].append(deepcopy(request));self.save(state);self.fresh()

    def pending_before_send(self,request):
        # The original native transport has just performed its final candidate
        # guard. Recheck this exact persisted command, clocks and original age;
        # do not repeat its durable intent or construct a new source query.
        self.bound(host_only=True)
        expected=self.state['cleanup']['request'] if self.state['cleanup'] is not None else self.state['mutations'][-1]
        need(request==expected)
        if request['operation']=='attempt':self.held_deadline()
        self.fresh(already_guarded=True)

    def held_deadline(self):
        need(self.state['holdHost'] is not None and self.bound()-self.state['holdHost']<10)

    def pending_only(self,event):
        start=self.bound();requested=self.pending.clock_ms();self.pending.read(self.run,event)
        raw=dict(request=deepcopy(self.pending.last_request),original=frame(self.pending.last_raw))
        self.pending_packet(raw);self.anchor=start,requested,self.pending.last['capturedEpochMs'];self.fresh();return raw

    @current_return
    def release_owned(self):
        """Partial-failure release, with no UI dependency, replay or stale verdict."""
        with self.lock.held():
            self.load();need(self.state is not None and len(self.state['mutations'])>=3)
            cleanup=self.state['cleanup'];event=cleanup['eventId'] if cleanup is not None else self.state['eventId'] or ''
            raw=self.pending_only(event);value=self.pending_packet(raw);commit=value['commit']
            need(commit and commit['captureCommandId']==self.state['mutations'][2]['commandId'])
            if cleanup is None:
                need(value['lastIntentSequence']==self.state['mutations'][-1]['intentSequence'])
                state=deepcopy(self.state);state['cleanup']=dict(phase='issued',eventId=commit['observation']['eventId'],request=None,frames=[raw])
                self.save(state);self.fresh();self.pending.operate(self.run,'release',event_id=self.state['cleanup']['eventId'])
                raw=self.pending_only(self.state['cleanup']['eventId']);value=self.pending_packet(raw)
            state=deepcopy(self.state);cleanup=state['cleanup'];request=cleanup['request']
            need(request is not None and value['lastIntentSequence']==request['intentSequence']
                and value['instance']==request['ownerInstance'] and not value['commit']['observation']['pending']
                and not value['resources']['pendingRuns'])
            if raw['request']['commandId']!=cleanup['frames'][-1]['request']['commandId']:cleanup['frames'].append(raw)
            cleanup['phase']='observed';self.save(state)
            result=dict(pendingReleased=True,originalEventId=cleanup['eventId'],journalRetained=True,completeLifecycle=False)
            self.fresh();return result

    @current_return
    def back(self,replacement=False):
        with self.lock.held():
            self.load();need(self.state['phase']==('held' if replacement else 'prepared'))
            row=self.capture();packets,pending=self.packet(row);current=ui.current_editor(packets['ui']);need(current is not None)
            if replacement:self.held_deadline();need(current['id']==self.state['scriptId'] and pending['commit']['observation']['pending'])
            else:need(current['kind']=='chat')
            state=deepcopy(self.state);phase='replace-x-issued' if replacement else 'chat-x-issued'
            state['frames'].append(row);state['phase']=phase;state['backs'].append(dict(phase=phase,originalId=current['id'],envelope=None,neutral=None));self.save(state);self.fresh()
            def intent(value):
                envelope(value,self.world.session.profile);state=deepcopy(self.state);need(state['backs'][-1]['envelope'] is None)
                state['backs'][-1]['envelope']=deepcopy(value);self.save(state,host_only=True);self.fresh(host_only=True)
            def before_publish(value):
                need(value==self.state['backs'][-1]['envelope']);self.fresh(host_only=True)
            self.world.session.stage(self.binding['processIdentity'],'controller.button',deepcopy(BUTTON),intent=intent,before_publish=before_publish)
            return self.reconcile()

    @current_return
    def open_scripts(self,replacement=False):
        with self.lock.held():
            self.load();need(self.state['phase']==('replacement-home' if replacement else 'home'))
            state=deepcopy(self.state);state['phase']='reopening' if replacement else 'opening';self.save(state)
            self.route.open_manager();return self.reconcile()

    @current_return
    def mutate(self,operation):
        prior,phase={'focus':('opened','focus-issued'),'type':('focused','type-issued'),'hold':('typed','hold-issued'),
            'attempt':('reopened','attempt-issued'),'release':('attempted','release-issued')}[operation]
        with self.lock.held():
            self.load();need(self.state['phase']==prior);row=self.capture();_packets,before=self.packet(row)
            if operation=='attempt':self.held_deadline()
            if operation=='hold':need(not before['commit'])
            state=deepcopy(self.state);state['frames'].append(row);state['phase']=phase;self.save(state);self.fresh()
            self.pending.operate(self.run,operation,event_id=self.state['eventId'] or '')
            return self.reconcile()

    @current_return
    def reconcile(self):
        with self.lock.held():
            self.load();phase=self.state['phase']
            if phase in ('chat-x-issued','replace-x-issued'):
                state=deepcopy(self.state);back=state['backs'][-1];need(back['envelope'] is not None)
                back['neutral']=deepcopy(self.world.session.require_owned_neutral(self.binding['processIdentity'],back['envelope']))
                row=self.capture();packets,_pending=self.packet(row);PicoLifecycleBack.home(packets['ui'],back['originalId'])
                state['frames'].append(row);state['phase']='home' if phase=='chat-x-issued' else 'replacement-home';self.save(state)
                result=self.report();self.fresh();return result
            row=self.capture();packets,pending=self.packet(row);current=ui.current_editor(packets['ui'])
            need(current is not None and current['kind']=='scripts' and current['visible'] and pending['current']['status']=='ready'
                and current['text']==pending['current']['text'] and current['focused']==pending['current']['focused'])
            state=deepcopy(self.state);state['frames'].append(row)
            if phase in ('opening','reopening'):
                normal=self.route.capture();last=state['normal'][-1];need(normal['lastCommandSequence']==last['sequence']
                    and normal['bridgeId']==last['bridgeId'] and normal['generation']==last['generation'] and self.route.control(normal,'scripts.from-url') is not None)
                need(not current['focused'] and current['text']=='' and measured_keyboard(packets['ui']['source']['keyboard']) is False)
                if phase=='opening':state.update(scriptId=current['id'],phase='opened')
                else:
                    old=PicoLifecycleBack.row(packets['ui'],state['scriptId']);need(not old['fieldAlive'] and not old['pageAlive'])
                    need(pending['commit'] and pending['current']['token']!=pending['commit']['fieldToken'])
                    state.update(replacementId=current['id'],phase='reopened')
            else:
                request=state['mutations'][-1];need(request['operation']==OPERATIONS[phase]
                    and pending['lastIntentSequence']==request['intentSequence'] and pending['instance']==request['ownerInstance'])
                if phase in ('focus-issued','type-issued'):
                    need(current['focused'] and measured_keyboard(packets['ui']['source']['keyboard']) is True
                        and current['text']==('retry-'+self.run if phase=='type-issued' else ''))
                    state['phase']='typed' if phase=='type-issued' else 'focused'
                elif phase=='hold-issued':
                    commit=pending['commit'];need(commit and commit['captureCommandId']==request['commandId'] and commit['observation']['pending'])
                    # Preserve the original elapsed hold age after a lost
                    # capture answer; first successful observation is not birth.
                    state.update(phase='held',eventId=commit['observation']['eventId'],
                        holdHost=row['hostMonotonic']-commit['observation']['elapsedMs']/1000)
                elif phase in ('attempt-issued','release-issued'):
                    event=pending['commit']['observation']['events'][-1]
                    need(event['kind']=='rejected' and event['reason']=='context-retired' and not pending['commit']['observation']['pending']
                        and not pending['resources']['pendingRuns'] and current['id']==state['replacementId'] and current['text']==''
                        and not current['focused'] and measured_keyboard(packets['ui']['source']['keyboard']) is False)
                    state['phase']='attempted' if phase=='attempt-issued' else 'released'
                else:need(False)
            self.save(state);result=self.report();self.fresh();return result

    def quiet_packet(self,state,row):
        packets,pending=self.packet(row);current=ui.current_editor(packets['ui']);neutral(packets['gesture'])
        actual=self.world.anchor.measure(packets['drive']);event=pending['commit']['observation']['events'][-1]
        need(current is not None and current['id']==state['replacementId'] and current['text']=='' and not current['focused']
            and measured_keyboard(packets['ui']['source']['keyboard']) is False and not any(item['focused'] for item in packets['ui']['source']['editors'])
            and not pending['resources']['pendingRuns'] and not pending['commit']['observation']['pending']
            and event['kind']=='rejected' and event['reason']=='context-retired'
            and not actual['heldInputs'] and actual['worldDisplacement']<=.025
            and len(self.world.attempts(self.world.state,packets['gesture']))==1)
        return packets

    @current_return
    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('released','quiet'));indices=[];window=None
            for index in range(25):
                row=self.capture();packets=self.quiet_packet(self.state,row)
                if window is None:window=drive.AvatarReleaseWindow(drive.AvatarDisplacement(packets['drive']))
                complete=window.observe(packets['drive'],row['hostMonotonic']);state=deepcopy(self.state)
                state['frames'].append(row);indices.append(len(state['frames'])-1);state.update(quiet=indices,phase='quiet' if complete else 'released')
                self.save(state);self.fresh()
                if complete:result=self.report();self.fresh();return result
                need(index<24);self.world.sleep(.25)
            need(False)

    def report(self):
        packets,pending=self.packet(self.state['frames'][-1]);current=ui.current_editor(packets['ui'])
        if current is not None:
            original=ui.current_editor(self.packet(self.state['frames'][0])[0]['ui'])
            need(current['id'] in (original['id'],self.state['scriptId'],self.state['replacementId']))
        generation=0 if current is None else 4 if current['id']==self.state['replacementId'] else 3 if current['id']==self.state['scriptId'] else 2
        commit=pending['commit'];terminal=commit['observation']['events'][-1] if commit else None
        actual=self.world.anchor.measure(packets['drive'])
        return dict(editor=current['kind'] if current else 'none',text=current['text'] if current else '',generation=generation,
            focused=bool(current and current['focused']),keyboard=measured_keyboard(packets['ui']['source']['keyboard']),
            deferredInputs=len(pending['resources']['pendingRuns']),staleAttempts=int(bool(terminal and terminal['kind']=='rejected' and terminal['reason']=='context-retired')),
            heldInputs=actual['heldInputs'],worldDisplacement=actual['worldDisplacement'],positionDelta=dict(zip(('x','y','z'),actual['positionDelta'])),
            worldAttempts=len(self.world.attempts(self.world.state,packets['gesture'])),
            originalEventId=self.state['eventId'],journalRetained=True,completeLifecycle=False)


@current_return
def run_pending(owner):
    need(type(owner) is PicoLifecyclePending)
    try:
        with owner.lock.held():
            owner.load()
            if owner.state is None:owner.prepare()
            need(owner.state['cleanup'] is None)
            while owner.state['phase']!='quiet':
                phase=owner.state['phase']
                if phase=='prepared':owner.back()
                elif phase=='home':owner.open_scripts()
                elif phase in ('opened','focused','typed','reopened','attempted'):
                    owner.mutate(dict(opened='focus',focused='type',typed='hold',reopened='attempt',attempted='release')[phase])
                elif phase=='held':owner.back(True)
                elif phase=='replacement-home':owner.open_scripts(True)
                elif phase=='released':return owner.quiet()
                else:owner.reconcile()
            return owner.quiet() # A new current full quiet window, never old evidence.
    except Exception:raise NativeUIError('Lifecycle pending continuation unresolved; original input/event ownership retained, none repeated') from None
