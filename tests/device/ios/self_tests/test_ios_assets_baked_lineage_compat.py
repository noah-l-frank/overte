"""Literal baked image DTO grammar, existing actual PNG/mesh consumer.

The baked prerequisite is the existing declared unit source. This is consumer
compatibility, not a native producer/model parser/device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_images as images
from ios.adapters.assets_input_lineage import validate
from ios.adapters.assets_scene_facts import peer_model
from ios.self_tests.assets_scene_facts_fixture import pair
from ios.self_tests.test_ios_assets_model_images import bundle
from ios.self_tests.test_ios_graphics_measurements import RUN,TICKET,HOST,BINDING


class AssetsBakedLineageCompatibilityTests(unittest.TestCase):
    def test_existing_actual_PNG_mesh_compose_retains_legacy_positive_integer_bytes_above_new_bundle_limit(self):
        for size in (32768,32769,2**53-1):
            with self.subTest(bytes=size):
                frame,raw,policy,proof,marker=bundle();proof['bytes']=size;before=deepcopy(frame)
                result,subject=images.compose(RUN,TICKET,BINDING,frame,raw,policy,proof,marker,after_epoch=HOST)
                self.assertEqual(size,result['bodyBytes']);self.assertEqual(proof['readerId'],result['readerId'])
                self.assertEqual([7,19],result['renderItemIds']);self.assertEqual((128,96),subject.size);self.assertEqual(before,frame)
    def test_baked_literal_image_join_keeps_old_pid_equality_and_rejects_old_invalid_bytes_types_and_range(self):
        frame,raw,policy,proof,marker=bundle();proof['processId']=42.0
        result,_=images.compose(RUN,TICKET,BINDING,frame,raw,policy,proof,marker,after_epoch=HOST);self.assertEqual(42,result['processId'])
        for value in (True,0,-1,1.0,2**53):
            sample=bundle();sample[3]['bytes']=value
            with self.subTest(bytes=value),self.assertRaises(NativeUIError):
                images.compose(RUN,TICKET,BINDING,*sample,after_epoch=HOST)
    def test_actual_independent_peer_sources_keep_literal_baked_join_and_old_peer_byte_bound(self):
        primary,peer,proof=pair();proof['processId']=float(proof['processId'])
        # This field was an exact-schema prerequisite but not interpreted by
        # the old peer join. Its enclosing Parsed owner remains authoritative.
        proof['creationRequestId']='legacy-unused-prerequisite';result=peer_model(primary,peer,proof)
        self.assertFalse(result['renderedPixelsAvailable']);self.assertFalse(result['resourceRetirementAvailable'])
        proof['bytes']=32769
        with self.assertRaises(NativeUIError):peer_model(primary,peer,proof)
    def test_new_bundle_keeps_32768_limit_and_distinct_schema_while_common_baked_grammar_stays_positive(self):
        proof=bundle()[3];proof['bytes']=32769;validate(proof)
        item={k:v for k,v in proof.items() if k not in ('assetModelBakedInputProofVersion','bakeRequestId','outputPath')}
        prefix='/e2e-'+RUN+'/';item.update(assetModelBundleInputProofVersion=1,resource='gltf-bundle/main.gltf',path=prefix+'main.gltf',
            files=[dict(path=prefix+name,bytes=32769 if name=='main.gltf' else 1,sha256='e'*64) for name in ('main.gltf','mesh/triangle.bin','textures/checker.png')])
        with self.assertRaises(NativeUIError):validate(item)
        item['bytes']=32768;item['files'][0]['bytes']=32768;validate(item)


if __name__=='__main__':unittest.main()
