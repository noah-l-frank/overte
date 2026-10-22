"""Original raw fences/private PNGs; all native/SDK/GPU producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.graphics_subject_geometry import projected_box
from self_tests.test_native_completed_frame import view
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.self_tests import test_ios_emote_samples as fixture
from ios.self_tests.test_ios_graphics_measurements import NATIVE,HOST,RUN,BINDING,TICKET
from self_tests.test_native_vulkan_world_frame import World


class RawFramesTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.SamplesTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        f=self.fixture;f.scope.ticket=TICKET;f.scope.frames=[];f.scope.state.update(phase='new',baseline=None,pending=None)
        self.gpus={};self.sequence=0;self.tree=deepcopy(f.template['worldBefore']['source']['tree']);self.tree.update(totalEntities=0,entities=[])
        self.background=Image.new('RGBA',(640,400),(75,85,100,255));self.present=False
        self.render()
        original_world=f.world
        def empty(run):
            p=original_world(run);s=p['source'];s['tree']=deepcopy(self.tree)
            if not self.present:s['markers']=[];s['scriptOriginal']['source']['effects'].update(scannedEntities=0,entities=[])
            return p
        f.world=empty;f.vulkan=self.vulkan
        renderers=f.renderers
        def rendered(run):
            p=renderers(run);p['source']['tree']=deepcopy(self.tree);return p
        f.renderers=rendered
    def render(self):
        image=self.background.copy()
        if self.present:
            marker=self.fixture.template['worldBefore']['source']['markers'][0];box=projected_box(marker,view(),[640,400])
            ImageDraw.Draw(image).rectangle(tuple(int(v) for v in box),fill=(240,15,180,255))
        stream=BytesIO();image.save(stream,format='PNG');self.fixture.raw=stream.getvalue()
    def marker(self,shown,*,paint=True):
        self.present=shown
        self.tree=deepcopy(self.fixture.template['worldBefore']['source']['tree']);self.tree.update(revisionBefore=2 if shown else 3,revisionAfter=2 if shown else 3)
        if not shown:self.tree.update(totalEntities=0,entities=[])
        if paint:self.render()
    def owner(self):
        f=self.fixture;return IOSEmoteRestorationFrames(f.runtime,'owned',f.scope,f.root,f.lock,
            monotonic=lambda:f.gpu.clock,epoch_ms=lambda:HOST+f.gpu.clock*1000,sleep=lambda duration:f.gpu.sleep(duration))
    def vulkan(self,intent,receipt):
        f=self.fixture;current=[None]
        def sending(query):
            request=query['requestId']
            if request not in self.gpus:
                gpu=World();gpu.clock=f.gpu.clock;gpu.sequence=self.sequence;gpu.source_extent=[320,200];gpu.target_extent=[640,400]
                gpu.png=f.raw;gpu.raw_pixels=Image.open(BytesIO(f.raw)).convert('RGBA').tobytes()
                gpu.epoch=lambda:NATIVE+round(f.gpu.clock*1000)
                def observed(p):
                    if 'image' in p.get('source',{}):p['source']['image'].update(width=640,height=400)
                    if 'renderTrace' in p.get('source',{}):p['source']['renderTrace']['frameId']=request[4:]
                gpu.fault=observed;self.gpus[request]=gpu
            gpu=self.gpus[request];gpu.clock=max(gpu.clock,f.gpu.clock);f.gpu=gpu;current[0]=gpu;gpu.send(query);self.sequence=max(self.sequence,gpu.sequence)
        def reading():
            raw=current[0].original();self.sequence=max(self.sequence,current[0].sequence);return raw
        return NativeVulkanWorldFrame(sending,reading,lambda:NATIVE+round(f.gpu.clock*1000),lambda:True,42,intent,receipt=receipt,
            monotonic=lambda:f.gpu.clock,sleep=lambda duration:f.gpu.sleep(duration))
    def test_pre_marker_and_postcleanup_fences_keep_untouched_pngs_without_challenge_relabel(self):
        owner=self.owner();first=owner.capture('initial');f=self.fixture;f.scope.state.update(phase='released',pending=None)
        second=owner.capture('cleanup');old,raw=owner.frame(first);new,after=owner.frame(second)
        self.assertEqual(f.raw,raw);self.assertEqual(raw,after);self.assertNotEqual(old['capture']['requestId'],new['capture']['requestId'])
        self.assertTrue(all(not frame['source']['markers'] for frame in (old['worldBefore'],new['worldAfter'])))
        count=sum(len(gpu.commands) for gpu in self.gpus.values())
        archive=IOSEmoteRestorationFrames.archive(owner.store.read(),store=owner.store,root=f.root,binding=BINDING,run=RUN,role='primary',lock=f.lock)
        self.assertEqual(new,archive.frame(second)[0]);self.assertEqual(count,sum(len(gpu.commands) for gpu in self.gpus.values()))
    def test_uncertain_read_retires_original_gpu_without_resending_or_deleting_empty_inode(self):
        owner=self.owner();factory=self.vulkan
        def lost(intent,receipt):
            reader=factory(intent,receipt);send=reader.send
            def sending(query):
                send(query)
                if query['operation']=='read':raise OSError('Lost raw fenced capture')
            reader.send=sending;return reader
        self.fixture.vulkan=lost
        with self.assertRaises(NativeUIError):owner.capture('initial')
        self.fixture.vulkan=factory;rebuilt=self.owner();self.assertTrue(rebuilt.abandon())
        sample=rebuilt.original(rebuilt.state['records'][-1]);self.assertEqual('abandoned',sample['phase'])
        self.assertEqual(1,sum(q['operation']=='read' for gpu in self.gpus.values() for q in gpu.commands))
        self.assertTrue(any(self.fixture.root.glob('*.png')))
    def test_reserved_before_native_creation_uses_actual_once_release_tombstone(self):
        def unavailable(_):raise OSError('Original World query lost before GPU owner')
        self.fixture.world=unavailable
        with self.assertRaises(OSError):self.owner().capture('initial')
        owner=self.owner();self.assertTrue(owner.abandon());self.assertEqual('abandoned',owner.original(owner.state['records'][-1])['phase'])
        self.assertEqual(0,sum(q['operation']=='read' for gpu in self.gpus.values() for q in gpu.commands))
        self.assertEqual(1,sum(q['operation']=='release' for gpu in self.gpus.values() for q in gpu.commands))

    def test_lost_reserved_native_release_is_inspected_without_repeating_it(self):
        self.fixture.world=lambda _:(_ for _ in ()).throw(OSError('Lost original world'))
        with self.assertRaises(OSError):self.owner().capture('initial')
        factory=self.vulkan
        def lost(intent,receipt):
            reader=factory(intent,receipt);send=reader.send
            def sending(query):
                send(query)
                if query['operation']=='release':raise OSError('Unknown native tombstone return')
            reader.send=sending;return reader
        self.fixture.vulkan=lost
        with self.assertRaises(NativeUIError):self.owner().abandon()
        self.fixture.vulkan=factory;owner=self.owner();self.assertTrue(owner.abandon())
        commands=[q for gpu in self.gpus.values() for q in gpu.commands]
        self.assertEqual(1,sum(q['operation']=='release' for q in commands));self.assertEqual(1,sum(q['operation']=='inspect' for q in commands))

    def test_preexisting_native_slot_is_never_read_or_released_by_this_owner(self):
        factory=self.vulkan
        def occupied(intent,receipt):
            reader=factory(intent,receipt);send=reader.send
            def sending(query):
                send(query)
                if query['operation']=='inspect':
                    gpu=self.gpus[query['requestId']];gpu.request=dict(commandId='ios-'+'d'*32)
                    gpu.started=gpu.clock;gpu.metadata=True
                    gpu.value['source'].update(present=True,metadataBytes=200,pngBytes=len(gpu.png))
            reader.send=sending;return reader
        self.fixture.vulkan=occupied
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        owner=self.owner();request=owner.state['pending']['requestId'];gpu=self.gpus[request]
        original=(deepcopy(gpu.request),gpu.png,gpu.metadata,gpu.retired)
        with self.assertRaises(NativeUIError):owner.abandon()
        self.assertEqual(original,(gpu.request,gpu.png,gpu.metadata,gpu.retired))
        self.assertEqual(['inspect'],[q['operation'] for q in gpu.commands])
        self.assertIsNotNone(self.owner().state['pending'])

    def test_original_proven_empty_inspection_can_retire_reservation_without_a_read(self):
        factory=self.vulkan
        def stopped(intent,receipt):
            reader=factory(intent,receipt);perform=reader.perform
            def performing(query):
                if query['operation']=='read':raise OSError('Stopped before read intent')
                return perform(query)
            reader.perform=performing;return reader
        self.fixture.vulkan=stopped
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        self.fixture.vulkan=factory;self.assertTrue(self.owner().abandon())
        operations=[q['operation'] for gpu in self.gpus.values() for q in gpu.commands]
        self.assertNotIn('read',operations);self.assertEqual(1,operations.count('release'))

    def test_lost_original_artifact_commit_adopts_same_native_frame_without_recapture(self):
        from adapters.normal_feature_state import PrivateFeatureState
        owner=self.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==owner.file(1).path and not lost:lost.append(True);raise OSError('Lost immutable raw-frame return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):owner.capture('initial')
        count=sum(len(gpu.commands) for gpu in self.gpus.values());self.assertTrue(self.owner().resolve())
        self.assertEqual(count,sum(len(gpu.commands) for gpu in self.gpus.values()));self.assertEqual(1,len(self.owner().state['records']))

    def test_changed_png_and_original_world_or_renderer_birth_do_not_retire_ownership(self):
        owner=self.owner();ref=owner.capture('initial');original=owner.original(ref)
        from adapters.script_feature.history import unpack,pack
        for field in ('worldAfter','renderersAfter'):
            value=deepcopy(original);frame=unpack(value['payload'])[0];frame[field]['instance']='f'*32;value['payload']=pack([frame])
            with self.subTest(field=field),self.assertRaises(NativeUIError):owner.validate(value)
        record=unpack(original['owner'])[0];(owner.root/record['name']).write_bytes(b'foreign raw pixels')
        with self.assertRaises(NativeUIError):self.owner()

    def test_fully_returned_unqualified_camera_can_only_abandon_its_actual_gpu_owner(self):
        factory=self.fixture.world
        def moved(run):
            value=factory(run);value['source']['view']['position'][0]+=1.;return value
        self.fixture.world=moved;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture('initial')
        commands=sum(len(gpu.commands) for gpu in self.gpus.values())
        self.assertTrue(self.owner().abandon());rebuilt=self.owner()
        self.assertEqual('abandoned',rebuilt.original(rebuilt.state['records'][0])['phase'])
        self.assertEqual(1,sum(q['operation']=='read' for gpu in self.gpus.values() for q in gpu.commands))
        self.assertGreaterEqual(sum(len(gpu.commands) for gpu in self.gpus.values()),commands)

    def test_original_world_birth_from_abandoned_read_remains_a_later_capture_floor(self):
        factory=self.fixture.world
        def foreign(run):
            value=factory(run);value['instance']='f'*32;return value
        self.fixture.world=foreign
        rendered=self.fixture.renderers
        self.fixture.renderers=lambda _:(_ for _ in ()).throw(OSError('Lost renderer after returned World'))
        with self.assertRaises(OSError):self.owner().capture('initial')
        owner=self.owner();self.assertTrue(owner.abandon());self.fixture.world=factory;self.fixture.renderers=rendered
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        with self.assertRaises(NativeUIError):self.owner()

    def gpu_reset_after_abandonment(self,*,birth):
        factory=self.vulkan
        def lost(intent,receipt):
            reader=factory(intent,receipt);send=reader.send
            def sending(query):
                send(query)
                if query['operation']=='read':raise OSError('Lost original GPU read')
            reader.send=sending;return reader
        self.fixture.vulkan=lost
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        self.fixture.vulkan=factory;self.assertTrue(self.owner().abandon())
        if birth:
            def replaced(intent,receipt):
                reader=factory(intent,receipt);send=reader.send
                def sending(query):
                    send(query);gpu=self.gpus[query['requestId']];old=gpu.fault
                    def observed(packet):
                        if old:old(packet)
                        packet['instance']='e'*32
                    gpu.fault=observed;gpu.value['instance']='e'*32
                reader.send=sending;return reader
            self.fixture.vulkan=replaced
        else:self.sequence=0
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        # The returned later request is internally well-formed. Independent
        # historical replay still refuses its reset against abandoned receipts.
        with self.assertRaises(NativeUIError):self.owner()

    def test_abandoned_gpu_counter_floor_cannot_reset_in_a_later_valid_request(self):
        self.gpu_reset_after_abandonment(birth=False)

    def test_abandoned_gpu_source_birth_cannot_change_in_a_later_valid_request(self):
        self.gpu_reset_after_abandonment(birth=True)

    def test_pending_actual_gpu_carrier_requires_its_original_owner_context_and_dtos(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from adapters.script_feature.history import unpack,pack
        factory=self.vulkan
        def lost(intent,receipt):
            reader=factory(intent,receipt);send=reader.send
            def sending(query):
                send(query)
                if query['operation']=='read':raise OSError('Lost actual GPU read')
            reader.send=sending;return reader
        self.fixture.vulkan=lost
        with self.assertRaises(NativeUIError):self.owner().capture('initial')
        owner=self.owner();request=owner.state['pending']['requestId']
        store=PrivateFeatureState(owner.lock.path.with_name('graphics-world-frame-primary-0-'+request[4:]+'.json'))
        original=store.read()
        for field in ('binding','receipt'):
            value=deepcopy(original)
            if field=='binding':value['binding']['artifactSha256']='e'*64
            else:
                rows=unpack(value['transcript']);rows[0]['receipt']['sequence']=True;value['transcript']=pack(rows)
            store.write(value,original)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.owner()
            store.write(original,value)

    def lost_native_wrapper(self,fail_at,*,abandon=False):
        factory=self.fixture.native;reader=factory(None);original=reader.read;calls=[0]
        def lost(after):
            calls[0]+=1;value=original(after)
            if calls[0]==fail_at:raise OSError('Lost actual native return')
            return value
        reader.read=lost;self.fixture.native=lambda _:reader
        if abandon:
            self.fixture.world=lambda _:(_ for _ in ()).throw(OSError('Lost original World before GPU'))
            # First native begin returns; force the abandon begin/end loss.
            with self.assertRaises(OSError):self.owner().capture('initial')
            self.assertIs(reader.read,lost)
            self.fixture.native=factory
            abandoned_reader=factory(None);abandoned_original=abandoned_reader.read;calls[0]=0
            original=abandoned_original;abandoned_reader.read=lost
            self.fixture.native=lambda _:abandoned_reader
            with self.assertRaises(OSError):self.owner().abandon()
            self.assertIs(abandoned_reader.read,lost)
        else:
            with self.assertRaises(OSError):self.owner().capture('initial')
            self.assertIs(reader.read,lost)
        self.fixture.native=factory
        self.assertTrue(self.owner().abandon())

    def test_lost_native_begin_restores_only_the_installed_read_wrapper(self):
        self.lost_native_wrapper(1)

    def test_lost_native_end_restores_only_the_installed_read_wrapper(self):
        self.lost_native_wrapper(2)

    def test_lost_abandon_native_end_restores_only_the_installed_read_wrapper(self):
        self.lost_native_wrapper(2,abandon=True)

    def test_avatar_profile_uses_its_actual_original_world_schema_and_private_namespace(self):
        from adapters.original_marker_restoration_frames import OriginalMarkerRestorationFrames
        from adapters.original_marker_scope import _components
        from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
        class AvatarFrames(OriginalMarkerRestorationFrames):PROFILE='avatar'
        f=self.fixture;scope=f.scope
        avatar=object.__new__(IOSAvatarMarkerScope);avatar.__dict__.update(scope.__dict__)
        avatar._marker_components=_components('avatar')
        # No marker exists in either genuine original. Only the native action's
        # independently versioned Avatar envelope differs from the Emote DTO.
        original=f.world
        def world(run):
            value=original(run);value['iosAvatarWorldVersion']=value.pop('iosEmoteWorldVersion')
            value['clockDomain']='native-main-avatar-world';return value
        sources=f.runtime._sources
        def source(selector):
            value=sources(selector)
            value['observer'].avatar_world=lambda _clock:type('Reader',(),{'last':None,'read':lambda _self,run:world(run)})()
            return value
        f.runtime._sources=source
        owner=AvatarFrames(f.runtime,'owned',avatar,f.root,f.lock,monotonic=lambda:f.gpu.clock,
            epoch_ms=lambda:HOST+f.gpu.clock*1000,sleep=lambda duration:f.gpu.sleep(duration))
        reference=owner.capture('initial');self.assertEqual('avatar',owner.original(reference)['profile'])
        self.assertTrue(owner.store.path.name.startswith('ios-avatar-'))
        self.assertTrue(owner.file(1).path.name.startswith('avatar-restoration-'))


if __name__=='__main__':unittest.main()
