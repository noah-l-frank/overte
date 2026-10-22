"""Synthetic native source counterexamples; no compiler or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest

from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import payload
from ios.adapters import create_state as source, create_product_state as product

RUN = 'a'*32
ID = '11111111-1111-4111-8111-111111111111'
ROOT = '22222222-2222-4222-8222-222222222222'
DOMAIN = '33333333-3333-4333-8333-333333333333'
EPOCH = 1700000000000
SESSION = '44444444-4444-4444-8444-444444444444'


def packet():
    return dict(iosCreateStateVersion=1, requestId='ios-'+'b'*32, runId=RUN, instance='c'*32, sequence=1,
        processId=42, clockDomain='native-main-create', clockBefore=dict(epochMs=EPOCH, monotonicMs=0),
        clockAfter=dict(epochMs=EPOCH+2, monotonicMs=2), source=dict(complete=True, tabletShown=False,
            domainId=DOMAIN, canRez=True, canRezTmp=False, roots=[], entities=[], tree=dict(entityInventoryVersion=1,
                profile='native-entity-edit-wire-v1', treeInstance='d'*32, revisionBefore=0, revisionAfter=0,
                totalEntities=0, complete=True, entities=[])))


def add_editor(value, *, selected=None, error=False, text=''):
    value['source']['tabletShown'] = True
    value['source']['roots'].append(dict(id=ROOT, destroyed=False, kind='editor', visible=True, active=True,
        page=dict(profile='native-create-v1', tab=2, selectedIds=selected or [], statusError=error, statusText=text,
                  componentSourceSha256='e'*64, inputReady=False), changed={}, voxelSettings={}, numericFocus=False))


def add_model(value):
    raw = b'actual original editable-wire seam'
    row = dict(id=ID, hostType='domain', ready=True, createdEpochUs=str(EPOCH*1000), lastEditedEpochUs=str(EPOCH*1000+1),
               lastEditedAfterEpochUs=str(EPOCH*1000+1), semanticBytes=len(raw), semanticSha256=hashlib.sha256(raw).hexdigest())
    value['source']['tree'].update(revisionBefore=1, revisionAfter=1, totalEntities=1, entities=[row])
    entity = {key: row[key] for key in ('id', 'hostType', 'createdEpochUs', 'lastEditedEpochUs')}
    entity.update(name='e2e-'+RUN+'-model', type='Model', shape='', dimensions=[1, 1, 1], modelURL='http://fixture/model.gltf',
        textures='', lastEditedBy='44444444-4444-4444-8444-444444444444', locked=False, visible=True, voxels={},
        model=dict(present=True, loaded=True, addedToScene=True, failed=False, textures=[]))
    value['source']['entities'].append(entity); return entity


def version2(value):
    value['iosCreateStateVersion'] = 2; value['source']['localSessionId'] = SESSION
    value['source']['view'] = dict(position=[0, 0, 0], rotation=[0, 0, 0, 1], fieldOfViewDegrees=60,
                                   aspectRatio=1, perspective=True, uiWidth=768, uiHeight=768)
    for row in value['source']['entities']: row.update(position=[0, 0, -4], rotation=[0, 0, 0, 1])
    return value


def remap(row):
    raw = payload('checker.png', RUN, 'f'*32)[1]; url = 'http://fixture/owned/checker.png'
    row['textures'] = json.dumps({'checker.png': url})
    row['model']['textures'] = [dict(material=0, channel=0, slot='checker.png', url=url, loaded=True,
        original=dict(textureOriginalVersion=1, instance='f'*32, url=url, complete=True, consumptions=[dict(
            sequence=1, consumedEpochMs=EPOCH, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            base64=base64.b64encode(raw).decode())]))]


class CreateStateTests(unittest.TestCase):
    def test_state3_adds_original_marker_properties_without_changing_legacy_state2(self):
        value = version2(packet()); row = add_model(value); version2(value)
        source.original(value); value['iosCreateStateVersion'] = 3
        with self.assertRaises(NativeUIError): source.original(value)
        row.update(sourceUrl='',userData='',collisionless=False); source.original(value)
        row['sourceUrl'] = 'qrc:/scripts/original-marker.html'; row['userData'] = '{"actual":true}'
        self.assertEqual(row['sourceUrl'],source.live(value)['entities'][0]['sourceUrl'])

    def test_complete_empty_native_tree_is_only_state_and_keeps_original_clocks(self):
        value = packet(); self.assertIs(value, source.original(value))
        self.assertEqual(dict(objects=[], editor=False, picker=False, error='none', canRez=True, selection=[],
                              textured=False, voxelValue=0), product.project(value, RUN, []))
        self.assertEqual(EPOCH, value['clockBefore']['epochMs']); self.assertNotIn('performed', value)

    def test_property_override_alone_is_not_actual_texture_effect(self):
        value = packet(); row = add_model(value); add_editor(value, selected=[ID]); row['textures'] = '{"checker.png":"http://fixture/checker.png"}'
        with self.assertRaises(NativeUIError): product.project(value, RUN, [ID])
        remap(row); observed = product.project(value, RUN, [ID]); self.assertTrue(observed['textured'])
        self.assertEqual(['model'], observed['selection'])

    def test_wrong_slot_loaded_url_missing_original_or_changed_original_bytes_refuse_effect(self):
        for fault in ('slot', 'url', 'pending', 'missing', 'corrupt', 'foreign-content', 'not-added', 'failed'):
            value = packet(); row = add_model(value); remap(row); texture = row['model']['textures'][0]
            if fault == 'slot': texture['slot'] = 'wrong.png'
            elif fault == 'url': texture['url'] += '?foreign'
            elif fault == 'pending': texture['loaded'] = False
            elif fault == 'missing': texture['original']['consumptions'] = []
            elif fault == 'corrupt': texture['original']['consumptions'][0]['sha256'] = '0'*64
            elif fault == 'foreign-content':
                raw = b'wrong downloaded bytes'; texture['original']['consumptions'][0].update(
                    base64=base64.b64encode(raw).decode(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            elif fault == 'not-added': row['model']['addedToScene'] = False
            else: row['model']['failed'] = True
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, ValueError)): product.project(value, RUN, [ID])

    def test_matching_old_basename_is_not_adopted_as_an_owned_creation(self):
        before = packet(); add_model(before); version2(before); after = deepcopy(before)
        after.update(requestId='ios-'+'f'*32, sequence=2); add_editor(after, selected=[ID])
        with self.assertRaises(NativeUIError): product.adopt_created(before, after, [], RUN)
        before = version2(packet()); created = product.adopt_created(before, after, [], RUN)
        self.assertEqual(ID, created['id']); self.assertEqual([], before['source']['entities'])

    def test_foreign_actor_entity_or_actual_non_domain_host_cannot_establish_ownership(self):
        before = version2(packet()); after = packet(); after.update(requestId='ios-'+'f'*32, sequence=2)
        add_model(after); version2(after); add_editor(after, selected=[ID]); actor = deepcopy(after)
        actor['source']['domainId'] = '55555555-5555-4555-8555-555555555555'
        with self.assertRaises(NativeUIError): product.adopt_created(before, after, [], RUN, actor=actor)
        after['source']['entities'][0]['hostType'] = 'avatar'; after['source']['tree']['entities'][0]['hostType'] = 'avatar'
        with self.assertRaises(NativeUIError): product.adopt_created(before, after, [], RUN)

    def test_denial_requires_actual_error_and_both_rez_permissions_are_measured(self):
        value = packet(); value['source'].update(canRez=False, canRezTmp=False)
        add_editor(value, error=True, text=product.PERMISSION_ERROR)
        self.assertEqual('permission-denied', product.project(value, RUN, [])['error'])
        self.assertFalse(product.project(value, RUN, [])['canRez'])
        # Restoring permission alone does not erase the actual old status label.
        value['source']['canRezTmp'] = True
        observed = product.project(value, RUN, [])
        self.assertEqual('permission-denied', observed['error']); self.assertTrue(observed['canRez'])
        value['source']['roots'][0]['page']['statusText'] = 'Unknown unrelated failure'
        with self.assertRaises(NativeUIError): product.project(value, RUN, [])

    def test_native_pid_birth_counter_hidden_root_destruction_and_original_tree_are_preserved(self):
        before = packet(); add_editor(before)
        after = deepcopy(before); after.update(sequence=2, requestId='ios-'+'f'*32)
        after['clockBefore'] = dict(epochMs=EPOCH+3, monotonicMs=3); after['clockAfter'] = dict(epochMs=EPOCH+4, monotonicMs=4)
        after['source']['roots'][0] = dict(id=ROOT, destroyed=True)
        source.validate(after, dict(schemaVersion=1, action=source.ACTION, runId=RUN, commandId=after['requestId']), 42, previous=before)
        for fault in ('revived', 'dropped', 'birth', 'counter', 'pid', 'domain'):
            new = deepcopy(after); new.update(sequence=3, requestId='ios-'+'e'*32)
            if fault == 'revived': new['source']['roots'] = deepcopy(before['source']['roots'])
            elif fault == 'dropped': new['source']['roots'] = []
            elif fault == 'birth': new['instance'] = 'e'*32
            elif fault == 'counter': new['sequence'] = 2
            elif fault == 'pid': new['processId'] = 43
            else: new['source']['domainId'] = '55555555-5555-4555-8555-555555555555'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                source.validate(new, dict(schemaVersion=1, action=source.ACTION, runId=RUN, commandId=new['requestId']), 42, previous=after)

    def test_partial_map_wrong_identity_or_native_future_clock_cannot_prove_empty(self):
        for fault in ('partial', 'rows', 'future'):
            value = packet()
            if fault == 'partial': value['source']['complete'] = False
            elif fault == 'rows': value['source']['tree']['totalEntities'] = 1
            else: value['clockAfter']['epochMs'] += 5000
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): product.project(value, RUN, [])


if __name__ == '__main__': unittest.main()
