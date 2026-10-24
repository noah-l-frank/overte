"""Local Setup decode dataflow with actual Source/Observer byte guards.

SDK/native producers and Setup measurement verdicts are explicit boundary
models. Production original grammar, scoped Source/Observer reads and outward
file identity checks are real. This is not native cleanup qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
from ios.adapters.world_web_terminal_live import WorldWebTerminalLive
from ios.self_tests import test_ios_world_web_observer as fixture


class WorldWebSetupDataflowTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebObserverTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.sdk.use_snapshot=True;self.f.sdk.use_whole_snapshot=True

    def context(self):
        f=self.f;source=f.sdk.owner(f.source_store,f.lock);observer=f.observer(source)
        reference,measured=observer.capture()
        owner=object.__new__(WorldWebSetupRetirement)
        owner.observer,owner.source,owner.peer=observer,source,None
        owner.binding,owner.run,owner.role=deepcopy(source.binding),source.run,'primary'
        owner.baseline=deepcopy(source.state['records'][0]);owner.required_images=[]
        owner.state=dict(unchangedOriginalState=True)
        request='ios-'+'b'*32
        records=[dict(index=index,acquisition=('%032x'%index),images=[request],parts=[],writing=None,carrier=None)
            for index in range(1,4)]
        state=dict(phase='retired',ticket='a'*32,baseline=deepcopy(owner.baseline),records=records,pending=None,
            barrier=1,quiet=[1,2,3],restoration=request,images=[request])
        original=dict(iosWorldWebSetupRetirementOriginalVersion=1,owner=owner.envelope(state))
        proof=dict(ticket=state['ticket'],public=deepcopy(measured['public']),acquisition=deepcopy(measured['acquisition']),
            quiet=dict(explicitMeasurementBoundary=True),held=[])
        def measurement(row):
            observer.validate_original(reference)
            return dict(before=dict(index=row['index']*2),after=dict(index=row['index']*2+1))
        return source,observer,owner,state,original,proof,measurement

    def test_exact_original_decode_and_qualification_once_with_copied_outward_results(self):
        with self.f.held():
            source,_observer,owner,state,original,proof,measurement=self.context()
            original_before=deepcopy(original);prior=deepcopy(owner.state);queries=len(self.f.sdk.native.commands)
            with patch.object(owner,'measure',side_effect=measurement) as measured,patch.object(owner,'qualification',return_value=proof) as qualified:
                decoded,actual,verdict=owner.qualified_original(original)
                self.assertEqual(3,measured.call_count);self.assertEqual(1,qualified.call_count)
            self.assertEqual(state,decoded);self.assertEqual(proof,actual)
            decoded['records'].clear();actual['public']['resources'].append('unqualified-alias')
            verdict['acquisition'].clear()
            self.assertEqual(original_before,original);self.assertEqual([],proof['public']['resources'])
            self.assertEqual(prior,owner.state);self.assertEqual(queries,len(self.f.sdk.native.commands))
            self.assertIsNone(source._round)

    def test_changed_or_replaced_actual_carrier_after_final_measurement_is_denied(self):
        for replacement in (False,True):
            self.f=fixture.WorldWebObserverTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
            self.f.sdk.use_snapshot=True;self.f.sdk.use_whole_snapshot=True
            with self.subTest(replacement=replacement),self.f.held():
                source,_observer,owner,_state,original,proof,measurement=self.context()
                frame=source.frame(source.state['records'][-1]);path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0]
                prior=deepcopy(owner.state);queries=len(self.f.sdk.native.commands)
                def changed(_state):
                    raw=path.read_bytes()
                    if replacement:
                        other=path.with_suffix('.replacement');other.write_bytes(raw);other.chmod(0o600);other.replace(path)
                    else:
                        with path.open('r+b') as stream:stream.seek(0);stream.write(b' ')
                    return proof
                with patch.object(owner,'measure',side_effect=measurement),patch.object(owner,'qualification',side_effect=changed):
                    with self.assertRaises(NativeUIError):owner.qualified_original(original)
                self.assertEqual(prior,owner.state);self.assertIsNone(source._round)
                self.assertEqual(queries,len(self.f.sdk.native.commands))

    def test_terminal_consumer_uses_one_checked_setup_result(self):
        with self.f.held():
            _source,_observer,owner,_state,original,proof,measurement=self.context()
            live=object.__new__(WorldWebTerminalLive);live.owner=owner
            with patch.object(owner,'measure',side_effect=measurement),patch.object(owner,'qualification',return_value=proof) as qualified,patch.object(owner,'frame',return_value=dict(after=None)):
                actual=live.measure(original)
                self.assertEqual(1,qualified.call_count)
            self.assertEqual(original,actual['original']);self.assertEqual(proof['public'],actual['public'])
            self.assertEqual([],actual['held'])


if __name__=='__main__':unittest.main()
