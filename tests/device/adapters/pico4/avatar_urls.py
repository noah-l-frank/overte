"""Durable normal Avatar URL/failure/restore subflow, without whole area claims.

Native model/geometry effects, normal input and fixture authorization have
separate originals. The owner remains retained after URL restoration because
Avatar/People contexts, bookmarks, wearables, peer and backend are not retired.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time
from urllib.parse import urljoin
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.pico4.avatar_state import NativePicoAvatarState,ACTION,validate,continuity,failed,sha
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI,control_id,text,project
from adapters.pico4.navigation import validate_snapshot
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import scope,nonce
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.fixtures import pinned_resource

VERSION=1


def packet(record,pid):
    exact(record,{'raw','sha256'});need(type(record['raw']) is str and sha(record['raw'])==record['sha256'])
    value=decode(record['raw']);validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),pid,value.get('capturedEpochMs'));return value


def loaded_url(url):
    # Read the existing immutable common FST foundation rather than inventing a
    # requested geometry URL or guessing a successful Model's current URL.
    fst=pinned_resource('avatar-a.fst').decode('utf-8');rows=[line.split('=',1)[1].strip() for line in fst.splitlines() if line.split('=',1)[0].strip()=='filename' and '=' in line]
    need(rows==['mannequin/mannequin.fbx']);return urljoin(url,rows[0])


class PicoAvatarUrls:
    def __init__(self,store,binding,phase,lock,native,widgets,controls,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people' and isinstance(lock,ScriptSourceLock)
            and all(callable(v) for v in (native,widgets,controls,guard,monotonic,sleep)))
        self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.native,self.widgets,self.controls_factory,self.guard,self.monotonic,self.sleep=native,widgets,controls,guard,monotonic,sleep
        self.pid=int(binding['processIdentity'].split(':')[0]);need(integer(self.pid,1));self.run=phase.run
        self.previous=store.read();self.clock=self.anchor=None;self.failed=False;self._reconciling=False;self._before_send=self.before_send
        self.state=dict(stage='reserved',baseline=None,prepared=None,frames=[],calls=[],inputs=[],pending=None,unresolved=[],restored=False)
        self.bound()
        if self.previous is not None:self.state=self.restore(self.previous)
    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.previous,self.store.read()))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock));self.clock=now
    def restore(self,value):
        exact(value,{'picoAvatarUrlsOwnerVersion','binding','runId','fixtureUrl','payload'})
        need(type(value['picoAvatarUrlsOwnerVersion']) is int and value['picoAvatarUrlsOwnerVersion']==1 and same(value['binding'],self.binding)
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];self.check(state);return deepcopy(state)
    def phase_original(self,value):
        phase_packet(value,run=self.run,area='avatar-people',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
        need(value['activations']);return value['activations'][-1]
    def check(self,state):
        exact(state,{'stage','baseline','prepared','frames','calls','inputs','pending','unresolved','restored'})
        need(state['stage'] in ('reserved','active','restoring','restored') and type(state['restored']) is bool
            and type(state['frames']) is list and len(state['frames'])<=128 and type(state['calls']) is list and len(state['calls'])<=8
            and type(state['inputs']) is list and len(state['inputs'])<=128 and (state['pending'] is None or nonce(state['pending'])))
        need(type(state['unresolved']) is list and len(set(state['unresolved']))==len(state['unresolved']) and len(state['unresolved'])<=8)
        previous=None;last_phase=None
        for frame in state['frames']:
            exact(frame,{'native','widgets','phaseBefore','phaseAfter','hostStarted','hostFinished'})
            need(number(frame['hostStarted'],0,1e15) and number(frame['hostFinished'],frame['hostStarted'],frame['hostStarted']+1.5))
            actual=packet(frame['native'],self.pid);continuity(previous,actual);previous=actual
            validate_snapshot(frame['widgets'],self.pid,frame['widgets']['updatedEpochMs']);project(frame['widgets'])
            need(frame['widgets']['bridgeId']==self.binding['sessionId'])
            self.phase_original(frame['phaseBefore']);self.phase_original(frame['phaseAfter'])
            if last_phase is not None:phase_packet(frame['phaseBefore'],run=self.run,area='avatar-people',request=frame['phaseBefore']['requestId'],epoch=frame['phaseBefore']['capturedEpochMs'],previous=last_phase)
            last_phase=frame['phaseAfter']
            need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']) and frame['phaseBefore']['active']==frame['phaseAfter']['active'])
        need((state['baseline'] is None)==(not state['frames']))
        if state['baseline'] is not None:need(same(state['baseline'],state['frames'][0]))
        if state['prepared'] is not None:
            need(integer(state['prepared'],2,len(state['frames'])));self.baseline_quiet(state)
        else:need(state['stage']=='reserved' and not state['calls'])
        tickets=set()
        for call in state['calls']:
            exact(call,{'ticket','verb','url','phase','attempted','settled','quiet','before'})
            activation=self.phase_original(call['phase']);need(call['ticket']==activation['ticket'] and call['ticket'] not in tickets
                and call['verb'] in ('avatar-url','avatar-restore','cleanup') and activation['stimulus']['verb']==call['verb']
                and type(call['attempted']) is bool and type(call['settled']) is bool and (not call['settled'] or call['attempted']))
            need(integer(call['before'],1,len(state['frames'])))
            tickets.add(call['ticket']);text(call['url'])
            if call['settled']:self.quiet_original(state,call)
            else:need(call['quiet'] is None)
            if call['verb']=='avatar-url':need(call['url']==self.phase.fixture_url+'tickets/'+call['ticket']+'/'+activation['stimulus']['inputs']['resource'])
            else:need(state['baseline'] is not None and call['url']==packet(state['baseline']['native'],self.pid)['source']['requestedUrl'])
        need(set(state['unresolved'])<=tickets and all(not r['settled'] for r in state['calls'] if r['ticket'] in state['unresolved']))
        need(state['pending'] not in state['unresolved'] and {r['ticket'] for r in state['calls'] if not r['settled']}==set(state['unresolved'])|({state['pending']} if state['pending'] is not None else set()))
        need(state['pending'] is None or state['calls'] and state['calls'][-1]['ticket']==state['pending'] and not state['calls'][-1]['settled'])
        for row in state['inputs']:
            exact(row,{'ticket','intent','command'});need(row['ticket'] in tickets)
            intent=row['intent'];exact(intent,{'avatarPeopleInputVersion','action','controlId','controlToken','scope'});scope(intent['scope'])
            need(type(intent['avatarPeopleInputVersion']) is int and intent['avatarPeopleInputVersion']==1 and control_id(intent['controlId'])
                and intent['action'] in ('activate','replace','scroll','set-value') and nonce(intent['controlToken']) and intent['scope']['instance']==self.binding['sessionId'] and intent['scope']['processId']==self.pid)
            if row['command'] is not None:self.command_original(row['command'],intent)
        if state['restored']:need(state['stage']=='restored' and state['pending'] is None and state['calls'][-1]['settled'] and state['calls'][-1]['verb'] in ('cleanup','avatar-restore'))
    @staticmethod
    def command_original(command,intent):
        fields={'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}
        if intent['action']=='replace':fields.add('text')
        exact(command,fields);s=intent['scope'];need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and nonce(command['commandId'])
            and command['bridgeId']==s['instance'] and command['generation']==s['generation'] and command['sequence']==s['sequence']+1
            and command['observedElapsedMs']==s['elapsedMs'] and all(command[k]==intent[k] for k in ('controlId','controlToken','action')))
    def save(self):
        self.bound();self.check(self.state)
        value=dict(picoAvatarUrlsOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([self.state]))
        self.store.write(value,self.previous);self.previous=deepcopy(value);self.bound()
        if self.anchor is not None:self.fresh_current()
    def reader(self):
        value=self.native();need(isinstance(value,NativePicoAvatarState) and value.pid==self.pid)
        if self.state['frames']:value.restore([packet(f['native'],self.pid) for f in self.state['frames']])
        return value
    def phase_fence(self,original=None):
        self.bound();current=self.phase.status(previous=self.state['frames'][-1]['phaseAfter'] if self.state['frames'] else None);self.phase_original(current)
        if original is not None:need(current['active']==original['active'] and same(current['activations'],original['activations']))
        if self.state['pending'] is not None or self._reconciling:
            call=self.state['calls'][-1];need((current['active'] or call['verb']=='cleanup') and same(current['activations'],call['phase']['activations']) and current['activations'][-1]['ticket']==call['ticket'])
        return current
    def fresh_current(self):
        need(self.anchor is not None and self.state['frames']);start,epoch,clock=self.anchor
        now=self.monotonic();need(number(now,start,1e15));actual=clock();need(integer(actual,epoch))
        floor=max(actual,epoch+math.ceil((now-start)*1000));frame=self.state['frames'][-1]
        fresh(packet(frame['native'],self.pid)['capturedEpochMs'],max(floor,frame['phaseAfter']['capturedEpochMs']))
        phase_epoch=self.phase.epoch_ms();need(number(phase_epoch,1,1e15))
        fresh(frame['phaseAfter']['capturedEpochMs'],max(math.ceil(phase_epoch),frame['phaseAfter']['capturedEpochMs']+math.ceil((now-frame['hostFinished'])*1000)))
        validate_snapshot(frame['widgets'],self.pid,floor)
    def sample(self):
        self.bound();need(len(self.state['frames'])<128)
        reader=self.reader();started=self.monotonic();epoch=reader.clock_ms();need(integer(epoch,1));self.anchor=None
        before=self.phase_fence();value=reader.read();widgets=self.widgets();after=self.phase_fence(before)
        validate_snapshot(widgets,self.pid,reader.clock_ms());project(widgets)
        need(widgets['bridgeId']==self.binding['sessionId'] and value['capturedEpochMs']<=widgets['updatedEpochMs'])
        ended=self.monotonic();need(number(ended,started,started+1.5) and reader.last_raw is not None and decode(reader.last_raw)==value)
        frame=dict(native=dict(raw=reader.last_raw,sha256=reader.last_sha256),widgets=deepcopy(widgets),phaseBefore=before,phaseAfter=after,hostStarted=started,hostFinished=ended)
        self.state['frames'].append(frame)
        if self.state['baseline'] is None:self.state['baseline']=deepcopy(frame)
        self.anchor=(started,epoch,reader.clock_ms);self.save();return self.finish(frame)
    def finish(self,frame):
        retained=deepcopy(frame);self.bound();self.phase_fence(frame['phaseAfter']);self.fresh_current();return retained
    def record_input(self,intent):
        self.bound();need(self.state['pending'] is not None and len(self.state['inputs'])<128)
        self.sample();self.phase_fence();self.fresh_current();self.state['inputs'].append(dict(ticket=self.state['pending'],intent=deepcopy(intent),command=None));self.save()
    def before_send(self,command,navigation):
        self.bound();need(self.state['pending'] is not None and self.state['inputs']);self.phase_fence();self.fresh_current()
        row=self.state['inputs'][-1];need(row['ticket']==self.state['pending'] and row['command'] is None);self.command_original(command,row['intent'])
        # Only the exact privately owned input is publishable after the last SDK
        # guard. A new fixture phase or expired native anchor prevents dispatch.
        identifier=command['controlId'];call=self.state['calls'][-1]
        need(identifier in ('tablet.home','avatar.entry','avatar.url','avatar.dialog.input','avatar.dialog.confirm','avatar.dialog.cancel') or identifier.startswith('tablet.page.'))
        if command['action']=='replace':need(identifier=='avatar.dialog.input' and command['text']==call['url'])
        else:need(command['action']=='activate')
        need(identifier!='avatar.dialog.cancel' or call['verb']=='cleanup')
        row['command']=deepcopy(command);self.save();self.phase_fence();self.bound();self.fresh_current()
    def controls(self):
        ui=self.controls_factory(self.record_input,self._before_send);need(isinstance(ui,TokenAvatarPeopleUI));return ui
    def matches(self,source,call,baseline=None,before=None):
        baseline=packet(self.state['baseline']['native'],self.pid)['source'] if baseline is None else baseline
        need(source['sessionId']==baseline['sessionId'] and source['modelInstance']==baseline['modelInstance'])
        before=packet(self.state['frames'][call['before']-1]['native'],self.pid)['source'] if before is None else before
        if source['requestedUrl']!=call['url'] or source['preferenceUrl']!=call['url'] or not same(source['avatarEntityStorage'],baseline['avatarEntityStorage']) or any(abs(source[k]-before[k])>.0001 for k in ('scale','targetScale')):return False
        if source['modelLoads']['requestedSha256']!=sha(source['modelUrl']):return False
        if call['verb'] in ('avatar-restore','cleanup'):
            return all(same(source[k],baseline[k]) for k in ('requestedUrl','preferenceUrl','modelName','avatarEntityStorage','modelUrl','scale','targetScale','hipsJoint','loaded','rigId','localRenderingEnabled')) and source['geometry'] is not None and baseline['geometry'] is not None and source['geometry']['url']==baseline['geometry']['url'] and not failed(source)
        if source['avatarLoads']['currentGeneration']!=before['avatarLoads']['currentGeneration']+1:return False
        if call['url'].endswith('/missing.fst'):
            return failed(source) and any(e['kind']=='finished' and e['success'] is False and e['requestedSha256']==sha(call['url']) and e['resourceSha256']==sha(call['url']) and e['capturedEpochMs']>=before['modelLoads']['capturedEpochMs'] for e in source['modelLoads']['events']) and (not source['loaded'] or source['geometry']['url']=='qrc:/meshes/mannequin/mannequin.fbx')
        return source['modelUrl']==call['url'] and source['loaded'] and source['geometry']['url']==loaded_url(call['url']) and any(e['generation']==source['modelLoads']['currentGeneration'] and e['kind']=='finished' and e['success'] is True and e['resourceSha256']==sha(call['url']) for e in source['modelLoads']['events']) and not failed(source) and source['hipsJoint']>=0 and source['avatarLoads']['requestedSha256']==sha(call['url']) and any(e['generation']==source['avatarLoads']['currentGeneration'] and e['kind']=='finished' and e['success'] is True and e['resourceSha256']==sha(call['url']) for e in source['avatarLoads']['events'])
    @staticmethod
    def stable(source):
        value={k:deepcopy(source[k]) for k in ('requestedUrl','preferenceUrl','modelName','avatarEntityStorage','modelUrl','modelInstance','rigId','geometry','loaded','scale','targetScale','hipsJoint')}
        for key in ('avatarLoads','modelLoads'):value[key]=deepcopy(source[key]['events'])
        return value
    def quiet_original(self,state,call):
        proof=call['quiet'];exact(proof,{'first','last'})
        need(integer(proof['first'],1,len(state['frames'])) and integer(proof['last'],proof['first']+1,len(state['frames'])))
        frames=state['frames'][proof['first']-1:proof['last']];baseline=packet(state['baseline']['native'],self.pid)['source'];previous=None;stable=None
        for frame in frames:
            actual=packet(frame['native'],self.pid);source=actual['source'];need(self.matches(source,call,baseline,packet(state['frames'][call['before']-1]['native'],self.pid)['source']))
            need(same(frame['phaseAfter']['activations'],call['phase']['activations']) and (frame['phaseAfter']['active'] or call['verb']=='cleanup'))
            observed=self.stable(source);need(stable is None or same(stable,observed));stable=observed
            if previous is not None:need(0<=frame['hostFinished']-previous['hostFinished']<=.5 and 0<=actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']<=500)
            previous=frame
        need(frames[-1]['hostFinished']-frames[0]['hostFinished']>=3 and packet(frames[-1]['native'],self.pid)['capturedEpochMs']-packet(frames[0]['native'],self.pid)['capturedEpochMs']>=3000)

    def settle(self):
        need(self.state['pending'] is not None or self._reconciling);started=self.monotonic();quiet=None;native_start=None;stable=None;quiet_index=None;previous_time=None
        for attempt in range(103):
            frame=self.sample();value=packet(frame['native'],self.pid);source=value['source'];call=self.state['calls'][-1]
            observed=self.stable(source)
            ready=self.matches(source,call);now=self.monotonic()
            if previous_time is not None and (now-previous_time[0]>.5 or value['capturedEpochMs']-previous_time[1]>500):quiet=native_start=stable=quiet_index=None
            previous_time=(now,value['capturedEpochMs'])
            if ready and (stable is None or stable==observed):
                if quiet is None:quiet=now;native_start=value['capturedEpochMs'];stable=observed;quiet_index=len(self.state['frames'])
                if now-quiet>=3 and value['capturedEpochMs']-native_start>=3000:
                    self.phase_fence();self.fresh_current();call['quiet']=dict(first=quiet_index,last=len(self.state['frames']));call['settled']=True;self.state['pending']=None
                    self.state['restored']=call['verb'] in ('avatar-restore','cleanup');self.state['stage']='restored' if self.state['restored'] else 'active';self.save();return self.finish(frame)
            else:quiet=native_start=stable=quiet_index=None
            need(now-started<20 and attempt<102);self.sleep(.25)
        raise NativeUIError('Original Avatar URL/model effect did not settle')
    def baseline_quiet(self,state):
        frames=state['frames'][:state['prepared']];first=frames[0];base=packet(first['native'],self.pid)['source'];previous=None
        for frame in frames:
            actual=packet(frame['native'],self.pid)
            need(same(self.stable(actual['source']),self.stable(base)) and same(frame['phaseAfter']['activations'],first['phaseAfter']['activations']) and frame['phaseAfter']['active'])
            if previous is not None:need(0<=frame['hostFinished']-previous['hostFinished']<=.5 and 0<=actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']<=500)
            previous=frame
        need(frames[-1]['hostFinished']-first['hostFinished']>=3 and packet(frames[-1]['native'],self.pid)['capturedEpochMs']-packet(first['native'],self.pid)['capturedEpochMs']>=3000)
    def prepare(self):
        need(self.state['stage']=='reserved' and not self.state['calls'] and not self.state['frames']);current=self.phase_fence();need(self.phase_original(current)['stimulus']==dict(verb='baseline',inputs={}))
        first=self.sample();source=packet(first['native'],self.pid)['source'];need(source['loaded'] and source['geometry'] is not None and not failed(source)
            and source['hipsJoint']>=0 and abs(source['scale']-source['targetScale'])<.0001)
        need(source['requestedUrl']==source['preferenceUrl'] and source['modelUrl']==source['requestedUrl'] and source['modelLoads']['requestedSha256']==sha(source['modelUrl']))
        text(source['requestedUrl']);previous=first
        for attempt in range(14):
            self.sleep(.25);frame=self.sample();actual=packet(frame['native'],self.pid)
            need(same(self.stable(actual['source']),self.stable(source)) and same(frame['phaseAfter']['activations'],first['phaseAfter']['activations'])
                and frame['hostFinished']-previous['hostFinished']<=.5 and actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']<=500)
            if frame['hostFinished']-first['hostFinished']>=3 and actual['capturedEpochMs']-packet(first['native'],self.pid)['capturedEpochMs']>=3000:
                self.state['prepared']=len(self.state['frames']);self.state['stage']='active';self.save();return self.finish(frame)
            previous=frame
        raise NativeUIError('Original Avatar baseline did not become independently quiet')
    def act(self,*,cleanup=False):
        need(self.state['baseline'] is not None and self.state['stage'] in ('active','restored') and self.state['pending'] is None and (not self.state['unresolved'] or cleanup))
        self.sample();baseline=packet(self.state['baseline']['native'],self.pid)['source'];before=packet(self.state['frames'][-1]['native'],self.pid)['source']
        need(all(abs(before[k]-baseline[k])<=.0001 for k in ('scale','targetScale')) and same(before['avatarEntityStorage'],baseline['avatarEntityStorage'])
            and self.state['frames'][-1]['widgets']['open'] and self.state['frames'][-1]['widgets']['ready'])
        phase=self.phase_fence();activation=self.phase_original(phase);verb=activation['stimulus']['verb'];ticket=activation['ticket']
        if verb=='cleanup':
            owned={baseline['requestedUrl']}|{r['url'] for r in self.state['calls']}
            need(before['requestedUrl'] in owned and before['preferenceUrl']==before['requestedUrl']
                and before['avatarLoads']['requestedSha256']==sha(before['requestedUrl'])
                and before['modelLoads']['requestedSha256']==sha(before['modelUrl'])
                and before['modelUrl'] in {before['requestedUrl'],'qrc:/meshes/defaultAvatar_full.fst'})
        else:
            if self.state['calls'] and self.state['calls'][-1]['settled']:
                old=self.state['calls'][-1];known=packet(self.state['frames'][old['quiet']['last']-1]['native'],self.pid)['source'];need(self.matches(before,old))
            else:
                known=baseline;need(self.matches(before,dict(verb='cleanup',url=baseline['requestedUrl'],before=1)))
            need(all(before[k]['currentGeneration']==known[k]['currentGeneration'] for k in ('avatarLoads','modelLoads')))
        need((not cleanup or verb=='cleanup') and (phase['active'] or verb=='cleanup') and verb in ('avatar-url','avatar-restore','cleanup') and ticket not in {r['ticket'] for r in self.state['calls']} and len(self.state['calls'])<8)
        if verb=='avatar-url':
            resource=activation['stimulus']['inputs']['resource'];need(resource in ('avatar-a.fst','missing.fst'));url=self.phase.fixture_url+'tickets/'+ticket+'/'+resource
        else:url=packet(self.state['baseline']['native'],self.pid)['source']['requestedUrl']
        self.state['calls'].append(dict(ticket=ticket,verb=verb,url=url,phase=phase,attempted=False,settled=False,quiet=None,before=len(self.state['frames'])));self.state['pending']=ticket;self.state['restored']=False
        if verb=='cleanup':self.state['stage']='restoring'
        self.save();call=self.state['calls'][-1];call['attempted']=True;self.save()
        ui=self.controls();ui.open()
        if verb=='cleanup' and ui.row(ui.capture(),'avatar.dialog.cancel') is not None:ui.input('avatar.dialog.cancel')
        current=packet(self.state['frames'][-1]['native'],self.pid)['source']
        if not (verb=='cleanup' and self.matches(current,call)):ui.set_url(url)
        return self.settle()
    def cleanup(self):
        need(self.state['baseline'] is not None)
        self.bound();phase=self.phase.status(previous=self.state['frames'][-1]['phaseAfter']);activation=self.phase_original(phase)
        need(activation['stimulus']==dict(verb='cleanup',inputs={}))
        if self.state['pending'] is not None:
            need(self.state['calls'][-1]['verb']!='cleanup')
            self.state['unresolved'].append(self.state['pending']);self.state['pending']=None;self.anchor=None;self.save()
        # Normal cleanup may restore an original URL while retaining all earlier
        # uncertain tickets. It cannot discard them or qualify whole cleanup.
        return self.act(cleanup=True)

    def reconcile(self):
        # Uncertain input is observed, never replayed. Earlier focused fields or
        # absent effects remain pending and cannot become a consumed checkpoint.
        need(self.state['pending'] is not None or self.state['calls'] and self.state['calls'][-1]['settled'])
        self._reconciling=True
        try:return self.settle()
        finally:self._reconciling=False
    def invoke(self,operation):
        need(operation in ('prepare','act','sample','reconcile','cleanup'))
        with self.lock.held():
            try:return getattr(self,operation)()
            except Exception:self.failed=True;raise
