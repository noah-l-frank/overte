"""Real private archives/loopback phases; native/GPU/SDK clocks modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import unittest

from PIL import Image,ImageDraw
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import marker_bytes
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_sample import NavigationSampleOwner,NavigationMarkerPending
from ios.adapters.navigation_samples import NavigationSamples
from ios.self_tests import test_ios_navigation_sample as sample_tests
from ios.self_tests.test_ios_navigation_sample import SDK,BINDING
from self_tests.test_native_vulkan_world_frame import World
from self_tests.test_native_completed_frame import view
from navigation_observation import viewpoint_urls


class GPU:
    def __init__(self,sdk):
        self.sdk=sdk;self.worlds={};self.sequence=0;self.frames=0
        self.marker=sdk.body['Entities'][-1]['sourceUrl'].split('/tickets/')[1].split('/')[0]
        self.current=None;self.drop=False;self.birth='c'*32;self.reuse_frame=False;self.commands=[]
    def raster(self):
        camera=self.sdk.navigation.source['view']['position'];recorded=view();recorded['position']=list(camera)
        image=Image.new('RGBA',(640,400),(120,120,120,255));draw=ImageDraw.Draw(image)
        def screen(point):
            camera_point=[a-b for a,b in zip(point,camera)]+[1]
            clip=[sum(recorded['projection'][row*4+col]*camera_point[col] for col in range(4)) for row in range(4)]
            return [(clip[0]/clip[3]+1)*320,(1-clip[1]/clip[3])*200]
        draw.polygon([tuple(screen(point)) for point in [[-4,0,.75],[-4,4,.75],[4,4,.75],[4,0,.75]]],fill=(180,80,180,255))
        marker=self.sdk.body['Entities'][-1];cx,cy,cz=[marker['position'][axis] for axis in 'xyz']
        width,height=[marker['dimensions'][axis] for axis in 'xy']
        left,top=screen([cx-width/2,cy+height/2,cz]);right,bottom=screen([cx+width/2,cy-height/2,cz])
        left,top,right,bottom=map(round,(left,top,right,bottom))
        card=Image.open(BytesIO(marker_bytes(self.sdk.run,self.marker))).convert('RGBA')
        image.paste(card.resize((right-left,bottom-top),Image.Resampling.NEAREST),(left,top))
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue(),image.tobytes(),recorded
    def factory(self,intent,receipt):
        def send(query):
            self.commands.append(deepcopy(query));key=query['requestId']
            if key not in self.worlds:
                source=World();source.source_extent=source.target_extent=[640,400]
                source.png,source.raw_pixels,recorded=self.raster()
                def actual(packet):
                    packet['instance']=self.birth
                    if 'source' in packet and 'renderTrace' in packet['source']:
                        packet['source']['renderTrace']['recordedView']=deepcopy(recorded)
                        packet['source']['renderTrace']['frameId']='d'*32 if self.reuse_frame else format(self.frames,'032x')
                source.change=actual
                source.fault=lambda packet:packet['source']['image'].update(width=640,height=400) if 'vulkanWorldFrameVersion' in packet else actual(packet)
                self.worlds[key]=source
            source=self.worlds[key];self.current=source;source.clock=self.sdk.gpu.clock;source.sequence=self.sequence
            if query['operation']=='read':self.frames+=1
            source.send(query);self.sequence=source.sequence;self.sdk.gpu.clock=source.clock
        def original():
            source=self.current;source.clock=self.sdk.gpu.clock;source.sequence=self.sequence
            raw=source.original();self.sequence=source.sequence;self.sdk.gpu.clock=source.clock
            if self.drop and source.commands[-1]['operation']=='read':return ''
            return raw
        return NativeVulkanWorldFrame(send,original,self.sdk.gpu.epoch,lambda:self.sdk.okay,42,intent,receipt=receipt,
            monotonic=lambda:self.sdk.gpu.clock,sleep=self.sdk.gpu.sleep)


class NavigationSamplesTests(unittest.TestCase):
    def setUp(self):
        sample_tests.NavigationSampleTests.setUp(self);self.index_store=PrivateFeatureState(self.root/'ios-navigation-primary-0-samples.json')
        self.sdk=SDK(self.harness,self.run);self.gpu=GPU(self.sdk)
        self.fixture=NavigationFixtureReader(self.client,self.run);self.fixture.attach()
    def child(self,request):
        return NavigationSampleOwner(PrivateFeatureState(self.root/('ios-navigation-primary-0-'+request[4:]+'-sample.json')),
            self.root,BINDING,self.run,'primary',0,request,self.lock,lambda:self.sdk.okay,native=self.sdk.native(),
            navigation=self.sdk.navigation.reader(),fixture=self.fixture,frame_factory=self.gpu.factory,sleep=self.sdk.gpu.sleep,
            monotonic=lambda:self.sdk.gpu.clock,epoch_ms=lambda:1_000_000+self.sdk.gpu.clock*1000)
    def index(self,*,historical=False,binding=BINDING,factory=None):
        return NavigationSamples(self.index_store,self.root,binding,self.run,'primary',0,self.lock,lambda:self.sdk.okay,
            factory=None if historical else factory or self.child,historical=historical)
    def take(self,index,ticket=None,label='A'):
        ticket=ticket or self.fixture.phase.status()['activations'][-1]['ticket']
        return index.read(ticket,viewpoint_urls(self.harness.inputs['sceneUrl'])[label],label,1_000_000+self.sdk.gpu.clock*1000-1)
    def activate(self,ticket,label='A'):
        self.client.activate(ticket,'open',{});self.gpu.marker=ticket
        url=viewpoint_urls(self.harness.inputs['sceneUrl'])[label];self.sdk.navigation.url=url
        self.sdk.navigation.source['sceneUrl']=url;x=0 if label=='A' else 2
        self.sdk.navigation.source['avatar']['feetPosition']=[x,0,4];self.sdk.navigation.source['view']['position']=[x,1.6,4]

    def test_indexed_originals_survive_reconstruction_and_historical_no_sdk_reads(self):
        with self.lock.held():
            index=self.index();first=self.take(index);second=self.take(self.index())
            self.assertNotEqual(first['requestId'],second['requestId']);self.assertEqual(2,len(self.index().state['rows']))
            original=self.index().archive(first['requestId']);commands=deepcopy(self.gpu.commands);self.sdk.okay=False
            frozen=self.index(historical=True);self.assertEqual(original,frozen.archive(first['requestId']))
            self.assertEqual(commands,self.gpu.commands)
            with self.assertRaises(NativeUIError):self.take(frozen)

    def test_marker_pending_is_archived_and_next_read_uses_a_new_request_only(self):
        with self.lock.held():
            self.gpu.marker='c'*32;index=self.index()
            with self.assertRaises(NavigationMarkerPending):self.take(index)
            row=index.state['rows'][0];self.assertEqual('marker-pending',row['status']);self.assertIsNone(index.archive(row['requestId'])[1])
            self.gpu.marker=self.fixture.phase.status()['activations'][-1]['ticket'];result=self.take(index)
            self.assertNotEqual(row['requestId'],result['requestId']);self.assertEqual(2,self.gpu.frames)
            self.assertEqual(2,len(index.state['seenFrames']))

    def test_changed_selects_immediately_previous_observed_B_and_then_A(self):
        with self.lock.held():
            index=self.index();first=self.take(index);self.activate('c'*32,'B');second=self.take(index,'c'*32,'B')
            self.assertGreaterEqual(index.changed(second['requestId'])['image']['subjectChangedFraction'],.05)
            self.activate('e'*32,'A');third=self.take(index,'e'*32,'A')
            self.assertGreaterEqual(index.changed(third['requestId'])['image']['subjectChangedFraction'],.05)
            self.assertEqual(third['requestId'],index.state['latestObserved']);self.assertNotEqual(first['requestId'],third['requestId'])

    def test_new_marker_with_unchanged_subject_is_not_changed_evidence(self):
        with self.lock.held():
            index=self.index();self.take(index);self.activate('c'*32);second=self.take(index,'c'*32)
            with self.assertRaises(AssertionError):index.changed(second['requestId'])

    def test_partial_unknown_capture_recovery_is_terminal_and_never_recaptures(self):
        with self.lock.held():
            self.gpu.drop=True;index=self.index()
            with self.assertRaises(NativeUIError):self.take(index)
            self.gpu.drop=False;again=self.index();again.recover();self.assertEqual('failed',again.state['phase'])
            self.assertEqual('abandoned',again.state['rows'][0]['status'])
            with self.assertRaises(NativeUIError):self.take(again)
            self.assertEqual(1,self.gpu.frames);self.assertEqual(1,sum(row['operation']=='release' for row in self.gpu.commands))

    def test_lost_index_return_adopts_exact_sealed_original_without_capture_or_retiming(self):
        with self.lock.held():
            index=self.index();write=self.index_store.write
            def lose(value,previous):
                state=unpack(value['payload'])[0]
                if state['phase']=='ready' and state['rows']:raise OSError('Synthetic lost index result before commit')
                return write(value,previous)
            self.index_store.write=lose
            with self.assertRaises(OSError):self.take(index)
            self.index_store.write=write;again=self.index();row=again.state['rows'][0]
            original=again.archive_store(row).read();again.recover()
            self.assertEqual(original,again.archive_store(row).read());self.assertEqual('ready',again.state['phase'])
            self.assertEqual(1,self.gpu.frames);self.assertEqual('observed',row['status'])

    def test_missing_child_metadata_after_started_intent_remains_unresolved(self):
        with self.lock.held():
            index=self.index();write=self.index_store.write
            def lose(value,previous):
                result=write(value,previous);state=unpack(value['payload'])[0]
                if state['phase']=='reading' and state['rows'][-1]['childStarted']:raise OSError('Synthetic lost start result')
                return result
            self.index_store.write=lose
            with self.assertRaises(OSError):self.take(index)
            self.index_store.write=write;again=self.index()
            with self.assertRaises(NativeUIError):again.recover()
            with self.assertRaises(NativeUIError):self.take(again)
            self.assertEqual(0,self.gpu.frames)

    def test_never_started_reservation_can_be_abandoned_without_a_native_command(self):
        with self.lock.held():
            index=self.index(factory=lambda _request:(_ for _ in ()).throw(OSError('Synthetic factory loss')))
            with self.assertRaises(OSError):self.take(index)
            again=self.index();again.recover();self.assertEqual('failed',again.state['phase'])
            self.assertFalse(again.state['rows'][0]['childStarted']);self.assertEqual([],self.gpu.commands)

    def test_sealed_original_is_not_replaced_by_later_mutable_cleanup_proofs(self):
        with self.lock.held():
            index=self.index();result=self.take(index);row=index.state['rows'][0];sealed=deepcopy(index.archive_store(row).read())
            child=self.child(row['requestId']);child.drain();child.drain()
            self.assertEqual(sealed,index.archive_store(row).read());self.assertEqual(result['image'],index.archive(row['requestId'])[1]['image'])

    def test_collective_drain_retains_originals_and_current_native_inspect_ledger(self):
        with self.lock.held():
            index=self.index();self.take(index);self.take(index)
            header=deepcopy(index.store.read());sealed=[deepcopy(index.archive_store(row).read()) for row in index.state['rows']]
            captures=self.gpu.frames;proof=index.drain();self.assertEqual(2,len(proof['rows']))
            self.assertEqual(captures,self.gpu.frames);self.assertEqual(header,index.store.read())
            self.assertEqual(sealed,[index.archive_store(row).read() for row in index.state['rows']])
            commands=deepcopy(self.gpu.commands);self.sdk.okay=False
            frozen=self.index(historical=True);self.assertEqual(proof,frozen.validate_drain(proof))
            self.assertEqual(commands,self.gpu.commands)

    def test_drain_cannot_borrow_foreign_absence_or_omit_original_native_ledger(self):
        with self.lock.held():
            index=self.index();self.take(index);proof=index.drain()
            for fault in ('request','birth','sequence','owner','child','index','row'):
                value=deepcopy(proof);row=value['rows'][0]
                if fault=='request':row['absence']['requestId']='ios-'+'f'*32
                elif fault=='birth':row['absence']['instance']='f'*32
                elif fault=='sequence':row['absence']['sequence']-=1
                elif fault=='owner':row['frameOwner']['absence']=None
                elif fault=='child':
                    state=unpack(row['child']['payload'])[0];state['drains']=[]
                    from adapters.script_feature.history import pack
                    row['child']['payload']=pack([state])
                elif fault=='index':value['indexSha256']='f'*64
                else:value['rows']=[]
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):index.validate_drain(value)

    def test_lost_collective_return_only_reinspects_without_capture_or_sealed_archive_changes(self):
        with self.lock.held():
            index=self.index();self.take(index);sealed=deepcopy(index.archive_store(index.state['rows'][0]).read())
            first=index.drain();second=self.index().drain()
            self.assertEqual(1,self.gpu.frames);self.assertGreater(second['rows'][0]['absence']['sequence'],first['rows'][0]['absence']['sequence'])
            self.assertEqual(sealed,index.archive_store(index.state['rows'][0]).read())
            self.assertEqual(1,sum(row['operation']=='read' for row in self.gpu.commands))

    def test_unresolved_capture_cannot_be_skipped_by_collective_drain(self):
        with self.lock.held():
            self.gpu.drop=True;index=self.index()
            with self.assertRaises(NativeUIError):self.take(index)
            commands=deepcopy(self.gpu.commands)
            with self.assertRaises(NativeUIError):index.drain()
            self.assertEqual(commands,self.gpu.commands)

    def test_late_index_validation_cannot_return_a_fresh_measurement(self):
        with self.lock.held():
            index=self.index();seal=index.seal
            def slow(row,child):
                result=seal(row,child);self.sdk.gpu.sleep(2.);return result
            index.seal=slow
            with self.assertRaises(NativeUIError):self.take(index)
            self.assertEqual(1,self.gpu.frames);again=self.index();self.assertEqual('ready',again.state['phase'])
            row=again.state['rows'][0];sample,_result=again.archive(row['requestId'])
            self.assertLess(sample['frame']['clockJoin']['hostAfterMonotonic'],self.sdk.gpu.clock)
            self.assertEqual(1,self.gpu.frames)

    def test_foreign_candidate_or_changed_archive_hash_cannot_adopt_evidence(self):
        with self.lock.held():
            index=self.index();result=self.take(index)
            with self.assertRaises(NativeUIError):self.index(binding=BINDING|dict(artifactSha256='f'*64))
            store=index.archive_store(index.state['rows'][0]);before=store.read();changed=deepcopy(before);changed['originalSha256']='f'*64;store.write(changed,before)
            with self.assertRaises(NativeUIError):index.archive(result['requestId'])

    def assert_corrupt_source_rejected(self,fault):
        with self.lock.held():
            index=self.index();self.take(index)
            if fault=='frame':self.gpu.frames=0
            elif fault=='counter':self.gpu.sequence=0
            else:self.gpu.birth='f'*32
            with self.assertRaises(NativeUIError):self.take(index)
            self.assertEqual('reading',index.state['phase'])

    def test_native_frame_reuse_cannot_advance_the_index(self):self.assert_corrupt_source_rejected('frame')
    def test_native_counter_reset_cannot_advance_the_index(self):self.assert_corrupt_source_rejected('counter')
    def test_native_source_replacement_cannot_advance_the_index(self):self.assert_corrupt_source_rejected('birth')
