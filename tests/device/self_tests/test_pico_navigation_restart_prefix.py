"""Original twelve-action host composition; Qt/VM/kernel/SDK are explicit models.

First eleven actions, real TLS replies, PNG files and owned Session execute.
The one ordinary Stop/Launch SDK boundary consumes its own durable original
intent. New modeled producers read actual modeled product persistence; no old
frame or requested world/bookmark is installed as the new source packet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.native_navigation_directory import NativeNavigationDirectory
from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.native_navigation_modals import NativeNavigationModals
from adapters.native_navigation_panels import NativeNavigationPanels
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.navigation_arrival import NavigationArrival
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.navigation_continuation import NavigationContinuation
from adapters.pico4.navigation_generation import history
from adapters.pico4.navigation_history import NavigationHistory
from adapters.pico4.navigation_originals import read_original
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource
from adapters.pico4.navigation_restart import NavigationRestart
from adapters.pico4.navigation_restart_input import issue_once
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.restart_inputs import validate_native_restart
from adapters.token_places_ui import TokenPlacesUI,sha
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from self_tests import test_native_feature_observation as features
from self_tests import test_native_process_presence as presence
from self_tests import test_navigation_arrival as arrival
from self_tests import test_navigation_directory as directory
from self_tests import test_pico_navigation_bookmark_prefix as bookmark
from self_tests import test_pico_navigation_prefix as prefix


class Model(bookmark.Model):
    """Persist only actual consumed normal model changes, never a plan state."""
    def __init__(self,root):
        self.bridge=str(uuid.uuid4());self.generation=str(uuid.uuid4())
        super().__init__(root);self.births={key:uuid.uuid4().hex for key in ('environment','settings','directory','bookmarks','panels','modals','replies')}
    def persist(self):
        # Startup reads the actual preceding backing file without rewriting its
        # physical identity. Later ordinary bookmark controls use normal persist.
        if self.disk.exists() and not hasattr(self,'native_sequence'):
            self.map=json.loads(self.disk.read_text());return
        return super().persist()
    def send(self,command):
        result=super().send(command)
        value=dict(selected=self.selected,effective=self.effective,position=self.owner_test.world.position)
        store=PrivateFeatureState(self.root/'synthetic-product-navigation-startup.json');store.write(value,store.read())
        return result
    def source_send(self,request):
        super().source_send(request)
        self.packet.update(processId=prefix.PID,instance=self.births['environment'])
        self.packet['settings']['instance']=self.births['settings']
    def source_read(self,request):
        super().source_read(request);self.source_packet['instance']=self.births['directory']
    def native_send(self,request):
        super().native_send(request);self.native_packet['instance']=self.births['bookmarks']
    def private(self,request,kind):
        super().private(request,kind);self.native_packets[kind].update(instance=self.births[kind],processId=prefix.PID)


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationRestartPrefixTests(unittest.TestCase):
    model_type=Model
    process_start='10001'
    setUpClass=classmethod(prefix.NavigationPrefixTests.setUpClass.__func__)
    tearDownClass=classmethod(prefix.NavigationPrefixTests.tearDownClass.__func__)
    setUp=prefix.NavigationPrefixTests.setUp
    make=bookmark.NavigationBookmarkPrefixTests.make
    write=prefix.NavigationPrefixTests.write
    read=prefix.NavigationPrefixTests.read
    installed=prefix.NavigationPrefixTests.installed
    activate=bookmark.NavigationBookmarkPrefixTests.activate

    def target_fingerprint(self):
        return hashlib.sha256(('owned-model\0'+str(('owned-layer',self.root))).encode()).hexdigest()

    def twelve_call(self):
        ticket=uuid.uuid4().hex;self.server.journal.activate(prefix.RUN,ticket,'restart-app',{});self.model.provider.activate(prefix.RUN,ticket)
        return dict(contractVersion=CONTRACT_VERSION,runId=prefix.RUN,fixtureUrl=self.url+'/feature-fixture/v1/runs/'+prefix.RUN+'/',ticket=ticket,verb='restart-app',inputs={})

    def first_eleven(self):
        self.flow.prepare();self.flow.observe();self.actor=self.make('actor');self.actor.observe()
        for verb in prefix.VERBS:
            self.flow.act(self.activate(verb));self.flow.observe();self.actor.observe()
        self.original_parent=self.flow;self.original_actor=self.actor;self.original_model=self.model
        self.original_prefix=self.flow.store.path.read_bytes();self.original_ui=read_original(self.flow.source.normal.io.original.navigation.path)
        self.original_native=self.flow.transit().transit.stereo_factory(self.flow.transit().state['ticket']).native_factory()
        self.running=True;self.sdk_calls=[];self.new_model=None;self.current_identity=self.binding['processIdentity']
        self.scope_configuration=('owned-layer',self.root)
        # The real fingerprint was bound before the first ordinary input.

    def launch_receiver(self):
        old=self.original_model;state=PrivateFeatureState(self.root/'synthetic-product-navigation-startup.json').read()
        self.new_model=Model(self.root);m=self.new_model;m.clock=old.clock;m.owner_test=self;m.network=self.url
        m.selected=state['selected'];m.effective=state['effective'];m.acct['observation']['endpointSha256']=sha(m.effective)
        m.login=False;m.shown=False;m.page=False
        self.new_world=arrival.Model(run=prefix.RUN);self.new_world.temporary._finalizer.detach()
        self.new_world.close=lambda:None
        print('Retained original Navigation generation-1 world fixture:',self.new_world.root,flush=True)
        self.new_world.position=state['position'];self.new_world.epoch=m.epoch;self.new_world.guard=m.guard
        subject_birth=uuid.uuid4().hex
        self.new_world.subject.edit=lambda value:value.update(processId=32,instance=subject_birth)
        self.new_native=features.Boundary();self.native_birth=uuid.uuid4().hex
        def source(value):
            # Boundary.send has just constructed this new original DTO. Its
            # nested fence/animation clocks must be that producer's actual
            # publication epoch too, rather than Boundary's default 20000.
            bookmark.first_transit.new_source_clock(value,m.epoch())
            value.update(processId=32,instance=self.native_birth,
                lifecycle=dict(backgrounds=self.old_packet['lifecycle']['backgrounds'],activations=self.old_packet['lifecycle']['activations']+1,
                    launches=self.old_packet['lifecycle']['launches']+1))
            PrivateFeatureState(self.root/f'navigation-prefix-generation-1-native-original-{value["sequence"]:03d}.json').write(value,None)
        self.new_native.mutate=source
        self.kernel=presence.Boundary(pid=32,epoch_ms=m.epoch);self.kernel.presence='absent'
        def kernel(value):
            value.update(instance=self.native_birth)
            PrivateFeatureState(self.root/f'navigation-prefix-generation-1-kernel-original-{value["sequence"]:03d}.json').write(value,None)
        self.kernel.edit=kernel
        self.running=True;self.current_identity='32:10002'

    def native_reader(self):
        m=self.new_model
        return NativeFeatureObservation(self.new_native.send,self.new_native.original,m.epoch,m.guard,32,monotonic=lambda:m.clock,sleep=m.sleep)

    def successor(self,inputs,state,*,parent=None):
        need(self.new_model is not None and self.running and self.current_identity=='32:10002')
        m=self.new_model;binding=deepcopy(self.binding);binding.update(processIdentity=self.current_identity,sessionId=m.bridge)
        # One new host context per role. The old process/bridge file is retained.
        original=self.original_parent if parent is None else parent
        def write(_target,_package,path,raw):raise AssertionError('No normal UI input belongs to restart-app')
        def read(_target,_package,path,**_kwargs):
            need(path.endswith('observation.json'));return json.dumps(m.raw())
        adb=SimpleNamespace(write_debug_app_file=write,read_debug_app_file=read,epoch_milliseconds=lambda _target:m.epoch(),foreground_package=lambda _target:'org.overte.pico')
        adapter=SimpleNamespace(adb=adb,require_same_process=lambda *_args:m.guard(),require_pico_session_identity=lambda _target:self.current_identity,
            _installation=lambda _target:True,probe_retry_policy=lambda:(1,0),require=lambda _target:True,pico_input_session=lambda _target:self.session)
        transport=NativeNavigationIO(adapter,'owned-model',self.current_identity,lambda _operation:need(False))
        navigation=PicoNavigation(transport,self.root/('navigation-prefix-generation-1-'+original.role+'-ui.json'),
            dict(schemaVersion=1,sourceRevision=binding['sourceRevision'],artifactSha256=binding['artifactSha256'],installedCandidateVerified=True),
            self.current_identity,prefix.INPUTS['sceneUrl'],monotonic=lambda:m.clock,sleep=m.sleep)
        ordinary=PicoScriptIO(navigation);ui=TokenPlacesUI(PicoPlacesIO(ordinary),lambda _value:need(False),prefix.RUN,monotonic=lambda:m.clock,sleep=m.sleep)
        def reader(cls,send,raw):return cls(send,raw,m.epoch,m.guard,32,monotonic=lambda:m.clock,sleep=m.sleep)
        storage=reader(NativeLocationBookmarks,m.native_send,lambda:json.dumps(m.native_packet))
        panels=reader(NativeNavigationPanels,lambda value:m.private(value,'panels'),lambda:json.dumps(m.native_packets['panels']))
        modals=reader(NativeNavigationModals,lambda value:m.private(value,'modals'),lambda:json.dumps(m.native_packets['modals']))
        environment=reader(NativeNavigationEnvironment,m.source_send,lambda:json.dumps(m.packet))
        roots=reader(NativeNavigationDirectory,m.source_read,lambda:json.dumps(m.source_packet))
        m.modal.replies.edit=lambda value:value.update(instance=m.births['replies'],processId=32)
        replies=reader(NativeNavigationReplies,m.modal.replies.send,m.modal.replies.original)
        w=self.new_world
        def subject_send(request):w.update_subject();w.subject.send(request)
        subject=NativeGraphicsSubject(subject_send,w.subject.original,m.epoch,m.guard,32,require_framework=True,monotonic=lambda:m.clock,sleep=m.sleep)
        def probe(after):value=w.probe(after);value['nativeMotion']['processId']=32;return value
        pose=NavigationArrival(probe,subject,m.epoch,m.guard,prefix.RUN,binding,prefix.INPUTS['sceneUrl'],monotonic=lambda:m.clock)
        result=NavigationPrefixSource(ui,pose,storage,panels,environment,modals,roots,original.source.status,prefix.RUN,binding,prefix.INPUTS,
            original.source.provider_instance,self.url,directory.PROFILE,m.epoch,m.guard,replies=replies)
        return dict(source=result,native=self.native_reader(),presence=self.kernel.reader(),session=self.session)

    def bind_restart(self,parent=None):
        parent=self.original_parent if parent is None else parent
        def outside(plan):
            if plan is not None and plan['phase']==getattr(self,'advance_at',None):
                self.advance_at=None;self.activate('open')
            return True
        def stopped():return dict(running=self.running,identity=self.current_identity if self.running else None)
        holder={}
        def shell(target,*arguments):
            need(target=='owned-model');owner=holder['owner'];self.sdk_calls.append(arguments)
            if arguments==('am','force-stop','org.overte.pico'):
                need(owner.inputs.read()['phase']=='stop-issued')
                if getattr(self,'ignore_stop',False):return
                self.running=False;self.original_model.alive=False
                if getattr(self,'replace_header',False):
                    path=parent.store.path;raw=path.read_bytes();temporary=path.with_name('synthetic-header-replacement.json')
                    temporary.write_bytes(raw);temporary.chmod(0o600);os.replace(temporary,path)
                    self.assertEqual(raw,path.read_bytes())
                if getattr(self,'lose_stop',False):raise NativeUIError('Synthetic applied Stop response lost')
            else:
                need(arguments==('am','start','-W','-n','org.overte.pico/.E2eLauncherActivity')
                    and owner.inputs.read()['phase']=='launch-issued' and not self.running and not self.session.state_path.exists())
                self.old_packet=deepcopy(owner.state['oldNative']);self.launch_receiver()
                self.pid_patch=patch.object(prefix,'PID',32);self.pid_patch.start();self.addCleanup(self.pid_patch.stop)
                if getattr(self,'lose_launch',False):raise NativeUIError('Synthetic applied Launch response lost')
        installed=dict(sourceRevision=parent.binding['sourceRevision'],artifactSha256=parent.binding['artifactSha256'])
        adapter=SimpleNamespace(pico_configuration=self.scope_configuration,require=lambda _target:True,
            _installation=lambda _target:deepcopy(installed),require_controlled_debug_identity=lambda _target:self.current_identity,
            require_pico_session_identity=lambda _target:self.session.bound_process_identity(),
            require_same_process=lambda _target,identity,_why:need(self.running and identity==self.current_identity),
            adb=SimpleNamespace(shell=shell,foreground_package=lambda _target:'org.overte.pico'),
            profile={},debug_launcher_arguments=lambda _target:(),pico_input_session=lambda _target:self.session)
        def stop(_fence):return issue_once(adapter,'owned-model','app.stop',holder['owner'])
        def launch(_fence):return issue_once(adapter,'owned-model','app.launch',holder['owner'])
        def rebind(inputs,authority):
            need(inputs.read()['phase']=='launch-issued' and self.session.is_unbound());before=authority()
            actual=self.native_reader().read(0);validate_native_restart(inputs.read()['oldNative'],dict(pid=actual['processId'],instance=actual['instance'],lifecycle=actual['lifecycle']))
            exited=self.kernel.reader().require_absent(31);need(exited['instance']==actual['instance'] and authority()==before)
            self.session.begin(self.current_identity)
        def factory(original):
            need(original.lock is self.lock and original.scope()==parent.scope())
            store=PrivateFeatureState(self.root/'navigation-prefix-restart.json')
            owner=NavigationRestart(original,store,None if store.read() is not None else self.original_native,
                outside_guard=outside,stop=stop,stopped=stopped,launch=launch,rebind=rebind,
                successor=lambda inputs,state:self.successor(inputs,state,parent=original))
            holder['owner']=owner;return owner
        return NavigationContinuation(parent,factory),factory

    def cold(self,factory):
        parent=self.original_parent
        with self.lock.held():
            original=history(self.root,prefix.RUN,parent.phase,self.lock,role='primary',status=parent.source.status,
                provider_instance=parent.source.provider_instance,inputs=parent.source.inputs,origin=self.url,profile=parent.source.profile)
            return NavigationContinuation(original,factory)

    def test_continuous_twelve_original_owner_forest_once_sdk_restart_and_new_process_sources(self):
        self.first_eleven();parent=self.original_parent
        flow,factory=self.bind_restart();actor=NavigationContinuation(self.original_actor,factory);call=self.twelve_call()
        try:
            flow.act(call);actual=flow.observe()
            peer=actor.observe();self.assertEqual(actual['state'],peer['state'])
            self.assertEqual(actual['sequence'],peer['sequence'])
        except Exception as error:
            if error.__context__ is not None:traceback.print_exception(error.__context__)
            raise
        self.assertEqual('A',actual['state']['location']);self.assertFalse(actual['state']['panel']);self.assertFalse(actual['fullNavigationRecipe'])
        self.assertEqual(2,len(self.sdk_calls));self.assertEqual(self.original_prefix,parent.store.path.read_bytes())
        self.assertEqual(self.original_ui,read_original(parent.source.normal.io.original.navigation.path))
        self.assertEqual(11,len(parent.state['completed']));self.assertEqual('ready',flow.continuation_disk['phase'])
        owner=flow.restart();self.assertEqual('observed',owner.inputs.read()['phase']);self.assertNotEqual(owner.state['session']['sessionNonce'],owner.state['newSession']['sessionNonce'])
        self.assertEqual(1,owner.state['newSession']['nextSequence']);self.assertEqual([],self.xr.envelopes[9:])
        with self.lock.held():
            historical=history(self.root,prefix.RUN,parent.phase,self.lock,role='primary',status=parent.source.status,
                provider_instance=parent.source.provider_instance,inputs=parent.source.inputs,origin=self.url,profile=parent.source.profile)
            self.assertIsInstance(historical,NavigationHistory);self.assertEqual(parent.disk,historical.disk)
        self.assertEqual(2,len(self.sdk_calls));self.assertFalse(self.original_model.alive)

    def test_cold_lost_applied_stop_keeps_original_lineage_without_second_stop(self):
        self.first_eleven();flow,factory=self.bind_restart();call=self.twelve_call();self.lose_stop=True
        with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual(1,len(self.sdk_calls));self.assertFalse(self.running)
        self.assertEqual('stop-issued',flow.restart().inputs.read()['phase'])
        self.lose_stop=False;cold=self.cold(factory);cold.act(call);actual=cold.observe()
        self.assertEqual(2,len(self.sdk_calls));self.assertEqual('A',actual['state']['location'])
        self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())
        self.assertEqual('observed',cold.restart().inputs.read()['phase'])

    def test_cold_lost_applied_launch_reads_new_process_and_never_launches_again(self):
        self.first_eleven();flow,factory=self.bind_restart();call=self.twelve_call();self.lose_launch=True
        with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual(2,len(self.sdk_calls));self.assertTrue(self.running);self.assertTrue(self.session.is_unbound())
        self.assertEqual('launch-issued',flow.restart().inputs.read()['phase'])
        self.lose_launch=False;cold=self.cold(factory);cold.act(call);actual=cold.observe()
        self.assertEqual(2,len(self.sdk_calls));self.assertEqual('A',actual['state']['location'])
        self.assertEqual(1,cold.restart().state['newSession']['nextSequence'])

    def test_ignored_stop_and_cold_read_preserve_issued_intent_without_launch_or_repeat(self):
        self.first_eleven();flow,factory=self.bind_restart();call=self.twelve_call();self.ignore_stop=True
        with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual(1,len(self.sdk_calls));self.assertTrue(self.running)
        before=flow.restart().inputs.store.path.read_bytes();cold=self.cold(factory)
        with self.assertRaises(NativeUIError):cold.act(call)
        self.assertEqual(1,len(self.sdk_calls));self.assertEqual(before,cold.restart().inputs.store.path.read_bytes())
        self.assertEqual('stop-issued',cold.restart().inputs.read()['phase'])

    def test_final_phase_after_launch_intent_blocks_actual_launch_and_keeps_old_session(self):
        self.first_eleven();flow,_factory=self.bind_restart();call=self.twelve_call();self.advance_at='launch-issued'
        original=self.session.state_path.read_bytes()
        with self.assertRaises(NativeUIError):flow.act(call)
        self.assertEqual(1,len(self.sdk_calls));self.assertFalse(self.running)
        self.assertEqual('launch-issued',flow.restart().inputs.read()['phase'])
        self.assertEqual(original,self.session.state_path.read_bytes());self.assertIsNone(self.new_model)

    def test_same_bytes_replacement_old_header_refuses_launch_and_cold_before_new_runtime(self):
        self.first_eleven();flow,factory=self.bind_restart();call=self.twelve_call();self.replace_header=True
        before=read_original(self.original_parent.store.path)
        with self.assertRaises(NativeUIError):flow.act(call)
        after=read_original(self.original_parent.store.path);self.assertEqual(before['sha256'],after['sha256'])
        self.assertNotEqual(before['signature'],after['signature']);self.assertEqual(1,len(self.sdk_calls));self.assertIsNone(self.new_model)
        with self.assertRaises(NativeUIError):self.cold(factory)
        self.assertEqual(1,len(self.sdk_calls))

    def test_actual_private_cold_factory_uses_original_history_before_live_qt_and_refuses_foreign_target(self):
        self.first_eleven();flow,_factory=self.bind_restart();flow.act(self.twelve_call())
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        from test_normal_scripts import PicoNormalScriptsTests
        h=PicoNormalScriptsTests();h.setUp();self.addCleanup(h.doCleanups)
        parent=self.original_parent
        def lock(_target,value):self.assertIs(value,self.lock);return self.lock
        # Use the actual private factory with this fixture's already-owned
        # target/layer/root scope. No candidate/Qt/native observation is
        # acquired from h's separate SDK model during historical admission.
        with patch.object(h.instance,'pico_configuration',self.scope_configuration),\
             patch.object(h.instance,'_script_journey',return_value=SimpleNamespace(_lock=lock)),\
             patch.object(h.instance,'_scripts',side_effect=AssertionError('Live Qt before historical admission')) as scripts,\
             patch.object(h.instance,'_native_feature_observer',side_effect=AssertionError('Native SDK before historical admission')) as native,\
             patch.object(h.instance,'_installation',side_effect=AssertionError('Candidate SDK before historical admission')) as candidate,\
             self.lock.held():
            def make(target):
                return h.instance._navigation_prefix(target,prefix.RUN,parent.phase,parent.source.status,
                    parent.source.provider_instance,parent.source.inputs,self.url,parent.source.profile,source_lock=self.lock)
            actual=make('owned-model');self.assertIsInstance(actual.prefix,NavigationHistory)
            self.assertEqual(parent.disk,actual.prefix.disk);self.assertEqual(parent.binding,actual.prefix.binding)
            with self.assertRaises(ValueError):make('foreign-model-target')
            scripts.assert_not_called();native.assert_not_called();candidate.assert_not_called()
        self.assertEqual(2,len(self.sdk_calls))

    def test_late_foreign_successor_binding_refuses_publication_and_retains_original_frame(self):
        self.first_eleven();flow,_factory=self.bind_restart();flow.act(self.twelve_call());owner=flow.restart()
        original=owner.successor;seen=[]
        def changed(inputs,state):
            result=original(inputs,state);source=result['source'];guard=source.guard;capture=source.capture;done=[]
            def frame(*args,**kwargs):
                value=capture(*args,**kwargs);done.append(True);return value
            def final_guard():
                result=guard()
                if done:source.binding['targetFingerprint']='e'*64;seen.append(True)
                return result
            source.capture=frame;source.guard=final_guard;return result
        owner.successor=changed
        with self.assertRaises(NativeUIError):flow.observe()
        self.assertTrue(seen);self.assertEqual(2,len(self.sdk_calls))
        store=PrivateFeatureState(self.root/'navigation-prefix-generation-1-primary-sources.json')
        value=store.read();self.assertEqual(1,len(value['chunks']))
        self.assertEqual(owner.state['proof']['input']['newBinding'],value['scope']['binding'])
        self.assertTrue(store.path.with_name(store.path.name+'.frame-000.json').is_file())
        self.assertEqual(self.original_prefix,self.original_parent.store.path.read_bytes())


if __name__=='__main__':unittest.main()
