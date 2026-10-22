"""Durable normal HMD View-menu setup and original camera-mode restoration.

The parent retains this journal: closed UI and restored mode do not establish
menu callback/context retirement, stereo visibility or whole Emote completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_avatar_render import validate as avatar_packet,controlled_resources
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.normal_view_menu import PicoViewMenu,project
from adapters.pico4.tablet_home import PicoTabletHome,validate as home_packet,validate_input as home_input
from adapters.pico4 import view_menu_lifetimes
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.android.input_geometry import observed_grip_pose
from openxr_input.controller_protocol import validate_envelope
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=4
MODES={'first person look at':'view-menu.first','look at':'view-menu.third'}
PARTS=('open','menu','view','mode','home','close')
KINDS={prefix+'-'+part for prefix in ('prepare','restore') for part in PARTS}


class PicoEmoteView:
    def __init__(self,store,binding,phase,lock,original,avatar,guard,input_session,home,controller,
                 *,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and isinstance(lock,ScriptSourceLock)
            and all(callable(v) for v in (original,avatar,guard,input_session,home,controller,monotonic,sleep)))
        lock.assert_held()
        self.store,self.binding,self.phase,self.lock=store,deepcopy(context(binding)),phase,lock
        self.original,self.avatar,self.guard,self.input_session=original,avatar,guard,input_session
        self.home,self.controller_factory,self._session=home,controller,None
        self.monotonic,self.sleep=monotonic,sleep
        self.run,self.pid=phase.run,int(binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        self.started=self.clock=None;self.failed=False;self.anchor=None;self.require_resources=False
        self._before_send=self.before_send
        self.previous=store.read()
        self.state=dict(phase='reserved',original=None,current=None,steps=[])
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)

    @property
    def session(self):
        if self._session is None:
            value=self.controller_factory();need(isinstance(value,PicoOpenXrAdapterSession));self._session=value
        return self._session

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<60));self.clock=now

    def packet(self,value,previous=None):
        exact(value,{'avatar','widgets','home','phaseBefore','phaseAfter'})
        a=value['avatar'];avatar_packet(a,dict(schemaVersion=1,commandId=a.get('requestId'),action='feature-avatar-render-observe'),self.pid,a.get('capturedEpochMs'))
        need(a['source'].get('cameraStateVersion')==1 and a['source']['cameraState']['hmd'])
        widgets=value['widgets'];validate_snapshot(widgets,self.pid,widgets.get('updatedEpochMs'));project(widgets)
        if previous is not None and 'picoViewMenuLifetimes' in previous['widgets']:
            need('picoViewMenuLifetimes' in widgets)
            view_menu_lifetimes.accept(previous['widgets']['picoViewMenuLifetimes'],widgets['picoViewMenuLifetimes'])
        need(widgets['bridgeId']==self.binding['sessionId'] and a['capturedEpochMs']<=widgets['updatedEpochMs'])
        home=value['home'];home_packet(home,home.get('commandId'),self.pid,home.get('capturedEpochMs'))
        need(home['tabletShown']==widgets['open'])
        before,after=value['phaseBefore'],value['phaseAfter']
        phase_packet(before,run=self.run,area='emotes',request=before.get('requestId'),epoch=before.get('capturedEpochMs'),
            previous=None if previous is None else previous['phaseAfter'])
        phase_packet(after,run=self.run,area='emotes',request=after.get('requestId'),epoch=after.get('capturedEpochMs'),previous=before)
        need(before['activations'] and same(before['activations'],after['activations']) and before['active']==after['active'])
        if previous is not None:
            old=previous['avatar'];need(old['instance']==a['instance'] and a['sequence']>old['sequence']
                and a['requestId']!=old['requestId'] and a['requestedEpochMs']>=old['capturedEpochMs'])
            left=previous['widgets'];need(widgets['lastCommandSequence']>=left['lastCommandSequence']
                and widgets['elapsedMs']>=left['elapsedMs'] and widgets['updatedEpochMs']>=left['updatedEpochMs']
                and (widgets['generation']==left['generation'] or widgets['open']!=left['open']))
            old=previous['home'];need(all(home[k]==old[k] for k in ('instance','generation','tabletId','homeId','parentId'))
                and home['sourceSequence']>old['sourceSequence'] and home['commandId']!=old['commandId']
                and home['elapsedMs']>=old['elapsedMs'] and home['capturedEpochMs']>=old['capturedEpochMs'])
            self.unchanged(previous,value)

    @staticmethod
    def unchanged(original,current):
        a,b=original['avatar'],current['avatar'];need(a['instance']==b['instance'])
        a,b=a['source'],b['source']
        need(all(same(a[k],b[k]) for k in ('modelInstance','rigId','geometry')))
        if 'avatarResourcesVersion' in a:
            need(b.get('avatarResourcesVersion')==a['avatarResourcesVersion'] and same(a['avatarResources'],b.get('avatarResources')))
        need(all(same(a['cameraState'][k],b['cameraState'][k]) for k in ('hmd','zoomMin','zoomDefault')))
        # Native head/camera pose may advance in HMD. The owned avatar itself
        # must stay at its original location, orientation and model scale.
        for key,tolerance in (('feetPosition',.03),('orientation',.001),('modelScale',.0001)):
            left,right=a['pose'][key],b['pose'][key]
            left=left if isinstance(left,list) else [left];right=right if isinstance(right,list) else [right]
            need(len(left)==len(right) and all(abs(x-y)<=tolerance for x,y in zip(left,right)))

    def decode(self,value):
        exact(value,{'picoEmoteViewVersion','runId','fixtureUrl','binding','payload'})
        need(type(value['picoEmoteViewVersion']) is int and value['picoEmoteViewVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.phase.fixture_url and same(value['binding'],self.binding))
        records=unpack(value['payload']);need(len(records)==1);state=records[0]
        exact(state,{'phase','original','current','steps'});need(state['phase'] in ('reserved','preparing','ready','restoring','restored'))
        need(type(state['steps']) is list and len(state['steps'])<=12)
        if state['original'] is None:need(state['phase']=='reserved' and state['current'] is None and not state['steps']);return state
        self.packet(state['original']);need(not state['original']['widgets']['open'] and state['original']['home']['onHomeScreen']
            and state['original']['avatar']['source']['cameraMode'] in MODES)
        original=state['original']['avatar']['source'];need(original['cameraMode']!='first person look at'
            or original['cameraState']['boomLength']==original['cameraState']['zoomMin'])
        self.packet(state['current']);self.unchanged(state['original'],state['current'])
        kinds=set();pending=0;chain=state['original'];order=[]
        for prefix in ('prepare','restore'):
            order.extend(prefix+'-'+part for part in PARTS)
        for index,row in enumerate(state['steps']):
            exact(row,{'kind','control','before','intent','after','stream'})
            need(row['kind'] in KINDS and row['kind'] not in kinds and row['kind']==order[index]);kinds.add(row['kind'])
            expected={'open':'tablet.open','menu':'scripts.menu','view':'view-menu.view','home':'tablet.home-ray','close':'tablet.close'}
            part=row['kind'].split('-')[1]
            need(row['control']==(MODES['look at' if row['kind'].startswith('prepare') else state['original']['avatar']['source']['cameraMode']]
                if part=='mode' else expected[part]))
            self.packet(row['before'],chain);self.unchanged(state['original'],row['before'])
            need(row['before']['phaseBefore']['activations'][-1]['stimulus']['verb']==
                ('baseline' if row['kind'].startswith('prepare') else 'cleanup'))
            need(type(row['intent']) is list and len(row['intent'])<=1)
            if row['intent']:self.intent_packet(row['intent'][0],row)
            controller=row['control'] in ('tablet.open','tablet.close','tablet.home-ray')
            if controller:
                exact(row['stream'],{'envelope','neutral'})
                stream=row['stream']
                if stream['envelope'] is not None:
                    need(len(row['intent'])==1);self.stream_packet(row,stream['envelope'])
                    older=[r['stream']['envelope'] for r in state['steps'][:index] if r['stream'] is not None and r['stream']['envelope'] is not None]
                    if older:need(stream['envelope']['sessionNonce']==older[-1]['sessionNonce'] and stream['envelope']['sequence']>older[-1]['sequence'])
                else:need(stream['neutral'] is None)
                if stream['neutral'] is not None:
                    need(stream['envelope'] is not None)
                    PicoLifecycleBack.neutral(stream['neutral'],stream['envelope'],row['before']['home']['capturedEpochMs'])
            else:need(row['stream'] is None)
            if row['after'] is None:pending+=1;need(index==len(state['steps'])-1)
            else:
                need(len(row['intent'])==1);self.packet(row['after'],row['before']);self.effect(row,row['after'])
                if controller:need(row['stream']['neutral'] is not None and row['stream']['neutral']['updatedEpochMs']<=row['after']['home']['capturedEpochMs']+250)
                self.unchanged(state['original'],row['after'])
            chain=row['after'] or row['before']
        if not same(chain,state['current']):self.packet(state['current'],chain)
        need(pending<=1)
        if state['phase'] in ('ready','restored'):
            need(not pending and len(state['steps'])==(6 if state['phase']=='ready' else 12)
                and not state['current']['widgets']['open'] and state['current']['home']['onHomeScreen'])
            need(state['current']['avatar']['source']['cameraMode']==('look at' if state['phase']=='ready' else state['original']['avatar']['source']['cameraMode']))
            if state['phase']=='restored':need(state['current']['avatar']['source']['cameraState']['boomLength']==original['cameraState']['boomLength'])
        return deepcopy(state)

    def save(self,*,host_only=False):
        if host_only:
            # The exact original controller sequence is locked by stage().
            # No session, ADB or guard reentry is permitted in its callback.
            self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous));self.host_fresh()
        else:self.bound()
        value=dict(picoEmoteViewVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,
            binding=self.binding,payload=pack([self.state]))
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
            if host_only:self.host_fresh()
            else:self.bound()
        except Exception:self.failed=True;raise

    def host_fresh(self):
        need(self.anchor is not None);started,epoch,host,_clock=self.anchor;now=self.monotonic()
        need(number(now,started,started+1.5) and (self.clock is None or now>=self.clock))
        current=self.state['steps'][-1]['before']
        for captured in (current['avatar']['requestedEpochMs'],current['widgets']['updatedEpochMs'],current['home']['capturedEpochMs']):
            fresh(captured,epoch+math.ceil((now-started)*1000))
        fresh(current['phaseBefore']['capturedEpochMs'],host+math.ceil((now-started)*1000));self.clock=now

    def stream_packet(self,row,value):
        # Validation uses the original protocol, including the actual calibrated
        # Home ray. A tablet ACK or requested input never proves neutralization.
        validate_envelope(value,self.session.profile)
        control=row['control'];need(control in ('tablet.open','tablet.close','tablet.home-ray'))
        operation='input.primary' if control=='tablet.home-ray' else control
        if control=='tablet.home-ray':
            home=row['intent'][0]['home'];arguments=observed_grip_pose(home['sensorToWorld'],home['headPosition'],home['position'])
        else:arguments=dict(holdMilliseconds=1000)
        need(value['commands']==[dict(id=operation.replace('.','-')+'-'+str(value['sequence']),operation=operation,arguments=arguments)])

    def stream_intent(self,row,value):
        need(row['stream'] is not None and row['stream']['envelope'] is None and row['after'] is None and len(row['intent'])==1)
        self.stream_packet(row,value);row['stream']['envelope']=deepcopy(value);self.save(host_only=True)

    def neutral(self,row):
        if row['stream'] is None:return
        stream=row['stream'];need(stream['envelope'] is not None)
        if stream['neutral'] is None:
            value=self.session.require_owned_neutral(self.binding['processIdentity'],stream['envelope'])
            PicoLifecycleBack.neutral(value,stream['envelope'],row['before']['home']['capturedEpochMs'])
            stream['neutral']=deepcopy(value);self.save()

    def read(self,verb):
        self.bound();previous=self.state['current'];reader=self.avatar();need(reader.pid==self.pid and reader.ios is False)
        if previous:reader.restore([previous['avatar']])
        started=self.monotonic();epoch=reader.clock_ms();host=self.phase.epoch_ms()
        before=self.phase.status(None if previous is None else previous['phaseAfter'])
        avatar=reader.read();widgets=None
        if self.require_resources:controlled_resources(avatar)
        # Navigation publishes independently. Wait for an actually newer GUI
        # observation; never relabel an older file with the avatar query time.
        for attempt in range(16):
            widgets=self.original().capture()
            if widgets['updatedEpochMs']>=avatar['capturedEpochMs']:break
            need(attempt<15 and self.monotonic()-started<1.5);self.sleep(.05)
        route=self.home();need(isinstance(route,PicoTabletHome) and route.source.pid==self.pid)
        value=dict(avatar=avatar,widgets=widgets,home=route.source.capture(),phaseBefore=before,phaseAfter=self.phase.status(before))
        self.packet(value,previous);need(before['activations'][-1]['stimulus']['verb']==verb and (before['active'] or verb=='cleanup'))
        self.anchor=(started,epoch,host,reader.clock_ms);self.delivery(value)
        return value

    def delivery(self,value):
        self.bound();need(self.anchor is not None);started,epoch,host,clock=self.anchor
        native_now=clock();host_now=self.phase.epoch_ms()
        phase=self.phase.status(value['phaseAfter']);need(same(phase['activations'],value['phaseAfter']['activations'])
            and phase['active']==value['phaseAfter']['active'])
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous));finished=self.monotonic()
        need(number(finished,started,started+5) and integer(native_now,epoch) and number(host_now,host,1e15))
        fresh(value['avatar']['requestedEpochMs'],max(native_now,epoch+math.ceil((finished-started)*1000)))
        fresh(value['widgets']['updatedEpochMs'],max(native_now,epoch+math.ceil((finished-started)*1000)))
        fresh(value['home']['capturedEpochMs'],max(native_now,epoch+math.ceil((finished-started)*1000)))
        fresh(value['phaseBefore']['capturedEpochMs'],max(host_now,host+math.ceil((finished-started)*1000)))
        self.clock=finished

    def before_send(self,command):
        need(self.state['steps']);row=self.state['steps'][-1]
        need(row['after'] is None and row['stream'] is None and len(row['intent'])==1
            and row['control']==command.get('controlId') and command.get('action')=='activate')
        widgets=row['intent'][0]['widgets'];control=next(item for item in widgets['controls'] if item['id']==row['control'])
        need(all(command.get(key)==value for key,value in dict(bridgeId=widgets['bridgeId'],generation=widgets['generation'],
            sequence=widgets['lastCommandSequence']+1,controlToken=control['token']).items()))
        self.delivery(row['before'])

    @staticmethod
    def intent_packet(value,row):
        exact(value,{'control','widgets','view','home'})
        need(value['control']==row['control']);widgets=value['widgets']
        validate_snapshot(widgets,widgets.get('processId'),widgets.get('updatedEpochMs'))
        before=row['before']['widgets']
        need(all(widgets[k]==before[k] for k in ('bridgeId','generation','processId','lastCommandSequence'))
            and widgets['elapsedMs']>=before['elapsedMs'] and widgets['updatedEpochMs']>=before['updatedEpochMs'])
        if row['control'].startswith('view-menu.'):
            request=value['view'];exact(request,{'viewMenuInputVersion','action','controlId','controlToken','menuInstance','checkedBefore','scope'})
            p=project(widgets);rows=[r for r in p['controls'] if r['id']==row['control']]
            need(len(rows)==1 and request==dict(viewMenuInputVersion=1,action='activate',controlId=row['control'],
                controlToken=rows[0]['token'],menuInstance=rows[0]['menuInstance'],checkedBefore=rows[0]['checked'],scope=p['scope']))
        else:need(value['view'] is None)
        if row['control']=='tablet.home-ray':
            home=value['home'];home_input(home,widgets['processId'],home.get('capturedEpochMs'),'tablet.home-ray')
            old=row['before']['home'];need(all(home[k]==old[k] for k in ('instance','tabletId','homeId','parentId'))
                and home['sourceSequence']>old['sourceSequence'] and home['capturedEpochMs']>=old['capturedEpochMs'])
        else:need(value['home'] is None)

    def intent(self,row,widgets,view=None,home=None):
        self.bound();need(not row['intent'] and row['after'] is None)
        value=dict(control=row['control'],widgets=deepcopy(widgets),view=deepcopy(view),home=deepcopy(home));self.intent_packet(value,row)
        row['intent'].append(value);self.save();self.delivery(row['before'])

    @staticmethod
    def effect(row,current):
        control=row['control'];widgets=current['widgets']
        need(same(row['before']['phaseAfter']['activations'],current['phaseBefore']['activations'])
            and row['before']['phaseAfter']['active']==current['phaseBefore']['active'])
        if control in ('tablet.open','tablet.close'):
            need(widgets['open']==(control=='tablet.open') and (not widgets['open'] or widgets['ready']) and current['home']['onHomeScreen'])
        elif control=='tablet.home-ray':need(widgets['open'] and widgets['ready'] and current['home']['onHomeScreen'])
        else:
            need(widgets['open'] and widgets['ready'] and not current['home']['onHomeScreen'])
            need(widgets['lastCommandSequence']==row['before']['widgets']['lastCommandSequence']+1)
            target='view-menu.view' if control=='scripts.menu' else 'view-menu.third' if control=='view-menu.view' else control
            rows=[r for r in widgets['controls'] if r['id']==target]
            need(len(rows)==1 and rows[0]['inputReady'])
            if control in MODES.values():
                need(rows[0]['checked'] and current['avatar']['source']['cameraMode']==next(mode for mode,key in MODES.items() if key==control))
                old=row['before']['avatar']['source'];state=old['cameraState'];now=current['avatar']['source']
                expected=state['boomLength'] if old['cameraMode']==now['cameraMode'] else state['zoomMin'] if control=='view-menu.first' else (
                    state['zoomDefault'] if state['boomLength']==state['zoomMin'] else state['boomLength'])
                need(now['cameraState']['boomLength']==expected)

    def step(self,kind,control,verb):
        self.bound();old=[r for r in self.state['steps'] if r['kind']==kind]
        if old:
            need(len(old)==1);row=old[0]
            if row['after'] is not None:return
            # A reserved or dispatched step is re-observed only. Even a lost
            # pre-dispatch write response cannot authorize another input.
            need(len(row['intent'])==1)
        else:
            before=self.read(verb)
            need(before['avatar']['source']['cameraMode']==self.state['current']['avatar']['source']['cameraMode']
                and before['avatar']['source']['cameraState']['boomLength']==self.state['current']['avatar']['source']['cameraState']['boomLength'])
            self.state['current']=deepcopy(before)
            row=dict(kind=kind,control=control,before=before,intent=[],after=None,
                stream=dict(envelope=None,neutral=None) if control in ('tablet.open','tablet.close','tablet.home-ray') else None)
            self.state['steps'].append(row);self.save()
            io=self.original()
            if row['stream'] is None:io.navigation.io.bind_before_send(self._before_send)
            if control=='tablet.home-ray':
                need(not before['home']['onHomeScreen'])
                route=self.home();need(isinstance(route,PicoTabletHome) and route.source.pid==self.pid)
                route.ensure(lambda _stage,original,_control:self.intent(row,io.capture(),home=original),
                    stream_intent=lambda value:self.stream_intent(row,value))
            elif control.startswith('view-menu.'):
                widgets=io.capture();flow=PicoViewMenu(io,lambda request:self.intent(row,widgets,request),monotonic=self.monotonic,sleep=self.sleep)
                flow.activate(control,project(widgets))
            else:
                widgets=io.capture();self.intent(row,widgets)
                if control in ('tablet.open','tablet.close'):
                    self.session.stage(self.binding['processIdentity'],control,dict(holdMilliseconds=1000),
                        intent=lambda value:self.stream_intent(row,value))
                else:
                    rows=[r for r in widgets['controls'] if r['id']==control];need(len(rows)==1 and rows[0]['enabled'])
                    io.navigation.input(control,token=rows[0]['token'])
            need(len(row['intent'])==1)
        self.neutral(row)
        started=self.monotonic()
        for attempt in range(51):
            current=self.read(verb)
            try:self.effect(row,current)
            except RuntimeError:
                need(attempt<50 and self.monotonic()-started<5);self.sleep(.1);continue
            if row['stream'] is not None:need(row['stream']['neutral']['updatedEpochMs']<=current['home']['capturedEpochMs']+250)
            row['after']=deepcopy(current);self.state['current']=current;self.save();self.delivery(current);return
        need(False)

    def operate(self,restore=False):
        need(type(restore) is bool);self.bound();need(self.started is None);self.started=self.monotonic()
        verb='cleanup' if restore else 'baseline';prefix='restore' if restore else 'prepare'
        try:
            with self.input_session():
                if self.state['phase']=='reserved':
                    need(not restore);original=self.read(verb)
                    need(not original['widgets']['open'] and original['avatar']['source']['cameraMode'] in MODES
                        and original['avatar']['source']['loaded'] and original['home']['onHomeScreen'])
                    source=original['avatar']['source'];need(source['cameraMode']!='first person look at'
                        or source['cameraState']['boomLength']==source['cameraState']['zoomMin'])
                    self.state.update(phase='preparing',original=deepcopy(original),current=original);self.save()
                if restore:
                    need(self.state['phase'] in ('preparing','ready','restoring','restored'))
                    # Retain unresolved setup rather than guessing whether its
                    # deferred ordinary input might still mutate the camera.
                    need(all(row['after'] is not None for row in self.state['steps'] if row['kind'].startswith('prepare')))
                else:need(self.state['phase'] in ('preparing','ready'))
                terminal='restored' if restore else 'ready'
                if self.state['phase']!=terminal:
                    if restore:self.state['phase']='restoring';self.save()
                    mode=self.state['original']['avatar']['source']['cameraMode'] if restore else 'look at'
                    for part,control in (('open','tablet.open'),('menu','scripts.menu'),('view','view-menu.view'),('mode',MODES[mode]),
                            ('home','tablet.home-ray'),('close','tablet.close')):
                        self.step(prefix+'-'+part,control,verb)
                    self.state['phase']=terminal;self.save()
                current=self.read(verb);need(not current['widgets']['open'] and current['home']['onHomeScreen']
                    and current['avatar']['source']['cameraMode']==(self.state['original']['avatar']['source']['cameraMode'] if restore else 'look at'))
                need(current['avatar']['source']['cameraState']['boomLength']==
                    (self.state['original'] if restore else self.state['current'])['avatar']['source']['cameraState']['boomLength'])
                self.state['current']=current;self.save();self.delivery(current);return {'performed':True}
        finally:self.started=None

    def prepare(self):return self.operate()
    def restore(self):return self.operate(True)

    def controlled(self,*,restore=False):
        """Normal view preparation/restoration with actual bundled byte admission.

        Original v4 histories without this optional native source remain owned;
        they cannot be upgraded into this controlled-avatar qualification.
        """
        self.bound();need(type(restore) is bool and not self.require_resources)
        originals=[] if self.state['original'] is None else [self.state['original'],self.state['current']]
        for row in self.state['steps']:originals.extend([row['before']]+([] if row['after'] is None else [row['after']]))
        for original in originals:controlled_resources(original['avatar'])
        self.require_resources=True
        try:return self.operate(restore)
        finally:self.require_resources=False

    def controller_retirement(self):
        """Fresh original final stream neutral; historical originals stay owned."""
        self.bound();need(self.state['phase']=='restored')
        current=self.read('cleanup');need(not current['widgets']['open'] and current['home']['onHomeScreen']
            and current['avatar']['source']['cameraMode']==self.state['original']['avatar']['source']['cameraMode']
            and current['avatar']['source']['cameraState']['boomLength']==self.state['original']['avatar']['source']['cameraState']['boomLength'])
        streams=[row for row in self.state['steps'] if row['stream'] is not None]
        need(len(streams)==6 and all(row['after'] is not None and row['stream']['neutral'] is not None for row in streams))
        value=self.session.require_owned_neutral(self.binding['processIdentity'],streams[-1]['stream']['envelope'])
        PicoLifecycleBack.neutral(value,streams[-1]['stream']['envelope'],streams[-1]['before']['home']['capturedEpochMs'])
        need(value['updatedEpochMs']<=current['home']['capturedEpochMs']+250)
        self.state['current']=current;self.save();self.delivery(current)
        return dict(retired=True,streams=deepcopy([row['stream'] for row in streams]),finalNeutral=deepcopy(value),journalsRetained=True)

    def menu_retirement(self):
        """Fresh original known-menu liveness; keeps every parent journal."""
        self.bound();need(self.state['phase']=='restored')
        original=self.state['original']['widgets'];need('picoViewMenuLifetimes' in original)
        current=self.read('cleanup');need('picoViewMenuLifetimes' in current['widgets'])
        need(not current['widgets']['open'] and current['home']['onHomeScreen']
            and current['avatar']['source']['cameraMode']==self.state['original']['avatar']['source']['cameraMode']
            and current['avatar']['source']['cameraState']['boomLength']==self.state['original']['avatar']['source']['cameraState']['boomLength'])
        released=view_menu_lifetimes.retired(original['picoViewMenuLifetimes'],current['widgets']['picoViewMenuLifetimes'])
        self.state['current']=current;self.save();self.delivery(current)
        return dict(retired=released,original=current['widgets']['picoViewMenuLifetimes'],journalsRetained=True)
