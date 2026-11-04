"""Prospective genuine original-owner comparisons; no native renderer executes."""
from copy import deepcopy
import hashlib,os,unittest,uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PublicationPending
from ios.adapters.snapshot_actor_primary_png_join import SnapshotActorPrimaryPNGJoin
from ios.adapters.snapshot_actor_primary_png_factory import retained_original_pixel_join
from ios.self_tests.snapshot_actor_primary_png_domain import ActorPrimaryPNGDomain
from ios.self_tests.snapshot_actor_pixel_domain import ActorPixelDomain,DeclaredActorFrame,RUN,TICKET

def originals(domain):
    # Own two actual fixture roots only; no historical/global corpus inventory.
    roots=(domain.primary.ctx.root,domain.actor.ctx.root);rows={}
    for root in roots:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                info=path.lstat();rows[str(path)]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
    return rows

def counts(domain):
    return(domain.primary.capture.capture_count,len(domain.primary.provenance_queries),len(domain.pixel_queries),len(domain.posts),domain.renderer.reads,domain.primary.screen_calls)

class SnapshotActorPrimaryPNGJoinTests(unittest.TestCase):
    def test_genuine_independent_full_png_originals_join_without_new_capture_query_or_wda(self):
        d=ActorPrimaryPNGDomain(self);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            before=counts(d);saved=originals(d);value=join.proof()
            self.assertTrue(value['originalCropRGBAEqual']and value['canonicalActorPixelOriginalPublished'])
            self.assertFalse(value['newCaptureOrQueryOrPOST']or value['nativeQualified']or value['wholeQualified'])
            self.assertEqual(before,counts(d));self.assertEqual(saved,originals(d));self.assertEqual(0,d.primary.screen_calls)
            self.assertNotEqual(value['primaryBinding']['targetFingerprint'],value['actorBinding']['targetFingerprint'])
            self.assertEqual([0,0,128,128],value['actorRectTopLeft'])

    def test_actual_asymmetric_recorded_bottom_left_crop_maps_to_exact_actor_top_left_pixels(self):
        d=ActorPrimaryPNGDomain(self,rect=(17,29,64,48));d.prepare_primary()
        with d.retained_pair()as(join,actor):value=join.proof()
        self.assertEqual([17,51,81,99],value['actorRectTopLeft'])
        self.assertEqual(value['hashes']['primaryRGBA'],value['hashes']['actorCropRGBA'])
        self.assertNotEqual(value['hashes']['actorFullRGBA'],value['hashes']['actorCropRGBA'])
        self.assertFalse(value['pixelNormalizationApplied'])

    def test_different_original_lossless_png_encodings_preserve_separate_byte_hashes(self):
        d=ActorPrimaryPNGDomain(self,primary_compression=0);d.prepare_primary()
        with d.retained_pair()as(join,actor):value=join.proof()
        self.assertNotEqual(value['hashes']['primaryPNG'],value['hashes']['actorPNG'])
        self.assertEqual(value['hashes']['primaryRGBA'],value['hashes']['actorFullRGBA'])
        self.assertFalse(value['PNGEncodedByteEqualityRequired'])

    def test_one_independently_produced_actor_pixel_difference_cannot_be_normalized(self):
        d=ActorPrimaryPNGDomain(self,rect=(17,29,64,48),actor_pixel_change=True);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            before=counts(d);saved=originals(d)
            with self.assertRaises(NativeUIError):join.proof()
            self.assertEqual(before,counts(d));self.assertEqual(saved,originals(d))

    def test_wrong_recorded_crop_origin_refuses_without_relabeling_saved_png(self):
        d=ActorPrimaryPNGDomain(self,rect=(17,29,64,48))
        # A contradictory LOWER original measurement, before any native/input
        # owner exists. No saved PFS/OFS/PNG packet is changed to force success.
        d.rect[1]=30;d.prepare_primary()
        with d.retained_pair()as(join,actor):
            with self.assertRaises(NativeUIError):join.proof()

    def test_genuine_other_recorded_camera_projection_cannot_be_guessed_equal(self):
        def camera(frame):frame['camera']['projection'][0]=2
        d=ActorPrimaryPNGDomain(self,actor_change=camera);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            with self.assertRaises(NativeUIError):join.proof()

    def test_genuine_other_actor_source_extent_or_viewport_cannot_be_scaled(self):
        def extent(frame):frame['viewport']=[0,0,64,256]
        d=ActorPrimaryPNGDomain(self,actor_change=extent);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            with self.assertRaises(NativeUIError):join.proof()

    def test_foreign_saved_actor_reference_and_proxy_mapping_are_not_original_authority(self):
        d=ActorPrimaryPNGDomain(self);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            other=ActorPixelDomain(self)
            with other.pixels()as foreign:
                foreign.observe_original(1,TICKET);owner=foreign.actors.owner(1,historical=True)
                bad=SnapshotActorPrimaryPNGJoin(join.capture,join.provenance,join.actor,owner.original(),join.publication)
                with self.assertRaises(NativeUIError):bad.proof()
            class Proxy(dict):pass
            with self.assertRaises(NativeUIError):
                SnapshotActorPrimaryPNGJoin(join.capture,join.provenance,join.actor,Proxy(join.actor_original),join.publication)

    def test_same_bytes_new_primary_or_actor_original_inode_refuses_real_historical_read(self):
        for role in('primary','actor'):
            with self.subTest(role=role):
                d=ActorPrimaryPNGDomain(self);d.prepare_primary()
                with d.retained_pair()as(join,actor):
                    if role=='primary':path=join.capture.history('artifact',join.capture.state['artifact']).path()
                    else:
                        child=join.actor.child(historical=True);files=child.files();path=files.path(files.expand(child.state['proof']))
                    before=path.stat();raw=path.read_bytes();replacement=path.with_name(path.name+'.new-inode')
                    replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
                    self.assertNotEqual(before.st_ino,path.stat().st_ino)
                    with self.assertRaises(NativeUIError):join.proof()

    def test_uncertain_canonical_post_cannot_be_replayed_or_treated_as_pixel_receipt(self):
        d=ActorPrimaryPNGDomain(self);d.prepare_primary();d.drop_post=True
        with d.pixels()as actor:
            with self.assertRaises(PublicationPending):actor.observe_original(1,TICKET)
        with d.retained_pair(publish=False)as(join,actor):
            before=counts(d);saved=originals(d)
            with self.assertRaises(NativeUIError):join.proof()
            with self.assertRaises(NativeUIError):join.proof()
            self.assertEqual(before,counts(d));self.assertEqual(saved,originals(d))
        self.assertEqual(1,len(d.posts));self.assertEqual(1,len(d.pixel_queries))

    def test_real_historical_factory_reopens_exact_originals_with_all_live_ports_and_writes_forbidden(self):
        d=ActorPrimaryPNGDomain(self);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            first=join.proof();saved=originals(d);before=counts(d)
            def forbidden(*_a,**_k):raise AssertionError('Historical original join attempted live observation or write')
            with patch.object(PrivateFeatureState,'write',side_effect=forbidden),patch.object(type(d.actor_client),'request',forbidden),\
                    patch.object(d.actor.ctx.native,'send',forbidden),patch.object(d.primary.ctx.native,'send',forbidden):
                reopened=retained_original_pixel_join(join.capture,join.provenance.index,actor.actors,1)
                self.assertEqual(first,reopened.proof())
            self.assertEqual(saved,originals(d));self.assertEqual(before,counts(d))

    def test_later_frame_cannot_replace_selected_saved_cut_or_make_historical_original_fresh(self):
        d=ActorPrimaryPNGDomain(self);d.prepare_primary()
        with d.retained_pair()as(join,actor):
            first=join.proof();saved=originals(d);before=counts(d)
            frame=deepcopy(d.renderer.current.inputs);frame.update(frameInstance=uuid.uuid4().hex,frameIndex=frame['frameIndex']+1)
            d.renderer.current=DeclaredActorFrame(frame,d.renderer.current.rgba)
            self.assertFalse(d.renderer.original()['complete'])
            self.assertEqual(first,join.proof());self.assertEqual(saved,originals(d));self.assertEqual(before,counts(d))
            self.assertNotEqual(frame['frameInstance'],first['actorFrame']['frameInstance'])
            self.assertFalse(first['captureTemporalBracketingEstablished']or first['nativeAdmissionQualified'])
