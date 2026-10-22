"""Actual Pico Emote wrapper with explicit native/Qt/OpenXR boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
import subprocess
import unittest
from unittest.mock import patch
import uuid
import test_normal_scripts as sources
from self_tests.test_native_feature_observation import probe_source
from self_tests.test_token_emote_ui import EmoteBoundary
from adapters.token_emote_ui import TokenEmoteUI,snapshot as validate_emote
from adapters.pico4.navigation import validate_snapshot


class PicoEmoteTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance,self.native=self.fixture.instance,self.fixture.native
        self.widget=EmoteBoundary();self.widget.instance=self.native.bridge_id;self.widget.generation=self.native.generation
        self.native.opened=True;self.before_input=None;self.fault=None;self.intents=[]
        original=self.widget.capture
        def capture():
            value=original();value['emoteControlsVersion']=2
            for row in value['controls']:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
            return value
        self.widget.capture=capture
        snapshot_original=self.native.snapshot;write_original=self.native.write_debug_app_file
        def snapshot():
            value=snapshot_original();actual=self.widget.capture()
            value.update(emoteControlsVersion=2,emoteSourceSequence=actual['scope']['sourceSequence'],
                controls=deepcopy(actual['controls']),elapsedMs=actual['scope']['elapsedMs'],
                lastCommandSequence=self.widget.command_sequence)
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            if self.fault=='missing':value.pop('emoteControlsVersion');value.pop('emoteSourceSequence')
            if self.fault=='version':value['emoteControlsVersion']=True
            return value
        self.snapshot=snapshot
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return write_original(target,package,path,raw)
            command=json.loads(raw)
            if self.before_input:self.before_input()
            actual=self.widget.capture();row=next(r for r in actual['controls'] if r['id']==command['controlId'])
            valid=(row['token']==command['controlToken'] and command['sequence']==self.widget.command_sequence+1
                and command['bridgeId']==self.widget.instance and command['generation']==self.widget.generation)
            self.native.inputs.append(deepcopy(command))
            if valid:
                if command['action']=='scroll':self.widget.scroll(command['controlId'],command['direction'],token=row['token'])
                else:self.widget.activate(command['controlId'],token=row['token'])
            self.native.sequence=self.widget.command_sequence
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=valid,error='' if valid else 'control-unavailable',processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        for boundary in (patch.object(self.native,'snapshot',side_effect=snapshot),
                         patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch('adapters.token_emote_ui.TokenEmoteUI',partial(TokenEmoteUI,
                             monotonic=lambda:self.widget.clock,sleep=self.widget.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.instance._emote_controls(self.native.target,self.intents.append)

    def test_real_wrapper_reaches_retained_chooser_and_all_ten_buttons_without_effect_verdicts(self):
        from adapters.token_emote_ui import NAMES
        self.flow.open()
        for name in NAMES:self.flow.play(name)
        self.assertTrue(self.widget.page);self.assertEqual('Love',self.widget.active)
        self.flow.cancel();self.flow.close()
        self.assertFalse(self.widget.page);self.assertEqual('',self.widget.active)
        self.assertIn('down',self.widget.actions)
        self.assertEqual(list(range(1,len(self.native.inputs)+1)),[r['sequence'] for r in self.native.inputs])
        self.assertTrue(all(set(row)<= {'controlId','action','sequence','instance','generation','direction','original'} for row in self.intents))
        self.assertFalse(any(c.startswith('feature.emotes.') for c in self.instance.capabilities(self.native.target)))

    def test_ignored_ordinary_entry_and_scroll_never_retry_the_same_input(self):
        self.widget.fault='ignored'
        with self.assertRaises(RuntimeError):self.flow.open()
        self.assertEqual(['emote.entry'],self.widget.actions)
        self.widget.fault=None;self.flow.open();self.widget.fault='ignored-scroll'
        count=len(self.native.inputs)
        with self.assertRaises(RuntimeError):self.flow.play('Love')
        self.assertEqual(count+1,len(self.native.inputs));self.assertEqual('',self.widget.active)

    def test_changed_original_token_or_page_cannot_be_recaptured_for_delivery(self):
        self.flow.open();reference=self.flow.capture();self.widget.active='Love'
        with self.assertRaises(RuntimeError):self.flow.io.activate('emote.play.Crying',reference=reference)
        self.assertEqual(1,len(self.native.inputs))
        self.before_input=lambda:setattr(self.widget,'generation',str(uuid.uuid4()))
        with self.assertRaises(RuntimeError):self.flow.play('Crying')
        self.assertNotIn('emote.play.Crying',self.widget.actions)

    def test_missing_boolean_version_foreign_candidate_and_unsafe_schema_fail_closed(self):
        for fault in ('missing','version'):
            self.fault=fault
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):self.flow.capture()
        self.fault=None;self.native.digest='f'*64
        with self.assertRaises(RuntimeError):self.flow.open()
        self.assertEqual([],self.native.inputs)

    def test_v1_shared_snapshot_stays_strict_and_version_downgrade_is_refused(self):
        value=self.widget.capture();validate_emote(value)
        value['emoteControlsVersion']=1
        with self.assertRaises(RuntimeError):validate_emote(value)
        self.flow.capture();self.fault='version'
        with self.assertRaises(RuntimeError):self.flow.capture()

    def test_native_pico_decoder_refuses_unknown_emote_state_and_reused_source_cursors(self):
        value=self.snapshot();validate_snapshot(value,123,self.native.epoch_milliseconds(self.native.target))
        value['controls'][0]['expected']=True
        with self.assertRaises(RuntimeError):validate_snapshot(value,123,self.native.epoch_milliseconds(self.native.target))
        self.flow.capture();original=self.widget.capture
        self.widget.capture=lambda:dict(original(),scope=self.flow.previous['scope'])
        with self.assertRaises(RuntimeError):self.flow.capture()

    def test_durable_source_factory_uses_existing_lock_candidate_and_actual_vr_binding(self):
        from adapters.pico4.emote_sources import PicoEmoteSources
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        before=len(self.native.inputs)
        with lock.held():
            owner=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            self.assertIsInstance(owner,PicoEmoteSources)
            self.assertEqual(self.native.bridge_id,owner.binding['sessionId']);self.assertEqual(123,owner.pid)
            self.assertEqual(lock,owner.lock);self.assertEqual([],owner.frames)
        self.assertEqual(before,len(self.native.inputs))
        foreign=ScriptSourceLock(seam.root/'foreign.lock')
        with foreign.held(),self.assertRaises(ValueError):
            self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,foreign)

    def test_source_transcript_survives_base_cleanup_and_prevents_success(self):
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            owner=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner.save();original=owner.store.read()
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertEqual(original,owner.store.read())

    def test_durable_inputs_factory_requires_original_primary_source_and_retains_ownership(self):
        from adapters.pico4.emote_inputs import PicoEmoteInputs
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            source=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner=self.instance._emote_inputs(self.native.target,source)
            self.assertIsInstance(owner,PicoEmoteInputs);self.assertIs(source,owner.source)
            effects=self.instance._emote_effects(self.native.target,owner)
            self.assertIs(effects.inputs,owner);self.assertIs(effects.source,source)
            owner.save();original=owner.store.read()
            actor=self.instance._emote_sources(self.native.target,seam.phase,'actor',seam.root,lock)
            with self.assertRaises(ValueError):self.instance._emote_inputs(self.native.target,actor)
            actor_effects=self.instance._emote_effects(self.native.target,owner,current_source=actor)
            self.assertIs(actor_effects.source,actor);self.assertIs(actor_effects.input_source,source)
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(original,owner.store.read())

    def test_actual_js_probe_polls_only_the_same_read_and_cancels_replaced_observation_timers(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=[],files=[],queue=new Map(),next=1,cleared=[];
const Script={setTimeout:(fn,ms)=>{if(ms!==50)throw Error("unexpected wait");const id=next++;queue.set(id,fn);return id;},
 clearTimeout:id=>{cleared.push(id);queue.delete(id);}};
const counts=new Map();
const Test={featureScriptWork:r=>{calls.push({...r});const n=(counts.get(r.commandId)||0)+1;counts.set(r.commandId,n);
 if(n===1)return {requestId:r.commandId,pending:true};
 return {schemaVersion:1,requestId:r.commandId,source:{actualTimerHandle:7}};},saveObject:(value,name)=>files.push({value,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-work-observe",managerInstance:"c".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||queue.size!==1||files.length!==0)throw Error("pending is not a completed observation");
let entry=[...queue.entries()][0];queue.delete(entry[0]);entry[1]();
if(calls.length!==2||files[0].value.source.actualTimerHandle!==7||files[0].name!=="feature-script-work.json")throw Error("original result");
for(const edit of [{expectedTimers:0},{code:"Script.clearTimeout(7)"},{managerInstance:["c".repeat(32)]},
 {managerInstance:"c".repeat(32)+"\n"},{commandId:["b".repeat(32)]},{schemaVersion:true}]){
 applyAndroidControlCommand({...request,commandId:"b".repeat(32),...edit});}
if(calls.length!==2)throw Error("expected results or foreign command admitted");
applyAndroidControlCommand({...request,commandId:"d".repeat(32)});
const old=[...queue.values()][0];
applyAndroidControlCommand({...request,commandId:"e".repeat(32)});
const before=calls.length;old();if(calls.length!==before||cleared.length!==1)throw Error("replaced read callback survived");
delete Test.featureScriptWork;applyAndroidControlCommand({...request,commandId:"f".repeat(32)});
if(files[1].value.available!==false)throw Error("missing native owner green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


    def test_actual_js_pending_deadline_never_synthesizes_zero_timers(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[],queue=[];
const Script={setTimeout:fn=>{queue.push(fn);return queue.length;},clearTimeout:()=>{}};
const Test={featureScriptWork:r=>{calls++;return {requestId:r.commandId,pending:true};},saveObject:value=>files.push(value)};
SOURCE
applyAndroidControlCommand({schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-work-observe",managerInstance:"c".repeat(32)});
while(queue.length){const fn=queue.shift();fn();}
if(calls!==51||files.length!==1||files[0].available!==false||"source" in files[0])throw Error("pending guessed empty work");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


    def test_actual_work_factory_is_read_only_and_candidate_bound(self):
        from self_tests.test_native_script_work import WorkBoundary, MANAGER
        source=WorkBoundary()
        epoch=self.native.epoch_milliseconds(self.native.target)
        source.epoch=epoch
        native_send=source.send
        def send(target,identity,description,command):
            self.assertEqual(self.native.target,target);self.assertEqual('123:synthetic-start',identity)
            source.epoch=self.native.epoch_milliseconds(target)
            native_send(command);source.value['processId']=123
        original_read=self.native.read_debug_app_file
        def original(target,package,path,**options):
            if path != 'files/overte-e2e/feature-script-work.json':return original_read(target,package,path,**options)
            self.assertEqual('org.overte.pico',package)
            self.assertEqual('files/overte-e2e/feature-script-work.json',path)
            self.assertEqual({'attempts':1},options);return source.original()
        with patch.object(self.instance,'write_control_command',side_effect=send), patch.object(self.native,'read_debug_app_file',side_effect=original,create=True):
            reader=self.instance._script_work(self.native.target);value=reader.read(MANAGER)
            self.assertEqual(source.value,value);self.assertEqual([],self.native.inputs)
            bad=deepcopy(source.commands[-1]);bad['expectedTimers']=0
            with self.assertRaises(RuntimeError):reader.send(bad)
            self.assertEqual(1,len(source.commands))


    def test_actual_avatar_factory_preserves_originals_and_refuses_changed_candidate(self):
        from self_tests.test_native_avatar_render import Boundary
        source=Boundary();native_send=source.send
        def send(target,identity,description,command):
            self.assertEqual(self.native.target,target);self.assertEqual('123:synthetic-start',identity)
            source.epoch=self.native.epoch_milliseconds(target)
            native_send(command);source.sample['processId']=123
        original_read=self.native.read_debug_app_file
        def original(target,package,path,**options):
            if path!='files/overte-e2e/feature-avatar-render.json':return original_read(target,package,path,**options)
            self.assertEqual('org.overte.pico',package);self.assertEqual({'attempts':1},options)
            return source.original()
        with patch.object(self.instance,'write_control_command',side_effect=send),patch.object(self.native,'read_debug_app_file',side_effect=original):
            reader=self.instance._avatar_render_observer(self.native.target);value=reader.read()
            self.assertEqual(source.sample,value);self.assertEqual([],self.native.inputs)
            before=len(source.commands)
            changed={**self.instance._installation(self.native.target),'artifactSha256':'f'*64}
            with patch.object(self.instance,'_installation',return_value=changed),self.assertRaises(RuntimeError):reader.read()
            self.assertEqual(before,len(source.commands));self.assertEqual(value,reader.last)

    def test_actual_stereo_model_factory_uses_original_private_capture_and_candidate_guards(self):
        from self_tests.test_pico_emote_model_draws import ModelBoundary
        source=ModelBoundary(self.native.epoch_milliseconds(self.native.target));source.capture['processId']=123;native_send=source.send
        def send(target,identity,description,command):
            self.assertEqual(self.native.target,target);self.assertEqual('123:synthetic-start',identity)
            source.epoch=self.native.epoch_milliseconds(target)
            native_send(command)
        original_read=self.native.read_debug_app_file
        def original(target,package,path,**options):
            if path!='files/overte-e2e/feature-pico-world-model-draws.json':return original_read(target,package,path,**options)
            self.assertEqual('org.overte.pico',package);self.assertEqual({'attempts':1},options)
            return source.original()
        with patch.object(self.instance,'write_control_command',side_effect=send),patch.object(self.native,'read_debug_app_file',side_effect=original):
            reader=self.instance._emote_model_draws_observer(self.native.target);value=reader.read(source.capture)
            self.assertEqual(source.sample,value);self.assertEqual([],self.native.inputs)
            count=len(source.commands);changed={**self.instance._installation(self.native.target),'artifactSha256':'f'*64}
            with patch.object(self.instance,'_installation',return_value=changed),self.assertRaises(RuntimeError):reader.read(source.capture)
            self.assertEqual(count,len(source.commands));self.assertEqual(value,reader.last)

    def test_orphaned_lifetime_journal_remains_owned_after_base_cleanup(self):
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            source=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner=self.instance._emote_lifetime(self.native.target,source)
            self.assertEqual(self.instance._emote_lifetime_store(self.native.target,'primary').path,owner.store.path)
            owner.save();original=owner.store.read();self.assertIsNone(source.store.read())
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(original,owner.store.read())

    def test_background_factory_can_reopen_private_scope_without_foreground_native_repair(self):
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held(),patch.object(self.instance,'_script_runtime',side_effect=AssertionError('No native UI construction')):
            owner=self.instance._emote_background(self.native.target,seam.phase,seam.root,lock)
            self.assertEqual(self.instance._emote_background_store(self.native.target).path,owner.store.path)
            owner.store.write({'syntheticUnresolvedOwnership':True},None);original=owner.store.read()
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(original,owner.store.read())

    def test_emote_capture_factory_shares_exact_parent_lock_and_excludes_other_capture_owners(self):
        from adapters.pico4.graphics_binding import PicoGraphicsBinding,SerializedWorldCapture
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            source=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner=self.instance._emote_world_render_capture(self.native.target,source)
            self.assertIsInstance(owner,SerializedWorldCapture);self.assertIs(owner.source_lock,lock)
            self.assertEqual(source.binding,owner.owner.binding);self.assertEqual('primary',owner.owner.role)
            self.assertTrue(owner.capture.require_cameras);self.assertTrue(owner.capture.stereo);owner.owner.guard()
            facade=PicoGraphicsBinding(self.instance)
            stores=[self.instance._world_render_store(self.native.target),
                self.instance._emote_world_render_store(self.native.target,'actor')]
            stores.extend(facade.world_render_store(self.native.target,role=role) for role in ('primary','actor'))
            for store in stores:
                store.write({'unresolvedForeignCapture':True},None)
                with self.assertRaises((RuntimeError,ValueError)):owner.owner.guard()
                store.discard(store.read())
            owner.owner.guard()
            changed={**self.instance._installation(self.native.target),'artifactSha256':'f'*64}
            with patch.object(self.instance,'_installation',return_value=changed),self.assertRaises((RuntimeError,ValueError)):owner.owner.guard()
        self.assertEqual([],self.native.inputs)

    def test_orphaned_emote_image_and_world_journals_prevent_base_cleanup_success(self):
        from adapters.normal_feature_state import PrivateFeatureState
        source=self.instance._emote_source_store(self.native.target,'primary')
        image=PrivateFeatureState(source.path.with_name(source.path.stem+'-image-7.json'))
        world=self.instance._emote_world_render_store(self.native.target,'primary')
        for store in (image,world):store.write({'unresolvedEmoteCapture':True},None)
        originals=[store.read() for store in (image,world)]
        self.assertIsNone(source.read())
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertEqual(originals,[store.read() for store in (image,world)])

    def test_actual_view_menu_factory_uses_bound_native_tokens_and_normal_pico_input_once(self):
        from adapters.pico4.normal_view_menu import PicoViewMenu
        self.native.opened=True;original_snapshot=self.native.snapshot;original_write=self.native.write_debug_app_file
        menu=str(uuid.uuid4());token=str(uuid.uuid4());checked=[False]
        def snapshot():
            value=original_snapshot();value['viewMenuControlsVersion']=1
            value['controls'].append(dict(id='view-menu.third',token=token,menuInstance=menu,checked=checked[0],
                enabled=True,focused=False,inputReady=True));return value
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command.get('controlId')!='view-menu.third':return original_write(target,package,path,raw)
            self.assertEqual(1,len(self.intents));self.assertEqual(token,command['controlToken'])
            self.assertEqual('activate',command['action']);self.native.inputs.append(deepcopy(command))
            self.native.sequence=command['sequence'];checked[0]=True
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=self.native.epoch_milliseconds(target))
        with patch.object(self.native,'snapshot',side_effect=snapshot),patch.object(self.native,'write_debug_app_file',side_effect=write):
            flow=self.instance._view_menu_controls(self.native.target,self.intents.append);self.assertIsInstance(flow,PicoViewMenu)
            before=flow.capture();flow.activate('view-menu.third',before);self.assertTrue(flow.capture()['controls'][0]['checked'])
            self.assertEqual(1,len(self.native.inputs))
            with self.assertRaises(RuntimeError):flow.activate('view-menu.third',before)
            self.assertEqual(1,len(self.native.inputs));self.native.digest='f'*64
            with self.assertRaises((RuntimeError,ValueError)):flow.capture()

    def test_actual_emote_view_factory_keeps_exact_parent_lock_and_original_candidate_binding(self):
        from adapters.pico4.emote_view import PicoEmoteView
        from self_tests import test_pico_emote_sources as phase_fixture
        original=phase_fixture.SourcesTests();original.setUp();self.addCleanup(original.doCleanups)
        lock=self.instance._script_journey()._lock(self.native.target)
        with lock.held():
            owner=self.instance._emote_view(self.native.target,original.phase,lock)
            self.assertIsInstance(owner,PicoEmoteView);self.assertIs(lock,owner.lock)
            self.assertEqual(self.instance._emote_view_store(self.native.target).path,owner.store.path)
            self.assertEqual(self.instance._script_runtime(self.native.target)[2],owner.binding)
            self.assertEqual(123,owner.pid);self.assertEqual([],self.native.inputs)
            self.native.digest='f'*64
            with self.assertRaises((RuntimeError,ValueError)):owner.prepare()
            self.assertEqual([],self.native.inputs)

    def test_unresolved_emote_view_mode_cannot_be_discarded_by_base_process_cleanup(self):
        store=self.instance._emote_view_store(self.native.target);value={'unresolvedOriginalView':True}
        store.write(value,None)
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(value,store.read())


if __name__=='__main__':unittest.main()
