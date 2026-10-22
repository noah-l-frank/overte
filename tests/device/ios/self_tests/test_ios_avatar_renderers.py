"""Synthetic renderer/native boundaries; actual model/peer devices unqualified."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_renderers as renderers

SELF = '00000000-0000-4000-8000-000000000001'
PEER = '00000000-0000-4000-8000-000000000002'
ENTITY = '00000000-0000-4000-8000-000000000003'
RESOURCE = 'https://controlled.invalid/avatar.fst'
WEARABLE = 'https://controlled.invalid/gltf-bundle/main.gltf'


def packet():
    row = dict(sessionId=SELF, self=True, replicated=False, requestedUrl=RESOURCE, resourceUrl=RESOURCE,
        geometryLoaded=True, rigReady=True, shouldRender=True, addedToScene=True, targetScale=1., modelScale=1.,
        jointNames=['Root', 'Head', 'Hips'], jointIndices=dict(Root=0, Head=1, Hips=2), hipsIndex=2,
        rigPose=dict(rigId=123, capturedEpochMs=1700000000100, evaluationSequence=100,
                     animationsEnabled=True, graphLoaded=True, overrideActive=False, joints=[[0, 0, 0, 1, 0, 0, 0]]), externalPose=None,
        boundsReady=True,bounds=dict(corner=[1.,2.,3.],dimensions=[.7,1.9,.5]))
    peer = deepcopy(row); peer.update(sessionId=PEER, self=False, rigPose=None,
        externalPose=dict(externalPoseVersion=1, instance='d'*32, rigId=124, capturedEpochMs=1700000000100,
                          evaluationSequence=10, totalJoints=1, joints=[[0, 0, 0, 1, 0, 0, 0]]))
    inventory = dict(entityInventoryVersion=1, profile='native-entity-edit-wire-v1', treeInstance='f'*32,
        revisionBefore=1, revisionAfter=1, totalEntities=0, complete=True, entities=[])
    return dict(iosAvatarRenderersVersion=4, requestId='ios-'+'b'*32, runId='a'*32, instance='c'*32, sequence=1,
        processId=42, clockDomain='native-main-avatar-renderers', clockBefore=dict(epochMs=1700000000100, monotonicMs=100),
        clockAfter=dict(epochMs=1700000000110, monotonicMs=110),
        source=dict(complete=True, avatars=[row, peer], avatarEntities=[], tree=inventory))


def attach(value, parent=SELF):
    source = value['source']; source['avatarEntities'].append(dict(id=ENTITY, name='Custom wearable', type='Model',
        parentId=parent, parentJointIndex=2, relayParentJoints=False, visible=True, modelUrl=WEARABLE,
        resourceUrl=WEARABLE, modelAvailable=True, geometryLoaded=True, addedToScene=True, loadFailed=False,
        lastEditedEpochUs='1000'))
    source['tree'].update(totalEntities=1, entities=[dict(id=ENTITY, hostType='avatar', ready=True,
        createdEpochUs='1000', lastEditedEpochUs='1000', lastEditedAfterEpochUs='1000',
        semanticBytes=1234, semanticSha256='e'*64)])


class RendererTests(unittest.TestCase):
    def test_legacy_v1_is_read_without_invented_joint_indices_and_cannot_satisfy_current_peer_join(self):
        legacy = packet(); legacy['iosAvatarRenderersVersion'] = 1
        for row in legacy['source']['avatars']:
            del row['jointIndices']; del row['externalPose']; del row['bounds']; del row['boundsReady']; row['hipsIndex'] = 63
        renderers.original(legacy)
        self.assertNotIn('jointIndices', legacy['source']['avatars'][1])
        with self.assertRaises(NativeUIError): renderers.loaded(legacy, PEER, RESOURCE, 1., remote=True)
        with self.assertRaises(NativeUIError): renderers.evaluated(legacy, PEER, after_epoch=1700000000100, remote=True)
        current = packet(); attach(current)
        downgraded = deepcopy(current); downgraded['iosAvatarRenderersVersion'] = 1
        for row in downgraded['source']['avatars']:
            for key in ('jointIndices','externalPose','bounds','boundsReady'):del row[key]
        downgraded.update(requestId='ios-'+'d'*32, sequence=2)
        query = dict(schemaVersion=1, commandId=downgraded['requestId'], runId=downgraded['runId'], action=renderers.ACTION)
        with self.assertRaises(NativeUIError): renderers.validate(downgraded, query, 42, previous=current)

    def test_remote_original_external_pose_has_own_source_sequence_and_needs_no_AnimGraph(self):
        value = packet(); self.assertIsNone(value['source']['avatars'][1]['rigPose'])
        pose = renderers.external(value, PEER, after_epoch=1700000000100)
        self.assertEqual(10, pose['evaluationSequence']); self.assertNotIn('graphLoaded', pose)
        for changed in (dict(after_epoch=1700000000101),):
            with self.assertRaises(NativeUIError): renderers.external(value, PEER, **changed)
        legacy = deepcopy(value); legacy['iosAvatarRenderersVersion'] = 2
        for row in legacy['source']['avatars']:
            for key in ('externalPose','bounds','boundsReady'):del row[key]
        renderers.original(legacy)
        with self.assertRaises(NativeUIError): renderers.loaded(legacy, PEER, RESOURCE, 1., remote=True)
        with self.assertRaises(NativeUIError): renderers.external(legacy, PEER, after_epoch=1700000000100)
        with self.assertRaises(NativeUIError): renderers.external(value, SELF, after_epoch=1700000000100)

    def test_remote_render_bounds_require_current_actual_mesh_and_cannot_use_requested_scale_fallback(self):
        value=packet();self.assertEqual(dict(corner=[1.,2.,3.],dimensions=[.7,1.9,.5]),renderers.bounds(value,PEER,remote=True))
        value['source']['avatars'][1].update(boundsReady=False,bounds=None)
        renderers.original(value)
        with self.assertRaises(NativeUIError):renderers.bounds(value,PEER,remote=True)
        value=packet();value['source']['avatars'][1]['bounds']['dimensions'][1]=0
        with self.assertRaises(NativeUIError):renderers.original(value)
        legacy=packet();legacy['iosAvatarRenderersVersion']=3
        for row in legacy['source']['avatars']:del row['bounds'];del row['boundsReady']
        renderers.original(legacy)
        with self.assertRaises(NativeUIError):renderers.external(legacy,PEER,after_epoch=1700000000100)

    def test_new_remote_source_envelope_cannot_retime_or_rewrite_same_actual_external_copy(self):
        first = packet(); second = deepcopy(first); second.update(requestId='ios-'+'d'*32, sequence=2)
        second['clockBefore'] = dict(epochMs=1700000000200, monotonicMs=200)
        second['clockAfter'] = dict(epochMs=1700000000210, monotonicMs=210)
        query = dict(schemaVersion=1, commandId=second['requestId'], runId=second['runId'], action=renderers.ACTION)
        renderers.validate(second, query, 42, previous=first)
        for key, replacement in (('capturedEpochMs', 1700000000200), ('instance', '0'*32), ('rigId', 999),
                                  ('evaluationSequence', 9), ('totalJoints', 0), ('joints', [[0, 0, 0, 1, 1, 0, 0]])):
            changed = deepcopy(second); changed['source']['avatars'][1]['externalPose'][key] = replacement
            with self.subTest(key=key), self.assertRaises(NativeUIError): renderers.validate(changed, query, 42, previous=first)

    def test_actual_remote_model_and_scale_require_loaded_rig_scene_and_render_state(self):
        value = packet()
        self.assertEqual(PEER, renderers.loaded(value, PEER, RESOURCE, 1., remote=True)['sessionId'])
        for field, replacement in (('geometryLoaded', False), ('rigReady', False), ('addedToScene', False),
                                   ('shouldRender', False), ('modelScale', 1.5), ('targetScale', 1.5),
                                   ('resourceUrl', RESOURCE+'?retained=old'), ('replicated', True)):
            altered = deepcopy(value); row = altered['source']['avatars'][1]; row[field] = replacement
            if field == 'geometryLoaded': row['rigReady'] = False
            with self.subTest(field=field), self.assertRaises(NativeUIError):
                renderers.loaded(altered, PEER, RESOURCE, 1., remote=True)

    def test_remote_actor_cannot_be_satisfied_by_self_or_missing_avatar(self):
        value = packet()
        with self.assertRaises(NativeUIError): renderers.loaded(value, SELF, RESOURCE, 1., remote=True)
        value['source']['avatars'].pop()
        with self.assertRaises(NativeUIError): renderers.loaded(value, PEER, RESOURCE, 1., remote=True)

    def test_original_local_evaluated_pose_does_not_get_retimed_and_cannot_impersonate_remote_external_pose(self):
        value = packet()
        pose = renderers.evaluated(value, SELF, after_epoch=1700000000100)
        self.assertEqual(100, pose['evaluationSequence']); self.assertEqual(123, pose['rigId'])
        with self.assertRaises(NativeUIError): renderers.evaluated(value, SELF, after_epoch=1700000000101)
        with self.assertRaises(NativeUIError): renderers.evaluated(value, PEER, after_epoch=1700000000100, remote=True)
        altered = deepcopy(value); altered['source']['avatars'][0]['rigPose'] = None
        with self.assertRaises(NativeUIError): renderers.evaluated(altered, SELF, after_epoch=1700000000100)

    def test_actual_owned_wearable_uses_observed_creation_id_and_runtime_Hips(self):
        value = packet(); attach(value)
        self.assertTrue(renderers.wearable(value, ENTITY, SELF, WEARABLE))
        self.assertFalse(renderers.wearable(value, PEER, SELF, WEARABLE))
        value['source']['avatarEntities'][0]['parentJointIndex'] = 63
        with self.assertRaises(NativeUIError): renderers.wearable(value, ENTITY, SELF, WEARABLE)

    def test_remote_wearable_needs_actual_remote_parent_and_loaded_original_Model(self):
        value = packet(); attach(value, PEER)
        self.assertTrue(renderers.wearable(value, ENTITY, PEER, WEARABLE, remote=True))
        for field, replacement in (('parentId', SELF), ('modelUrl', WEARABLE+'?other=1'), ('geometryLoaded', False),
                                   ('addedToScene', False), ('loadFailed', True), ('relayParentJoints', True),
                                   ('visible', False), ('resourceUrl', '')):
            altered = deepcopy(value); altered['source']['avatarEntities'][0][field] = replacement
            with self.subTest(field=field), self.assertRaises(NativeUIError):
                renderers.wearable(altered, ENTITY, PEER, WEARABLE, remote=True)

    def test_hidden_or_detached_unowned_avatar_entities_cannot_disappear_from_inventory(self):
        first = packet(); attach(first)
        first['source']['avatarEntities'][0].update(visible=False, parentId='00000000-0000-0000-0000-000000000000')
        self.assertEqual(1, len(renderers.preserve_unowned(first, deepcopy(first), set())))
        after = packet()
        with self.assertRaises(NativeUIError): renderers.preserve_unowned(first, after, set())
        self.assertEqual({}, renderers.preserve_unowned(first, after, {ENTITY}))

    def test_partial_edited_duplicate_or_omitted_original_map_does_not_claim_absence(self):
        for fault in ('partial', 'omitted', 'duplicate', 'edited', 'hips'):
            value = packet(); attach(value)
            if fault == 'partial': value['source']['tree']['complete'] = False
            elif fault == 'omitted': value['source']['avatarEntities'] = []
            elif fault == 'duplicate': value['source']['avatars'].append(deepcopy(value['source']['avatars'][1]))
            elif fault == 'edited': value['source']['avatarEntities'][0]['lastEditedEpochUs'] = '1001'
            else: value['source']['avatars'][1]['hipsIndex'] = 1
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): renderers.original(value)

    def test_monotone_envelope_cannot_hide_tree_source_replacement_or_unchanged_revision_edit(self):
        first = packet(); attach(first)
        second = deepcopy(first); second.update(requestId='ios-'+'d'*32, sequence=2)
        second['clockBefore'] = dict(epochMs=1700000000200, monotonicMs=200)
        second['clockAfter'] = dict(epochMs=1700000000210, monotonicMs=210)
        query = dict(schemaVersion=1, commandId=second['requestId'], runId=second['runId'], action=renderers.ACTION)
        renderers.validate(second, query, 42, previous=first)
        for fault in ('treeBirth', 'sameRevisionEdit', 'selfReplacement', 'pid', 'stale'):
            altered = deepcopy(second)
            if fault == 'treeBirth': altered['source']['tree']['treeInstance'] = '0'*32
            elif fault == 'sameRevisionEdit': altered['source']['tree']['entities'][0]['semanticSha256'] = '0'*64
            elif fault == 'selfReplacement':
                altered['source']['avatars'][0]['self'] = False; altered['source']['avatars'][1]['self'] = True
            elif fault == 'pid': altered['processId'] = 43
            else: altered['clockAfter']['epochMs'] += 10000
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                renderers.validate(altered, query, 42, previous=first)


if __name__ == '__main__': unittest.main()
