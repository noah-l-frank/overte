"""Actual existing stdio client/server; Browser owner is a declared DTO model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from adapter_operation_host import PicoOperationHost
from adapters.normal_ui import NativeUIError
from self_tests import test_pico_operation_host as original

WORKER = Path(__file__).with_name('pico_browser_operation_host_worker.py').resolve()


class BrowserOperationTransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.PicoOperationHostTests('runTest'); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root; self.manifest = self.fixture.manifest
    @contextmanager
    def model(self, fault='normal'):
        artifacts = self.root/fault; artifacts.mkdir(mode=0o700)
        trace = self.root/(fault+'.jsonl')
        prefix = [sys.executable, str(WORKER), '--fault', fault, '--trace', str(trace)]
        with patch('adapter_operation_host.pico_command', return_value=prefix):
            host = PicoOperationHost(self.manifest, 'explicit-host-model', artifacts)
            self.fixture.hosts.append(host); yield host
    def budget(self, seconds=120):
        now = time.monotonic()
        return dict(id='a'*32, startedMonotonic=now, deadlineMonotonic=now+seconds)
    def component(self, host, operation='begin', whole=None):
        fields = dict(artifactRoot=str(host.artifacts), foreignFixtureUrl='http://foreign.test/feature-fixture/v1',
            nonce='c'*32) if operation=='begin' else None
        return host.browser_component('b'*32, 'http://controlled.test/feature-fixture/v1/runs/'+'b'*32+'/',
            operation, fields, whole_budget=whole or self.whole)
    def trace(self, fault='normal'):
        return [json.loads(line)['kind'] for line in (self.root/(fault+'.jsonl')).read_text().splitlines()]

    def test_actual_same_cli_delivers_private_dtos_under_one_budget_without_common_claim(self):
        with self.model() as host:
            self.whole = self.budget()
            first = self.component(host); second = self.component(host, 'actor.return')
            self.assertTrue(first['protocolOnly']); self.assertFalse(first['completeCommonObservation'])
            self.assertEqual(first['originalBudgetSha256'], second['originalBudgetSha256'])
            pid = host.process.pid; host.close()
            self.assertEqual(0, host.wait_status); self.assertFalse(Path(f'/proc/{pid}').exists())
            self.assertEqual(['factory', 'browser-factory', 'browser-private-begin',
                'browser-private-actor.return', 'browser-close'], self.trace())
            self.assertEqual('closed', host.archive.state['phase'])

    def test_expired_original_whole_budget_never_starts_a_child(self):
        with self.model() as host:
            now = time.monotonic(); self.whole = dict(id='a'*32, startedMonotonic=now-2, deadlineMonotonic=now-1)
            with patch('adapter_operation_host.subprocess.Popen', side_effect=AssertionError('No late process')) as launch:
                with self.assertRaises(NativeUIError): self.component(host)
            launch.assert_not_called(); self.assertIsNone(host.process)

    def test_input_boundary_keeps_one_original_budget_through_actual_stdio_and_readonly_call(self):
        with self.model() as host:
            self.whole=self.budget();self.component(host)
            run='b'*32;url='http://controlled.test/feature-fixture/v1/runs/'+run+'/'
            with host.browser_input_context(run,url,'prepare',None,whole_budget=self.whole):
                original=dict(host._browser_input_budget)
                self.assertTrue(host.invoke(host.manifest,host.target,'app.process',{})['running'])
            self.assertIsNone(host._browser_input_budget);host.close()
            frames=[json.loads(p.read_bytes()) for p in host.artifacts.glob('request-*.bin')]
            selected=[row for row in frames if row['operation'] in ('input.begin','input.end')]
            self.assertEqual(2,len(selected))
            self.assertTrue(all(row['picoBrowserOperationRequestVersion']==2 and row['actionBudget']==original for row in selected))
            public=[row for row in frames if row['operation']=='app.process']
            self.assertEqual(1,len(public));self.assertLessEqual(public[0]['deadlineMonotonic'],original['deadlineMonotonic'])
            self.assertEqual(1,self.trace().count('factory'));self.assertEqual(1,self.trace().count('browser-factory'))

    def test_original_deadline_counts_cold_factory_and_keeps_request_without_reply(self):
        fault = 'browser-factory-timeout'
        with self.model(fault) as host:
            self.whole = self.budget(.2)
            with self.assertRaises(RuntimeError): self.component(host)
            self.assertTrue(host.failed); host.abort()
            self.assertTrue(list(host.artifacts.glob('request-*.bin')))
            with self.assertRaises(RuntimeError): self.component(host, 'actor.return')
            self.assertEqual(1, self.trace(fault).count('browser-factory'))


if __name__ == '__main__':
    unittest.main()
