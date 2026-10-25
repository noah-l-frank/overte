"""Factory/public observe plus real separate Actor process on one host SDK.

Native/clock/selector producers are explicit host boundaries. This pre-input
case does not qualify the complete journey, native execution or device timing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import os
import unittest
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,actor_baseline
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletPairedEntryTests(unittest.TestCase):
    def test_actual_factory_public_baseline_and_independent_host_Actor_use_one_existing_HTTP_SDK(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary
        try:result=fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        except Exception as error:
            # Production lock errors suppress private details. This fixture
            # contains only controlled host data; retain its original cause.
            seen=set()
            while error.__context__ is not None and id(error) not in seen:
                seen.add(id(error));error=error.__context__
            raise AssertionError('Actual controlled boundary failure') from error
        self.assertEqual([],result['resources']);self.assertFalse(result['state']['open'])
        # The ordinary public operation released its actual lock before the
        # independent process obtains its own native sources and publication.
        lock=ScriptSourceLock(b.root/'script-feature-sources.lock')
        with lock.held():lock.assert_held()
        context=multiprocessing.get_context('spawn');receive,send=context.Pipe(duplex=False)
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        process=context.Process(target=actor_baseline,args=(inputs,fixture.clock,send))
        process.start();send.close()
        try:
            self.assertTrue(receive.poll(60),'Independent original Actor did not return within its operation budget')
            value=receive.recv();self.assertNotIn('error',value,value.get('traceback'))
            process.join(5);self.assertEqual(0,process.exitcode)
            self.assertNotEqual(os.getpid(),value['hostProcessId']);self.assertGreaterEqual(value['sequence'],1)
            actual=fixture.fixture.journal.snapshot(RUN);self.assertEqual(1,len(actual['entries']))
            self.assertEqual(value['sequence'],actual['entries'][0]['actorSequence'])
            self.assertEqual('tablet',actual['entries'][0]['facts']['surface'])
            self.assertFalse(any(method=='DELETE' or path=='/session' for method,path in fixture.sdk.calls))
            self.assertTrue(any(path.endswith('/execute/sync') for method,path in fixture.sdk.calls))
            self.assertEqual([],fixture.sdk.errors)
        finally:
            receive.close()
            if process.is_alive():
                # Test-only host child responsibility, never a device stop.
                process.terminate();process.join(5)


if __name__=='__main__':unittest.main()
