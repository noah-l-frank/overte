"""Actual actor HTTP serialization and Opener delays retain once-POST owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope
from feature_journeys.witness import Client
from self_tests import test_phase_witness_publisher as facts_fixture
from self_tests import test_phase_retirement_publisher as retirement_fixture
from ios.self_tests import test_ios_sdk_operation_guard as sdk_fixture


class PublicationOperationGuardTests(unittest.TestCase):
    def fixture(self,kind):
        f=facts_fixture.PhaseWitnessPublisherTests() if kind=='facts' else retirement_fixture.PhaseRetirementTests()
        f.setUp();self.addCleanup(f.doCleanups);offset=[0.]
        if kind=='facts':
            f.phase.epoch_ms=lambda:time.time()*1000+offset[0]*1000
            f.phase.monotonic=lambda:time.monotonic()+offset[0]
            f.server.journal.clock=f.phase.epoch_ms
            with f.lock.held():owner=f.owner()
            owner.epoch_ms=f.phase.epoch_ms;owner.monotonic=f.phase.monotonic
        else:
            f.phase.monotonic=lambda:10.1+offset[0]
            with f.lock.held():owner=f.owner()
            owner.monotonic=f.phase.monotonic
        def advance():
            offset[0]+=2.
            if kind=='retirement':f.now+=2000.
        return f,owner,advance

    def test_late_actual_client_serialization_sends_no_facts_or_retirement_and_never_resends(self):
        for kind in ('facts','retirement'):
            with self.subTest(kind=kind):
                f,owner,advance=self.fixture(kind);original=f.original();request=f.actor.request;attempts=[];opened=[]
                route='/samples' if kind=='facts' else '/retirements'
                real_dumps=json.dumps
                def slow(value,*args,**kwargs):advance();return real_dumps(value,*args,**kwargs)
                def target(path,value=None,*args,**kwargs):
                    if path.endswith(route) and value is not None:
                        attempts.append(path)
                        with patch('feature_journeys.witness.json.dumps',side_effect=slow):return request(path,value,*args,**kwargs)
                    return request(path,value,*args,**kwargs)
                from feature_journeys import witness
                build=witness.build_opener
                def factory(*args,**kwargs):
                    opener=build(*args,**kwargs);actual=opener.open
                    def opening(*args,**kwargs):opened.append(True);return actual(*args,**kwargs)
                    opener.open=opening;return opener
                with f.lock.held(),patch.object(f.actor,'request',side_effect=target):
                    # Earlier genuine phase reads use HTTP; only the actual
                    # issued publication Client request is instrumented below.
                    original_target=target
                    def publication(path,value=None,*args,**kwargs):
                        if path.endswith(route) and value is not None:
                            with patch('feature_journeys.witness.build_opener',side_effect=factory):return original_target(path,value,*args,**kwargs)
                        return request(path,value,*args,**kwargs)
                    with patch.object(f.actor,'request',side_effect=publication),self.assertRaises((ValueError,NativeUIError)):
                        owner.publish(original)
                    self.assertEqual([],opened);self.assertEqual(1,len(attempts));self.assertEqual('issued',owner.state['pending']['phase'])
                    # Unknown issued outcome owns its journal. Neither original
                    # nor later source may cause a second publication POST.
                    with self.assertRaises((ValueError,NativeUIError)):owner.publish(original)
                    self.assertEqual(1,len(attempts))
                if kind=='facts':self.assertEqual([],f.server.journal.snapshot(f.run)['entries'])
                else:self.assertEqual([],f.server.phase_retirements.snapshot(f.run)['entries'])

    def test_slow_actual_opener_preparation_is_checked_after_build_and_context_releases(self):
        f,owner,advance=self.fixture('facts');client=Client(f.url,'r'*64);enabled=[True];opened=[]
        from feature_journeys import witness
        build=witness.build_opener
        def factory(*args,**kwargs):
            opener=build(*args,**kwargs);actual=opener.open;enabled[0]=False
            def opening(*args,**kwargs):opened.append(True);return actual(*args,**kwargs)
            opener.open=opening;return opener
        with scope(lambda:enabled[0]):
            with patch('feature_journeys.witness.build_opener',side_effect=factory),self.assertRaises(ValueError):client.request('/runs/'+f.run)
            self.assertEqual([],opened);enabled[0]=True
        self.assertEqual(f.run,client.request('/runs/'+f.run)['runId'])

    def test_real_sdk_process_guard_does_not_recurse_through_its_own_final_send(self):
        sdk=sdk_fixture.SDKOperationGuardTests();sdk.setUp();self.addCleanup(sdk.doCleanups)
        f,owner,_advance=self.fixture('facts');original=f.original()
        def process_guard():
            sdk.send();return True
        owner.guard=process_guard
        with f.lock.held():self.assertEqual(1,owner.publish(original))
        self.assertTrue(sdk.requests);self.assertEqual(1,len(f.server.journal.snapshot(f.run)['entries']))


if __name__=='__main__':unittest.main()
