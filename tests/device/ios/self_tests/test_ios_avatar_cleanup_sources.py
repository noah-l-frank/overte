"""Ordinary Avatar recipes and retained source/timer/HTTP cleanup originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid
from adapters.normal_ui import NativeUIError,Locator
from ios.adapters import normal_input
from ios.adapters.avatar_cleanup_sources import restored
from ios.adapters.avatar_observation import source_history
from ios.self_tests import test_ios_avatar_actions as fixture_module
from ios.self_tests import test_ios_avatar_entities as entity_fixture

EXPECTED=entity_fixture.EXPECTED|{'/system/pal.js':dict(codeUnits=32,sha256='2'*64)}


class AvatarCleanupSourcesTests(unittest.TestCase):
    def setUp(self):
        f=fixture_module.AvatarActionTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        held=f.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        source=f.fixture;worker=source.prototypes['scripts']['source']['workers'][0]
        worker['avatar']['code'].append(dict(sequence=2,url='qrc:/scripts/system/pal.js',submittedEpochMs=1700000000003,
            encoding='utf-16le-code-units',**EXPECTED['/system/pal.js']))
        worker['uiWork']=dict(avatarUiWorkVersion=1,instance='f'*32,complete=True,timers=[])
        worker['uiWork']['timers']=[dict(timerId='d'*32,handle=2,callerChain=['qrc:/scripts/system/pal.js'],
            createdEpochMs=1700000000010,singleShot=False,intervalMs=100,activeAtBirth=True,remainingAtBirthMs=100,
            destroyedEpochMs=None,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,
            lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None)]
        observed=source.widget.observed
        def widgets():
            value=observed();value['avatarInventory']=dict(iosAvatarUiInventoryVersion=1,complete=True,roots=[]);return value
        source.widget.observed=widgets
        seam=patch.object(normal_input,'urlopen',source.widget.post);seam.start();self.addCleanup(seam.stop)
        f.source=f.make_sources();self.actions=f.owner();self.actions.prepare();self.baseline=self.actions.state['baseline']['revision']
        self.actions.act(f.action('avatar-url',dict(resource='avatar-a.fst'),'2'*32))
        self.actions.act(f.action('avatar-restore',{},'3'*32))
        f.sdk.click(Locator('accessibility id','OverteTabletClose'));source.journal.activate(source.run,'4'*32,'cleanup')
        f.source.read()
    def measure(self):
        owner=self.f.source;sources=source_history(owner.previous,None,store=owner.store,root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        return restored(sources,self.baseline,len(sources.frames),fixture_url=owner.phase.fixture_url,expected_code=EXPECTED)
    def test_original_restored_model_closed_root_and_new_timer_weak_death_are_separate_requirements(self):
        f=self.f.fixture;worker=f.prototypes['scripts']['source']['workers'][0]
        worker['uiWork']['timers'].append(dict(timerId='e'*32,handle=1,callerChain=['qrc:/scripts/system/avatarapp.js'],
            createdEpochMs=f.now(),singleShot=True,intervalMs=5000,activeAtBirth=True,remainingAtBirthMs=5000,
            destroyedEpochMs=None,fired=0,entered=0,left=0,depth=0,pendingDispatch=0,
            lastFiredEpochMs=None,lastCallbackEpochMs=None,lastDispatchEpochMs=None))
        self.f.source.read()
        with self.assertRaises(NativeUIError):self.measure()
        timer=worker['uiWork']['timers'][-1];timer['destroyedEpochMs']=f.now();self.f.source.read()
        proof=self.measure();self.assertEqual(timer['destroyedEpochMs'],proof['endpointEpochMs'])
        self.assertEqual('original',proof['appearance']['state']['avatar']);self.assertEqual([],proof['ownedHttp'])
    def test_restored_appearance_and_timer_closure_cannot_hide_a_new_retained_XHR(self):
        f=self.f.fixture;http=f.prototypes['http'];source=deepcopy(http['events'][0]['details']);identity='f'*32
        def event(kind,details):
            http['events'].append(dict(sequence=len(http['events'])+1,eventId=uuid.uuid4().hex,xhrId=identity,kind=kind,
                clock=dict(epochMs=f.now(),monotonicMs=round(f.clock*1000)),details=details))
        event('created',source);self.f.source.read()
        with self.assertRaises(NativeUIError):self.measure()
        for kind in ('callbacks-released','timer-destroyed','xhr-destroyed'):event(kind,{})
        self.f.source.read();proof=self.measure();self.assertEqual([identity],proof['ownedHttp']);self.assertGreater(proof['endpointEpochMs'],0)
    def test_missing_passive_root_inventory_or_timer_component_never_becomes_empty_cleanup(self):
        for fault in ('inventory','uiWork'):
            with self.subTest(fault=fault):
                if fault=='inventory':
                    old=self.f.fixture.widget.observed
                    def unavailable():
                        value=old();del value['avatarInventory'];return value
                    self.f.fixture.widget.observed=unavailable
                    self.f.source.read()
                    with self.assertRaises(NativeUIError):self.measure()
                    self.f.fixture.widget.observed=old
                else:
                    del self.f.fixture.prototypes['scripts']['source']['workers'][0]['uiWork']
                    with self.assertRaises(NativeUIError):self.f.source.read()
    def test_hidden_detached_retained_Qt_root_is_not_closed_by_visible_control_absence(self):
        source=self.f.fixture;observed=source.widget.observed
        def retained():
            value=observed();value['avatarInventory']['roots']=[dict(rootId=source.widget.root(),
                qmlSource='file:///app.bundle/qml/hifi/AvatarApp.qml',role='avatar',visible=False,enabled=False,
                attached=False,windowPresent=False,panels=dict(popup=False,favorite=False,settings=False,wearables=False))]
            return value
        source.widget.observed=retained;frame=self.f.source.read();self.assertEqual([],frame['ui']['controls'])
        with self.assertRaises(NativeUIError):self.measure()
    def test_original_defaultPal_periodic_timer_can_live_but_its_active_dispatch_cannot_be_ignored(self):
        f=self.f.fixture;row=f.prototypes['scripts']['source']['workers'][0]['uiWork']['timers'][0]
        self.assertEqual({},self.measure()['timers']['owned'][f.prototypes['scripts']['source']['workers'][0]['membership']['instance']])
        row.update(fired=1,entered=1,left=0,depth=1,pendingDispatch=1,lastFiredEpochMs=f.now(),lastCallbackEpochMs=f.now())
        self.f.source.read()
        with self.assertRaises(NativeUIError):self.measure()
        row.update(left=1,depth=0,pendingDispatch=0,lastDispatchEpochMs=f.now());self.f.source.read()
        self.assertEqual(0,self.measure()['endpointEpochMs']);self.assertIsNone(row['destroyedEpochMs'])


if __name__=='__main__':unittest.main()
