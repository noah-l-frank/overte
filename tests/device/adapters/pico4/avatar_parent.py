"""Partial common-v16 parent over the existing normal Avatar source owners.

Only supported normal acts are admitted. Nine-field observation, independent
peer/image/Model actors and final release are deliberately unavailable. The
existing children keep their own exact phase/input/quiet/retained ownership;
this parent adds fresh, independent original preference/callback observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
from adapters.native_feature_observation import decode,exact,integer,need,number,fresh
from adapters.normal_feature_state import context,PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_preferences as preferences,avatar_model_connections as callbacks
from adapters.pico4.avatar_urls import PicoAvatarUrls
from adapters.pico4.avatar_favorites import PicoAvatarFavorites,phase_original
from adapters.pico4.avatar_originals import AvatarOriginalFrames
from adapters.pico4.avatar_favorite_effect import original_preferences
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=1
OPERATIONS=frozenset('feature.avatar-people.'+kind for kind in ('act','observe','cleanup'))
URL_VERBS={'avatar-url','avatar-restore'}
FAVORITE_VERBS={'avatar-bookmark-save','avatar-scale','avatar-bookmark-choose','avatar-bookmark-delete'}
SOURCES={'preferences':preferences,'callbacks':callbacks}
CLASSES={'preferences':preferences.NativePicoAvatarPreferences,'callbacks':callbacks.NativePicoAvatarModelConnections}


class PicoAvatarParent:
    def __init__(self,store,binding,phase,lock,urls,favorites,sources,guard,*,monotonic=time.monotonic):
        need(isinstance(lock,ScriptSourceLock) and isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people'
            and set(sources)==set(SOURCES) and all(callable(v) for v in (*sources.values(),urls,favorites,guard,monotonic)))
        self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.urls,self.favorites,self.sources,self.guard,self.monotonic=urls,favorites,sources,guard,monotonic
        self.pid=int(binding['processIdentity'].split(':')[0]);self.run=phase.run
        self.archive=AvatarOriginalFrames(store,self.binding,self.run,phase.fixture_url,'parent')
        key=store.path.name.removeprefix('avatar-parent-owner-').removesuffix('-'+self.run+'.json')
        need(re.fullmatch('[0-9a-f]{32}',key) is not None);self.key=key
        self.readers={};self.child_pair=None;self.clock=None;self.previous=store.read()
        self.state=dict(prepared=False,frames=[],calls=[],pending=None)
        self.bound()
        if self.previous is not None:self.state=self.restore(self.previous)
    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.previous,self.store.read()))
        self.budget()
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock));self.clock=now
    def budget(self):
        # Count every persisted parent/child original and root in this exact
        # target/run domain, including compressed payload's full decoded bytes.
        files=total=0
        for kind in ('parent','urls','favorites'):
            for group in ('owner','frame'):
                prefix='avatar-'+kind+'-'+group+'-'+self.key+'-'+self.run
                for path in self.store.path.parent.glob(prefix+'*.json'):
                    suffix='' if group=='owner' else '-[0-9a-f]{32}'
                    need(re.fullmatch(re.escape(prefix)+suffix+r'\.json',path.name) is not None)
                    record=PrivateFeatureState(path).read();need(record is not None)
                    files+=1;total+=len(canonical(record))
                    if 'payload' in record:total+=len(canonical(unpack(record['payload'])))
                    need(files<=512 and total<=16*1024*1024)
    def frame(self,frame):
        exact(frame,set(SOURCES)|{'phaseBefore','phaseAfter','hostStarted','hostFinished'})
        need(number(frame['hostStarted'],0,1e15) and number(frame['hostFinished'],frame['hostStarted'],frame['hostStarted']+1.5))
        values={}
        for key,module in SOURCES.items():
            record=frame[key];exact(record,{'raw','sha256'})
            need(type(record['raw']) is str and hashlib.sha256(record['raw'].encode()).hexdigest()==record['sha256'])
            value=decode(record['raw']);module.validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=module.ACTION),self.pid,value.get('capturedEpochMs'))
            values[key]=value
        a,b=values['preferences'],values['callbacks'];actual=a['source']['snapshot']['cache']['native']
        need(a['instance']==b['instance'] and actual['sessionId']==b['source']['sessionId'])
        for key in ('phaseBefore','phaseAfter'):phase_original(frame[key],self.run)
        need(same(frame['phaseBefore']['activations'],frame['phaseAfter']['activations']) and frame['phaseBefore']['active']==frame['phaseAfter']['active'])
        return values
    def check(self,state):
        exact(state,{'prepared','frames','calls','pending'})
        need(type(state['prepared']) is bool and type(state['frames']) is list and len(state['frames'])<=128
            and type(state['calls']) is list and len(state['calls'])<=16)
        previous=previous_frame=None
        for frame in state['frames']:
            value=self.frame(frame)
            if previous is not None:
                for key,module in SOURCES.items():module.continuity(previous[key],value[key])
                need(frame['hostStarted']>=previous_frame['hostFinished'])
                phase_packet(frame['phaseBefore'],run=self.run,area='avatar-people',request=frame['phaseBefore']['requestId'],
                    epoch=frame['phaseBefore']['capturedEpochMs'],previous=previous_frame['phaseAfter'])
            previous,previous_frame=value,frame
        tickets=set()
        for call in state['calls']:
            exact(call,{'request','before','after','child'})
            request=arguments('feature.avatar-people.act',call['request']);ticket=request['ticket']
            need(request['runId']==self.run and request['fixtureUrl']==self.phase.fixture_url and ticket not in tickets
                and request['verb'] in URL_VERBS|FAVORITE_VERBS and integer(call['before'],1,len(state['frames'])))
            activation=phase_original(state['frames'][call['before']-1]['phaseAfter'],self.run)
            need(activation['ticket']==ticket and activation['stimulus']==dict(verb=request['verb'],inputs=request['inputs']))
            if call['after'] is not None:
                need(integer(call['after'],call['before']+1,len(state['frames'])))
                before,after=state['frames'][call['before']-1],state['frames'][call['after']-1]
                need(same(before['phaseAfter']['activations'],after['phaseAfter']['activations']))
                self.child_original(call,after)
            else:need(call['child'] is None)
            tickets.add(ticket)
        pending=[call['request']['ticket'] for call in state['calls'] if call['after'] is None]
        need(pending==([] if state['pending'] is None else [state['pending']]))
    def restore(self,record):
        exact(record,{'picoAvatarParentVersion','binding','runId','fixtureUrl','payload'})
        need(type(record['picoAvatarParentVersion']) is int and record['picoAvatarParentVersion']==VERSION
            and same(record['binding'],self.binding) and record['runId']==self.run and record['fixtureUrl']==self.phase.fixture_url)
        states=unpack(record['payload']);need(len(states)==1);state=states[0]
        need(type(state) is dict and type(state.get('frames')) is list and len(state['frames'])<=128)
        state['frames']=[self.archive.frame_original(ref) for ref in state['frames']];self.check(state);return state
    def save(self):
        self.bound();self.check(self.state);payload=deepcopy(self.state)
        payload['frames']=[self.archive.frame_reference(frame) for frame in self.state['frames']]
        record=dict(picoAvatarParentVersion=VERSION,binding=self.binding,runId=self.run,fixtureUrl=self.phase.fixture_url,payload=pack([payload]))
        self.store.write(record,self.previous);self.previous=deepcopy(record);self.bound()
    def reader(self,key):
        if key not in self.readers:
            reader=self.sources[key]();need(isinstance(reader,CLASSES[key]) and reader.pid==self.pid)
            if self.state['frames']:reader.restore([self.frame(frame)[key] for frame in self.state['frames']])
            self.readers[key]=reader
        return self.readers[key]
    def sample(self):
        self.bound();need(len(self.state['frames'])<128);started=self.monotonic();before=self.phase.status()
        frame={}
        for key in SOURCES:
            reader=self.reader(key);value=reader.read();need(reader.last_raw is not None and decode(reader.last_raw)==value)
            frame[key]=dict(raw=reader.last_raw,sha256=reader.last_sha256)
        after=self.phase.status(previous=before);ended=self.monotonic()
        frame.update(phaseBefore=before,phaseAfter=after,hostStarted=started,hostFinished=ended);values=self.frame(frame)
        for key in SOURCES:fresh(values[key]['capturedEpochMs'],self.reader(key).clock_ms())
        self.state['frames'].append(frame);self.save();return frame
    def children(self):
        # One actual pair per parent lifetime. Replaying historical parent
        # records must not repeatedly construct new live SDK/widget readers.
        if self.child_pair is None:self.child_pair=(self.urls(),self.favorites())
        urls,favorites=self.child_pair
        need(isinstance(urls,PicoAvatarUrls) and isinstance(favorites,PicoAvatarFavorites)
            and all(child.lock is self.lock and child.run==self.run and same(child.binding,self.binding)
                and child.phase.fixture_url==self.phase.fixture_url for child in (urls,favorites)))
        need(all(same(child.previous,child.store.read()) for child in (urls,favorites)))
        return urls,favorites
    def child_original(self,call,frame):
        kind='urls' if call['request']['verb'] in URL_VERBS else 'favorites'
        exact(call['child'],{'kind','frame'});need(call['child']['kind']==kind)
        urls,favorites=self.children();owner=urls if kind=='urls' else favorites
        archive=owner.originals if kind=='urls' else owner.archive
        actual=[row for row in owner.state['calls'] if row['ticket']==call['request']['ticket']]
        need(len(actual)==1 and actual[0]['settled'] and actual[0]['verb']==call['request']['verb'])
        expected=owner.state['frames'][actual[0]['quiet']['last']-1]
        need(same(call['child']['frame'],archive.frame_reference(expected)))
        child=archive.frame_original(call['child']['frame']);need(same(child,expected))
        need(same(child['phaseAfter']['activations'],frame['phaseAfter']['activations']))
        values=self.frame(frame);original_preferences(decode(child['preferences']['raw']),values['preferences'])
        native=decode(child['native']['raw'])
        need(native['instance']==values['callbacks']['instance']
            and native['source']['avatarLoads']['instance']==values['callbacks']['source']['avatarInstance']
            and callbacks.retired(values['callbacks']))
    def prepare(self):
        """Internal baseline admission, never an invented common-v16 observe."""
        self.bound();need(not self.state['prepared'] and not self.state['calls'])
        frame=self.sample();need(phase_original(frame['phaseAfter'],self.run)['stimulus']==dict(verb='baseline',inputs={}))
        urls,favorites=self.children()
        for owner in (urls,favorites):
            need(owner.state['prepared'] is None);owner.invoke('prepare')
        self.sample();self.state['prepared']=True;self.save()
    def act(self,request):
        arguments('feature.avatar-people.act',request);self.bound()
        need(request['runId']==self.run and request['fixtureUrl']==self.phase.fixture_url and self.state['prepared']
            and self.state['pending'] is None and len(self.state['calls'])<16 and request['verb'] in URL_VERBS|FAVORITE_VERBS
            and request['ticket'] not in {call['request']['ticket'] for call in self.state['calls']})
        frame=self.sample();activation=phase_original(frame['phaseAfter'],self.run)
        need(frame['phaseAfter']['active'] and activation['ticket']==request['ticket']
            and activation['stimulus']==dict(verb=request['verb'],inputs=request['inputs']))
        # Durable intent precedes the child's durable input intent and normal
        # input. Lost results remain owned; calling again cannot resend them.
        self.state['calls'].append(dict(request=deepcopy(request),before=len(self.state['frames']),after=None,child=None))
        self.state['pending']=request['ticket'];self.save()
        urls,favorites=self.children();owner=urls if request['verb'] in URL_VERBS else favorites
        owner.invoke('act');need(owner.state['pending'] is None and owner.state['calls'][-1]['settled']
            and owner.state['calls'][-1]['ticket']==request['ticket'])
        self.sample();call=self.state['calls'][-1];call['after']=len(self.state['frames'])
        child=owner.state['frames'][owner.state['calls'][-1]['quiet']['last']-1]
        call['child']=dict(kind='urls' if owner is urls else 'favorites',
            frame=owner.originals.frame_reference(child) if owner is urls else owner.archive.frame_reference(child))
        self.child_original(call,self.state['frames'][-1]);self.state['pending']=None;self.save()
        self.archive.verify_frames(self.state['frames']);return dict(performed=True)
    def observe(self,request):
        arguments('feature.avatar-people.observe',request)
        raise NativeUIError('Complete original Avatar/People observation and independent actor are unavailable')
    def cleanup(self,request):
        arguments('feature.avatar-people.cleanup',request)
        raise NativeUIError('Original Avatar/People child sources remain retained; final release is unavailable')
