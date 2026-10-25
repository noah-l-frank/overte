"""Whole cleanup samplers at the same explicitly modeled native process.

These are original native producer boundaries only. The actual AccountManager
model still performs ordinary login/logout and real HTTPS; cleanup, quiet and
historical decoders are never replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
from ios.adapters import avatar_state,avatar_social_http,avatar_scripts,people_model,avatar_entities,world_web_keys,uikit_input,web_closures
from ios.adapters.native_geometry import OriginalGeometry
from ios.self_tests.avatar_image_domain import ImageDomain,RUN
from ios.self_tests.test_ios_world_web_keys import QtKeys
from ios.self_tests.avatar_uikit_fixture import UIKit2Boundary
from ios.self_tests.avatar_login_roots_fixture import LoginRoots


class FinalDomain(ImageDomain):
    def __init__(self,test):
        super().__init__(test);outer=self;self.keys={};self.geometry={};self.uikit={};self.login_roots={};self.worldless_web_queries={}
        for role,scene in self.scenes.items():
            n=self.natives[role];self.login_roots[role]=LoginRoots(n)
            self.worldless_web_queries[role]=[]
            observed=n.observed
            def widgets(old=observed,domain=scene.domain):
                value=old()
                inventory=value['scriptInventory']
                if inventory['inventoryVersion']==1:
                    # This is the same modeled getter, not another capture:
                    # read the existing whole-tree census without advancing
                    # time inside private-login input processing. Script-page
                    # and picker samples already use HeldDomain's v2 getter.
                    assert domain.io.qt.page!='scripts' and not domain.io.file.opened
                    assert not inventory['managers'] and not inventory['pickers']
                    domain.roots.elapsed=round(domain.time*1000)
                    value['scriptInventory']=dict(inventory,inventoryVersion=2,
                        rootOwnership=domain.roots.source(),rootMembership=dict(managers=[],pickers=[]))
                return value
            n.observed=widgets
            # Native Login and full-source snapshots observe the same actual
            # host operands, including a cached root after visible controls go.
            scene.widgets=n.observed
            self.uikit[role]=UIKit2Boundary(n.epoch,lambda:round(outer.clock[0]*1000),pid=31)
            original_call=n.call
            def ordinary(method,path,payload=None,*,n=n,old=original_call,boundary=self.uikit[role]):
                if method=='POST' and path.endswith('/click'):return boundary.touch(lambda:old(method,path,payload))
                return old(method,path,payload)
            n.call=ordinary
            keys=QtKeys();keys.started_epoch=n.epoch();keys.born_epoch=n.epoch()-1;self.keys[role]=keys;self.geometry[role]=dict(sequence=0,current=None)
            def tick(n=n,keys=keys):outer.clock[0]+=.001;keys.epoch=n.epoch();return keys.epoch
            keys.tick=tick
            mutate=scene.f.mutate
            def model(name,value,n=n,old=mutate):
                old(name,value)
                if name=='state':
                    # Actual anonymous NodeList/MyAvatar UUID nullness belongs
                    # to this native producer, never a reader-side replacement.
                    value['source']['sessionPresent']=n.account['loggedIn']
                    if not n.account['loggedIn']:value['source']['sessionId']='00000000-0000-0000-0000-000000000000'
            scene.f.mutate=model
        base=type(self.runtime)
        class Runtime(base):
            def _sources(_self,selector):
                result=super()._sources(selector);f=outer.scenes[selector].f;n=outer.natives[selector];clock=result['clock_source']
                for name,method,kind in (('state','avatar_state',avatar_state.IOSAvatarState),('http','avatar_social_http',avatar_social_http.IOSAvatarSocialHttp),
                    ('scripts','avatar_scripts',avatar_scripts.IOSAvatarScripts),('people','people_model',people_model.IOSPeopleModel),('entities','avatar_entities',avatar_entities.IOSAvatarEntities)):
                    def factory(given,name=name,kind=kind):
                        reader=f.reader(name,kind);reader.clock_ms=lambda:given.read(given.sequence)['capturedEpochMs'];return reader
                    setattr(result['observer'],method,factory)
                def key_source(given):
                    keys=outer.keys[selector];current=[None]
                    def send(query):
                        value=keys.packet();value.update(requestId=query['commandId'],runId=query['runId'],processId=31)
                        for name in ('clockBefore','clockAfter'):value[name]['monotonicMs']=round(outer.clock[0]*1000)
                        value['source'].update(bornEpochMs=keys.born_epoch,startup=dict(observed=True,epochMs=keys.started_epoch,monotonicMs=1000,windowCount=0,modifiers=0))
                        current[0]=value
                    return world_web_keys.IOSWorldWebKeys(send,lambda:json.dumps(current[0]),lambda:given.read(given.sequence)['capturedEpochMs'],lambda:True,31,
                        monotonic=lambda:outer.clock[0],sleep=outer.sleep)
                def geometry():
                    channel=outer.geometry[selector]
                    def send(query):
                        outer.clock[0]+=.001;channel['sequence']+=1
                        # Original UIKit keyboard metrics are independent of
                        # the global key/IME event argument ledger.
                        keyboard=n.login.dialog and n.login.focused is not None
                        channel['current']=dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,sampleEpochMs=n.epoch(),sampleSequence=channel['sequence'],
                            nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,
                                keyboardVisible=keyboard,imeInsetBottom=250 if keyboard else 0),window=dict(width=1024,height=728)))
                    return OriginalGeometry(send,lambda:json.dumps(channel['current']),lambda:clock.read(clock.sequence)['capturedEpochMs'],lambda:True,
                        monotonic=lambda:outer.clock[0],sleep=outer.sleep)
                def uikit_source(given):
                    current=[None]
                    def send(query):outer.clock[0]+=.001;current[0]=outer.uikit[selector].packet(query)
                    return uikit_input.IOSUIKitInput(send,lambda:json.dumps(current[0]),lambda:given.read(given.sequence)['capturedEpochMs'],lambda:True,31,
                        monotonic=lambda:outer.clock[0],sleep=outer.sleep)
                def web_source():
                    current=[None];domain=outer.scenes[selector].domain
                    def send(query):
                        web_closures.command(query);test.assertEqual(RUN,query['runId'])
                        test.assertEqual(domain.scope.fixture_url,query['fixtureUrl'])
                        outer.worldless_web_queries[selector].append(deepcopy(query))
                        # This is a fresh modeled native getter sample, not
                        # a retained packet. Echo its incoming request before
                        # the first raw return; clocks/contexts come unchanged
                        # from the same actual modeled cache/callback source.
                        value=domain.web(query['runId'],query['fixtureUrl'])
                        value['commandId']=query['commandId'];domain.scope.web.last=deepcopy(value);current[0]=value
                    return web_closures.IOSWebClosures(send,lambda:json.dumps(current[0]),
                        lambda:clock.read(clock.sequence)['capturedEpochMs'],result['check'],n.pid,
                        monotonic=lambda:outer.clock[0],sleep=outer.sleep)
                result['observer'].uikit_input=uikit_source;result['observer'].world_web_keys=key_source;result['observer'].geometry=geometry
                result['observer'].web_closures=web_source;return result
        self.runtime.__class__=Runtime
