"""One-send normal Graphics background/activation with original OS/native proof."""
# Decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Original iOS candidate, OS process/foreground and normal activation stay platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments
from ios.adapters.graphics_preferences import IOSGraphicsPreferences,advance
from ios.adapters.graphics_scene import IOSGraphicsScene
from ios.adapters.login_source import nonce
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import pack,unpack,same

VERSION=1


class IOSGraphicsBackground:
    @classmethod
    def recover(cls,adapter,selector,client,run,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        """Reconstruct input ownership without requiring foreground native IO.

        Scene/preferences are historical decoders. Only the existing OS/source
        status guard may run before the single owned activation is observed.
        The later native source read still requires canonical foreground admission.
        """
        need(isinstance(lock,ScriptSourceLock));lock.assert_held()
        scene=IOSGraphicsScene._archive_scope(adapter=adapter,selector=selector,client=client,run=run)
        scene.previous=scene.store.read();need(scene.previous is not None)
        scene.state=scene.decode(scene.previous);scene.binding=context(scene.state['binding']);scene.pid=int(scene.binding['processIdentity'])
        scene.lock,scene.monotonic,scene.sleep=lock,monotonic,sleep;scene.started=scene.last_clock=None
        def guard():
            cls.status_packet(adapter._graphics_lifecycle_status(selector,scene.binding),scene.binding)
            return True
        scene.guard=guard;guard()
        preferences=IOSGraphicsPreferences(scene,monotonic=monotonic,sleep=sleep)
        need(preferences.state is not None)
        return cls(preferences,monotonic=monotonic,sleep=sleep)

    def __init__(self,preferences,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(preferences,IOSGraphicsPreferences) and preferences.state is not None
            and callable(monotonic) and callable(sleep))
        self.preferences,self.scene=preferences,preferences.scene
        self.adapter,self.selector,self.run,self.lock=preferences.adapter,preferences.selector,preferences.run,preferences.lock
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        self.store=PrivateFeatureState(preferences.store.path.with_name('ios-graphics-background.json'))
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    @classmethod
    def archive(cls,value,*,scene):
        """Historical source validation without foreground admission."""
        from types import SimpleNamespace
        scope=object.__new__(cls);scope.scene,scope.run=scene,scene.run
        scope.preferences=SimpleNamespace(fixture_url=scene.client.url+'/runs/'+scene.run+'/')
        return deepcopy(scope.decode(value))

    def decode(self,value):
        exact(value,{'iosGraphicsBackgroundVersion','runId','fixtureUrl','payload'})
        need(type(value['iosGraphicsBackgroundVersion']) is int and value['iosGraphicsBackgroundVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.preferences.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','arguments','phase','before','background','after'})
        need(same(context(state['binding']),self.scene.binding)
            and state['phase'] in ('background-issued','background-observed','foreground-issued','observed'))
        call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='background-resume' and call['runId']==self.run and call['fixtureUrl']==self.preferences.fixture_url)
        before=state['before'];nonce(before['requestId']);native_packet(before,before['requestId'],self.scene.pid,before['capturedEpochMs'])
        if state['background'] is not None:
            self.status_packet(state['background'],state['binding']);need(state['background']['foreground'] is False)
        if state['phase']!='background-issued':need(state['background'] is not None)
        if state['after'] is not None:self.completed(before,state['after'])
        need(state['phase']!='observed' or state['after'] is not None)
        return state

    @staticmethod
    def status_packet(value,binding):
        exact(value,{'binding','foreground','running','appState'})
        need(same(context(value['binding']),binding) and type(value['foreground']) is bool and value['running'] is True
            and type(value['appState']) is int and value['appState'] in (2,3,4)
            and value['foreground']==(value['appState']==4))
        return value

    @staticmethod
    def completed(before,after):
        advance(before,after);a,b=before['lifecycle'],after['lifecycle']
        need(b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1
            and b['launches']==a['launches'] and before['graphics']==after['graphics'])

    def bound(self):
        # The foreground-only native/UI guard must not be called while the
        # normally backgrounded process is waiting for its one owned activation.
        self.lock.assert_held();now=self.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or 0<=now-self.started<30)
            and same(self.store.read(),self.previous)
            and same(self.preferences.store.read(),self.preferences.previous)
            and same(self.scene.store.read(),self.scene.previous))
        self.last_clock=now

    def save(self):
        self.bound()
        value=dict(iosGraphicsBackgroundVersion=VERSION,runId=self.run,fixtureUrl=self.preferences.fixture_url,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def status(self):
        self.bound();packet=self.adapter._graphics_lifecycle_status(self.selector,self.scene.binding)
        self.status_packet(packet,self.scene.binding);self.bound();return deepcopy(packet)

    def wait_background(self):
        started=self.monotonic();need(number(started,0,1e15))
        for attempt in range(51):
            packet=self.status()
            if packet['foreground'] is False:return packet
            if self.monotonic()-started>=5 or attempt==50:break
            self.sleep(.1)
        raise NativeUIError('Normal iOS Graphics background input did not change the original OS foreground state')

    def act(self,call):
        call=deepcopy(arguments('feature.graphics.act',call))
        need(call['verb']=='background-resume' and call['runId']==self.run and call['fixtureUrl']==self.preferences.fixture_url)
        self.started=self.monotonic();self.bound()
        with self.adapter.existing_input_session(self.selector):
            if self.state is None:
                need(self.preferences.state['phase'] in ('ready','acknowledged') and self.scene.state['phase']=='active'
                    and not any(self.scene.state['leases'].values()))
                self.status();before=self.preferences.source();self.bound()
                self.state=dict(binding=deepcopy(self.scene.binding),arguments=call,phase='background-issued',
                    before=before,background=None,after=None);self.save()
                # Durable one-send intent precedes ordinary Home input. A lost
                # response leaves this exact state and is never redelivered.
                self.adapter.invoke(self.selector,'lifecycle.background',{});self.bound()
            else:need(same(self.state['arguments'],call))
            if self.state['phase']=='background-issued':
                self.state.update(phase='background-observed',background=self.wait_background());self.save()
            if self.state['phase']=='background-observed':
                need(self.status()['foreground'] is False)
                self.state['phase']='foreground-issued';self.save()
                self.adapter.invoke(self.selector,'app.launch',{});self.bound()
            need(self.state['phase'] in ('foreground-issued','observed') and self.status()['foreground'] is True)
            packet=self.preferences.source();self.completed(self.state['before'],packet)
            if self.state['after'] is not None:advance(self.state['after'],packet)
            self.state.update(phase='observed',after=deepcopy(packet));self.save();self.bound()
        return {'performed':True} # Fresh GPU/image persistence remains separate.

    def retire(self):
        self.started=self.monotonic();self.bound();need(self.state is not None and self.state['phase']=='observed'
            and self.preferences.state['phase'] in ('ready','acknowledged','cleaned')
            and not any(self.scene.state['leases'].values()))
        with self.adapter.existing_input_session(self.selector):
            need(self.status()['foreground'] is True);packet=self.preferences.source();advance(self.state['after'],packet)
            need(all(packet['lifecycle'][key]>=value for key,value in self.state['after']['lifecycle'].items()))
            self.bound();self.decode(self.previous);self.store.discard(self.previous);need(self.store.read() is None)
