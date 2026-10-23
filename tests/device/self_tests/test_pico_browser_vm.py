"""Original VM/code/lifetime/chunk join; SDK, V8 and Qt producer DTOs are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_vm import PicoBrowserVm,reviewed
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_native_script_object_lifetimes import Boundary as Objects
from self_tests.test_native_script_observation import Boundary as Scripts,code_source
from self_tests.test_native_script_membership import membership_source,manager
from self_tests.test_chat_script_source import BINDING
from feature_journeys.scenarios import VERSION

RUN='b'*32;TICKET='c'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
SCRIPT=URL+'tickets/'+TICKET+'/client.js'


class Boundary:
    def __init__(self,root):
        self.objects=Objects();self.script=Scripts();self.stopped=False;self.edit=None;self.root=root
        self.objects.row.update(instance='a'*32,registeredEpochMs=14000,workerCreatedEpochMs=14900)
        self.script.engine.update(url=SCRIPT);self.script.engine['required'].update(sequence=0,modules=[])
        pins,raw=reviewed()
        def full(value):
            value.update(instance='a'*32,requestedEpochMs=self.objects.epoch,capturedEpochMs=self.objects.epoch)
            if self.stopped:value['source']['engines']=[]
            code_source(value,raw.decode('utf-8'))
            membership_source(value,[] if self.stopped else [manager(url=SCRIPT,epoch=14500)])
            value['source']['membership']['revision']=2 if self.stopped else 1
            value['source'].update(effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]),
                loadSourceVersion=1,loads=dict(complete=True,instance='d'*32,sequence=0,events=[]),compiledSourceVersion=1)
            for engine in value['source']['engines']:
                engine['compiled']=dict(compiledSourcesVersion=1,complete=True,compilations=[dict(scriptId=17,
                    resourceName=SCRIPT,**pins,compiledEpochMs=19000)])
            if self.edit:self.edit(value)
        self.script.mutate=full
        self.http=dict(browserFixtureVersion=1,instance='f'*32,ready=False,sequence=1,responses=[dict(sequence=1,responseId='e'*32,
            capturedEpochMs=14999,ticket=TICKET,resource='client.js',origin='primary',status=200,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())])
        self.lock=ScriptSourceLock(root/'script-sources.lock');self.store=PrivateFeatureState(root/'browser-primary-vm.json')
    def owner(self,role='primary'):
        scripts=self.script.reader();scripts.clock_ms=lambda:self.objects.epoch;scripts.monotonic=lambda:self.objects.host
        with self.lock.held():
            return PicoBrowserVm(RUN,URL,SCRIPT,role,BINDING,scripts,self.objects.reader(),
                self.store if role=='primary' else PrivateFeatureState(self.root/'browser-actor-vm.json'),self.lock,lambda:deepcopy(self.http))
    def count(self):return len(self.objects.calls)+len(self.script.commands)


class PicoBrowserVmTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.b=Boundary(self.root)
    def capture(self,owner):
        with self.b.lock.held():return owner.capture()
    def test_submitted_and_compiled_http_client_pins_original_vm_and_retained_qobjects_block_table_absence(self):
        owner=self.b.owner();self.assertEqual(dict(retired=False,running=True),self.capture(owner))
        self.b.stopped=True;self.assertEqual(dict(retired=False,running=False),self.capture(owner))
        for kind in ('manager','engine','worker'):
            self.b.objects.row[kind+'Alive']=False;self.b.objects.row[kind+'DestroyedEpochMs']=19999
            result=self.capture(owner)
            self.assertEqual(kind=='worker',result['retired'])
        cold=self.b.owner();self.assertEqual(dict(retired=True,running=False),self.capture(cold))
        self.assertEqual(6,len(cold.frames));self.assertEqual('a'*32,cold.origin['manager'])
    def test_independent_actor_has_separate_original_transactions_and_cold_restore_performs_no_query(self):
        primary=self.b.owner();self.capture(primary);count=self.b.count()
        cold=self.b.owner();self.assertEqual(count,self.b.count());self.assertEqual(primary.origin,cold.origin)
        actor=self.b.owner('actor');self.capture(actor)
        self.assertNotEqual(actor.store.path,primary.store.path);self.assertEqual(1,len(actor.frames));self.assertEqual(1,len(primary.frames))
        self.assertNotEqual(actor.frames[0]['scripts']['requestId'],primary.frames[0]['scripts']['requestId'])

    def test_same_json_tuple_or_subclass_cannot_change_cached_original_before_query(self):
        owner=self.b.owner();self.capture(owner);original=deepcopy(owner.frames[0]);count=self.b.count()
        with self.b.lock.held():
            copy=owner.frames;copy[0]['scripts']['source']['engines']=tuple(copy[0]['scripts']['source']['engines'])
            owner.verify();self.assertEqual(original,owner.frame(0))
            from adapters.chat_journey.source_chunks import json_digest
            with self.assertRaises((ValueError,RuntimeError)):json_digest(copy[0])
            class ForeignScope(dict):pass
            owner.scope=ForeignScope(owner.scope)
            with self.assertRaises((ValueError,RuntimeError)):owner.verify()
        self.assertEqual(count,self.b.count())
    def test_compilation_http_or_actual_lifetime_identity_cannot_be_substituted(self):
        for fault in ('code','http','lifetime'):
            with tempfile.TemporaryDirectory() as directory:
                b=Boundary(Path(directory));owner=b.owner()
                if fault=='code':b.edit=lambda value:value['source']['engines'][0]['compiled']['compilations'][0].update(sha256='f'*64)
                elif fault=='http':b.http['responses'][0]['sha256']='f'*64
                else:b.objects.row['instance']='e'*32
                with b.lock.held(),self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):owner.capture()
                self.assertEqual('reading',owner.store.read()['phase'])
                count=b.count()
                with self.assertRaises((ValueError,RuntimeError)):b.owner()
                self.assertEqual(count,b.count())
    def test_slow_or_native_jumping_original_intent_cas_cannot_issue_first_source_query(self):
        for native in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                b=Boundary(Path(directory));owner=b.owner();write=owner.store.write
                def late(value,previous):
                    write(value,previous)
                    if native:b.objects.epoch+=2000
                    else:b.objects.host+=2
                with b.lock.held(),patch.object(owner.store,'write',side_effect=late),self.subTest(native=native),self.assertRaises((ValueError,RuntimeError)):owner.capture()
                self.assertEqual(0,b.count());self.assertEqual('reading',owner.store.read()['phase'])
    def test_orphan_or_replaced_original_chunk_never_becomes_current_vm_proof(self):
        owner=self.b.owner();self.capture(owner);child=owner.chunks.store(0);raw=child.path.read_bytes()
        replacement=child.path.with_name('replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(child.path)
        with self.b.lock.held(),self.assertRaises((ValueError,RuntimeError)):owner.capture()
        count=self.b.count();owner.store.path.unlink()
        with self.assertRaises((ValueError,RuntimeError)):self.b.owner()
        self.assertEqual(count,self.b.count());self.assertEqual(raw,child.path.read_bytes())

    def test_changed_warm_original_frame_or_origin_refuses_before_next_native_query(self):
        for fault in ('frame','origin','quiet','scope'):
            with tempfile.TemporaryDirectory() as directory:
                b=Boundary(Path(directory));owner=b.owner()
                with b.lock.held():
                    owner.capture();owner.capture();count=b.count()
                    if fault=='frame':
                        from adapters.script_journey.history import canonical
                        changed=owner.frame(0);changed['hostMonotonic']+=.001
                        owner._frames=(canonical(changed),)+owner._frames[1:]
                    elif fault=='origin':owner.origin['manager']='f'*32
                    elif fault=='scope':owner.scope['binding']['sessionId']='foreign'
                    else:owner.windows.append(dict(first=0,last=1,afterEpochMs=1))
                    with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):owner.capture()
                    self.assertEqual(count,b.count());self.assertEqual('ready',owner.store.read()['phase'])

    def retired(self,b):
        b.stopped=True
        for kind in ('manager','engine','worker'):
            b.objects.row[kind+'Alive']=False;b.objects.row[kind+'DestroyedEpochMs']=19999

    def test_original_three_clock_quiet_is_retained_across_later_fresh_reads_and_cold_reconstruction(self):
        owner=self.b.owner();self.capture(owner);self.retired(self.b)
        with self.b.lock.held():
            for index in range(1,33):
                self.b.objects.host=index*.1;self.b.objects.epoch=20000+100*index
                owner.capture()
                if owner.quiet(20001):break
            self.assertEqual(1,len(owner.windows));window=deepcopy(owner.windows[0])
            self.b.objects.host+=10;self.b.objects.epoch+=10000;self.assertTrue(owner.capture()['retired'])
            self.assertTrue(owner.quiet(20001));self.assertEqual([window],owner.windows)
        cold=self.b.owner()
        with self.b.lock.held():self.assertTrue(cold.quiet(20001))
        self.assertEqual([window],cold.windows)

    def test_frozen_native_or_long_gap_cannot_create_vm_quiet_marker(self):
        for frozen in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                b=Boundary(Path(directory));owner=b.owner()
                with b.lock.held():
                    owner.capture();self.retired(b)
                    b.objects.host=.1;b.objects.epoch=20100;owner.capture();self.assertFalse(owner.quiet(20001))
                    b.objects.host+=.1 if frozen else .6
                    if not frozen:b.objects.epoch+=600
                    owner.capture()
                    with self.subTest(frozen=frozen),self.assertRaises((ValueError,RuntimeError)):owner.quiet(20001)
                    self.assertEqual([],owner.windows);self.assertEqual([],owner.store.read()['quiet'])

    def test_parent_and_original_facade_report_retained_objects_despite_empty_service_table(self):
        from self_tests.test_pico_tablet_web_feature import PicoTabletWebFeatureTests
        fixture=PicoTabletWebFeatureTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        flow=fixture.flow();flow.prepare();b=Boundary(fixture.root)
        def scripts(target,*,read_only):
            self.assertTrue(read_only);reader=b.script.reader()
            reader.clock_ms=lambda:b.objects.epoch;reader.monotonic=lambda:b.objects.host
            return reader
        def objects(target,*,source_lock):
            self.assertIs(flow.lock,source_lock);source_lock.assert_held();return b.objects.reader()
        fixture.original._script_execution_observer=scripts;fixture.original._script_object_lifetimes=objects
        request=flow.source.client.request
        flow.source.client.request=lambda path,*args,**kwargs:deepcopy(b.http) if path.endswith('/browser') else request(path,*args,**kwargs)
        with flow.lock.held():
            owner=flow.owner();owner['scriptUrl']=SCRIPT;flow.save(owner)
        value=flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(['script:tablet-web-client'],value['resources']);self.assertFalse(value['state']['open'])
        with flow.lock.held():
            cold=flow.adapter._tablet_web_vm(flow.selector,flow)
            self.assertEqual(1,len(cold.frames));self.assertEqual('primary',cold.scope['role'])
        b.stopped=True
        value=flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=value['sequence']))
        self.assertEqual(['script:tablet-web-client'],value['resources'])
        self.retired(b)
        value=flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=value['sequence']))
        self.assertEqual([],value['resources'])

    def test_actual_generic_cleanup_refuses_rootless_browser_chunks_and_preserves_originals(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native
        from adapters.pico4.script_journey import PicoScriptJourney
        from adapters.pico4.tablet_web_binding import retained
        fixture=native.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.navigation_setup();adapter=fixture.instance();target=fixture.fake.target
        journey=PicoScriptJourney(adapter);journey.state_area='tablet-web'
        self.assertFalse(retained(adapter,target));self.assertIsNone(journey.existing_state_path(target))
        directory=journey.state_path(target).parent;self.assertFalse(retained(adapter,target))
        chunk=directory/'pico-tablet-web-primary-vm.chunk-000000.json';chunk.write_bytes(b'original retained source');chunk.chmod(0o600)
        self.assertTrue(retained(adapter,target))
        with self.assertRaises((ValueError,RuntimeError)):adapter.cleanup(target)
        self.assertEqual(b'original retained source',chunk.read_bytes());self.assertFalse(fixture.fake.running)
        self.assertIn(('am','force-stop','org.overte.pico'),fixture.fake.events)
        chunk.unlink();directory.rmdir();directory.symlink_to(fixture.fixture.root,target_is_directory=True)
        with self.assertRaises((ValueError,RuntimeError)):retained(adapter,target)

    def test_actual_generic_cleanup_keeps_original_browser_capture_owner_without_parent_feature(self):
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native
        fixture=native.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.navigation_setup();adapter=fixture.instance();target=fixture.fake.target
        original=dict(original='uncertain-original-browser-native-image-and-receipt-owner')
        stores=[adapter._browser_world_render_store(target,role) for role in ('primary','actor')]
        for store in stores:store.write(original,None)
        with self.assertRaises((ValueError,RuntimeError)):adapter.cleanup(target)
        self.assertFalse(fixture.fake.running)
        for store in stores:self.assertEqual(original,store.read())


if __name__=='__main__':unittest.main()
