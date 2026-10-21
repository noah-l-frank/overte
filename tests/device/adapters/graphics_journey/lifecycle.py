"""One-send normal Graphics background/activation with original OS/native proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.graphics_journey.scene import GraphicsScene
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.witness import Client
from feature_journeys.contract import arguments
from adapters.graphics_journey.preferences import GraphicsPreferences,advance
from adapters.script_journey.history import pack,unpack,same

VERSION=1


class GraphicsBackground:
    def __init__(self,preferences,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(preferences,GraphicsPreferences) and preferences.state is not None
            and callable(monotonic) and callable(sleep))
        self.preferences,self.scene=preferences,preferences.scene
        self.adapter,self.selector,self.run,self.lock=preferences.adapter,preferences.selector,preferences.run,preferences.lock
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        self.binding=deepcopy(self.scene.binding);self.pid=self.scene.pid
        self.fixture_url=self.preferences.fixture_url;self.client=self.scene.client
        self.scene_store,self.preferences_store=self.scene.store,self.preferences.store
        self.archives=None
        self.store=PrivateFeatureState(preferences.store.path.with_name('graphics-background.json'))
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def recover(cls,adapter,selector,client,run,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        """Load immutable owner archives while the process may be backgrounded.

        No live owner/guard is fabricated. Actual OS admission precedes any
        remaining normal input; foreground native owners are acquired only
        after the original process is independently observed in the foreground.
        """
        need(isinstance(client,Client) and client.run==run and client.area=='graphics'
            and isinstance(lock,ScriptSourceLock) and callable(monotonic) and callable(sleep));lock.assert_held()
        scope=GraphicsScene._archive_scope(adapter=adapter,selector=selector,client=client,run=run)
        scene_value=scope.store.read();need(scene_value is not None)
        scope.state=scope.decode(scene_value);scope.binding=scope.state['binding']
        preferences_store=PrivateFeatureState(scope.store.path.with_name('graphics-preferences.json'))
        preferences_value=preferences_store.read();need(preferences_value is not None)
        preferences=GraphicsPreferences.archive(preferences_value,scene=scope)
        owner=object.__new__(cls)
        owner.preferences=owner.scene=None
        owner.adapter,owner.selector,owner.client,owner.run,owner.lock=adapter,selector,client,run,lock
        owner.binding=deepcopy(scope.binding);owner.pid=int(owner.binding['processIdentity'].split(':')[0])
        owner.fixture_url=client.url+'/runs/'+run+'/'
        owner.scene_store,owner.preferences_store=scope.store,preferences_store
        owner.archives=dict(scene=deepcopy(scene_value),preferences=deepcopy(preferences_value),
            sceneState=deepcopy(scope.state),preferencesState=deepcopy(preferences))
        owner.monotonic,owner.sleep,owner.started,owner.last_clock=monotonic,sleep,None,None
        owner.store=PrivateFeatureState(scope.store.path.with_name('graphics-background.json'))
        owner.previous=owner.store.read();need(owner.previous is not None)
        owner.state=owner.decode(owner.previous)
        return owner

    def scene_state(self):return self.scene.state if self.scene is not None else self.archives['sceneState']
    def preference_state(self):return self.preferences.state if self.preferences is not None else self.archives['preferencesState']

    @classmethod
    def archive(cls,value,*,scene):
        """Original historical lifecycle proof, with no SDK, clock or input."""
        need(isinstance(scene,GraphicsScene) and type(scene.state) is dict)
        owner=object.__new__(cls);owner.scene=scene;owner.run=scene.run
        owner.binding=deepcopy(scene.state['binding']);owner.pid=int(owner.binding['processIdentity'].split(':')[0])
        owner.fixture_url=scene.client.url+'/runs/'+scene.run+'/'
        return deepcopy(owner.decode(value))

    def current_source(self):
        if self.preferences is None:
            # Reconstruct the actual guarded live owners, never repurpose the
            # archive decoder as a live object or fake a successful guard.
            need(self.status()['foreground'] is True)
            scene=GraphicsScene(self.adapter,self.selector,self.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
            preferences=GraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep)
            need(same(scene.binding,self.binding) and same(scene.previous,self.archives['scene'])
                and same(preferences.previous,self.archives['preferences']))
            self.scene,self.preferences=scene,preferences;self.archives=None
        return self.preferences.source()

    def decode(self,value):
        exact(value,{'graphicsBackgroundVersion','runId','fixtureUrl','payload'})
        need(type(value['graphicsBackgroundVersion']) is int and value['graphicsBackgroundVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','arguments','phase','before','background','after'})
        need(same(context(state['binding']),self.binding)
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observed'))
        call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='background-resume' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        before=state['before'];native_packet(before,before['requestId'],self.pid,before['capturedEpochMs'])
        need(before['instance']==self.scene_state()['subject']['instance'])
        if state['background'] is not None:
            self.status_packet(state['background'],state['binding']);need(state['background']['foreground'] is False)
        if state['phase']!='background-issued':need(state['background'] is not None)
        if state['after'] is not None:self.completed(before,state['after'])
        need(state['phase']!='observed' or state['after'] is not None)
        return state

    @staticmethod
    def status_packet(value,binding):
        exact(value,{'binding','foreground','running'})
        need(same(context(value['binding']),binding) and type(value['foreground']) is bool and value['running'] is True)
        return value

    @staticmethod
    def completed(before,after):
        advance(before,after);a,b=before['lifecycle'],after['lifecycle']
        need(after['requestedEpochMs']>=before['capturedEpochMs']
            and b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1
            and b['launches']==a['launches'] and before['graphics']==after['graphics'])

    def bound(self):
        # The foreground-only native/UI guard must not be called while the
        # normally backgrounded process is waiting for its one owned activation.
        self.lock.assert_held();now=self.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or 0<=now-self.started<30)
            and same(self.store.read(),self.previous)
            and same(self.preferences_store.read(),self.preferences.previous if self.preferences is not None else self.archives['preferences'])
            and same(self.scene_store.read(),self.scene.previous if self.scene is not None else self.archives['scene']))
        self.last_clock=now

    def save(self):
        self.bound()
        value=dict(graphicsBackgroundVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def status(self):
        self.bound();packet=self.adapter._graphics_lifecycle_status(self.selector,self.binding)
        self.status_packet(packet,self.binding);self.bound();return deepcopy(packet)

    def wait_background(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            packet=self.status()
            if packet['foreground'] is False:return packet
            if self.monotonic()-started>=5 or attempt==50:break
            self.sleep(.1)
        raise NativeUIError('Normal Pico Graphics background input did not change the original OS foreground state')

    def act(self,call):
        call=deepcopy(arguments('feature.graphics.act',call))
        need(call['verb']=='background-resume' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.started=self.monotonic();self.bound()
        with self.adapter.existing_input_session(self.selector):
            if self.state is None:
                need(self.preference_state()['phase'] in ('ready','acknowledged') and self.scene_state()['phase']=='active'
                    and not any(self.scene_state()['leases'].values()))
                need(self.status()['foreground'] is True);before=self.current_source();self.bound()
                self.state=dict(binding=deepcopy(self.binding),arguments=call,phase='background-issued',
                    before=before,background=None,after=None);self.save()
                # Durable one-send intent precedes ordinary Home input. A lost
                # response leaves this exact state and is never redelivered.
                self.adapter._graphics_lifecycle_input(self.selector,'lifecycle.background',self.binding);self.bound()
            else:need(same(self.state['arguments'],call))
            if self.state['phase']=='background-issued':
                self.state.update(phase='background-observed',background=self.wait_background());self.save()
            if self.state['phase']=='background-observed':
                need(self.status()['foreground'] is False)
                self.state['phase']='foreground-issued';self.save()
                self.adapter._graphics_lifecycle_input(self.selector,'app.launch',self.binding);self.bound()
            need(self.state['phase'] in ('foreground-issued','observed') and self.status()['foreground'] is True)
            packet=self.current_source();self.completed(self.state['before'],packet)
            if self.state['after'] is not None:advance(self.state['after'],packet)
            self.state.update(phase='observed',after=deepcopy(packet));self.save();self.bound()
        return {'performed':True} # Fresh GPU/image persistence remains separate.

    def retire(self):
        self.started=self.monotonic();self.bound();need(self.state is not None and self.state['phase']=='observed'
            and self.preference_state()['phase'] in ('ready','acknowledged','cleaned')
            and not any(self.scene_state()['leases'].values()))
        with self.adapter.existing_input_session(self.selector):
            need(self.status()['foreground'] is True);packet=self.current_source();advance(self.state['after'],packet)
            need(all(packet['lifecycle'][key]>=value for key,value in self.state['after']['lifecycle'].items()))
            self.bound();self.decode(self.previous);self.store.discard(self.previous);need(self.store.read() is None)
