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
        jointNames=['Root', 'Head', 'Hips'], hipsIndex=2,
        rigPose=dict(rigId=123, capturedEpochMs=1700000000100, evaluationSequence=100,
                     animationsEnabled=True, graphLoaded=True, overrideActive=False, joints=[[0, 0, 0, 1, 0, 0, 0]]))
    peer = deepcopy(row); peer.update(sessionId=PEER, self=False)
    inventory = dict(entityInventoryVersion=1, profile='native-entity-edit-wire-v1', treeInstance='f'*32,
        revisionBefore=1, revisionAfter=1, totalEntities=0, complete=True, entities=[])
    return dict(iosAvatarRenderersVersion=1, requestId='ios-'+'b'*32, runId='a'*32, instance='c'*32, sequence=1,
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

    def test_original_remote_evaluated_pose_does_not_get_retimed_by_fresh_source_envelope(self):
        value = packet()
        pose = renderers.evaluated(value, PEER, after_epoch=1700000000100, remote=True)
        self.assertEqual(100, pose['evaluationSequence']); self.assertEqual(123, pose['rigId'])
        with self.assertRaises(NativeUIError): renderers.evaluated(value, PEER, after_epoch=1700000000101, remote=True)
        altered = deepcopy(value); altered['source']['avatars'][1]['rigPose'] = None
        with self.assertRaises(NativeUIError): renderers.evaluated(altered, PEER, after_epoch=1700000000100, remote=True)

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
