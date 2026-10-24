"""Durable normal Favorite/Scale input with independent original sources.

No observed callback alone supplies loaded geometry. Exact native preference
and physical bookmark restoration, and whole Avatar/People retirement, remain
separate retained obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import math
import struct
import time
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.pico4 import avatar_state,avatar_preferences,avatar_bookmarks,avatar_bookmark_loads
from adapters.pico4.avatar_originals import AvatarOriginalFrames
from adapters.pico4.avatar_urls import PicoAvatarUrls
from adapters.pico4.avatar_people_ui import TokenAvatarPeopleUI,control_id,project
from adapters.pico4.navigation import validate_snapshot
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import scope,nonce,navigation
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.fixtures import context as fixture_context

VERSION=1
SOURCES={'native':avatar_state,'preferences':avatar_preferences,'bookmarks':avatar_bookmarks,'loads':avatar_bookmark_loads}
CLASSES={'native':avatar_state.NativePicoAvatarState,'preferences':avatar_preferences.NativePicoAvatarPreferences,
    'bookmarks':avatar_bookmarks.NativePicoAvatarBookmarks,'loads':avatar_bookmark_loads.NativePicoAvatarBookmarkLoads}
VERBS={'avatar-bookmark-save','avatar-scale','avatar-bookmark-choose','avatar-bookmark-delete','cleanup'}


def phase_original(value,run):
    phase_packet(value,run=run,area='avatar-people',request=value.get('requestId'),epoch=value.get('capturedEpochMs'))
    need(value['activations']);return value['activations'][-1]


def validate_frame(frame,pid,binding,run):
    exact(frame,set(SOURCES)|{'widgets','phaseBefore','phaseAfter','hostStarted','hostFinished'})
    need(number(frame['hostStarted'],0,1e15) and number(frame['hostFinished'],frame['hostStarted'],frame['hostStarted']+1.5))
    values={}
    for kind,module in SOURCES.items():
        raw=frame[kind];exact(raw,{'raw','sha256'});need(type(raw['raw']) is str and avatar_state.sha(raw['raw'])==raw['sha256'])
        value=decode(raw['raw']);module.validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=module.ACTION),pid,value.get('capturedEpochMs'));values[kind]=value
    need(len({v['instance'] for v in values.values()})==1)
    PicoAvatarUrls.preference_join(values['native'],values['preferences'])
    validate_snapshot(frame['widgets'],pid,frame['widgets']['updatedEpochMs']);project(frame['widgets']);need(frame['widgets']['bridgeId']==binding['sessionId']
        and all(value['capturedEpochMs']<=frame['widgets']['updatedEpochMs'] for value in values.values()))
    for key in ('phaseBefore','phaseAfter'):phase_original(frame[key],run)
    need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']) and frame['phaseBefore']['active']==frame['phaseAfter']['active'])
    return values


def input_frame(frame,row,binding,pid,run):
    intent=row['intent'];s=intent['scope'];value=frame['widgets']
    need(phase_original(frame['phaseAfter'],run)['ticket']==row['ticket'] and value['bridgeId']==binding['sessionId']==s['instance']
        and value['generation']==s['generation'] and value['lastCommandSequence']==s['sequence'] and value['processId']==pid==s['processId']
        and 0<=value['elapsedMs']-s['elapsedMs']<=5000 and value['open'] and value['ready'])
    rows=[actual for actual in value['controls'] if actual['id']==intent['controlId']]
    need(len(rows)==1 and rows[0]['token']==intent['controlToken'] and rows[0]['enabled'] and (navigation(rows[0]['id']) or rows[0]['inputReady']))


class PicoAvatarFavorites:
    def __init__(self,store,binding,phase,lock,sources,widgets,controls,guard,urls,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people' and isinstance(lock,ScriptSourceLock)
            and type(sources) is dict and set(sources)==set(SOURCES) and all(callable(v) for v in (*sources.values(),widgets,controls,guard,urls,monotonic,sleep)))
        self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.factories,self.widgets,self.controls_factory,self.guard,self.urls=sources,widgets,controls,guard,urls
        self.monotonic,self.sleep,self.pid,self.run=monotonic,sleep,int(binding['processIdentity'].split(':')[0]),phase.run
        self.name=fixture_context(self.run)['name'];self.archive=AvatarOriginalFrames(store,self.binding,self.run,phase.fixture_url,'favorites')
        self.readers={};self.clock=self.anchor=None;self.previous=store.read();self._before_send=self.before_send;self.url_reader=None
        self._validated={};self._pairs=set()
        self.state=dict(stage='reserved',frames=[],baselineIndex=None,prepared=None,calls=[],inputs=[],pending=None,unresolved=[])
        self.bound()
        if self.previous is not None:self.state=self.restore(self.previous)
    def bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock));self.clock=now
    def decode_frame(self,frame):
        digest=hashlib.sha256(canonical(frame)).hexdigest()
        if digest not in self._validated:self._validated[digest]=validate_frame(frame,self.pid,self.binding,self.run)
        return self._validated[digest]
    def activation(self,value):return phase_original(value,self.run)
    def restore(self,value):
        exact(value,{'picoAvatarFavoritesVersion','binding','runId','fixtureUrl','payload'})
        need(type(value['picoAvatarFavoritesVersion']) is int and value['picoAvatarFavoritesVersion']==1 and same(value['binding'],self.binding)
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        need(type(state) is dict and type(state.get('frames')) is list and len(state['frames'])<=128)
        state['frames']=[self.archive.frame_original(ref) for ref in state['frames']];self.check(state);return state
    def check(self,state):
        exact(state,{'stage','frames','baselineIndex','prepared','calls','inputs','pending','unresolved'})
        need(state['stage'] in ('reserved','active','cleaning','retained') and type(state['frames']) is list and len(state['frames'])<=128
            and type(state['calls']) is list and len(state['calls'])<=8 and type(state['inputs']) is list and len(state['inputs'])<=128
            and (state['pending'] is None or nonce(state['pending'])) and type(state['unresolved']) is list and len(set(state['unresolved']))==len(state['unresolved']))
        before=None;previous_frame=None
        for frame in state['frames']:
            current=self.decode_frame(frame)
            if before is not None:
                pair=(hashlib.sha256(canonical(previous_frame)).hexdigest(),hashlib.sha256(canonical(frame)).hexdigest())
                if pair not in self._pairs:
                    for key,module in SOURCES.items():module.continuity(before[key],current[key])
                    a,b=previous_frame['phaseAfter'],frame['phaseBefore'];need(len(b['activations'])>=len(a['activations']) and b['activations'][:len(a['activations'])]==a['activations'])
                    self._pairs.add(pair)
            before=current;previous_frame=frame
        need((state['baselineIndex'] is None)==(not state['frames']))
        if state['baselineIndex'] is not None:need(integer(state['baselineIndex'],1,len(state['frames'])))
        if state['prepared'] is None:need(state['stage']=='reserved' and not state['calls'])
        else:
            need(integer(state['prepared'],state['baselineIndex']+1,len(state['frames'])));self.quiet_original(state,state['baselineIndex'],state['prepared'],None)
        tickets=set()
        for call in state['calls']:
            exact(call,{'ticket','verb','phase','before','expected','urlAuthority','attempted','settled','quiet'})
            activation=self.activation(call['phase']);need(nonce(call['ticket']) and call['ticket'] not in tickets and call['ticket']==activation['ticket']
                and call['verb'] in VERBS and call['verb']==activation['stimulus']['verb'] and type(call['attempted']) is bool and type(call['settled']) is bool
                and (not call['settled'] or call['attempted']) and integer(call['before'],1,len(state['frames'])))
            need(same(state['frames'][call['before']-1]['phaseAfter']['activations'],call['phase']['activations']))
            self.expected(call,state);tickets.add(call['ticket'])
            self.url_authority(self.decode_frame(state['frames'][call['before']-1]),reference=call['urlAuthority'])
            if call['settled']:
                exact(call['quiet'],{'first','last'});self.quiet_original(state,call['quiet']['first'],call['quiet']['last'],call)
            else:need(call['quiet'] is None)
        need(set(state['unresolved'])<=tickets and len(state['unresolved'])<=8 and state['pending'] not in state['unresolved']
            and {c['ticket'] for c in state['calls'] if not c['settled']}==set(state['unresolved'])|({state['pending']} if state['pending'] else set()))
        if state['pending']:need(state['calls'][-1]['ticket']==state['pending'] and not state['calls'][-1]['settled'])
        for row in state['inputs']:
            exact(row,{'ticket','intent','command','frame'});need(row['ticket'] in tickets and integer(row['frame'],1,len(state['frames'])))
            intent=row['intent'];exact(intent,{'avatarPeopleInputVersion','action','controlId','controlToken','scope'});scope(intent['scope'])
            need(type(intent['avatarPeopleInputVersion']) is int and intent['avatarPeopleInputVersion']==1 and control_id(intent['controlId']) and nonce(intent['controlToken'])
                and intent['action'] in ('activate','replace','scroll','set-value') and intent['scope']['instance']==self.binding['sessionId'] and intent['scope']['processId']==self.pid)
            input_frame(state['frames'][row['frame']-1],row,self.binding,self.pid,self.run)
            if row['command'] is not None:self.command_original(row['command'],intent)
    def save(self):
        self.bound();self.check(self.state);payload=deepcopy(self.state)
        payload['frames']=[self.archive.frame_reference(frame) for frame in self.state['frames']]
        value=dict(picoAvatarFavoritesVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([payload]))
        self.store.write(value,self.previous);self.previous=deepcopy(value);self.fresh_current()
    def phase_fence(self,original=None):
        self.bound();status=self.phase.status(previous=self.state['frames'][-1]['phaseAfter'] if self.state['frames'] else None);self.activation(status)
        if original is not None:need(status['active']==original['active'] and same(status['activations'],original['activations']))
        return status
    def fresh_current(self,*,guard=True):
        if guard:self.bound()
        if self.anchor is None:return
        started,epoch,clock=self.anchor;now=self.monotonic();need(number(now,started,1e15));actual=clock();need(integer(actual,epoch))
        floor=max(actual,epoch+math.ceil((now-started)*1000));frame=self.state['frames'][-1]
        for packet in self.decode_frame(frame).values():fresh(packet['capturedEpochMs'],max(floor,frame['phaseAfter']['capturedEpochMs']))
        validate_snapshot(frame['widgets'],self.pid,floor)
        phase_epoch=self.phase.epoch_ms();need(number(phase_epoch,1,1e15))
        fresh(frame['phaseAfter']['capturedEpochMs'],max(math.ceil(phase_epoch),frame['phaseAfter']['capturedEpochMs']+math.ceil((now-frame['hostFinished'])*1000)))
    def reader(self,key):
        if key not in self.readers:
            reader=self.factories[key]();need(isinstance(reader,CLASSES[key]) and reader.pid==self.pid)
            if self.state['frames']:reader.restore([self.decode_frame(frame)[key] for frame in self.state['frames']])
            self.readers[key]=reader
        return self.readers[key]
    def sample(self):
        self.bound();need(len(self.state['frames'])<128);native=self.reader('native');started=self.monotonic();epoch=native.clock_ms();self.anchor=None
        before=self.phase_fence();frame={}
        for kind in SOURCES:
            reader=self.reader(kind);packet=reader.read();need(reader.last_raw is not None and decode(reader.last_raw)==packet)
            frame[kind]=dict(raw=reader.last_raw,sha256=reader.last_sha256)
        widgets=self.widgets();after=self.phase_fence(before);ended=self.monotonic()
        frame.update(widgets=deepcopy(widgets),phaseBefore=before,phaseAfter=after,hostStarted=started,hostFinished=ended);self.decode_frame(frame)
        self.state['frames'].append(frame)
        if self.state['baselineIndex'] is None:self.state['baselineIndex']=len(self.state['frames'])
        self.anchor=(started,epoch,native.clock_ms);self.save();return self.finish(frame)
    def finish(self,frame):
        retained=deepcopy(frame);self.archive.verify_frames(self.state['frames']);self.phase_fence(frame['phaseAfter'])
        need(same(self.store.read(),self.previous));self.fresh_current(guard=False);return retained
    @staticmethod
    def empty_attachments(values):
        native=values['native']['source'];snapshot=values['preferences']['source']['snapshot'];handles=snapshot['cache']['native']['handles']
        need(not native['avatarEntityStorage']['rows'] and handles['avatarEntityIDCount']==handles['avatarEntityDataCount']==0)
        actual=handles['handles']['avatarEntityCount']['value'];need(base64.b64decode(actual['base64'],validate=True)==struct.pack('>IBi',2,0,0))
        key='Avatar/avatarEntityData/size'
        for rows in (snapshot['cache']['rows'],snapshot['writer']['rows'],snapshot['writer']['physical']['rows']['values']):
            need(not any(name.startswith('Avatar/avatarEntityData/') and name!=key for name in rows))
        for rows in (snapshot['cache']['rows'],snapshot['writer']['rows']):
            if key in rows:need(same(rows[key],actual))
        physical=snapshot['writer']['physical']['rows']['values']
        if key in physical:
            count=decode(base64.b64decode(physical[key]['base64'],validate=True).decode('utf-8'))
            need(type(count) is int and count==0)
    def base(self,state=None):
        state=self.state if state is None else state;need(state['baselineIndex'] is not None);return self.decode_frame(state['frames'][state['baselineIndex']-1])
    def bookmark_record(self,state=None):
        state=self.state if state is None else state
        saved=[call for call in state['calls'] if call['verb']=='avatar-bookmark-save'];need(len(saved)==1)
        return deepcopy(saved[0]['expected']['record'])
    def expected(self,call,state=None):
        state=self.state if state is None else state;before=self.decode_frame(state['frames'][call['before']-1]);inputs=self.activation(call['phase'])['stimulus']['inputs']
        if call['verb']=='avatar-bookmark-save':
            need(inputs==dict(name=self.name));expected=dict(record=dict(version=3,avatarUrl=before['native']['source']['requestedUrl'],avatarScale=1,avatarEntites=[],avatarIcon=''))
        elif call['verb']=='avatar-scale':need(inputs==dict(value=1.5));expected=dict(scale=1.5)
        elif call['verb']=='avatar-bookmark-choose':need(inputs==dict(name=self.name));expected=dict(record=self.bookmark_record(state))
        elif call['verb']=='avatar-bookmark-delete':need(inputs==dict(name=self.name));expected=dict(absent=True)
        else:need(inputs=={});expected=dict(absent=True,scale=1)
        need(same(expected,call['expected']));return expected
    def current_safe(self,values):
        self.empty_attachments(values);avatar_preferences.baseline(values['preferences']);native=values['native']['source'];base=self.base()['native']['source']
        need(native['modelInstance']==base['modelInstance'] and native['sessionId']==base['sessionId'] and native['avatarLoads']['instance']==base['avatarLoads']['instance'])
        before=self.base()['loads']['source']['loads']['rows'];current=values['loads']['source']['loads']['rows'];need(len(current)>=len(before))
        for row in current[len(before):]:
            need(row['nameSha256']==avatar_state.sha(self.name) and row['avatarInstance']==native['avatarLoads']['instance'] and row['sessionId']==native['sessionId'])
    def stable(self,frame):
        values=self.decode_frame(frame);return dict(native=PicoAvatarUrls.stable(values['native']['source']),preferences=PicoAvatarUrls.preference_stable(values['preferences']),
            bookmarks=values['bookmarks']['source']['storage']['bookmarks'],bookmarkPath=values['bookmarks']['source']['storage']['pathSha256'],
            bookmarkRaw=values['bookmarks']['source']['storage']['rawSha256'],bookmarkFile=values['bookmarks']['source']['storage']['file'],loads=values['loads']['source']['loads']['rows'])
    def matches(self,frame,call,state=None):
        state=self.state if state is None else state;values=self.decode_frame(frame);self.empty_attachments(values);avatar_preferences.baseline(values['preferences'])
        native=values['native']['source'];original=self.base(state);bookmarks=values['bookmarks']['source']['storage'];wanted=deepcopy(original['bookmarks']['source']['storage']['bookmarks'])
        if not(frame['widgets']['open'] and frame['widgets']['ready'] and any(row['id']=='avatar.page' for row in frame['widgets']['controls'])):return False
        if any(row['id'] in ('avatar.dialog.input','avatar.dialog.confirm','avatar.scale','avatar.settings.confirm') for row in frame['widgets']['controls']):return False
        verb=call['verb'];before=self.decode_frame(state['frames'][call['before']-1]);expected=call['expected']
        if verb!='avatar-bookmark-choose' or before['native']['source']['requestedUrl']==expected['record']['avatarUrl']:
            from adapters.pico4.avatar_favorite_effect import unchanged_preferences
            unchanged_preferences(before['preferences'],values['preferences'])
        if verb not in ('avatar-bookmark-delete','cleanup'):wanted[self.name]=self.bookmark_record(state) if verb!='avatar-bookmark-save' else expected['record']
        if bookmarks['bookmarks']!=wanted or bookmarks['pathSha256']!=original['bookmarks']['source']['storage']['pathSha256']:return False
        if native['modelInstance']!=original['native']['source']['modelInstance'] or native['sessionId']!=original['native']['source']['sessionId']:return False
        rows=values['loads']['source']['loads']['rows'];old=before['loads']['source']['loads']['rows']
        for row in rows[len(old):]:
            if not(row['nameSha256']==avatar_state.sha(self.name) and row['avatarInstance']==native['avatarLoads']['instance'] and row['sessionId']==native['sessionId']
                and row['connected'] and row['disconnected'] and row['completed'] and row['dispatches']==1 and row['active']==0 and not row['captureAlive'] and row['ownerThreadOnly']):return False
        if verb=='avatar-bookmark-choose':
            if len(rows)<=len(old) or any(row['urlSha256']!=avatar_state.sha(expected['record']['avatarUrl']) for row in rows[len(old):]):return False
            source=next(c for c in state['calls'] if c['verb']=='avatar-bookmark-save');saved=self.decode_frame(state['frames'][source['before']-1])['native']['source']
            if not(native['requestedUrl']==native['preferenceUrl']==native['modelUrl']==expected['record']['avatarUrl'] and native['loaded'] and native['geometry'] is not None
                and saved['geometry'] is not None and native['geometry']['url']==saved['geometry']['url'] and native['hipsJoint']>=0 and not avatar_state.failed(native)):return False
        else:
            if any(native[k]!=before['native']['source'][k] for k in ('requestedUrl','preferenceUrl','modelName','modelUrl','modelInstance','geometry')):return False
        if verb=='cleanup':
            from adapters.pico4.avatar_favorite_effect import original_preferences,original_bookmarks
            original_preferences(original['preferences'],values['preferences'])
            original_bookmarks(original['bookmarks']['source']['storage'],bookmarks)
            base=original['native']['source']
            if any(native[key]!=base[key] for key in ('requestedUrl','preferenceUrl','modelName','avatarEntityStorage','modelUrl','scale','targetScale')):return False
            if not(native['loaded'] and native['geometry'] is not None and base['geometry'] is not None
                    and native['geometry']['url']==base['geometry']['url'] and not avatar_state.failed(native)):return False
        scale=expected.get('scale',1 if verb=='avatar-bookmark-choose' else before['native']['source']['scale'])
        return all(abs(native[k]-scale)<.0001 for k in ('scale','targetScale'))
    def quiet_original(self,state,first,last,call):
        need(integer(first,1,len(state['frames'])) and integer(last,first+1,len(state['frames'])));frames=state['frames'][first-1:last];stable=None;previous=None
        for frame in frames:
            values=self.decode_frame(frame);observed=self.stable(frame);need(stable is None or same(stable,observed));stable=observed
            if call is None:
                self.empty_attachments(values);need(self.activation(frame['phaseAfter'])['stimulus']==dict(verb='baseline',inputs={}) and frame['phaseAfter']['active'])
                need(values['native']['source']['loaded'] and values['native']['source']['geometry'] is not None and values['native']['source']['scale']==values['native']['source']['targetScale']==1
                    and self.name not in values['bookmarks']['source']['storage']['bookmarks'] and all(not row['captureAlive'] and row['active']==0 for row in values['loads']['source']['loads']['rows']))
            else:need(self.matches(frame,call,state) and same(frame['phaseAfter']['activations'],call['phase']['activations']))
            if previous is not None:
                need(0<=frame['hostFinished']-previous['hostFinished']<=.5)
                for key in SOURCES:need(0<=values[key]['capturedEpochMs']-self.decode_frame(previous)[key]['capturedEpochMs']<=500)
            previous=frame
        need(frames[-1]['hostFinished']-frames[0]['hostFinished']>=3)
        for key in SOURCES:need(self.decode_frame(frames[-1])[key]['capturedEpochMs']-self.decode_frame(frames[0])[key]['capturedEpochMs']>=3000)
    def prepare(self):
        need(self.state['stage']=='reserved' and not self.state['calls']);started=self.monotonic();first=None;stable=None;previous=None
        for attempt in range(83):
            frame=self.sample();values=self.decode_frame(frame);self.empty_attachments(values);avatar_preferences.baseline(values['preferences'])
            need(self.activation(frame['phaseAfter'])['stimulus']==dict(verb='baseline',inputs={}) and frame['phaseAfter']['active'])
            observed=self.stable(frame);gap=previous is not None and (frame['hostFinished']-previous['hostFinished']>.5 or any(values[k]['capturedEpochMs']-self.decode_frame(previous)[k]['capturedEpochMs']>500 for k in SOURCES))
            if first is None or gap or not same(stable,observed):first=len(self.state['frames']);stable=observed;self.state['baselineIndex']=first;self.save()
            elif frame['hostFinished']-self.state['frames'][first-1]['hostFinished']>=3 and all(values[k]['capturedEpochMs']-self.decode_frame(self.state['frames'][first-1])[k]['capturedEpochMs']>=3000 for k in SOURCES):
                self.state['prepared']=len(self.state['frames']);self.state['stage']='active';self.save();return self.finish(frame)
            previous=frame;need(attempt<82 and self.monotonic()-started<20);self.sleep(.25)
    def record_input(self,intent):
        need(self.state['pending'] is not None and len(self.state['inputs'])<128);self.sample();self.phase_fence(self.state['calls'][-1]['phase']);self.fresh_current()
        self.state['inputs'].append(dict(ticket=self.state['pending'],intent=deepcopy(intent),command=None,frame=len(self.state['frames'])));self.save()
    @staticmethod
    def command_original(command,intent):
        fields={'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}
        for action,key in (('replace','text'),('set-value','value'),('scroll','direction')):
            if intent['action']==action:fields.add(key)
        exact(command,fields);s=intent['scope'];need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and nonce(command['commandId'])
            and command['bridgeId']==s['instance'] and command['generation']==s['generation'] and command['sequence']==s['sequence']+1
            and command['observedElapsedMs']==s['elapsedMs'] and all(command[k]==intent[k] for k in ('controlId','controlToken','action')))
    def before_send(self,command,navigation_channel):
        self.bound();need(self.state['pending'] is not None and self.state['inputs']);call=self.state['calls'][-1];self.phase_fence(call['phase']);self.fresh_current()
        row=self.state['inputs'][-1];need(row['ticket']==call['ticket'] and row['command'] is None);self.command_original(command,row['intent'])
        identifier=command['controlId'];allowed={'avatar.entry','avatar.dialog.confirm','avatar.dialog.cancel'}
        if call['verb']=='avatar-bookmark-save':allowed|={'avatar.bookmark.add','avatar.dialog.input'}
        if call['verb'] in ('avatar-scale','cleanup'):allowed|={'avatar.settings','avatar.scale','avatar.settings.scrollbar','avatar.settings.confirm'}
        if call['verb'] in ('avatar-bookmark-choose','avatar-bookmark-delete','cleanup'):
            allowed.add('avatar.bookmark.manage')
            for actual in self.state['frames'][-1]['widgets']['controls']:
                if actual.get('bookmarkName')==self.name:allowed.add(actual['id'])
        need(navigation(identifier) or identifier in allowed)
        if command['action']=='replace':need(identifier=='avatar.dialog.input' and command['text']==self.name)
        elif command['action']=='set-value':need(identifier=='avatar.scale' and command['value']==call['expected']['scale']*10)
        elif command['action']=='scroll':need(identifier=='avatar.settings.scrollbar' and command['direction']=='down')
        else:need(command['action']=='activate')
        need(identifier!='avatar.dialog.cancel' or call['verb']=='cleanup');row['command']=deepcopy(command);self.save();self.phase_fence(call['phase'])
        self.url_authority(self.decode_frame(self.state['frames'][-1]),reference=call['urlAuthority'])
        self.archive.verify_frames(self.state['frames']);self.phase_fence(call['phase'])
        need(same(self.store.read(),self.previous));self.fresh_current(guard=False)
    def url_authority(self,values,reference=None):
        if self.url_reader is None:self.url_reader=self.urls()
        owner=self.url_reader;need(isinstance(owner,PicoAvatarUrls) and same(owner.binding,self.binding) and owner.run==self.run and owner.state['pending'] is None
            and owner.state['calls'] and owner.state['calls'][-1]['settled'])
        need(same(owner.store.read(),owner.previous));owner.verify_frames()
        if reference is None:
            last=owner.state['calls'][-1];index=last['quiet']['last'];reference=dict(ticket=last['ticket'],frame=index,sha256=owner.state['frames'][index-1]['native']['sha256'])
        else:
            exact(reference,{'ticket','frame','sha256'});need(nonce(reference['ticket']) and integer(reference['frame'],1,len(owner.state['frames'])))
            rows=[call for call in owner.state['calls'] if call['ticket']==reference['ticket']];need(len(rows)==1 and rows[0]['settled']);last=rows[0]
            need(reference['frame']==last['quiet']['last'] and reference['sha256']==owner.state['frames'][reference['frame']-1]['native']['sha256'])
        known=avatar_state.decode(owner.state['frames'][reference['frame']-1]['native']['raw'])['source'];current=values['native']['source']
        need(all(current[k]==known[k] for k in ('requestedUrl','preferenceUrl','modelUrl','modelInstance','geometry','sessionId'))
            and all(current[k]['currentGeneration']==known[k]['currentGeneration'] for k in ('avatarLoads','modelLoads')))
        return last,reference
    def act(self,*,cleanup=False):
        need(self.state['prepared'] is not None and self.state['pending'] is None and (not self.state['unresolved'] or cleanup));frame=self.sample();values=self.decode_frame(frame);self.current_safe(values)
        phase=self.phase_fence(frame['phaseAfter']);activation=self.activation(phase);verb=activation['stimulus']['verb'];ticket=activation['ticket'];inputs=activation['stimulus']['inputs']
        need(verb in VERBS and (verb=='cleanup')==cleanup and ticket not in {c['ticket'] for c in self.state['calls']} and len(self.state['calls'])<8 and (phase['active'] or cleanup))
        original=self.base()['bookmarks']['source']['storage']['bookmarks'];actual=values['bookmarks']['source']['storage']['bookmarks'];wanted=deepcopy(original)
        last,authority=self.url_authority(values)
        if verb=='avatar-bookmark-save':
            need(last['verb']=='avatar-url' and last['url'].endswith('/avatar-a.fst') and inputs==dict(name=self.name) and self.name not in actual
                and all(abs(values['native']['source'][k]-1)<.0001 for k in ('scale','targetScale')) and not self.state['calls'])
            expected=dict(record=dict(version=3,avatarUrl=values['native']['source']['requestedUrl'],avatarScale=1,avatarEntites=[],avatarIcon=''))
        else:
            record=self.bookmark_record();wanted[self.name]=record
            if verb=='avatar-scale':need(inputs==dict(value=1.5));expected=dict(scale=1.5)
            elif verb=='avatar-bookmark-choose':need(inputs==dict(name=self.name));expected=dict(record=record)
            elif verb=='avatar-bookmark-delete':need(inputs==dict(name=self.name));expected=dict(absent=True)
            else:need(inputs=={});expected=dict(absent=True,scale=1)
        need(actual==wanted or cleanup and actual==original)
        call=dict(ticket=ticket,verb=verb,phase=phase,before=len(self.state['frames']),expected=expected,urlAuthority=authority,attempted=False,settled=False,quiet=None)
        self.state['calls'].append(call);self.state['pending']=ticket;self.save();call['attempted']=True;self.save()
        ui=self.controls_factory(self.record_input,self._before_send);need(isinstance(ui,TokenAvatarPeopleUI));ui.open()
        if verb=='avatar-bookmark-save':ui.save_bookmark(self.name)
        elif verb=='avatar-scale':ui.set_scale(1.5)
        elif verb=='avatar-bookmark-choose':ui.bookmark(self.name)
        elif verb=='avatar-bookmark-delete':ui.bookmark(self.name,delete=True)
        else:
            snapshot=ui.capture();field=ui.row(snapshot,'avatar.dialog.input',ready=False)
            if field is not None:need(field['text'] in ('',self.name));ui.input('avatar.dialog.cancel')
            if abs(values['native']['source']['scale']-1)>.0001:ui.set_scale(1)
            if self.name in actual:ui.bookmark(self.name,delete=True)
        return self.settle()
    def settle(self):
        need(self.state['pending'] is not None);started=self.monotonic();first=None;stable=None;previous=None
        for attempt in range(83):
            frame=self.sample();call=self.state['calls'][-1];observed=self.stable(frame);values=self.decode_frame(frame)
            gap=previous is not None and (frame['hostFinished']-previous['hostFinished']>.5 or any(values[k]['capturedEpochMs']-self.decode_frame(previous)[k]['capturedEpochMs']>500 for k in SOURCES))
            if not self.matches(frame,call):first=stable=None
            elif first is None or gap or not same(stable,observed):first=len(self.state['frames']);stable=observed
            elif frame['hostFinished']-self.state['frames'][first-1]['hostFinished']>=3 and all(values[k]['capturedEpochMs']-self.decode_frame(self.state['frames'][first-1])[k]['capturedEpochMs']>=3000 for k in SOURCES):
                self.phase_fence(call['phase']);call['settled']=True;call['quiet']=dict(first=first,last=len(self.state['frames']));self.state['pending']=None
                self.state['stage']='retained' if call['verb']=='cleanup' else 'active';self.save();return self.finish(frame)
            previous=frame;need(attempt<82 and self.monotonic()-started<20);self.sleep(.25)
    def reconcile(self):return self.settle()
    def effect_proof(self):
        self.bound();self.check(self.state);need(self.state['pending'] is None and not self.state['unresolved'] and self.state['calls'])
        call=self.state['calls'][-1];need(call['verb'] in ('avatar-scale','avatar-bookmark-choose') and call['settled']);quiet=call['quiet']
        need(same(self.store.read(),self.previous));self.archive.verify_frames(self.state['frames'])
        inputs=deepcopy([row for row in self.state['inputs'] if row['ticket']==call['ticket']])
        indices=sorted({call['before'],*[row['frame'] for row in inputs],*range(quiet['first'],quiet['last']+1)})
        for row in inputs:row['frame']=indices.index(row['frame'])+1
        return dict(avatarFavoriteEffectVersion=1,binding=deepcopy(self.binding),runId=self.run,fixtureUrl=self.phase.fixture_url,
            ticket=call['ticket'],phase=deepcopy(call['phase']),frames=deepcopy([self.state['frames'][index-1] for index in indices]),
            before=indices.index(call['before'])+1,quiet=dict(first=indices.index(quiet['first'])+1,last=indices.index(quiet['last'])+1),inputs=inputs)
    def cleanup(self):
        phase=self.phase_fence();need(self.activation(phase)['stimulus']==dict(verb='cleanup',inputs={}))
        if self.state['pending']:self.state['unresolved'].append(self.state['pending']);self.state['pending']=None;self.anchor=None;self.save()
        return self.act(cleanup=True)
    def invoke(self,operation):
        need(operation in ('prepare','act','sample','reconcile','cleanup'))
        with self.lock.held():return getattr(self,operation)()
