"""Current caller DTOs and unchanged literal legacy originals stay distinct."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical
from ios.adapters import avatar_scripts as scripts,avatar_social_http as http,avatar_ui_work as work
from ios.adapters.avatar_code import pins
from ios.self_tests import avatar_callers2_fixture as current
from ios.self_tests.test_ios_avatar_scripts import packet as literal_scripts1,created as literal_created1
from ios.self_tests import test_ios_avatar_social_http as legacy_http
from ios.self_tests.test_ios_avatar_ui_work import component as literal_work1,timer as literal_timer1
from self_tests import test_avatar_social_provider as provider_tests
from feature_journeys.avatar_social_provider import USERS


class AvatarCallersV2Tests(unittest.TestCase):
    def test_actual_current_producers_emit_body_and_outer2_with_native_stack_fields(self):
        value=current.scripts2();current.timer2(value);raw=canonical(value);scripts.original(value)
        self.assertEqual(raw,canonical(value));self.assertEqual(2,value['iosAvatarScriptsVersion'])
        detail=value['source']['workers'][0]['avatar']['events'][0]['details']
        self.assertNotIn('callerChain',detail);self.assertEqual('a1'*16,detail['callerStackId'])
        self.assertTrue(value['source']['workers'][0]['avatar']['callerStacks'][0]['callerStack']['complete'])
        social=current.http2();raw=canonical(social);http.original(social);self.assertEqual(raw,canonical(social))
        self.assertTrue(http.events(social)['7'*32]['replies']['8'*32]['callbackRead'])

    def test_literal_legacy1_stays_exact_and_does_not_acquire_stack_fields(self):
        value=literal_scripts1();literal_created1(value);raw=canonical(value);scripts.original(value);self.assertEqual(raw,canonical(value))
        self.assertNotIn('callerStack',value['source']['workers'][0]['avatar']['events'][0]['details'])
        legacy=legacy_http.SocialHttpTests();legacy.setUp();raw=canonical(legacy.value);http.original(legacy.value);self.assertEqual(raw,canonical(legacy.value))
        timer=literal_work1();timer['timers']=[literal_timer1()];raw=canonical(timer);work.validate(timer,9000001300)
        self.assertEqual(raw,canonical(timer));self.assertNotIn('callerStack',timer['timers'][0])
        with self.assertRaises(NativeUIError):scripts.join_http_code(value,legacy.value,legacy.consumed(),pins(),require_actual=True)

    def test_new_outer_cannot_relabel_legacy_body_or_legacy_chain_into_a_current_stack(self):
        value=current.scripts2();current.timer2(value)
        for fault in ('body','ui-work','created-chain','outer-bool'):
            changed=deepcopy(value);worker=changed['source']['workers'][0]
            if fault=='body':worker['avatar']['avatarScriptVersion']=1
            elif fault=='ui-work':worker['uiWork']['avatarUiWorkVersion']=1
            elif fault=='created-chain':worker['avatar']['events'][0]['details']['callerChain']=['qrc:/scripts/system/pal.js']
            else:changed['iosAvatarScriptsVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.original(changed)
        legacy=literal_scripts1();legacy['iosAvatarScriptsVersion']=2
        with self.assertRaises(NativeUIError):scripts.original(legacy)

    def test_actual_script_frame_must_join_its_original_submitted_code_and_not_late_source(self):
        value=current.scripts2();current.timer2(value)
        for fault in ('hash','submission','foreign-module','first-observation'):
            changed=deepcopy(value);detail=changed['source']['workers'][0]['avatar']['callerStacks'][0]
            if fault=='hash':detail['callerStack']['frames'][0]['compiled']['sha256']='b'*64
            elif fault=='submission':changed['source']['workers'][0]['avatar']['code'][1]['submittedEpochMs']=current.EPOCH-30
            elif fault=='foreign-module':detail['callerModules'][1]['url']='qrc:/scripts/system/pal.js'
            else:detail['callerStack']['frames'][0]['compiled']['firstObservedEpochMs']=current.EPOCH+1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.original(changed)

    def test_http_created_and_actual_response_read_share_original_engine_and_compiled_script_identity(self):
        value=current.http2();http.original(value)
        for fault in ('engine','compiled','top-frame','missing-stack','legacy-chain'):
            changed=deepcopy(value);detail=changed['callerStacks'][1]
            if fault=='engine':detail['callerStack']['instance']='b'*32
            elif fault=='compiled':detail['callerStack']['frames'][0]['compiled']['sha256']='b'*64
            elif fault=='top-frame':detail['callerModules'][0]['frame']=1
            elif fault=='missing-stack':del detail['callerStack']
            else:changed['events'][0]['details']['callerChain']=['qrc:/scripts/modules/request.js']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):http.original(changed)

    def test_default_snapshot_timer_work_remains_exact_legacy1(self):
        from ios.adapters.snapshot_work import TIMER_SUFFIXES
        legacy=dict(snapshotTimerWorkVersion=1,instance='a'*32,complete=True,timers=[]);raw=canonical(legacy)
        work.validate(legacy,current.EPOCH,schema='snapshotTimerWorkVersion',suffixes=TIMER_SUFFIXES)
        self.assertEqual(raw,canonical(legacy));legacy['snapshotTimerWorkVersion']=2
        with self.assertRaises(NativeUIError):work.validate(legacy,current.EPOCH,schema='snapshotTimerWorkVersion',suffixes=TIMER_SUFFIXES)

    def test_actual_provider_bytes_and_current_native_callback_join_independently_pinned_modules(self):
        logic=provider_tests.SocialTests();logic.setUp()
        with logic.provider.response('GET',USERS,'filter=connections',b'',logic.tokens['primary']) as response:
            status,raw,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(raw),sha256=current.wire(raw)['sha256']))
        value=current.http2(raw=raw,response_id=response_id,run=provider_tests.RUN)
        status=logic.provider.snapshot(provider_tests.RUN)
        receipt=http.consumed_response(value,status,provider_instance=logic.provider.instance,owned_origin='https://owned.invalid',
            run=provider_tests.RUN,ticket=provider_tests.TICKET,role='primary',after_native_epoch=current.EPOCH-100,
            after_provider_epoch=1700000000000,after_event=0)
        owner=current.scripts2(run=provider_tests.RUN,capture_offset=200)
        actual=scripts.join_http_code(owner,value,receipt,pins(),require_actual=True)
        self.assertEqual(owner['source']['workers'][0]['membership'],actual['manager'])
        wrong=pins();wrong['/modules/request.js']['sha256']='b'*64
        with self.assertRaises(NativeUIError):scripts.join_http_code(owner,value,receipt,wrong,require_actual=True)

    def test_strong_ui_timer_cleanup_uses_actual_v8_bytes_and_retains_dispatch_requirements(self):
        before=current.scripts2();after=current.scripts2(capture_offset=200,sequence=2,request='ios-'+'9'*32)
        current.timer2(after,created_epoch=current.EPOCH+130);worker=after['source']['workers'][0]
        timer=worker['uiWork']['timers'][0];timer['destroyedEpochMs']=current.EPOCH+150
        result=work.drained_since(before,after,{'b'*32},pins(),require_actual=True)
        self.assertEqual(current.EPOCH+150,result['endpointEpochMs'])
        self.assertEqual({'d'*32},set(result['owned']['b'*32]))
        for fault in ('compiled','pending','early-birth'):
            changed=deepcopy(after);timer=changed['source']['workers'][0]['uiWork']['timers'][0]
            if fault=='compiled':changed['source']['workers'][0]['uiWork']['callerStacks'][0]['callerStack']['frames'][0]['compiled']['sha256']='b'*64
            elif fault=='pending':timer.update(fired=1,pendingDispatch=1,lastFiredEpochMs=current.EPOCH+145)
            else:timer['createdEpochMs']=current.EPOCH-10
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):work.drained_since(before,changed,{'b'*32},pins(),require_actual=True)

    def test_new_capture_cannot_reset_caller_version_for_the_same_native_birth(self):
        before=current.scripts2();after=current.scripts2(capture_offset=200,sequence=2,request='ios-'+'9'*32)
        after['iosAvatarScriptsVersion']=1;worker=after['source']['workers'][0]
        worker['avatar']['avatarScriptVersion']=worker['uiWork']['avatarUiWorkVersion']=1
        del worker['avatar']['callerStacks'];del worker['uiWork']['callerStacks']
        scripts.original(after)
        query=dict(schemaVersion=1,commandId=after['requestId'],action=scripts.ACTION,runId=after['runId'])
        with self.assertRaises(NativeUIError):scripts.validate(after,query,42,previous=before)


if __name__=='__main__':unittest.main()
