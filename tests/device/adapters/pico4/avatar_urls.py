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
import os
import re
import stat
import time
from urllib.parse import urljoin
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import context,PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.avatar_state import NativePicoAvatarState,ACTION,validate,continuity,failed,sha
from adapters.pico4 import avatar_preferences as preference_source
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI,control_id,text,project
from adapters.pico4.navigation import validate_snapshot
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import scope,nonce
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.fixtures import pinned_resource

VERSION=2


def packet(record,pid):
    exact(record,{'raw','sha256'});need(type(record['raw']) is str and sha(record['raw'])==record['sha256'])
    value=decode(record['raw']);validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION),pid,value.get('capturedEpochMs'));return value


def loaded_url(url):
    # Read the existing immutable common FST foundation rather than inventing a
    # requested geometry URL or guessing a successful Model's current URL.
    fst=pinned_resource('avatar-a.fst').decode('utf-8');rows=[line.split('=',1)[1].strip() for line in fst.splitlines() if line.split('=',1)[0].strip()=='filename' and '=' in line]
    need(rows==['mannequin/mannequin.fbx']);return urljoin(url,rows[0])


class PicoAvatarUrls:
    def __init__(self,store,binding,phase,lock,native,widgets,controls,guard,*,preferences,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people' and isinstance(lock,ScriptSourceLock)
            and all(callable(v) for v in (native,widgets,controls,guard,preferences,monotonic,sleep)))
        self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.native,self.widgets,self.controls_factory,self.guard,self.monotonic,self.sleep=native,widgets,controls,guard,monotonic,sleep
        self.pid=int(binding['processIdentity'].split(':')[0]);need(integer(self.pid,1));self.run=phase.run
        prefix='avatar-urls-owner-';suffix='-'+self.run+'.json';name=self.store.path.name
        need(name.startswith(prefix) and name.endswith(suffix));artifact_key=name[len(prefix):-len(suffix)]
        need(re.fullmatch('[0-9a-f]{32}',artifact_key) is not None)
        self.frame_prefix='avatar-urls-frame-'+artifact_key+'-'+self.run+'-'
        self.preferences_factory,self.preferences_reader,self.version=preferences,None,VERSION
        self._frame_references={};self._frame_originals={};self._frame_files={}
        self.previous=store.read();self.clock=self.anchor=None;self.failed=False;self._reconciling=False;self._before_send=self.before_send
        self.state=dict(stage='reserved',baseline=None,baselineIndex=None,prepared=None,frames=[],calls=[],inputs=[],pending=None,unresolved=[],restored=False)
        self.bound()
        if self.previous is not None:self.state=self.restore(self.previous)
    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.previous,self.store.read()))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock));self.clock=now
    def restore(self,value):
        exact(value,{'picoAvatarUrlsOwnerVersion','binding','runId','fixtureUrl','payload'})
        need(type(value['picoAvatarUrlsOwnerVersion']) is int and value['picoAvatarUrlsOwnerVersion'] in (1,VERSION) and same(value['binding'],self.binding)
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url)
        self.version=value['picoAvatarUrlsOwnerVersion']
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        if self.version>=2:
            need(type(state) is dict and type(state.get('frames')) is list and len(state['frames'])<=128)
            if state['frames']:
                need(integer(state.get('baselineIndex'),1,len(state['frames'])) and same(state.get('baseline'),state['frames'][state['baselineIndex']-1]))
            else:need(state.get('baseline') is None and state.get('baselineIndex') is None)
            state['frames']=[self.frame_original(reference) for reference in state['frames']]
            state['baseline']=None if not state['frames'] else deepcopy(state['frames'][state['baselineIndex']-1])
        self.check(state);return deepcopy(state)
    def phase_original(self,value):
        phase_packet(value,run=self.run,area='avatar-people',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
        need(value['activations']);return value['activations'][-1]
    def check(self,state):
        exact(state,{'stage','baseline','prepared','frames','calls','inputs','pending','unresolved','restored'}|({'baselineIndex'} if self.version>=2 else set()))
        need(state['stage'] in ('reserved','active','restoring','restored') and type(state['restored']) is bool
            and type(state['frames']) is list and len(state['frames'])<=128 and type(state['calls']) is list and len(state['calls'])<=8
            and type(state['inputs']) is list and len(state['inputs'])<=128 and (state['pending'] is None or nonce(state['pending'])))
        need(type(state['unresolved']) is list and len(set(state['unresolved']))==len(state['unresolved']) and len(state['unresolved'])<=8)
        previous=None;previous_preferences=None;last_phase=None
        for frame in state['frames']:
            exact(frame,{'native','widgets','phaseBefore','phaseAfter','hostStarted','hostFinished'}|({'preferences'} if self.version>=2 else set()))
            need(number(frame['hostStarted'],0,1e15) and number(frame['hostFinished'],frame['hostStarted'],frame['hostStarted']+1.5))
            actual=packet(frame['native'],self.pid);continuity(previous,actual);previous=actual
            if self.version>=2:
                current_preferences=self.preference_packet(frame['preferences']);preference_source.continuity(previous_preferences,current_preferences);previous_preferences=current_preferences
                self.preference_join(actual,current_preferences)
            validate_snapshot(frame['widgets'],self.pid,frame['widgets']['updatedEpochMs']);project(frame['widgets'])
            need(frame['widgets']['bridgeId']==self.binding['sessionId'])
            self.phase_original(frame['phaseBefore']);self.phase_original(frame['phaseAfter'])
            if last_phase is not None:phase_packet(frame['phaseBefore'],run=self.run,area='avatar-people',request=frame['phaseBefore']['requestId'],epoch=frame['phaseBefore']['capturedEpochMs'],previous=last_phase)
            last_phase=frame['phaseAfter']
            need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']) and frame['phaseBefore']['active']==frame['phaseAfter']['active'])
        need((state['baseline'] is None)==(not state['frames']))
        if self.version>=2:
            need((state['baselineIndex'] is None)==(not state['frames']))
            if state['baseline'] is not None:need(integer(state['baselineIndex'],1,len(state['frames'])) and same(state['baseline'],state['frames'][state['baselineIndex']-1]))
        elif state['baseline'] is not None:need(same(state['baseline'],state['frames'][0]))
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
            if self.version>=2:
                original_phase=state['frames'][call['before']-1]['phaseAfter']
                need(self.phase_original(original_phase)['ticket']==call['ticket'] and same(original_phase['activations'],call['phase']['activations']))
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
    def frame_original(self,reference):
        exact(reference,{'avatarUrlFrameVersion','name','sha256'})
        need(type(reference['avatarUrlFrameVersion']) is int and reference['avatarUrlFrameVersion']==1
            and type(reference['sha256']) is str and len(reference['sha256'])==64 and all(c in '0123456789abcdef' for c in reference['sha256']))
        name=self.frame_prefix+reference['sha256'][:32]+'.json';need(reference['name']==name)
        if reference['sha256'] in self._frame_references:
            need(same(self._frame_references[reference['sha256']],reference));self.verify_frame_file(reference)
            return deepcopy(self._frame_originals[reference['sha256']])
        record=PrivateFeatureState(self.store.path.with_name(name)).read();need(record is not None)
        exact(record,{'avatarUrlFrameVersion','binding','runId','fixtureUrl','payload'})
        need(type(record['avatarUrlFrameVersion']) is int and record['avatarUrlFrameVersion']==1 and same(record['binding'],self.binding)
            and record['runId']==self.run and record['fixtureUrl']==self.phase.fixture_url)
        values=unpack(record['payload']);need(len(values)==1 and hashlib.sha256(canonical(values[0])).hexdigest()==reference['sha256'])
        self.verify_frame_file(reference,canonical(record)+b'\n')
        self._frame_references[reference['sha256']]=deepcopy(reference);self._frame_originals[reference['sha256']]=deepcopy(values[0]);return values[0]
    @staticmethod
    def frame_stamp(info):
        return (info.st_dev,info.st_ino,info.st_uid,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
    def verify_frame_file(self,reference,original=None):
        # Cache only parsing/decompression. Every admission and final input
        # fence rereads the original bounded descriptor, inode/stamps and bytes.
        store=PrivateFeatureState(self.store.path.with_name(reference['name']));store._parent();before=store.path.lstat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=65536
            and (os.name=='nt' or before.st_uid==os.geteuid() and stat.S_IMODE(before.st_mode)==0o600))
        descriptor=os.open(store.path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            opened=os.fstat(stream.fileno());need(self.frame_stamp(before)==self.frame_stamp(opened))
            raw=stream.read(65537);after=os.fstat(stream.fileno());current=store.path.lstat()
        stamp=self.frame_stamp(current);need(stamp==self.frame_stamp(after)==self.frame_stamp(opened) and len(raw)==current.st_size)
        observed=(stamp,hashlib.sha256(raw).hexdigest());digest=reference['sha256']
        if digest in self._frame_files:need(self._frame_files[digest]==observed)
        else:need(original is not None and raw==original);self._frame_files[digest]=observed
    def verify_frames(self):
        if self.version>=2:
            for frame in self.state['frames']:
                digest=hashlib.sha256(canonical(frame)).hexdigest();need(digest in self._frame_references)
                self.verify_frame_file(self._frame_references[digest])
    def frame_reference(self,frame):
        # Fixed Phone5527 content-addressed private blob foundation. An original
        # frame is never truncated to fit the root CAS envelope. Every leaf
        # keeps the existing pack/PrivateFeatureState limits and exact binding.
        digest=hashlib.sha256(canonical(frame)).hexdigest()
        if digest in self._frame_references:
            need(same(self._frame_originals[digest],frame));self.verify_frame_file(self._frame_references[digest]);return deepcopy(self._frame_references[digest])
        name=self.frame_prefix+digest[:32]+'.json';reference=dict(avatarUrlFrameVersion=1,name=name,sha256=digest)
        record=dict(avatarUrlFrameVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([frame]))
        store=PrivateFeatureState(self.store.path.with_name(name));old=store.read()
        if old is None:store.write(record,None)
        else:need(same(old,record))
        need(same(store.read(),record));self.verify_frame_file(reference,canonical(record)+b'\n')
        self._frame_references[digest]=deepcopy(reference);self._frame_originals[digest]=deepcopy(frame);return reference
    def save(self):
        self.bound();self.check(self.state)
        payload=deepcopy(self.state)
        if self.version>=2:
            payload['frames']=[self.frame_reference(frame) for frame in self.state['frames']]
            payload['baseline']=None if not payload['frames'] else deepcopy(payload['frames'][payload['baselineIndex']-1])
        value=dict(picoAvatarUrlsOwnerVersion=self.version,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([payload]))
        self.store.write(value,self.previous);self.previous=deepcopy(value);self.bound()
        if self.anchor is not None:self.fresh_current()
    def reader(self):
        value=self.native();need(isinstance(value,NativePicoAvatarState) and value.pid==self.pid)
        if self.state['frames']:value.restore([packet(f['native'],self.pid) for f in self.state['frames']])
        return value
    def preference_packet(self,record):
        exact(record,{'raw','sha256'});need(type(record['raw']) is str and sha(record['raw'])==record['sha256'])
        value=decode(record['raw']);preference_source.validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=preference_source.ACTION),self.pid,value.get('capturedEpochMs'));return value
    @staticmethod
    def preference_join(native,preferences):
        source=native['source'];actual=preferences['source']['snapshot']['cache']['native'];live=actual['live']
        need(source['modelInstance']==actual['modelInstance'] and source['sessionId']==actual['sessionId']
            and source['preferenceUrl']==live['preferenceUrl'] and source['modelName']==live['modelName']
            and all(abs(source[k]-live[k])<.0001 for k in ('scale','targetScale')))
    def preference_reader(self):
        if self.preferences_reader is None:
            value=self.preferences_factory();need(isinstance(value,preference_source.NativePicoAvatarPreferences) and value.pid==self.pid)
            if self.state['frames']:value.restore([self.preference_packet(f['preferences']) for f in self.state['frames']])
            self.preferences_reader=value
        return self.preferences_reader
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
        if self.version>=2:fresh(self.preference_packet(frame['preferences'])['capturedEpochMs'],max(floor,frame['phaseAfter']['capturedEpochMs']))
    def sample(self):
        self.bound();need(len(self.state['frames'])<128)
        reader=self.reader();started=self.monotonic();epoch=reader.clock_ms();need(integer(epoch,1));self.anchor=None
        before=self.phase_fence();value=reader.read()
        preferences=None
        if self.version>=2:
            preferences=self.preference_reader();actual_preferences=preferences.read();self.preference_join(value,actual_preferences)
        widgets=self.widgets();after=self.phase_fence(before)
        validate_snapshot(widgets,self.pid,reader.clock_ms());project(widgets)
        need(widgets['bridgeId']==self.binding['sessionId'] and value['capturedEpochMs']<=widgets['updatedEpochMs'])
        ended=self.monotonic();need(number(ended,started,started+1.5) and reader.last_raw is not None and decode(reader.last_raw)==value)
        frame=dict(native=dict(raw=reader.last_raw,sha256=reader.last_sha256),widgets=deepcopy(widgets),phaseBefore=before,phaseAfter=after,hostStarted=started,hostFinished=ended)
        if preferences is not None:
            need(preferences.last_raw is not None and decode(preferences.last_raw)==actual_preferences);frame['preferences']=dict(raw=preferences.last_raw,sha256=preferences.last_sha256)
        self.state['frames'].append(frame)
        if self.state['baseline'] is None:
            self.state['baseline']=deepcopy(frame)
            if self.version>=2:self.state['baselineIndex']=len(self.state['frames'])
        self.anchor=(started,epoch,reader.clock_ms);self.save();return self.finish(frame)
    def finish(self,frame):
        retained=deepcopy(frame);self.bound();self.phase_fence(frame['phaseAfter']);self.verify_frames();self.fresh_current();return retained
    def record_input(self,intent):
        self.bound();need(self.version>=2 and self.state['pending'] is not None and len(self.state['inputs'])<128)
        self.sample();self.phase_fence();self.fresh_current();self.state['inputs'].append(dict(ticket=self.state['pending'],intent=deepcopy(intent),command=None));self.save()
    def before_send(self,command,navigation):
        self.bound();need(self.version>=2 and self.state['pending'] is not None and self.state['inputs']);self.phase_fence();self.fresh_current()
        row=self.state['inputs'][-1];need(row['ticket']==self.state['pending'] and row['command'] is None);self.command_original(command,row['intent'])
        # Only the exact privately owned input is publishable after the last SDK
        # guard. A new fixture phase or expired native anchor prevents dispatch.
        identifier=command['controlId'];call=self.state['calls'][-1]
        need(identifier in ('tablet.home','avatar.entry','avatar.url','avatar.dialog.input','avatar.dialog.confirm','avatar.dialog.cancel') or identifier.startswith('tablet.page.'))
        if command['action']=='replace':need(identifier=='avatar.dialog.input' and command['text']==call['url'])
        else:need(command['action']=='activate')
        need(identifier!='avatar.dialog.cancel' or call['verb']=='cleanup')
        row['command']=deepcopy(command);self.save();self.phase_fence();self.verify_frames();self.bound();self.fresh_current()
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
        frames=state['frames'][proof['first']-1:proof['last']];baseline=packet(state['baseline']['native'],self.pid)['source'];previous=None;stable=None;stable_preferences=None
        for frame in frames:
            actual=packet(frame['native'],self.pid);source=actual['source'];need(self.matches(source,call,baseline,packet(state['frames'][call['before']-1]['native'],self.pid)['source']))
            need(same(frame['phaseAfter']['activations'],call['phase']['activations']) and (frame['phaseAfter']['active'] or call['verb']=='cleanup'))
            observed=self.stable(source);need(stable is None or same(stable,observed));stable=observed
            if self.version>=2:
                actual_preferences=self.preference_stable(self.preference_packet(frame['preferences']))
                need(stable_preferences is None or same(stable_preferences,actual_preferences));stable_preferences=actual_preferences
            if previous is not None:need(0<=frame['hostFinished']-previous['hostFinished']<=.5 and 0<=actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']<=500)
            if self.version>=2 and previous is not None:need(0<=self.preference_packet(frame['preferences'])['source']['snapshot']['capturedEpochMs']-self.preference_packet(previous['preferences'])['source']['snapshot']['capturedEpochMs']<=500)
            previous=frame
        need(frames[-1]['hostFinished']-frames[0]['hostFinished']>=3 and packet(frames[-1]['native'],self.pid)['capturedEpochMs']-packet(frames[0]['native'],self.pid)['capturedEpochMs']>=3000)
        if self.version>=2:need(self.preference_packet(frames[-1]['preferences'])['source']['snapshot']['capturedEpochMs']-self.preference_packet(frames[0]['preferences'])['source']['snapshot']['capturedEpochMs']>=3000)

    def settle(self):
        need(self.state['pending'] is not None or self._reconciling);started=self.monotonic();quiet=None;native_start=None;stable=None;quiet_index=None;previous_time=None
        for attempt in range(103):
            frame=self.sample();value=packet(frame['native'],self.pid);source=value['source'];call=self.state['calls'][-1]
            observed=self.stable(source);ready=self.matches(source,call)
            if self.version>=2:
                preferences=self.preference_packet(frame['preferences']);snapshot=preferences['source']['snapshot']
                physical_ready=snapshot['cacheMatchesWriter'] and snapshot['writer']['matchesPhysical']
                observed=dict(native=observed,preferences=self.preference_stable(preferences) if physical_ready else None);ready=ready and physical_ready
            now=self.monotonic()
            preference_epoch=value['capturedEpochMs'] if self.version==1 else snapshot['capturedEpochMs']
            if previous_time is not None and (now-previous_time[0]>.5 or value['capturedEpochMs']-previous_time[1]>500 or preference_epoch-previous_time[2]>500):quiet=native_start=stable=quiet_index=None
            previous_time=(now,value['capturedEpochMs'],preference_epoch)
            if ready and (stable is None or stable==observed):
                if quiet is None:quiet=now;native_start=value['capturedEpochMs'];stable=observed;quiet_index=len(self.state['frames'])
                preference_quiet=self.version==1 or self.preference_packet(frame['preferences'])['source']['snapshot']['capturedEpochMs']-self.preference_packet(self.state['frames'][quiet_index-1]['preferences'])['source']['snapshot']['capturedEpochMs']>=3000
                if now-quiet>=3 and value['capturedEpochMs']-native_start>=3000 and preference_quiet:
                    self.phase_fence();self.fresh_current();call['quiet']=dict(first=quiet_index,last=len(self.state['frames']));call['settled']=True;self.state['pending']=None
                    self.state['restored']=call['verb'] in ('avatar-restore','cleanup');self.state['stage']='restored' if self.state['restored'] else 'active';self.save();return self.finish(frame)
            else:quiet=native_start=stable=quiet_index=None
            need(now-started<20 and attempt<102);self.sleep(.25)
        raise NativeUIError('Original Avatar URL/model effect did not settle')
    @staticmethod
    def preference_stable(value):
        snapshot=preference_source.baseline(value)
        return dict(instance=value['source']['instance'],manager=snapshot['instance'],mutationSequence=snapshot['mutationSequence'],cache=snapshot['cache'],
            writer=snapshot['writer']['instance'],writerRows=snapshot['writer']['rows'],encodedRows=snapshot['writer']['encodedRows'],
            physicalRows=snapshot['writer']['physical']['rows'],physicalPath=snapshot['writer']['physical']['pathSha256'])
    def baseline_quiet(self,state):
        if self.version>=2:need(integer(state['prepared'],state['baselineIndex']+1,len(state['frames'])))
        frames=state['frames'][(state['baselineIndex']-1 if self.version>=2 else 0):state['prepared']];first=frames[0];base=packet(first['native'],self.pid)['source'];previous=None
        need(self.phase_original(first['phaseBefore'])['stimulus']==dict(verb='baseline',inputs={}))
        preferences=None if self.version==1 else self.preference_stable(self.preference_packet(first['preferences']))
        for frame in frames:
            actual=packet(frame['native'],self.pid)
            if self.version>=2:
                actual_preferences=self.preference_packet(frame['preferences']);preference_source.baseline(actual_preferences)
                need(same(preferences,self.preference_stable(actual_preferences)))
            need(same(self.stable(actual['source']),self.stable(base)) and same(frame['phaseAfter']['activations'],first['phaseAfter']['activations']) and frame['phaseAfter']['active'])
            if previous is not None:need(0<=frame['hostFinished']-previous['hostFinished']<=.5 and 0<=actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']<=500)
            if self.version>=2 and previous is not None:need(0<=self.preference_packet(frame['preferences'])['source']['snapshot']['capturedEpochMs']-self.preference_packet(previous['preferences'])['source']['snapshot']['capturedEpochMs']<=500)
            previous=frame
        need(frames[-1]['hostFinished']-first['hostFinished']>=3 and packet(frames[-1]['native'],self.pid)['capturedEpochMs']-packet(first['native'],self.pid)['capturedEpochMs']>=3000)
        if self.version>=2:need(self.preference_packet(frames[-1]['preferences'])['source']['snapshot']['capturedEpochMs']-self.preference_packet(first['preferences'])['source']['snapshot']['capturedEpochMs']>=3000)
    def prepare(self):
        need(self.version>=2 and self.state['stage']=='reserved' and not self.state['calls'] and not self.state['inputs'])
        current=self.phase_fence();need(self.phase_original(current)['stimulus']==dict(verb='baseline',inputs={}))
        started=self.monotonic();first=previous=None;stable=None
        for attempt in range(83):
            frame=self.sample();actual=packet(frame['native'],self.pid);source=actual['source'];preferences=self.preference_packet(frame['preferences'])
            snapshot=preferences['source']['snapshot']
            ready=(source['loaded'] and source['geometry'] is not None and not failed(source) and source['hipsJoint']>=0
                and abs(source['scale']-source['targetScale'])<.0001 and source['requestedUrl']==source['preferenceUrl']
                and source['modelUrl']==source['requestedUrl'] and source['modelLoads']['requestedSha256']==sha(source['modelUrl'])
                and snapshot['cacheMatchesWriter'] and snapshot['writer']['matchesPhysical'])
            observed=None if not ready else dict(native=self.stable(source),preferences=self.preference_stable(preferences))
            gap=previous is not None and (frame['hostFinished']-previous['hostFinished']>.5 or actual['capturedEpochMs']-packet(previous['native'],self.pid)['capturedEpochMs']>500
                or snapshot['capturedEpochMs']-self.preference_packet(previous['preferences'])['source']['snapshot']['capturedEpochMs']>500)
            if not ready:first=stable=None
            elif first is None or gap or not same(stable,observed):
                first=frame;stable=observed
                # No input or attempted call exists. Retain every earlier real
                # sample while reserving the first actually settled baseline.
                self.state['baseline']=deepcopy(frame);self.state['baselineIndex']=len(self.state['frames']);self.save()
            elif frame['hostFinished']-first['hostFinished']>=3 and actual['capturedEpochMs']-packet(first['native'],self.pid)['capturedEpochMs']>=3000 and snapshot['capturedEpochMs']-self.preference_packet(first['preferences'])['source']['snapshot']['capturedEpochMs']>=3000:
                self.state['prepared']=len(self.state['frames']);self.state['stage']='active';self.save();return self.finish(frame)
            previous=frame;need(self.monotonic()-started<20 and attempt<82);self.sleep(.25)
        raise NativeUIError('Original Avatar baseline did not become independently quiet')
    def act(self,*,cleanup=False):
        need(self.version>=2 and self.state['baseline'] is not None and self.state['stage'] in ('active','restored') and self.state['pending'] is None and (not self.state['unresolved'] or cleanup))
        self.sample();baseline=packet(self.state['baseline']['native'],self.pid)['source'];before=packet(self.state['frames'][-1]['native'],self.pid)['source']
        need(all(abs(before[k]-baseline[k])<=.0001 for k in ('scale','targetScale')) and same(before['avatarEntityStorage'],baseline['avatarEntityStorage'])
            and self.state['frames'][-1]['widgets']['open'] and self.state['frames'][-1]['widgets']['ready'])
        phase=self.phase_fence(self.state['frames'][-1]['phaseAfter']);activation=self.phase_original(phase);verb=activation['stimulus']['verb'];ticket=activation['ticket']
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
        need(self.version>=2 and self.state['baseline'] is not None)
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
