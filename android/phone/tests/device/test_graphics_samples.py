"""Durable actual host files with synthetic native sources; no product/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner,OwnedWorldRenderCapture
from adapters.world_render_evidence import NativeWorldRenderCapture,image_name
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles
from feature_journeys.witness import Client
from overte_phone_graphics import PhoneGraphicsIO
from overte_phone_graphics_samples import PhoneGraphicsSamples
from overte_phone_script_files import PhoneScriptFileIO
from overte_phone_script_history import unpack,pack
from overte_phone_script_lock import PhoneScriptSourceLock
from self_tests.test_world_render_receipt_inventory import Boundary as ReceiptBoundary
from self_tests.test_world_render_storage import Boundary as StorageBoundary
from test_graphics_images import BINDING
from test_graphics_measurements import Sources,RUN,TICKET,POLICY,original_image


class Originals:
    """No expected feature flags or action results enter this synthetic boundary."""
    def __init__(self,root):
        self.root,self.scene=root,Sources();self.clock=0.;self.okay=True;self.binding=deepcopy(BINDING)
        self.calls=[];self.counters={key:0 for key in ('native','subject','graphics','tablet','capture')}
        self.values={};self.fault=None;self.readers=[];self.fail_runtime=False;self.active_role='primary'
        self.storage=StorageBoundary();self.storage.raw=self.scene.pixels
        self.storage.mutate=lambda packet:packet.update(instance='a'*32)
        self.receipt_root=root/'native-receipts';self.receipt_root.mkdir(mode=0o700)
        self.inventory=ReceiptBoundary(self.receipt_root)
        for path in self.receipt_root.iterdir():path.unlink()
        self.inventory.issued.clear();self.inventory.mutate=lambda packet:packet.update(instance='a'*32)
        self.client=object.__new__(Client)
        self.client.url='http://controlled.invalid/feature-fixture/v1';self.client.run=RUN;self.client.area='graphics'
        self.client.graphics_instance=self.scene.instance;self.client.graphics_previous=None
        self.client.graphics_status=self.provider
        self.active=dict(schemaVersion=1,runId=RUN,area='graphics',ticket=TICKET,stimulus=dict(verb='baseline',inputs={}))
        self.client.request=lambda path:deepcopy(self.active) if path=='/runs/'+RUN+'/active' else (_ for _ in ()).throw(AssertionError('Unexpected fixture request'))
        self.lock=PhoneScriptSourceLock(root/'phone-script-sources.lock')

    def state_path(self,_selector):return self.root/'session.json'
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only
        if self.fail_runtime:raise AssertionError('Historical archive attempted SDK access')
        return None,None,deepcopy(self.binding),lambda:self.okay,None
    def options(self):return dict(monotonic=lambda:self.clock,sleep=lambda seconds:setattr(self,'clock',self.clock+seconds))
    def guard(self):return self.okay
    def epoch(self):return 20000

    def send(self,key,request):
        # This role must persist its own intent before any original source request.
        journal=PrivateFeatureState(self.root/('phone-graphics-'+self.active_role+'-0-samples.json')).read()
        assert journal is not None and unpack(journal['payload'])[0]['phase']=='reading'
        self.calls.append((key,deepcopy(request)));self.counters[key]+=1
        template={'native':'before','subject':'subject_before','graphics':'ui','tablet':'tablet','capture':'capture'}[key]
        value=deepcopy(getattr(self.scene,template));value['commandId' if key in ('graphics','tablet') else 'requestId']=request['commandId']
        cursor='sourceSequence' if key in ('graphics','tablet') else 'sequence';value[cursor]=self.counters[key]
        if key=='capture':
            value['source']['image']['name']=image_name(request['commandId'])
            value['source']['acquisitionSequence']=self.counters[key]
            value['source']['renderTrace']['frameId']=uuid.uuid4().hex
            if self.fault=='frame-reuse':value['source']['renderTrace']['frameId']=self.last_frame
            self.last_frame=value['source']['renderTrace']['frameId'];self.storage.present=True
        if self.fault==key+'-cursor':value[cursor]=1
        if self.fault==key+'-birth':value['instance']='f'*32
        if self.fault=='clock-rollback':value['capturedEpochMs']=19999
        if self.fault=='elapsed':self.clock+=21
        self.values[key]=value
        if self.fault=='lost-capture-return' and key=='capture':raise RuntimeError('Synthetic lost native dispatch return')

    def reader(self,key,cls):
        reader=cls(lambda request:self.send(key,request),lambda:json.dumps(self.values[key]),
                   self.epoch,self.guard,31,**self.options());self.readers.append((key,reader));return reader
    def _native_feature_observer(self,_selector,*,read_only):assert read_only;return self.reader('native',NativeFeatureObservation)
    def _graphics_subject_observer(self,_selector,*,read_only):assert read_only;return self.reader('subject',NativeGraphicsSubject)
    def _graphics_controls(self,_selector,_intent,*,read_only):assert read_only;return SimpleNamespace(io=self.reader('graphics',PhoneGraphicsIO))
    def _script_file_io(self,_selector,*,read_only):assert read_only;return self.reader('tablet',PhoneScriptFileIO)
    def provider(self):
        value=deepcopy(self.scene.provider);value['requestId']=uuid.uuid4().hex
        self.client.graphics_previous=deepcopy(value);return value

    def change_phase(self,ticket='7'*32):
        self.active=dict(schemaVersion=1,runId=RUN,area='graphics',ticket=ticket,stimulus=dict(verb='open',inputs={}))
        rows=self.scene.provider['activations'];rows.append(dict(sequence=len(rows)+1,ticket=ticket,activatedEpochMs=20000))
        self.scene.provider['ticket']=ticket;self.scene.image(ticket=ticket);self.storage.raw=self.scene.pixels

    def _world_render_capture(self,_selector,*,read_only,role,require_frame_view):
        assert read_only and require_frame_view
        store=PrivateFeatureState(self.root/('world-'+role+'.json'))
        owner=WorldRenderOwner(store,self.binding,self.guard,role=role)
        storage=NativeWorldRenderStorage(self.storage_send,lambda name:(self.receipt_root/name).read_text(),
            self.epoch,self.guard,31,receipt_intent=owner.receipt_intent,**self.options())
        cleanup=NativeWorldReceiptInventory(lambda request:self.inventory_send(owner,request),
            self.inventory.original,self.epoch,self.guard,31,owner.owned,lambda:storage.instance,**self.options())
        files=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.receipt_root/name).read_text()),cleanup)
        reader=NativeWorldRenderCapture(lambda request:self.send('capture',request),lambda:json.dumps(self.values['capture']),
            storage,self.epoch,self.guard,31,intent=owner.intent,require_frame_view=True,**self.options())
        self.readers.append(('capture',reader));return OwnedWorldRenderCapture(reader,storage,owner,files)

    def storage_send(self,request):
        self.calls.append(('storage',deepcopy(request)));self.storage.intents.append(deepcopy(request));self.storage.send(request)
        name=receipt_file(request['commandId']);path=self.receipt_root/name;path.write_text(self.storage.files[name]);path.chmod(0o600)
        self.inventory.issued[request['commandId']]=(request['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
        if self.fault=='storage-cursor':
            packet=json.loads(path.read_text());packet['sequence']=1;path.write_text(json.dumps(packet))
            self.inventory.issued[request['commandId']]=(request['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
    def inventory_send(self,owner,request):
        self.calls.append(('inventory',deepcopy(request)));self.inventory.owner=deepcopy(owner.owned())
        self.inventory.retired=not self.storage.present;self.inventory.present=self.storage.present
        self.inventory.callbacks=self.storage.callbacks;self.inventory.png_bytes=len(self.storage.raw) if self.storage.present else 0
        self.inventory.send(request)
        if self.fault=='inventory-cursor':self.inventory.value['sequence']=1

    def factory(self,**changes):
        values=dict(adapter=self,selector='controlled',client=self.client,run=RUN,provider_instance=self.scene.instance,
            role='primary',stage=0,lock=self.lock,artifact_root=self.root,image_policy=POLICY,
            epoch_ms=self.epoch,monotonic=lambda:self.clock)
        values.update(changes);self.active_role=values['role'];return PhoneGraphicsSamples(**values)


class GraphicsSamplesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-graphics-samples-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.boundary=Originals(self.root)
    def read(self,**changes):
        with self.boundary.lock.held():return self.boundary.factory(**changes).read(TICKET,20000)
    def state(self,role='primary',stage=0):
        return PrivateFeatureState(self.root/('phone-graphics-'+role+'-'+str(stage)+'-samples.json')).read()

    def test_original_sources_owned_png_and_separate_native_absence_are_joined_before_ready(self):
        actual=self.read();state=unpack(self.state()['payload'])[0]
        self.assertEqual(1,actual['sequence']);self.assertEqual('ready',state['phase']);self.assertIsNone(state['pending'])
        self.assertEqual(self.boundary.scene.pixels,Path(actual['imagePath']).read_bytes())
        self.assertEqual(20000,actual['capturedEpochMs']);self.assertFalse(actual['state']['hazePass'])
        self.assertEqual(['saved'],[image['phase'] for image in state['images']])
        self.assertEqual([],list(self.boundary.receipt_root.iterdir()));self.assertFalse((self.root/'world-primary.json').exists())
        self.assertEqual(['remove','inspect'],[r['operation'] for key,r in self.boundary.calls if key=='inventory'])
        self.assertTrue(all(r['action'] in ('feature-native-observe','feature-graphics-subject-observe','phone-graphics-ui',
            'phone-script-file-ui','feature-world-render-observe','feature-world-render-storage','feature-world-render-receipts')
            for _,r in self.boundary.calls))

    def test_recreated_producer_restores_original_cursors_and_acquires_a_distinct_frame_and_file(self):
        first=self.read();second=self.read();state=unpack(self.state()['payload'])[0]
        self.assertEqual(2,second['sequence']);self.assertNotEqual(first['imagePath'],second['imagePath'])
        self.assertEqual(2,len(state['seenFrames']));self.assertEqual(2,len(state['images']))
        self.assertEqual(2,self.boundary.counters['capture']);self.assertEqual(4,self.boundary.counters['native'])
        self.assertEqual(first['capturedEpochMs'],second['capturedEpochMs']) # Never retime original clocks.

    def test_each_original_source_cursor_survives_factory_recreation(self):
        for source in ('native','subject','graphics','tablet','capture','storage','inventory'):
            root=self.root/source;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():boundary.factory().read(TICKET,20000)
            boundary.fault=source+'-cursor'
            with self.subTest(source=source),boundary.lock.held(),self.assertRaises(NativeUIError):boundary.factory().read(TICKET,20000)
            state=unpack(PrivateFeatureState(root/'phone-graphics-primary-0-samples.json').read()['payload'])[0]
            self.assertEqual('reading',state['phase']);self.assertEqual(1,state['sequence'])

    def test_reused_gpu_frame_cannot_become_current_evidence_through_a_new_capture_nonce(self):
        self.read();self.boundary.fault='frame-reuse'
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual('reading',unpack(self.state()['payload'])[0]['phase'])
        self.assertFalse((self.root/'world-primary.json').exists())

    def test_native_birth_change_or_original_clock_rollback_cannot_reset_provenance(self):
        for fault in ('native-birth','subject-birth','graphics-birth','tablet-birth','capture-birth','clock-rollback'):
            root=self.root/fault;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():boundary.factory().read(TICKET,20000)
            boundary.fault=fault
            with self.subTest(fault=fault),boundary.lock.held(),self.assertRaises(NativeUIError):boundary.factory().read(TICKET,20000)

    def test_current_transport_hashes_cannot_hide_foreign_marker_pixels(self):
        raw,pixel_sha=original_image(ticket='f'*32);source=self.boundary.scene
        source.pixels=raw;self.boundary.storage.raw=raw
        source.capture['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=pixel_sha)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],list(self.root.glob('*.png')));self.assertFalse((self.root/'world-primary.json').exists())
        with self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory()

    def test_existing_foreign_capture_is_neither_adopted_nor_retired_by_a_new_sample(self):
        store=PrivateFeatureState(self.root/'world-primary.json')
        owner=WorldRenderOwner(store,BINDING,lambda:True,role='primary')
        owner.intent(dict(schemaVersion=1,commandId='f'*32,action='feature-world-render-observe'))
        original=store.read()
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(original,store.read());self.assertEqual([],self.boundary.calls)

    def test_lost_capture_return_drains_only_the_durably_correlated_measurement_without_replay(self):
        self.boundary.fault='lost-capture-return'
        with self.assertRaises(NativeUIError):self.read()
        state=unpack(self.state()['payload'])[0]
        self.assertEqual('reading',state['phase']);self.assertIsNotNone(state['pending']['captureIntent'])
        self.assertIsNotNone(state['pending']['retirement']);self.assertFalse((self.root/'world-primary.json').exists())
        self.assertEqual(1,sum(key=='capture' for key,_ in self.boundary.calls))
        self.assertEqual([],list(self.root.glob('*.png')))

    def test_ignored_memory_release_retains_native_ownership_and_never_returns_a_sample(self):
        self.boundary.storage.ignore_release=True
        with self.assertRaises(NativeUIError):self.read()
        self.assertTrue((self.root/'world-primary.json').exists());self.assertEqual('reading',unpack(self.state()['payload'])[0]['phase'])
        self.assertEqual(1,sum(key=='capture' for key,_ in self.boundary.calls))
        self.assertEqual(1,sum(key=='storage' and r['operation']=='release' for key,r in self.boundary.calls))

    def test_ignored_receipt_removal_retains_files_and_pending_sample(self):
        self.boundary.inventory.ignore_remove=True
        with self.assertRaises(NativeUIError):self.read()
        self.assertTrue(list(self.boundary.receipt_root.iterdir()));self.assertTrue((self.root/'world-primary.json').exists())
        self.assertEqual('reading',unpack(self.state()['payload'])[0]['phase'])

    def test_missing_or_replaced_original_png_cannot_become_a_recreated_history(self):
        first=self.read();path=Path(first['imagePath']);original=path.read_bytes();before=len(self.boundary.calls)
        for fault in ('missing','changed','replaced'):
            if path.exists():path.unlink()
            if fault!='missing':path.write_bytes(original if fault=='replaced' else b'foreign');path.chmod(0o600)
            with self.subTest(fault=fault),self.boundary.lock.held(),self.assertRaises((NativeUIError,OSError)):self.boundary.factory()
        self.assertEqual(before,len(self.boundary.calls))

    def test_lost_opened_image_intent_keeps_partial_file_and_refuses_producer_recreation(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();original=samples.images.intent
            def lost(value):
                original(value)
                if value['phase']=='opened':raise NativeUIError('Synthetic lost durable image intent return')
            samples.images.intent=lost
            with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            state=unpack(self.state()['payload'])[0]
            self.assertEqual('opened',state['images'][-1]['phase']);self.assertEqual(0,(self.root/state['images'][-1]['name']).stat().st_size)
            self.assertFalse((self.root/'world-primary.json').exists())
            with self.assertRaises(NativeUIError):self.boundary.factory()

    def test_foreign_run_role_binding_policy_or_artifact_root_cannot_adopt_a_history(self):
        self.read();before=len(self.boundary.calls)
        store=PrivateFeatureState(self.root/'phone-graphics-primary-0-samples.json');value=store.read()
        for key,replacement in (('runId','f'*32),('role','actor'),('artifactRoot',str(self.root/'foreign')),('imagePolicy',dict(source='native-screen'))):
            foreign=deepcopy(value);foreign[key]=replacement;store.write(foreign,store.read())
            with self.subTest(key=key),self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory()
            store.write(value,store.read())
        self.boundary.binding['processIdentity']='32:replacement'
        with self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory()
        self.assertEqual(before,len(self.boundary.calls))

    def test_historical_archive_reads_only_original_files_without_sdk_or_retiming(self):
        self.read();self.read();value=self.state();self.boundary.fail_runtime=True
        arguments=dict(client=self.boundary.client,run=RUN,provider_instance=self.boundary.scene.instance,role='primary',stage=0,
            binding=BINDING,artifact_root=self.root,image_policy=POLICY)
        state=PhoneGraphicsSamples.archive(value,**arguments)
        self.assertEqual(2,state['sequence']);self.assertEqual(20000,state['frame']['capture']['capturedEpochMs'])
        (self.root/state['images'][0]['name']).unlink()
        with self.assertRaises(FileNotFoundError):PhoneGraphicsSamples.archive(value,**arguments)

    def test_original_retirement_cannot_borrow_another_context_role_owner_or_absence_result(self):
        self.read();original=self.state();store=PrivateFeatureState(self.root/'phone-graphics-primary-0-samples.json')
        for fault in ('memory','context','owner','role','complete','files'):
            value=deepcopy(original);state=unpack(value['payload'])[0];proof=state['frame']['retirement']
            if fault=='memory':proof['memory']['present']=True
            elif fault=='context':proof['memory']['instance']='f'*32
            elif fault=='owner':proof['owner']['binding']['processIdentity']='32:foreign'
            elif fault=='role':proof['owner']['role']='actor'
            elif fault=='complete':proof['files']['absent']['source']['complete']=False
            else:proof['files']['absent']['source']['receipts'][0]['exists']=True
            value['payload']=pack([state]);store.write(value,store.read())
            with self.subTest(fault=fault),self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory()
            store.write(original,store.read())

    def test_actor_uses_distinct_original_history_and_never_adopts_primary_journal(self):
        self.read()
        actor=PrivateFeatureState(self.root/'phone-graphics-actor-0-samples.json');actor.write(self.state(),None)
        with self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory(role='actor')
        actor.discard(actor.read())
        with self.boundary.lock.held():actual=self.boundary.factory(role='actor').read(TICKET,20000)
        self.assertEqual(1,actual['sequence']);self.assertIn('-actor-',actual['imagePath'])
        self.assertEqual(1,unpack(self.state()['payload'])[0]['sequence'])

    def test_total_clock_regression_deadline_and_lost_binding_cannot_complete_a_sample(self):
        for fault in ('elapsed','guard'):
            root=self.root/fault;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():
                samples=boundary.factory()
                if fault=='elapsed':boundary.fault='elapsed'
                else:boundary.okay=False
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):samples.read(TICKET,20000)

    def test_changed_phase_retires_a_failed_observation_but_requires_an_entirely_new_sample(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();self.boundary.scene.image(ticket='f'*32);self.boundary.storage.raw=self.boundary.scene.pixels
            with self.assertRaises(AssertionError):samples.read(TICKET,20000)
            self.boundary.change_phase();item=samples.retire_changed_ticket()
            self.assertNotIn('state',item);self.assertEqual(TICKET,item['ticket']);self.assertEqual('7'*32,item['active']['ticket'])
            self.assertEqual([item['cursors']['capture']['source']['renderTrace']['frameId']],samples.state['seenFrames'])
            actual=self.boundary.factory().read('7'*32,20000)
        self.assertEqual(2,actual['sequence']);self.assertEqual(2,self.boundary.counters['capture'])
        self.assertEqual(1,len(unpack(self.state()['payload'])[0]['retirements']))

    def test_same_ticket_cannot_reset_a_failed_read_or_replay_any_native_request(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();self.boundary.scene.image(ticket='f'*32);self.boundary.storage.raw=self.boundary.scene.pixels
            with self.assertRaises(AssertionError):samples.read(TICKET,20000)
            before=len(self.boundary.calls)
            with self.assertRaises(NativeUIError):samples.retire_changed_ticket()
            self.assertEqual(before,len(self.boundary.calls));self.assertEqual('reading',samples.state['phase'])
            with self.assertRaises(NativeUIError):self.boundary.factory()

    def test_changed_phase_can_retry_scoped_ignored_cleanup_without_replaying_capture(self):
        for fault in ('memory','files'):
            root=self.root/fault;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():
                samples=boundary.factory()
                if fault=='memory':boundary.storage.ignore_release=True
                else:boundary.inventory.ignore_remove=True
                with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
                retained=deepcopy(samples.state['cursors']['storage'])
                self.assertIsNotNone(retained)
                boundary.storage.ignore_release=False;boundary.inventory.ignore_remove=False;boundary.change_phase()
                item=samples.retire_changed_ticket()
                self.assertGreater(item['cursors']['storage']['sequence'],retained['sequence'])
                self.assertEqual(1,boundary.counters['capture']);self.assertFalse((root/'world-primary.json').exists())
                self.assertEqual([],list(boundary.receipt_root.iterdir()))
                actual=boundary.factory().read('7'*32,20000);self.assertEqual(2,actual['sequence'])

    def test_unknown_capture_or_partial_png_remains_red_after_a_changed_ticket(self):
        for fault in ('lost-capture-return','partial-png'):
            root=self.root/fault;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():
                samples=boundary.factory()
                if fault=='lost-capture-return':boundary.fault=fault
                else:
                    original=samples.images.intent
                    def lost(value):
                        original(value)
                        if value['phase']=='opened':raise NativeUIError('Synthetic lost opened intent return')
                    samples.images.intent=lost
                with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
                boundary.change_phase()
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,OSError)):samples.retire_changed_ticket()
                self.assertEqual('reading',samples.state['phase']);self.assertEqual(1,boundary.counters['capture'])

    def test_absent_planned_file_intent_is_retained_as_an_original_negative_artifact(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();original=samples.images.intent
            def lost(value):
                original(value)
                if value['phase']=='planned':raise NativeUIError('Synthetic lost planned intent return')
            samples.images.intent=lost
            with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            self.boundary.change_phase();item=samples.retire_changed_ticket()
            self.assertEqual([],samples.state['images']);self.assertEqual(1,len(item['abandonedImages']))
            self.assertTrue(item['abandonedImages'][0]['absent'])
            restored=self.boundary.factory();self.assertEqual(1,restored.state['sequence'])
        value=self.state();arguments=dict(client=self.boundary.client,run=RUN,provider_instance=self.boundary.scene.instance,
            role='primary',stage=0,binding=BINDING,artifact_root=self.root,image_policy=POLICY)
        PhoneGraphicsSamples.archive(value,**arguments)
        path=self.root/item['abandonedImages'][0]['image']['name'];path.write_bytes(b'foreign late file');path.chmod(0o600)
        with self.assertRaises(NativeUIError):PhoneGraphicsSamples.archive(value,**arguments)
        self.assertEqual(b'foreign late file',path.read_bytes())

    def test_lost_saved_image_return_can_retire_verified_file_but_never_publish_old_facts(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();original=samples.images.intent
            def lost(value):
                original(value)
                if value['phase']=='saved':raise NativeUIError('Synthetic lost saved intent return')
            samples.images.intent=lost
            with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            self.boundary.change_phase();item=samples.retire_changed_ticket()
            self.assertNotIn('state',item);self.assertEqual(1,len(samples.state['images']))
            self.assertEqual('saved',samples.state['images'][0]['phase'])
            result=self.boundary.factory().read('7'*32,20000)
            self.assertNotEqual(samples.state['images'][0]['name'],Path(result['imagePath']).name)

    def test_foreign_or_moving_fixture_phase_cannot_retire_the_pending_read(self):
        for fault in ('run','area','moving'):
            root=self.root/fault;root.mkdir(mode=0o700);boundary=Originals(root)
            with boundary.lock.held():
                samples=boundary.factory();boundary.scene.image(ticket='f'*32);boundary.storage.raw=boundary.scene.pixels
                with self.assertRaises(AssertionError):samples.read(TICKET,20000)
                boundary.change_phase()
                if fault in ('run','area'):boundary.active['runId' if fault=='run' else 'area']='f'*32 if fault=='run' else 'scripts'
                else:
                    reads=[]
                    def changed(path):
                        reads.append(path);value=deepcopy(boundary.active)
                        if len(reads)>1:value['ticket']='8'*32
                        return value
                    boundary.client.request=changed
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):samples.retire_changed_ticket()
                self.assertEqual('reading',samples.state['phase'])

    def test_accepted_nonterminal_memory_cursor_cannot_roll_back_during_cleanup_retry(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();self.boundary.storage.ignore_release=True
            with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            floor=samples.state['cursors']['storage']['sequence'];self.assertGreater(floor,2)
            self.boundary.storage.ignore_release=False;self.boundary.storage.sequence=0;self.boundary.change_phase()
            with self.assertRaises(NativeUIError):samples.retire_changed_ticket()
            self.assertEqual(floor,samples.state['cursors']['storage']['sequence'])
            self.assertTrue((self.root/'world-primary.json').exists());self.assertEqual('reading',samples.state['phase'])

    def test_abandoned_intent_proof_survives_lost_phase_confirmation_without_new_capture(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();original=samples.images.intent
            def lost(value):
                original(value)
                if value['phase']=='planned':raise NativeUIError('Synthetic lost planned return')
            samples.images.intent=lost
            with self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            self.boundary.change_phase();request=self.boundary.client.request;reads=[]
            def interrupted(path):
                reads.append(path)
                if len(reads)>1:raise NativeUIError('Synthetic lost phase confirmation')
                return request(path)
            self.boundary.client.request=interrupted
            with self.assertRaises(NativeUIError):samples.retire_changed_ticket()
            retained=unpack(self.state()['payload'])[0]
            self.assertEqual(1,len(retained['pending']['abandonedImages']));self.assertEqual([],retained['images'])
            self.boundary.client.request=request;item=samples.retire_changed_ticket()
            self.assertEqual(retained['pending']['abandonedImages'],item['abandonedImages'])
            self.assertEqual(1,self.boundary.counters['capture'])

    def test_v1_ledger_is_refused_without_implicit_upgrade_or_native_access(self):
        self.read();store=PrivateFeatureState(self.root/'phone-graphics-primary-0-samples.json');value=store.read()
        value['graphicsSamplesVersion']=1;store.write(value,store.read());before=len(self.boundary.calls)
        with self.boundary.lock.held(),self.assertRaises(NativeUIError):self.boundary.factory()
        self.assertEqual(value,store.read());self.assertEqual(before,len(self.boundary.calls))

    def test_lost_world_owner_discard_return_retains_complete_original_proof_before_recovery(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory();original=PrivateFeatureState.discard
            def lost(store,value):
                original(store,value)
                if store.path==self.root/'world-primary.json':raise NativeUIError('Synthetic lost owner discard return')
            with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            state=unpack(self.state()['payload'])[0]
            self.assertEqual('reading',state['phase']);self.assertIsNotNone(state['pending']['retirement'])
            self.assertFalse((self.root/'world-primary.json').exists());self.boundary.change_phase()
            item=samples.retire_changed_ticket();self.assertEqual(state['pending']['retirement'],item['measurement'])
            self.assertEqual(1,self.boundary.counters['capture'])

    def test_ignored_world_owner_discard_ack_cannot_complete_a_sample_or_forget_proof(self):
        with self.boundary.lock.held():
            samples=self.boundary.factory()
            with patch.object(PrivateFeatureState,'discard',return_value=True),self.assertRaises(NativeUIError):samples.read(TICKET,20000)
            self.assertTrue((self.root/'world-primary.json').exists())
            self.assertIsNotNone(unpack(self.state()['payload'])[0]['pending']['retirement'])
            self.boundary.change_phase();samples.retire_changed_ticket()
            self.assertFalse((self.root/'world-primary.json').exists())
