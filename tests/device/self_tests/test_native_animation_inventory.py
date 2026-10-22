"""Passive cache/compiled-source joins over synthetic original boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.native_animation_inventory import NativeAnimationInventory,command,validate
from adapters.native_animation_source import NAMES
from adapters.emote_animation_readiness import ready
from adapters.normal_ui import NativeUIError
from test_native_animation_source import sample
from test_emote_rig_measurements import IncludedRigPackets

ROOT=Path(__file__).resolve().parents[3]


class InventoryBoundary:
    def __init__(self,root='file:///actual/configured/cache/scripts'):
        self.root=root;self.clock=0.;self.epoch=20000;self.sequence=0;self.value=None;self.commands=[]
        self.okay=True;self.ignored=False;self.mutate=None;self.resources=[]
        for name in NAMES:
            clip=sample(name);url=root+'/system/assets/animations/'+name+'.fbx'
            original=deepcopy(clip['assetSource']['model']);original['sourceUrlSha256']=hashlib.sha256(url.encode()).hexdigest()
            self.resources.append(dict(resourceInstance=clip['assetSource']['resourceInstance'],urlSha256=original['sourceUrlSha256'],
                loaded=True,failed=False,registrySlots=1,model=original))
        self.resources.sort(key=lambda row:row['resourceInstance'])

    def sleep(self,seconds):self.clock+=seconds

    def send(self,request):
        command(request,ios=request['commandId'].startswith('ios-'));self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.value=dict(animationInventoryVersion=1,commandId=request['commandId'],instance='a'*32,sequence=self.sequence,
            processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(complete=True,registrySlots=sum(row['registrySlots'] for row in self.resources),expiredSlots=0,resources=deepcopy(self.resources)))
        if self.mutate:self.mutate(self.value)

    def original(self):return json.dumps(self.value) if self.value is not None else ''

    def reader(self,**options):
        return NativeAnimationInventory(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)


def group(root='file:///actual/configured/cache/scripts'):
    model=IncludedRigPackets(root=root);source=model.group(model.native(20000,baseline=True));source.pop('native')
    boundary=InventoryBoundary(root);source['inventory']=boundary.reader().read(0);return source


class AnimationInventoryTests(unittest.TestCase):
    def test_passive_query_has_no_url_name_pin_or_load_and_returns_independent_originals(self):
        source=InventoryBoundary();reader=source.reader();first=reader.read(0);reader.read(1)
        self.assertEqual(12,len(first['source']['resources']));self.assertNotEqual(first['commandId'],reader.last['commandId'])
        self.assertTrue(all(set(row)=={'schemaVersion','commandId','action'} for row in source.commands))
        first['source']['resources'].clear();self.assertEqual(12,len(reader.last['source']['resources']))

    def test_real_duplicate_registry_slots_and_expired_entries_are_counted_without_duplicate_resources(self):
        source=InventoryBoundary();source.resources[0]['registrySlots']=2
        source.mutate=lambda value:value['source'].update(expiredSlots=3,registrySlots=16)
        value=source.reader().read(0);self.assertEqual(12,len(value['source']['resources']));self.assertEqual(16,value['source']['registrySlots'])

    def test_empty_actual_cache_can_be_observed_but_is_not_emote_readiness(self):
        source=InventoryBoundary();source.resources=[];self.assertEqual([],source.reader().read(0)['source']['resources'])
        value=group();value['inventory']['source'].update(resources=[],registrySlots=0)
        with self.assertRaises(NativeUIError):ready(value,pid=31,epoch=20000)

    def test_closed_grammar_rejects_desired_content_and_invalid_types_without_queries(self):
        request=dict(schemaVersion=1,commandId='a'*32,action='feature-animation-inventory-observe');command(request)
        for edit in (dict(schemaVersion=True),dict(commandId='a'*32+'\n'),dict(url='qrc:/expected.fbx'),dict(expectedSha256='f'*64),dict(action='prefetch')):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):command(request|edit)
        for cursor in (True,-1,1000000001):
            source=InventoryBoundary()
            with self.assertRaises(NativeUIError):source.reader().read(cursor)
            self.assertEqual([],source.commands)

    def test_incomplete_truncated_duplicate_or_incoherent_inventory_never_qualifies(self):
        for fault in ('missing','incomplete','slots','expired','duplicate','order','too-many','version','future-model','unknown'):
            source=InventoryBoundary()
            def mutate(value):
                current=value['source']
                if fault=='missing':current.clear();current['complete']=False
                elif fault=='incomplete':current['complete']=False
                elif fault=='slots':current['registrySlots']-=1
                elif fault=='expired':current['expiredSlots']=True
                elif fault=='duplicate':current['resources'].append(deepcopy(current['resources'][0]));current['registrySlots']+=1
                elif fault=='order':current['resources'].reverse()
                elif fault=='too-many':current['registrySlots']=1025
                elif fault=='version':value['animationInventoryVersion']=True
                elif fault=='future-model':current['resources'][0]['model']['parsedEpochMs']=20001
                else:current['expectedReady']=True
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(0)

    def test_foreign_stale_reused_nonce_or_regressed_native_cursor_does_not_replace_last(self):
        for edit in (dict(commandId='b'*32),dict(instance='b'*32),dict(processId=32),dict(capturedEpochMs=18000),
            dict(requestedEpochMs=19999),dict(sequence=1),dict(sequence=True)):
            source=InventoryBoundary();reader=source.reader();first=reader.read(0)
            source.mutate=lambda value:value.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(1)
            self.assertEqual(first,reader.last)

    def test_original_model_and_resource_url_identities_survive_absent_intermediate_rows(self):
        for fault in ('model','url'):
            source=InventoryBoundary();reader=source.reader();reader.read(0);removed=source.resources.pop(0);reader.read(1)
            if fault=='model':removed['model']['sha256']='f'*64
            else:removed['urlSha256']='f'*64
            source.resources.insert(0,removed)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(2)
            self.assertEqual(2,reader.last['sequence'])

    def test_slow_acquisition_final_validation_or_guard_loss_cannot_return_fresh_inventory(self):
        source=InventoryBoundary();source.mutate=lambda value:setattr(source,'clock',2)
        with self.assertRaises(NativeUIError):source.reader().read(0)
        source=InventoryBoundary();reader=source.reader();accept=reader.accept
        def slow(value):
            result=accept(value);source.clock+=2;return result
        reader.accept=slow
        with self.assertRaises(NativeUIError):reader.read(0)
        self.assertIsNone(reader.last)
        source=InventoryBoundary();source.okay=False
        with self.assertRaises(NativeUIError):source.reader().read(0)
        self.assertEqual([],source.commands)

    def test_missing_or_oversized_result_uses_one_query_and_no_resource_repair(self):
        source=InventoryBoundary();source.ignored=True
        with self.assertRaises(NativeUIError):source.reader().read(0)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5.1)
        source=InventoryBoundary();reader=source.reader();reader.original=lambda:'x'*262145
        with self.assertRaises(NativeUIError):reader.read(0)
        self.assertEqual(1,len(source.commands))

    def test_restore_is_historical_only_and_preserves_exact_birth_and_cursor(self):
        source=InventoryBoundary();original=source.reader().read(0);reader=source.reader();reader.restore(original)
        self.assertEqual(1,len(source.commands));next_value=reader.read(1);self.assertEqual(2,next_value['sequence'])
        with self.assertRaises(NativeUIError):reader.restore(next_value)
        with self.assertRaises(NativeUIError):source.reader(ios=True).restore(original)

    def test_all_twelve_original_cached_models_join_current_configured_compiled_source(self):
        for root in ('file:///actual/configured/cache/scripts','qrc:/scripts'):
            value=group(root);before=deepcopy(value);result=ready(value,pid=31,epoch=20000)
            self.assertEqual(NAMES,tuple(row['name'] for row in result['resources']));self.assertEqual(before,value)
            self.assertEqual(value['inventory']['source']['resources'],sorted([row['resource'] for row in result['resources']],key=lambda row:row['resourceInstance']))

    def test_missing_pending_failed_ambiguous_wrong_content_or_foreign_url_is_not_ready(self):
        for fault in ('missing','pending','failed','unknown-model','wrong-bytes','wrong-url','ambiguous','skip-parser'):
            value=group();source=value['inventory']['source'];row=source['resources'][0]
            if fault=='missing':source['resources'].pop(0);source['registrySlots']-=1
            elif fault=='pending':row['loaded']=False
            elif fault=='failed':row.update(loaded=False,failed=True)
            elif fault=='unknown-model':row['model']=None
            elif fault=='wrong-bytes':row['model']['sha256']='f'*64
            elif fault=='wrong-url':row['model']['sourceUrlSha256']='f'*64
            elif fault=='ambiguous':
                duplicate=deepcopy(row);duplicate['resourceInstance']='f'*32;source['resources'].append(duplicate);source['registrySlots']+=1
            else:row['model']['parser']='fbx-skip-unused-curves-v1'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):ready(value,pid=31,epoch=20000)

    def test_old_foreign_or_unbracketed_cache_cannot_borrow_current_source(self):
        for edit in (dict(instance='b'*32),dict(processId=32),dict(requestedEpochMs=19999),dict(capturedEpochMs=20001)):
            value=group();value['inventory'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):ready(value,pid=31,epoch=20001)

    def test_native_inventory_never_gets_or_creates_resources_and_reads_on_owner_thread(self):
        source=(ROOT/'libraries/animation/src/AnimationCache.cpp').read_text()
        body=source.split('QVariantMap AnimationCache::featureResourceObservation() {')[1].split('QVariantMap Animation::featureResourceObservation() const')[0]
        for forbidden in ('getAnimation(','getResource(','ensureLoading(','_resources.insert','_resources['):self.assertNotIn(forbidden,body)
        for required in ('QThread::currentThread()!=app->thread()','animation->thread()!=QThread::currentThread()',
            'original=_resources','_resources!=original','slot.first.isNull()==slot.second','toStrongRef()',
            'slots>1024','rows.size()>=256'):self.assertIn(required,body)
        bridge=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text().split('QVariantMap TestScriptingInterface::featureAnimationInventory(')[1].split('QVariantMap TestScriptingInterface::featureScriptRoots(')[0]
        self.assertLess(bridge.index('DependencyManager::isSet<AnimationCache>()'),bridge.index('DependencyManager::get<AnimationCache>()'))
        self.assertIn('Qt::BlockingQueuedConnection',bridge)


if __name__=='__main__':unittest.main()
