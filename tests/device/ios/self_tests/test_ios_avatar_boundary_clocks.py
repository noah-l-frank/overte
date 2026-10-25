"""Actual runtime/reader wiring under explicitly modeled producer clocks.

These tests qualify clock consistency, not physical CPU/transport timing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
import time
import unittest

from adapters.normal_ui import NativeUIError
from ios.self_tests.avatar_prepare_fixture import PrepareDomain,RUN
from self_tests import test_account_provider as tls


class AvatarBoundaryClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def owner(self,domain):
        role='primary';scope=domain.scenes[role].scope;lock=domain.owners[role].lock
        return domain.runtime._avatar_account_reads(role,domain.client,RUN,role,role,scope.root,lock,
            epoch_ms=domain.host,monotonic=lambda:domain.clock[0])

    def test_actual_runtime_binds_both_reader_clocks_before_first_original(self):
        domain=PrepareDomain(self);lock=domain.owners['primary'].lock
        with lock.held():
            owner=self.owner(domain);reader=owner.reader;clock=owner.clock_source
            self.assertTrue(reader.native_clock_bound);self.assertFalse(clock.native_clock_bound)
            for source in (reader,clock):self.assertEqual(domain.clock[0],source.monotonic())
            start=domain.clock[0];row=owner.read();packet=owner.packet(row)
            self.assertEqual('observed',row['status']);self.assertLess(domain.clock[0]-start,1.5)
            self.assertEqual(domain.natives['primary'].feature.sample['instance'],packet['instance'])
            self.assertEqual(31,packet['processId']);self.assertTrue(row['clocks'])

    def test_actual_original_write_crossing_the_same_boundary_clock_refuses_return_without_replaying_query(self):
        domain=PrepareDomain(self);lock=domain.owners['primary'].lock
        with lock.held():
            owner=self.owner(domain);write=owner.originals.write;queries=[];send=owner.reader.send
            def actual_send(query):queries.append(query.copy());return send(query)
            owner.reader.send=actual_send
            def delayed(index,value):
                result=write(index,value);domain.clock[0]+=1.501;return result
            with patch.object(owner.originals,'write',side_effect=delayed),self.assertRaises(NativeUIError):owner.read()
            self.assertEqual(1,len(queries));self.assertIsNotNone(owner.state['pending']['original'])
            self.assertEqual('saved',owner.state['pending']['original']['phase'])
            retained=owner.recover();self.assertEqual('abandoned',retained['status']);self.assertEqual(1,len(queries))
            self.assertEqual(queries[0],retained['query'])

    def test_real_default_reader_still_refuses_actual_slow_original_write(self):
        from ios.adapters.feature_observation import FeatureObservation
        domain=PrepareDomain(self);lock=domain.owners['primary'].lock
        with lock.held():
            source=domain.runtime._sources('primary');owner=self.owner(domain)
            # A newly constructed unmodified production reader uses real host
            # time. This intentional mixed-boundary negative reproduces the
            # physical guard; it is not used by the composed model journey.
            observer=FeatureObservation(source['client'],source['session'],source['target'],source['process'],epoch_ms=source['native_clock'])
            owner.reader=observer.bound_native_observer(owner.clock_source)
            write=owner.originals.write
            def delayed(index,value):result=write(index,value);time.sleep(1.501);return result
            started=time.monotonic();model=domain.clock[0]
            with patch.object(owner.originals,'write',side_effect=delayed),self.assertRaises(NativeUIError):owner.read()
            self.assertGreaterEqual(time.monotonic()-started,1.5);self.assertLess(domain.clock[0]-model,.1)
            self.assertEqual('saved',owner.state['pending']['original']['phase'])


if __name__=='__main__':unittest.main()
