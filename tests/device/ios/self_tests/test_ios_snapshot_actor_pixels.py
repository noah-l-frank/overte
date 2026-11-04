"""Prospective genuine-owner host cases; native/renderer/device remain models."""
from copy import deepcopy
import base64,hashlib,os,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PublicationPending
from ios.adapters.snapshot_actor_pixel_set import SnapshotActorPixelSet
from ios.adapters.snapshot_actor_pixel_publication import SnapshotActorPixelCanonicalPublication
from ios.adapters.snapshot_actor_pixels import pixels
from ios.self_tests.snapshot_actor_pixel_domain import ActorPixelDomain,DeclaredActorFrame,RUN,TICKET

class SnapshotActorPixelOriginalTests(unittest.TestCase):
    def test_genuine_actor_factory_retains_actual_png_and_publishes_same_original(self):
        d=ActorPixelDomain(self)
        with d.pixels()as actor:
            result=actor.observe_original(1,TICKET);owner=actor.actors.owner(1,historical=True)
            packet=owner.validate_original(owner.original())['nativeOriginal']['packet'];raw=pixels(packet['source'],42,packet['clockBefore']['epochMs'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),result['publication']['entry']['facts']['png']['sha256'])
            self.assertTrue(result['actorRenderPngOriginalRetained']and result['canonicalActorPixelOriginalPublished'])
            self.assertFalse(result['nativeQualified']or result['wholeQualified']or result['independentProcessAuthenticationEstablished'])
        self.assertEqual(1,len(d.pixel_queries));self.assertEqual(1,len(d.posts));self.assertEqual(0,d.primary.capture.capture_count)
        self.assertEqual(0,d.renderer.active);self.assertEqual(1,d.renderer.reads)

    def test_cold_historical_original_and_publication_replay_never_reacquires_pixels_or_posts(self):
        d=ActorPixelDomain(self)
        with d.pixels()as actor:
            result=actor.observe_original(1,TICKET);a=actor.actors
            def forbidden(*_a,**_k):raise AssertionError('Historical pixel original touched live transport or write')
            with patch.object(type(d.actor_client),'request',forbidden),patch.object(PrivateFeatureState,'write',side_effect=forbidden):
                history=SnapshotActorPixelSet(a.root,a.lock,a.binding,a.run,a.fixture_url)
                publication=SnapshotActorPixelCanonicalPublication(history,historical=True)
                self.assertEqual(result['publication'],publication.history()[0])
                owner=history.owner(1,historical=True);packet=owner.validate_original(owner.original())['nativeOriginal']['packet']
                self.assertTrue(pixels(packet['source'],42,packet['clockBefore']['epochMs']))
        self.assertEqual(1,len(d.pixel_queries));self.assertEqual(1,len(d.posts));self.assertEqual(1,d.renderer.reads)

    def test_replaced_held_frame_during_callback_is_unavailable_not_joined_by_ids(self):
        d=ActorPixelDomain(self,replaced_during_callback=True)
        self.assertIsNone(d.renderer.latest);self.assertEqual(0,d.renderer.active)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts);self.assertEqual(1,len(d.pixel_queries))

    def test_later_current_frame_cannot_borrow_the_retained_old_png(self):
        d=ActorPixelDomain(self);old=d.renderer.current
        frame=deepcopy(old.inputs);frame.update(frameInstance='1'*32,frameIndex=frame['frameIndex']+1)
        d.renderer.current=DeclaredActorFrame(frame,old.rgba)
        self.assertFalse(d.renderer.original()['complete'])
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts)

    def test_actual_native_png_hash_mismatch_is_refused_before_publication(self):
        def fault(body):body['source']['png']['sha256']='0'*64
        d=ActorPixelDomain(self,packet_fault=fault)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts);self.assertEqual(1,len(d.pixel_queries))

    def test_decoded_rgba_mismatch_is_refused_without_expected_pixel_substitution(self):
        def fault(body):body['source']['frame']['readback']['pixelSha256']='0'*64
        d=ActorPixelDomain(self,packet_fault=fault)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts)

    def test_actual_camera_crop_and_process_bindings_cannot_be_replaced(self):
        faults=(lambda b:b['source']['png']['frameBinding']['camera']['position'].__setitem__(0,1),
            lambda b:b['source']['frame']['readback'].__setitem__('rectBottomLeft',[1,0,32,32]),lambda b:b.__setitem__('processId',43),
            lambda b:b['source']['resource'].__setitem__('callbackScopeRetired',False),lambda b:b['source']['resource'].__setitem__('callbackScopeRetired',1))
        for fault in faults:
            with self.subTest(fault=fault):
                d=ActorPixelDomain(self,packet_fault=fault)
                with d.pixels()as actor:
                    with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
                self.assertEqual([],d.posts)

    def test_same_bytes_new_original_frame_inode_cannot_be_read_as_owned(self):
        d=ActorPixelDomain(self)
        with d.pixels()as actor:
            actor.observe_original(1,TICKET);owner=actor.actors.owner(1,historical=True);child=owner.child(historical=True);files=child.files()
            path=files.path(files.expand(child.state['proof']));raw=path.read_bytes();old=path.stat()
            temporary=path.with_name(path.name+'.replacement');temporary.write_bytes(raw);temporary.chmod(0o600);os.replace(temporary,path)
            self.assertNotEqual(old.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):actor.publication.reference(1)
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.pixel_queries))

    def test_lost_query_return_adopts_only_the_original_reply_without_second_native_read(self):
        d=ActorPixelDomain(self);d.lose_query=True
        with d.pixels()as actor:
            with self.assertRaises(OSError):actor.observe_original(1,TICKET)
        d.lose_query=False
        with d.pixels()as actor:self.assertTrue(actor.observe_original(1,TICKET)['canonicalActorPixelOriginalPublished'])
        self.assertEqual(1,len(d.pixel_queries));self.assertEqual(1,len(d.posts));self.assertEqual(1,d.renderer.reads)

    def test_saved_child_lost_parent_cas_return_reopens_genuine_owner_without_resend(self):
        d=ActorPixelDomain(self);actual=PrivateFeatureState.write;lost=[]
        def write(store,value,previous):
            result=actual(store,value,previous)
            if store.path.name=='ios-snapshot-actor-render-witness-0001.json'and value.get('iosSnapshotActorPixelWitnessOwnerVersion')==1 and not lost:
                from adapters.script_feature.history import unpack
                if unpack(value['payload'])[0]['phase']=='complete':lost.append(True);raise OSError('Real parent CAS completed, return lost')
            return result
        with patch.object(PrivateFeatureState,'write',write):
            with d.pixels()as actor:
                with self.assertRaises(OSError):actor.observe_original(1,TICKET)
        with d.pixels()as actor:self.assertTrue(actor.observe_original(1,TICKET)['canonicalActorPixelOriginalPublished'])
        self.assertEqual([True],lost);self.assertEqual(1,len(d.pixel_queries));self.assertEqual(1,len(d.posts))

    def test_uncertain_post_keeps_original_issued_and_recovers_only_real_journal_receipt(self):
        d=ActorPixelDomain(self);d.lose_post=True
        with d.pixels()as actor:
            with self.assertRaises(OSError):actor.observe_original(1,TICKET)
        with d.pixels()as actor:self.assertTrue(actor.observe_original(1,TICKET)['canonicalActorPixelOriginalPublished'])
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.pixel_queries))

    def test_ignored_post_ack_and_default_ui_family_cannot_become_pixel_success(self):
        d=ActorPixelDomain(self);d.drop_post=True
        with d.pixels()as actor:
            with self.assertRaises(PublicationPending):actor.observe_original(1,TICKET)
        with d.pixels()as actor:
            with self.assertRaises(PublicationPending):actor.observe_original(1,TICKET)
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.pixel_queries))
        d2=ActorPixelDomain(self,enabled=False)
        with d2.pixels()as actor:
            with self.assertRaises(ValueError):actor.observe_original(1,TICKET)
        self.assertEqual([],d2.journal.snapshot(RUN)['entries'])

    def test_same_frame_mutated_inputs_during_actual_model_callback_are_discarded(self):
        d=ActorPixelDomain(self,changed_inputs_during_callback=True)
        self.assertIsNone(d.renderer.latest);self.assertEqual(0,d.renderer.active)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts);self.assertEqual(1,len(d.pixel_queries))

    def test_foreign_owned_reference_and_proxy_mapping_do_not_grant_publication(self):
        d=ActorPixelDomain(self)
        with d.pixels()as actor:
            actor.publication.prepare();first=actor.actors.owner(1,historical=False);first.acquire(TICKET)
            reference=actor.publication.reference(1)
            actor.actors.native_floor(range(1,3));second=actor.actors.owner(2,historical=False);second.acquire(TICKET)
            foreign=dict(reference,ownerSha256=second.original()['ownerSha256'])
            with self.assertRaises(NativeUIError):actor.publication.validate_original(foreign)
            class Proxy(dict):pass
            with self.assertRaises(NativeUIError):actor.publication.validate_original(Proxy(reference))
        self.assertEqual([],d.posts);self.assertEqual(2,len(d.pixel_queries))

    def test_old_immutable_render_cannot_be_refreshed_by_new_getter_or_repeated_owner(self):
        d=ActorPixelDomain(self);original=deepcopy(d.renderer.latest)
        d.primary.capture.sleep(2)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual(original,d.renderer.latest);self.assertEqual(1,d.renderer.reads)
        self.assertEqual(1,len(d.pixel_queries));self.assertEqual([],d.posts)

    def test_existing_scene_publication_wal_is_never_reinterpreted_as_pixel_family(self):
        d=ActorPixelDomain(self)
        with d.independent()as scene:
            with self.assertRaises(ValueError):scene.observe_original(1,TICKET)
        path=d.actor.ctx.root/('phase-publication-snapshots-'+RUN+'-actor.json');original=path.read_bytes();info=path.stat()
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual(original,path.read_bytes());self.assertEqual((info.st_dev,info.st_ino),(path.stat().st_dev,path.stat().st_ino))
        self.assertEqual([],d.pixel_queries);self.assertEqual([],d.journal.snapshot(RUN)['entries'])

    def test_later_same_frame_input_mutation_invalidates_scene_and_pixels_without_readback_retry(self):
        d=ActorPixelDomain(self);held=d.renderer.current;original=deepcopy(held.inputs)
        initial=deepcopy(d.renderer.latest);self.assertEqual(1,d.renderer.reads)
        held.inputs['camera']['position'][0]=1
        d.renderer.consume(d.actor.clock()+1)
        self.assertIs(held,d.renderer.current);self.assertIsNone(d.renderer.scene_latest)
        self.assertIsNone(d.renderer.latest);self.assertFalse(d.renderer.original()['complete'])
        self.assertEqual(1,d.renderer.reads);self.assertEqual(0,d.renderer.active)
        held.inputs=deepcopy(original) # Restoring old fields cannot restore eligibility.
        d.renderer.consume(d.actor.clock()+2)
        self.assertIsNone(d.renderer.latest);self.assertIsNone(d.renderer.scene_latest)
        self.assertEqual(1,d.renderer.reads);self.assertEqual(original['recordedEpochMs'],initial['frame']['recordedEpochMs'])
        with d.pixels()as actor:
            with self.assertRaises(NativeUIError):actor.observe_original(1,TICKET)
        self.assertEqual([],d.posts)

    def test_unchanged_same_frame_representation_keeps_exact_original_without_second_readback(self):
        d=ActorPixelDomain(self);held=d.renderer.current;original=deepcopy(d.renderer.original())
        scene=deepcopy(d.renderer.scene_latest)
        d.renderer.consume(d.actor.clock()+1);d.renderer.consume(d.actor.clock()+2)
        self.assertIs(held,d.renderer.current);self.assertEqual(original,d.renderer.original())
        self.assertEqual(scene,d.renderer.scene_latest);self.assertEqual(1,d.renderer.reads)
        self.assertEqual(0,d.renderer.active);self.assertIsNone(d.renderer.invalidated_identity)

    def test_distinct_new_frame_can_advance_after_old_identity_was_invalidated(self):
        d=ActorPixelDomain(self);old=d.renderer.current;original=deepcopy(old.inputs)
        old.inputs['camera']['position'][0]=1;d.renderer.consume(d.actor.clock()+1)
        self.assertIsNone(d.renderer.scene_latest);self.assertIsNone(d.renderer.latest)
        fresh=deepcopy(original);fresh.update(frameInstance='2'*32,frameIndex=original['frameIndex']+1)
        d.renderer.current=DeclaredActorFrame(fresh,old.rgba)
        self.assertIsNot(old,d.renderer.current);d.renderer.consume(d.actor.clock()+2)
        self.assertTrue(d.renderer.original()['complete']);self.assertEqual(fresh,d.renderer.scene_latest)
        self.assertEqual('2'*32,d.renderer.original()['frame']['frameInstance'])
        self.assertEqual(2,d.renderer.reads);self.assertEqual(0,d.renderer.active)
        self.assertIsNone(d.renderer.invalidated_identity)

    def test_invalidated_a_then_real_b_then_restored_a_never_reanchors_either_frame(self):
        d=ActorPixelDomain(self);a=d.renderer.current;original=deepcopy(a.inputs)
        a.inputs['camera']['position'][0]=1;d.renderer.consume(d.actor.clock()+1)
        a.inputs=deepcopy(original)
        later=deepcopy(original);later.update(frameInstance='3'*32,frameIndex=original['frameIndex']+1)
        b=DeclaredActorFrame(later,a.rgba);d.renderer.current=b;d.renderer.consume(d.actor.clock()+2)
        self.assertTrue(d.renderer.original()['complete']);self.assertEqual(2,d.renderer.reads)
        b_original=deepcopy(d.renderer.original())
        d.renderer.current=a;d.renderer.consume(d.actor.clock()+3)
        self.assertFalse(d.renderer.original()['complete']);self.assertIsNone(d.renderer.scene_latest)
        self.assertTrue(d.renderer.index_regressed);self.assertEqual(later['frameIndex'],d.renderer.greatest_index)
        self.assertEqual(later['frameInstance'],d.renderer.greatest_identity);self.assertEqual(2,d.renderer.reads)
        d.renderer.current=b;d.renderer.consume(d.actor.clock()+4)
        self.assertFalse(d.renderer.original()['complete']);self.assertIsNone(d.renderer.scene_latest)
        self.assertEqual(2,d.renderer.reads);self.assertEqual(0,d.renderer.active)
        self.assertEqual(later['recordedEpochMs'],b_original['frame']['recordedEpochMs'])

    def test_equal_index_foreign_identity_cannot_replace_or_retry_the_rejected_head(self):
        d=ActorPixelDomain(self);a=d.renderer.current;original=deepcopy(a.inputs)
        foreign=deepcopy(original);foreign['frameInstance']='4'*32
        d.renderer.current=DeclaredActorFrame(foreign,a.rgba);d.renderer.consume(d.actor.clock()+1)
        self.assertIsNone(d.renderer.latest);self.assertIsNone(d.renderer.scene_latest)
        self.assertEqual(original['frameInstance'],d.renderer.greatest_identity)
        self.assertFalse(d.renderer.index_regressed);self.assertEqual(1,d.renderer.reads)
        d.renderer.current=a;d.renderer.consume(d.actor.clock()+2)
        self.assertFalse(d.renderer.original()['complete']);self.assertEqual(1,d.renderer.reads)
        higher=deepcopy(original);higher.update(frameInstance='5'*32,frameIndex=original['frameIndex']+1)
        d.renderer.current=DeclaredActorFrame(higher,a.rgba);d.renderer.consume(d.actor.clock()+3)
        self.assertTrue(d.renderer.original()['complete']);self.assertEqual(2,d.renderer.reads)

    def test_actual_declared_uint32_wrap_is_unavailable_for_remaining_process_lifetime(self):
        d=ActorPixelDomain(self);a=d.renderer.current;original=deepcopy(a.inputs)
        maximum=deepcopy(original);maximum.update(frameInstance='6'*32,frameIndex=2**32-1)
        d.renderer.current=DeclaredActorFrame(maximum,a.rgba);d.renderer.consume(d.actor.clock()+1)
        self.assertTrue(d.renderer.original()['complete']);self.assertEqual(2,d.renderer.reads)
        wrapped=deepcopy(original);wrapped.update(frameInstance='7'*32,frameIndex=0)
        d.renderer.current=DeclaredActorFrame(wrapped,a.rgba);d.renderer.consume(d.actor.clock()+2)
        self.assertFalse(d.renderer.original()['complete']);self.assertTrue(d.renderer.index_regressed)
        self.assertEqual(2**32-1,d.renderer.greatest_index);self.assertEqual(2,d.renderer.reads)
        after=deepcopy(original);after.update(frameInstance='8'*32,frameIndex=1)
        d.renderer.current=DeclaredActorFrame(after,a.rgba);d.renderer.consume(d.actor.clock()+3)
        self.assertIsNone(d.renderer.scene_latest);self.assertIsNone(d.renderer.latest)
        self.assertEqual(2,d.renderer.reads);self.assertEqual(0,d.renderer.active)
