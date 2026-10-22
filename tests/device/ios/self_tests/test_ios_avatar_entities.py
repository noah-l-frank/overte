"""Explicit native-return DTOs and independent actual renderer/code joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_entities as entities
from ios.self_tests import test_ios_avatar_scripts as scripts
from ios.self_tests import test_ios_avatar_renderers as renderers

APP='qrc:/scripts/system/avatarapp.js'
EXPECTED={'/system/avatarapp.js':dict(codeUnits=32,sha256='1'*64)}


def packet():
    code=scripts.packet();worker=code['source']['workers'][0]
    worker['avatar']['code'][0].update(url=APP,**EXPECTED['/system/avatarapp.js'])
    who=dict(callerVersion=1,method='addEntity',sequence=1,invokedEpochMs=1700000000120,
        manager=deepcopy(worker['membership']),code=deepcopy(worker['code']),callerChain=[APP],
        avatarCode={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')})
    detail=dict(entityId=renderers.ENTITY,hostType='avatar',modelUrl=renderers.WEARABLE,parentId=renderers.SELF,
        parentJointIndex=2,owningAvatarId=entities.avatar_renderers.SELF,lastEditedEpochUs='1000',localTreeAvailable=True)
    event=dict(sequence=1,eventId='3'*32,kind='add-returned',clock=dict(epochMs=1700000000130,monotonicMs=130),caller=who,entity=detail)
    value=dict(iosAvatarEntitiesVersion=1,requestId='ios-'+'4'*32,runId='a'*32,instance='5'*32,sequence=1,processId=42,
        clockDomain='native-main-avatar-entities',clockBefore=dict(epochMs=1700000000200,monotonicMs=200),
        clockAfter=dict(epochMs=1700000000210,monotonicMs=210),
        source=dict(avatarEntitiesLedgerVersion=1,instance='6'*32,complete=True,events=[event]))
    before=renderers.packet();after=deepcopy(before);renderers.attach(after)
    for value2 in (after,code):
        value2['clockBefore'].update(epochMs=1700000000200,monotonicMs=200)
        value2['clockAfter'].update(epochMs=1700000000210,monotonicMs=210)
    return value,before,after,code


def join(value,before,after,code):
    return entities.created(value,before,after,code,EXPECTED,avatar_id=renderers.SELF,resource=renderers.WEARABLE,after_epoch=1700000000120)


class AvatarEntityTests(unittest.TestCase):
    def test_actual_returned_UUID_precedes_renderer_join_and_retains_original_self_sentinel(self):
        value,before,after,code=packet();result=join(value,before,after,code)
        self.assertEqual(renderers.ENTITY,result['entity']['entityId'])
        self.assertEqual(entities.avatar_renderers.SELF,result['entity']['owningAvatarId'])
        self.assertNotEqual(renderers.SELF,result['entity']['owningAvatarId'])
        self.assertEqual('addEntity',result['caller']['method'])

    def test_loaded_matching_URL_never_supplies_a_missing_original_creation_or_adopts_preexisting_ID(self):
        value,before,after,code=packet();value['source']['events']=[]
        with self.assertRaises(NativeUIError):join(value,before,after,code)

    def test_original_returned_ownership_can_be_retained_before_pending_geometry_without_claiming_render_success(self):
        value,before,after,code=packet();after['source']['avatarEntities'][0]['geometryLoaded']=False
        owned=entities.returned(value,before,code,EXPECTED,avatar_id=renderers.SELF,resource=renderers.WEARABLE,after_epoch=1700000000120)
        self.assertEqual(renderers.ENTITY,owned['entity']['entityId'])
        with self.assertRaises(NativeUIError):join(value,before,after,code)

    def test_separate_manager_checks_its_actual_modules_against_reviewed_values_without_requiring_another_manager_code(self):
        from ios.adapters.avatar_code import for_worker
        value,_before,_after,code=packet();manager=value['source']['events'][0]['caller']['manager']['instance']
        reviewed=deepcopy(EXPECTED)|{'/system/pal.js':dict(codeUnits=10,sha256='2'*64)}
        self.assertEqual(EXPECTED,for_worker(code,manager,reviewed,required={'/system/avatarapp.js'}))
        changed=deepcopy(code);changed['source']['workers'][0]['avatar']['code'][0]['sha256']='0'*64
        with self.assertRaises(NativeUIError):for_worker(changed,manager,reviewed,required={'/system/avatarapp.js'})
        value,before,after,code=packet();renderers.attach(before)
        with self.assertRaises(NativeUIError):join(value,before,after,code)

    def test_original_return_is_not_loaded_geometry_or_actual_Hips_parenting(self):
        for fault in ('model','geometry','hips','owner','parent','tree','late'):
            value,before,after,code=packet();event=value['source']['events'][0]
            if fault=='model':after['source']['avatarEntities'][0]['resourceUrl']='https://controlled.invalid/other.gltf'
            elif fault=='geometry':after['source']['avatarEntities'][0]['geometryLoaded']=False
            elif fault=='hips':after['source']['avatarEntities'][0]['parentJointIndex']=63
            elif fault=='owner':event['entity']['owningAvatarId']=renderers.PEER
            elif fault=='parent':event['entity']['parentId']=renderers.PEER
            elif fault=='tree':event['entity']['localTreeAvailable']=False
            else:event['clock']['epochMs']=1700000000119
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):join(value,before,after,code)

    def test_actual_caller_evaluated_module_and_manager_are_independent_of_entity_properties(self):
        for fault in ('code','manager','call-chain','late-code','unfinished','pid','foreign-run'):
            value,before,after,code=packet();event=value['source']['events'][0]
            if fault=='code':event['caller']['avatarCode']['code'][0]['sha256']='0'*64
            elif fault=='manager':event['caller']['manager']['instance']='0'*32
            elif fault=='call-chain':event['caller']['callerChain']=['https://foreign.invalid/avatarapp.js']
            elif fault=='late-code':event['caller']['avatarCode']['code'][0]['submittedEpochMs']=1700000000121
            elif fault=='unfinished':value['source']['complete']=False
            elif fault=='pid':value['processId']=43
            else:value['runId']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):join(value,before,after,code)

    def test_new_envelope_never_rewrites_or_truncates_original_returns_and_caller_sequences(self):
        first,*_=packet();second=deepcopy(first);second.update(sequence=2,requestId='ios-'+'7'*32)
        for clock in (second['clockBefore'],second['clockAfter']):clock['epochMs']+=100;clock['monotonicMs']+=100
        query=dict(schemaVersion=1,commandId=second['requestId'],action=entities.ACTION,runId=second['runId'])
        entities.validate(second,query,42,previous=first)
        for fault in ('id','truncate','time','code','birth','version'):
            changed=deepcopy(second)
            if fault=='id':changed['source']['events'][0]['entity']['entityId']=renderers.PEER
            elif fault=='truncate':changed['source']['events']=[]
            elif fault=='time':changed['source']['events'][0]['clock']['epochMs']+=1
            elif fault=='code':changed['source']['events'][0]['caller']['avatarCode']['code'][0]['sha256']='0'*64
            elif fault=='birth':changed['source']['instance']='0'*32
            else:changed['iosAvatarEntitiesVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):entities.validate(changed,query,42,previous=first)

    def test_recursive_actual_deletions_share_one_original_call_but_no_creation_UUID_can_repeat(self):
        value,*_=packet();original=value['source']['events'][0]
        for index,entity_id in enumerate((renderers.ENTITY,renderers.PEER),2):
            event=deepcopy(original);event.update(sequence=index,eventId=f'{index+7:032x}',kind='deleted-local')
            event['caller'].update(method='deleteEntity',sequence=2);event['entity']['entityId']=entity_id
            event['clock'].update(epochMs=1700000000140,monotonicMs=140);value['source']['events'].append(event)
        entities.original(value)
        changed=deepcopy(value);changed['source']['events'][2]['caller']['sequence']=1
        with self.assertRaises(NativeUIError):entities.original(changed)
        changed=deepcopy(value);duplicate=deepcopy(original);duplicate.update(sequence=4,eventId='9'*32)
        duplicate['caller']['sequence']=3;duplicate['clock'].update(epochMs=1700000000150,monotonicMs=150)
        changed['source']['events'].append(duplicate)
        with self.assertRaises(NativeUIError):entities.original(changed)

    def test_native_hooks_retain_actual_product_ordering_and_do_not_source_ids_from_query(self):
        root=Path(__file__).resolve().parents[4]
        entity=(root/'libraries/entities/src/EntityScriptingInterface.cpp').read_text()
        add=entity[entity.index('QUuid EntityScriptingInterface::addEntityInternal'):entity.index('bool EntityScriptingInterface::addLocalEntityCopy')]
        self.assertLess(add.index('queueEntityMessage(PacketType::EntityAdd'),add.index('AvatarEntityObservation::instance().event'))
        delete=entity[entity.index('void EntityScriptingInterface::deleteEntity'):entity.index('QString EntityScriptingInterface::getEntityType')]
        self.assertLess(delete.index('deleteEntitiesByPointer'),delete.index('AvatarEntityObservation::instance().event'))
        self.assertLess(delete.index('clearAvatarEntityInternal'),delete.index('AvatarEntityObservation::instance().event'))
        self.assertIn('ScriptManager::featureNativeCallContext()',add);self.assertIn('ScriptManager::featureNativeCallContext()',delete)


if __name__=='__main__':unittest.main()
