"""Explicit native code/Qt timer boundary; no native compilation or device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_scripts as scripts
from ios.self_tests import test_ios_avatar_social_http as http_tests

RUN,MANAGER,TIMER='a'*32,'b'*32,'c'*32
PROTOCOL='qrc:/scripts/system/libraries/peopleConnection.js'


def packet():
    code='explicit synthetic submitted code'
    source=dict(sequence=1,url=PROTOCOL,submittedEpochMs=1700000000002,encoding='utf-16le-code-units',
        codeUnits=len(code),sha256=hashlib.sha256(code.encode('utf-16le')).hexdigest())
    worker=dict(membership=dict(instance=MANAGER,assigned=True,url='qrc:/scripts/defaultScripts.js',loadGeneration=1,assignedEpochMs=1700000000000),
        code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=10,sha256='d'*64,submittedEpochMs=1700000000001),
        running=True,stopping=False,finished=False,done=False,
        avatar=dict(avatarScriptVersion=1,instance='e'*32,complete=True,code=[source],events=[]))
    return dict(iosAvatarScriptsVersion=1,requestId='ios-'+'f'*32,runId=RUN,instance='0'*32,sequence=1,processId=42,
        clockDomain='native-main-avatar-scripts',clockBefore=dict(epochMs=1700000000100,monotonicMs=100),
        clockAfter=dict(epochMs=1700000000110,monotonicMs=110),source=dict(complete=True,revision=1,workers=[worker]))


def event(value,kind,detail=None,timer=TIMER):
    ledger=value['source']['workers'][0]['avatar'];index=len(ledger['events'])+1
    ledger['events'].append(dict(sequence=index,timerId=timer,kind=kind,capturedEpochMs=1700000000010+index,
                                details={} if detail is None else detail))


def created(value,timer=TIMER):
    event(value,'created',dict(handle=1,callerChain=['qrc:/scripts/system/pal.js',PROTOCOL],active=True,
        singleShot=True,intervalMs=250,remainingMs=250),timer=timer)


def next_packet(value,*,workers=None,revision=None):
    value=deepcopy(value);value.update(requestId='ios-'+f'{value["sequence"]:032x}',sequence=value['sequence']+1)
    for clock in (value['clockBefore'],value['clockAfter']):
        clock['epochMs']+=100;clock['monotonicMs']+=100
    if workers is not None:value['source']['workers']=workers
    if revision is not None:value['source']['revision']=revision
    return value


class AvatarScriptTests(unittest.TestCase):
    def test_bound_candidate_source_map_is_independent_and_cannot_be_generated_from_changed_native_code(self):
        value=packet();code=value['source']['workers'][0]['avatar']['code'][0]
        expected={'/system/libraries/peopleConnection.js':{key:code[key] for key in ('sha256','codeUnits')}}
        self.assertEqual(code,scripts.bound_code(value,MANAGER,expected)['/system/libraries/peopleConnection.js'][0])
        changed=deepcopy(value);changed['source']['workers'][0]['avatar']['code'][0]['sha256']='0'*64
        with self.assertRaises(NativeUIError):scripts.bound_code(changed,MANAGER,expected)
        with self.assertRaises(NativeUIError):scripts.bound_code(value,MANAGER,{})

    def test_actual_HTTP_caller_manager_and_original_module_bytes_are_joined_without_later_disk_identity(self):
        http=http_tests.SocialHttpTests();http.setUp();consumed=http.consumed()
        source=consumed['nativeCreated']['details'];value=packet();worker=value['source']['workers'][0]
        worker['membership']=deepcopy(source['engine']);worker['code']=deepcopy(source['submitted'])
        worker['avatar']['code']=[];expected={}
        for index,url in enumerate(source['callerChain'],1):
            text='independent candidate source '+str(index);raw=text.encode('utf-16le')
            identity=dict(codeUnits=len(text),sha256=hashlib.sha256(raw).hexdigest())
            suffix=next(suffix for suffix in scripts.SUFFIXES if url.endswith(suffix));expected[suffix]=identity
            worker['avatar']['code'].append(dict(sequence=index,url=url,submittedEpochMs=9000000002+index,
                encoding='utf-16le-code-units',**identity))
        value['clockBefore']=dict(epochMs=9000001100,monotonicMs=1100);value['clockAfter']=dict(epochMs=9000001110,monotonicMs=1110)
        result=scripts.join_http_code(value,http.value,consumed,expected)
        self.assertEqual(source['engine'],result['manager']);self.assertEqual(source['submitted'],result['submitted'])
        for fault in ('different-manager','late-code','foreign-native-read'):
            changed=deepcopy(value);receipt=deepcopy(consumed)
            if fault=='different-manager':changed['source']['workers'][0]['membership']['instance']='2'*32
            elif fault=='late-code':
                for index,code in enumerate(changed['source']['workers'][0]['avatar']['code']):code['submittedEpochMs']=9000001010+index
            else:receipt['nativeRead']['details']['sha256']='0'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.join_http_code(changed,http.value,receipt,expected)

    def test_original_code_is_retained_without_disk_reread_or_expected_code_substitution(self):
        value=packet();scripts.original(value);observed=scripts.worker(value,MANAGER)
        self.assertEqual(value['source']['workers'][0],observed)
        observed['avatar']['code'][0]['sha256']='0'*64
        self.assertNotEqual(observed['avatar']['code'],value['source']['workers'][0]['avatar']['code'])
        value['source']['workers'][0]['avatar']['complete']=False
        scripts.original(value)
        with self.assertRaises(NativeUIError):scripts.drained(value,{MANAGER})

    def test_singleShot_timer_can_be_destroyed_before_its_actual_callback_and_still_remains_owned(self):
        value=packet();created(value)
        self.assertFalse(scripts.drained(value,{MANAGER}))
        event(value,'fired',dict(active=False,remainingMs=-1));event(value,'destroyed');event(value,'callback-enter')
        self.assertFalse(scripts.drained(value,{MANAGER}))
        event(value,'callback-leave');self.assertTrue(scripts.drained(value,{MANAGER}))

    def test_elapsed_duration_and_inactive_timer_are_not_actual_destruction(self):
        value=packet();created(value)
        for clock in (value['clockBefore'],value['clockAfter']):clock['epochMs']+=600000;clock['monotonicMs']+=600000
        self.assertFalse(scripts.drained(value,{MANAGER}))
        event(value,'destroyed');self.assertTrue(scripts.drained(value,{MANAGER}))

    def test_callback_without_real_fire_duplicate_destructor_and_handle_reuse_before_destruction_fail(self):
        for fault in ('enter','leave','double-destroy','reuse'):
            value=packet();created(value)
            if fault=='enter':event(value,'callback-enter')
            elif fault=='leave':event(value,'callback-leave')
            elif fault=='double-destroy':event(value,'destroyed');event(value,'destroyed')
            else:created(value,timer='1'*32)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.original(value)
        value=packet();created(value);event(value,'destroyed');created(value,timer='1'*32)
        self.assertFalse(scripts.drained(value,{MANAGER}))

    def test_exact_immutable_code_and_timer_prefix_cannot_be_rewritten_or_truncated(self):
        first=packet();created(first);second=next_packet(first)
        query=dict(schemaVersion=1,commandId=second['requestId'],action=scripts.ACTION,runId=RUN)
        scripts.validate(second,query,42,previous=first)
        for fault in ('code','code-truncate','events','event-truncate','top-code','birth'):
            value=deepcopy(second);worker=value['source']['workers'][0]
            if fault=='code':worker['avatar']['code'][0]['sha256']='0'*64
            elif fault=='code-truncate':worker['avatar']['code']=[]
            elif fault=='events':worker['avatar']['events'][0]['details']['intervalMs']=500
            elif fault=='event-truncate':worker['avatar']['events']=[]
            elif fault=='top-code':worker['code']['sha256']='0'*64
            else:worker['avatar']['instance']='1'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.validate(value,query,42,previous=first)

    def test_unknown_pending_foreign_or_stopped_manager_does_not_become_clean_empty_scope(self):
        value=packet()
        for key,replacement in (('running',False),('stopping',True),('done',True),('finished',True)):
            altered=deepcopy(value);altered['source']['workers'][0][key]=replacement
            with self.subTest(key=key),self.assertRaises(NativeUIError):scripts.drained(altered,{MANAGER})
        with self.assertRaises(NativeUIError):scripts.drained(value,{'1'*32})
        with self.assertRaises(NativeUIError):scripts.drained(value,set())
        value['source']['workers'][0]['membership'].update(assigned=False,url='',loadGeneration=0,assignedEpochMs=0)
        scripts.original(value)
        with self.assertRaises(NativeUIError):scripts.drained(value,{MANAGER})

    def test_restore_replays_original_membership_and_rejects_retired_worker_reappearance(self):
        first=packet();absent=next_packet(first,workers=[],revision=2);returned=next_packet(absent,workers=deepcopy(first['source']['workers']),revision=3)
        reader=scripts.IOSAvatarScripts(lambda q:None,lambda:'',lambda:1700000000300,lambda:True,42)
        reader.restore([first,absent]);self.assertEqual({MANAGER},reader.retired)
        other=scripts.IOSAvatarScripts(lambda q:None,lambda:'',lambda:1700000000300,lambda:True,42)
        with self.assertRaises(NativeUIError):other.restore([first,absent,returned])
        self.assertIsNone(other.last)

    def test_invalid_source_code_urls_boolean_versions_and_foreign_PID_fail_closed(self):
        for fault in ('url','hash','version','pid','event-time'):
            value=packet();created(value)
            if fault=='url':value['source']['workers'][0]['avatar']['code'][0]['url']='https://foreign.invalid/system/libraries/peopleConnection.js'
            elif fault=='hash':value['source']['workers'][0]['avatar']['code'][0]['sha256']='wanted'
            elif fault=='version':value['iosAvatarScriptsVersion']=True
            elif fault=='pid':value['processId']=True
            else:value['source']['workers'][0]['avatar']['events'][0]['capturedEpochMs']=1700000001000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.original(value)


if __name__=='__main__':unittest.main()
