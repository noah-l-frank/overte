"""Synthetic original native boundaries; no native compiler or device invoked."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_state as avatar
from ios.adapters import feature_observation
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks
from self_tests.test_native_feature_observation import Boundary as ClockBoundary, probe_source

RUN = 'a'*32
ORIGINAL, A, MISSING, DEFAULT = ('https://owned.invalid/'+name+'.fst' for name in ('original', 'a', 'missing', 'default'))


def packet():
    return dict(iosAvatarStateVersion=1, requestId='ios-'+'b'*32, runId=RUN, instance='c'*32, sequence=1,
        processId=42, clockDomain='native-main-avatar', clockBefore=dict(epochMs=1700000000100, monotonicMs=100),
        clockAfter=dict(epochMs=1700000000200, monotonicMs=200),
        source=dict(sessionId='00000000-0000-4000-8000-000000000001', requestedUrl=ORIGINAL, resourceUrl=ORIGINAL,
            defaultResourceUrl=DEFAULT, geometryLoaded=True, rigReady=True, shouldRender=True,
            targetScale=1., modelScale=1., jointNames=['Root', 'Hips', 'Head'],
            bookmarks=dict(source='AvatarBookmarks.getBookmarks', entries={}, loadError=False),
            modelHistory=dict(avatarModelHistoryVersion=1, instance='d'*32, processId=42, currentGeneration=0,
                              eventSequence=0, complete=True, events=[])))


def event(value, kind, generation, url, *, assignment=0, resource=None, success=None):
    history = value['source']['modelHistory']; index = history['eventSequence']+1
    history['events'].append(dict(kind=kind, generation=generation, requestedUrl=url, resourceUrl=resource,
        success=success, assignment=assignment, resourceIdentity='ff' if assignment else None,
        eventSequence=index, epochMs=1700000000000+index, monotonicMs=index))
    history['currentGeneration'] = max(history['currentGeneration'], generation); history['eventSequence'] = index


def requested(value, generation, url, assignment):
    event(value, 'requested', generation, url)
    event(value, 'assigned', generation, url, assignment=assignment, resource=url)
    value['source']['requestedUrl'] = url; value['source']['resourceUrl'] = url


def model(value):
    return avatar.model_state(value, original_url=ORIGINAL, avatar_url=A, missing_url=MISSING)


class Boundary(Clocks):
    def __init__(self): super().__init__(None)
    def original(self):
        self.clock += .001; value = packet(); self.sequence += 1
        value.update(requestId=self.requests[-1]['commandId'], sequence=self.sequence)
        value['clockBefore'] = self.clocks(); self.clock += .001; value['clockAfter'] = self.clocks()
        self.last = deepcopy(value); return json.dumps(value)


class AvatarStateTests(unittest.TestCase):
    def test_existing_HTTP_AFC_factory_uses_actual_native_clock_and_original_fixed_file(self):
        native = Native(); clock = ClockBoundary(); source = Boundary(); observer = native.observer()
        observer.monotonic = lambda: source.clock; observer.sleep = source.sleep; observer.epoch_ms = lambda: 9000
        def stamp(value):
            source.native_clock(); epoch = source.epoch()
            value.update(processId=42, capturedEpochMs=epoch, requestedEpochMs=epoch, animation={}, animationFence={})
        clock.mutate = stamp
        def post(request, timeout):
            query = native.fixture.set_client_command(json.loads(request.data)); native.commands.append(deepcopy(query))
            native.echo = json.dumps(query).encode()
            (clock if query['action'] == 'feature-native-observe' else source).send(query)
            return native
        def execute(session, operation, values):
            self.assertEqual(('native-session', 'mobile: pullFile'), (session, operation))
            path = values['remotePath']; native.reads.append(path); prefix = '@org.example.client:documents/owned-results/'
            self.assertIn(path, (prefix+'feature-native-observation.json', prefix+avatar.FILE))
            return base64.b64encode((clock.original() if path.endswith('/feature-native-observation.json')
                                     else source.original()).encode()).decode()
        with patch.object(feature_observation, 'post_request', side_effect=post), patch.object(native, 'execute', side_effect=execute):
            reader = observer.avatar_state(); value = reader.read(RUN)
        self.assertEqual(source.last, value); self.assertEqual(3, len(native.reads))
        self.assertEqual(['feature-native-observe', avatar.ACTION, 'feature-native-observe'],
                         [row['action'] for row in native.commands])
        self.assertNotEqual(9000, value['clockAfter']['epochMs'])

    def test_existing_probe_dispatch_retains_actual_original_once_and_unavailable_never_means_loaded(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),source:{resourceUrl:'actual-native-original'}};
const Test={featureIOSAvatarState:c=>{calls++;return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-avatar-state',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files[0].v!==original||files[0].name!=='feature-ios-avatar-state.json')throw Error('Original replaced or repeated');
for(const extra of [{avatar:'A'},{url:'expected.fst'},{scale:1.5},{schemaVersion:true}]){
 applyClientCommand({...c,...extra,commandId:'ios-'+'f'.repeat(32)});
}if(calls!==1)throw Error('Wanted effect admitted');
delete Test.featureIOSAvatarState;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable'||files[1].v.source)throw Error('Missing native source became loaded');
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_original_loaded_geometry_and_settled_scale_are_separate_from_requested_url(self):
        value = packet(); self.assertEqual(dict(requestedAvatar='original', avatar='original', modelLoaded=True,
            loadFailed=False, scale=1.), model(value))
        requested(value, 1, A, 1)
        value['source'].update(geometryLoaded=False, rigReady=False)
        self.assertEqual('unavailable', model(value)['avatar']); self.assertFalse(model(value)['modelLoaded'])
        value['source'].update(geometryLoaded=True, rigReady=True)
        event(value, 'finished', 1, A, assignment=1, resource=A, success=True)
        self.assertEqual('A', model(value)['avatar'])

    def test_actual_failed_missing_assignment_survives_actual_default_fallback(self):
        value = packet(); requested(value, 1, MISSING, 1)
        value['source'].update(geometryLoaded=False, rigReady=False)
        self.assertFalse(model(value)['loadFailed'])
        event(value, 'finished', 1, MISSING, assignment=1, resource=MISSING, success=False)
        self.assertTrue(model(value)['loadFailed']); self.assertEqual('unavailable', model(value)['avatar'])
        event(value, 'assigned', 1, MISSING, assignment=2, resource=DEFAULT)
        event(value, 'finished', 1, MISSING, assignment=2, resource=DEFAULT, success=True)
        value['source'].update(resourceUrl=DEFAULT, geometryLoaded=True, rigReady=True)
        self.assertEqual('fallback', model(value)['avatar']); self.assertTrue(model(value)['modelLoaded'])
        self.assertTrue(model(value)['loadFailed'])

    def test_delayed_old_callback_keeps_original_generation_after_bookmark_recovery(self):
        value = packet(); requested(value, 1, MISSING, 1)
        requested(value, 2, A, 2)
        event(value, 'finished', 2, A, assignment=2, resource=A, success=True)
        # Actual old callback is still retained, with its captured original token.
        event(value, 'finished', 1, MISSING, assignment=1, resource=MISSING, success=False)
        self.assertEqual('A', model(value)['avatar']); self.assertFalse(model(value)['loadFailed'])
        altered = deepcopy(value)
        altered['source']['modelHistory']['events'][-1]['generation'] = 2
        with self.assertRaises(NativeUIError): model(altered)

    def test_advertised_missing_with_retained_A_and_no_resource_failure_cannot_pass(self):
        value = packet(); requested(value, 1, MISSING, 1)
        value['source']['resourceUrl'] = A
        with self.assertRaises(NativeUIError): model(value)
        value['source'].update(resourceUrl=DEFAULT)
        self.assertEqual('fallback', model(value)['avatar'])
        self.assertFalse(model(value)['loadFailed'])  # fallback alone does not invent the failure

    def test_failure_of_default_fallback_is_not_failure_of_missing_request(self):
        value = packet(); requested(value, 1, MISSING, 1)
        event(value, 'assigned', 1, MISSING, assignment=2, resource=DEFAULT)
        event(value, 'finished', 1, MISSING, assignment=2, resource=DEFAULT, success=False)
        value['source'].update(geometryLoaded=False, rigReady=False, resourceUrl=DEFAULT)
        self.assertFalse(model(value)['loadFailed'])

    def test_unsettled_scale_missing_rig_and_foreign_or_partial_history_are_not_ready(self):
        for fault in ('scale', 'nan', 'pid', 'partial', 'rig', 'joints'):
            value = packet()
            if fault == 'scale': value['source']['targetScale'] = 1.5
            elif fault == 'nan': value['source']['modelScale'] = float('nan')
            elif fault == 'pid': value['source']['modelHistory']['processId'] = 43
            elif fault == 'partial': value['source']['modelHistory']['complete'] = False
            elif fault == 'rig': value['source']['geometryLoaded'] = False
            else: value['source']['jointNames'] = []
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): model(value)

    def test_original_prefix_cannot_be_retimed_or_replaced(self):
        first = packet(); requested(first, 1, A, 1)
        second = deepcopy(first); second['sequence'] = 2; second['requestId'] = 'ios-'+'e'*32
        second['clockBefore'] = dict(epochMs=1700000000300, monotonicMs=300)
        second['clockAfter'] = dict(epochMs=1700000000400, monotonicMs=400)
        query = dict(schemaVersion=1, commandId=second['requestId'], runId=RUN, action=avatar.ACTION)
        avatar.validate(second, query, 42, previous=first)
        for fault in ('retime', 'replace', 'birth', 'regress', 'run', 'session'):
            altered = deepcopy(second)
            if fault == 'retime': altered['source']['modelHistory']['events'][0]['epochMs'] += 1
            elif fault == 'replace': altered['source']['modelHistory']['events'][1]['resourceIdentity'] = 'fe'
            elif fault == 'birth': altered['source']['modelHistory']['instance'] = 'f'*32
            elif fault == 'regress': altered['clockBefore']['monotonicMs'] = 0
            elif fault == 'run': altered['runId'] = 'f'*32
            else: altered['source']['sessionId'] = '00000000-0000-4000-8000-000000000002'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): avatar.validate(altered, query, 42, previous=first)

    def test_owned_bookmark_requires_independent_read_and_preserves_all_unowned_rows(self):
        value = packet(); baseline = dict(existing=dict(avatarUrl=ORIGINAL, avatarScale=1, avatarEntites=[]))
        value['source']['bookmarks']['entries'] = deepcopy(baseline)
        self.assertFalse(avatar.bookmark(value, 'owned', baseline))
        saved = dict(avatarUrl=A, avatarScale=1, avatarEntites=[], version=3)
        value['source']['bookmarks']['entries']['owned'] = saved
        self.assertTrue(avatar.bookmark(value, 'owned', baseline, saved))
        value['source']['bookmarks']['entries']['existing']['avatarScale'] = 1.5
        with self.assertRaises(NativeUIError): avatar.bookmark(value, 'owned', baseline, saved)

    def test_original_reader_sends_once_and_does_not_adopt_foreign_files_or_recapture_old_result(self):
        clock = [1.]; commands = []; sequence = [0]
        def now(): return 1700000000000+int(clock[0]*1000)
        def send(value): commands.append(value)
        def read():
            value = packet(); sequence[0] += 1
            value.update(requestId=commands[-1]['commandId'], sequence=sequence[0])
            value['clockBefore'] = dict(epochMs=now(), monotonicMs=int(clock[0]*1000))
            value['clockAfter'] = deepcopy(value['clockBefore'])
            return json.dumps(value)
        source = avatar.IOSAvatarState(send, read, now, lambda: True, 42, monotonic=lambda: clock[0],
            sleep=lambda duration: clock.__setitem__(0, clock[0]+duration))
        first = source.read(RUN); self.assertEqual(1, len(commands)); self.assertEqual(first, source.last)
        source.original = lambda: json.dumps(first)
        with self.assertRaises(NativeUIError): source.read(RUN)
        self.assertEqual(2, len(commands)); self.assertEqual(first, source.last)


if __name__ == '__main__': unittest.main()
