"""Explicit whole-run diagnostic; no default green catalog admission.

Run this module explicitly; it is not a default green catalog/unit selection.
Candidate/VR sources are declared host models, never actual device automation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from feature_journeys.engine import Journey
from self_tests.pico_browser_poll_diagnostic import PollReturns

ENTRY=Path(__file__).with_name('pico_browser_coordinator_worker.py').resolve()


class BrowserCoordinatorTests(unittest.TestCase):
    def test_actual_common_parent_and_original_coordinator_return_actual_actor_six(self):
        temporary=tempfile.TemporaryDirectory(prefix='browser-coordinator-')
        self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        p=subprocess.Popen([sys.executable,str(ENTRY),'--area','tablet-web'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,
                OVT_BROWSER_COORDINATOR_ROOT=str(root),PYTHONDONTWRITEBYTECODE='1'))
        try:stdout,stderr=p.communicate(timeout=145)
        except BaseException:
            if p.poll() is None:p.terminate()
            stdout,stderr=p.communicate(timeout=20)
            (root/'parent.stdout.bin').write_bytes(stdout);(root/'parent.stderr.bin').write_bytes(stderr)
            raise
        (root/'parent.stdout.bin').write_bytes(stdout);(root/'parent.stderr.bin').write_bytes(stderr)
        self.assertEqual(0,p.returncode,stderr.decode('utf-8','replace'))
        self.assertEqual(b'',stdout)
        result=json.loads((root/'coordinator-result.json').read_text())
        self.assertTrue(result['sequenceCompleted'] and result['actualCoordinator'] and result['actualActorSix'])
        self.assertFalse(result['canonicalCandidateRouter'] or result['deviceAcceptance'])
        self.assertEqual(28,result['phases']);self.assertLess(result['elapsed'],120)
        for name in ('parent','child','actor'):
            source=json.loads((root/(name+'-sources.json')).read_text())
            self.assertEqual([],source['changed']);self.assertEqual(source['before'],source['after'])
        self.assertFalse(Path(f'/proc/{p.pid}').exists())


class BrowserPollReturnTests(unittest.TestCase):
    def test_original_historical_peer_contradiction_remains_false(self):
        from self_tests.test_pico_browser_witness_receipt import BrowserWitnessReceiptTests
        fixture=BrowserWitnessReceiptTests();fixture.setup_wait(old_bad=True)
        with PollReturns(Journey) as diagnosis:
            fixture.fixture.wait(kinds=('peer',))
        consumed=[row for row in diagnosis.rows if row['check']=='observed_witness' and row['consume']]
        self.assertFalse(consumed[0]['okay'])
        self.assertEqual(2,consumed[0]['newCount'])
        self.assertTrue(all(row['okay'] for row in consumed[1:]))
        self.assertEqual(3,fixture.journey.phases[-1]['advancingSamples'])

    def test_actual_peer_preview_and_consumption_are_only_observed(self):
        from self_tests.test_pico_browser_poll_period import BrowserPollPeriodTests
        fixture=BrowserPollPeriodTests();fixture.setup_wait()
        with PollReturns(Journey) as diagnosis:
            fixture.wait(kinds=('peer',))
        rows=[row for row in diagnosis.rows if row['check']=='observed_witness']
        self.assertTrue(any(not row['consume'] for row in rows))
        self.assertTrue(any(row['consume'] for row in rows))
        self.assertTrue(all(row['newCount']==1 and row['okay'] for row in rows))
        self.assertEqual(3,fixture.journey.phases[-1]['advancingSamples'])

    def owner(self, now=2., epoch=2000):
        calls=[]
        owner=SimpleNamespace(samples=[],now=lambda:(calls.append('host') or now),
            epoch_ms=lambda:(calls.append('epoch') or epoch))
        return owner,calls

    def test_original_true_false_and_exact_original_clock_calls_are_preserved(self):
        owner,calls=self.owner()
        with PollReturns(Journey) as diagnosis:
            self.assertTrue(Journey.poll_original_current(owner,dict(sequence=1,capturedEpochMs=1800),1.8,1800))
            self.assertFalse(Journey.poll_original_current(owner,dict(sequence=2,capturedEpochMs=1800),0.,0))
        self.assertEqual(['host','epoch']*2,calls)
        self.assertEqual([True,False],[row['okay'] for row in diagnosis.rows])
        self.assertEqual([1,2],[row['sequence'] for row in diagnosis.rows])
        self.assertIsNone(diagnosis.tool)

    def test_same_received_peer_retains_real_age_and_no_extra_clock_read(self):
        owner,calls=self.owner()
        witness=dict(ticket='a'*32,sequence=3,actorSequence=9,capturedEpochMs=200)
        original=(b'original',.2,200,(0,0,0))
        with PollReturns(Journey) as diagnosis:
            self.assertFalse(Journey.poll_witness_current(owner,witness,original))
        self.assertEqual(['host','epoch'],calls)
        self.assertEqual((200,.2,200,False),tuple(diagnosis.rows[0][key] for key in
            ('captured','received','epochAtReceipt','okay')))

    def test_owned_tool_is_released_on_original_exception_without_changing_function(self):
        code=Journey.poll_original_current.__code__
        diagnosis=PollReturns(Journey)
        with self.assertRaisesRegex(ValueError,'original clock failure'):
            with diagnosis:
                tool=diagnosis.tool
                owner=SimpleNamespace(now=lambda:(_ for _ in ()).throw(ValueError('original clock failure')))
                Journey.poll_original_current(owner,{},0,0)
        self.assertEqual([],diagnosis.rows)
        self.assertIsNone(sys.monitoring.get_tool(tool))
        self.assertIs(code,Journey.poll_original_current.__code__)


class BrowserTemporaryRetentionTests(unittest.TestCase):
    def test_gc_context_failure_and_actual_interpreter_exit_keep_owned_diagnostic_originals(self):
        with tempfile.TemporaryDirectory(prefix='browser-diagnostic-retention-') as temporary:
            root=Path(temporary)
            code='''from pathlib import Path
import gc,json,tempfile
from self_tests import pico_browser_coordinator_worker as worker
worker.retained_temporaries()
paths={}
value=tempfile.TemporaryDirectory(prefix='gc-')
paths['gc']=value.name
(Path(value.name)/'marker').write_bytes(b'actual owned diagnostic bytes')
del value;gc.collect()
try:
    with tempfile.TemporaryDirectory(prefix='context-') as value:
        paths['context']=value
        (Path(value)/'marker').write_bytes(b'actual owned diagnostic bytes')
        raise RuntimeError('Original diagnostic unwind')
except RuntimeError:pass
value=tempfile.TemporaryDirectory(prefix='exit-')
paths['exit']=value.name
(Path(value.name)/'marker').write_bytes(b'actual owned diagnostic bytes')
(worker.ROOT/'paths.json').write_text(json.dumps(paths))
'''
            p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env=dict(os.environ,OVT_BROWSER_COORDINATOR_ROOT=str(root),PYTHONDONTWRITEBYTECODE='1'))
            stdout,stderr=p.communicate(timeout=10)
            self.assertEqual(0,p.returncode,stderr.decode());self.assertEqual(b'',stdout)
            self.assertFalse(Path('/proc',str(p.pid)).exists())
            paths=json.loads((root/'paths.json').read_text());self.assertEqual({'gc','context','exit'},set(paths))
            for value in paths.values():
                self.assertEqual(root,Path(value).parent)
                self.assertEqual(b'actual owned diagnostic bytes',(Path(value)/'marker').read_bytes())
            self.assertFalse(Path('/proc',str(p.pid)).exists())


class BrowserRetirementDiagnosticTests(unittest.TestCase):
    def fixture(self):
        from self_tests import test_pico_browser_capture_retirement as sources
        value=sources.PicoBrowserCaptureRetirementTests('runTest');value.setUp()
        self.addCleanup(value.doCleanups);value.baseline();return value

    def test_selected_original_methods_and_cadence_are_observed_without_extra_input(self):
        from self_tests.pico_browser_retirement_diagnostic import RetirementCosts
        source=self.fixture();before=len(source.f.target.command_log)
        with RetirementCosts() as costs:value=source.f.primary.retire_original_captures(source.f.actor)
        self.assertTrue(value['complete']);self.assertIsNone(costs.tool)
        report=costs.report();self.assertEqual([],report['unreturnedSelectedFrames'])
        self.assertTrue(report['cadence']);self.assertTrue(all(0<row['hostSeconds']<=.5 for row in report['cadence']))
        self.assertGreater(report['costs']['ChatArchiveCatalog.verify_all']['calls'],0)
        self.assertEqual(before,len(source.f.target.command_log))

    def test_actual_original_overlong_cadence_remains_refused_and_is_recorded(self):
        from unittest.mock import patch
        from adapters.normal_ui import NativeUIError
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        from self_tests.pico_browser_retirement_diagnostic import RetirementCosts
        source=self.fixture();append=PicoBrowserCaptureRetirement.append
        def slow(owner,row,*args,**kwargs):
            value=append(owner,row,*args,**kwargs)
            if row['kind']=='absence-window':source.f.clock.sleep(.55)
            return value
        with RetirementCosts() as costs,patch.object(PicoBrowserCaptureRetirement,'append',slow):
            with self.assertRaises(NativeUIError):source.f.primary.retire_original_captures(source.f.actor)
        self.assertIsNone(costs.tool);self.assertTrue(any(row['hostSeconds']>.5 for row in costs.report()['cadence']))
        owner=source.f.primary.capture_retirement;self.assertTrue(owner.failed);self.assertFalse(owner.completed)
        before=len(source.batches)
        with self.assertRaises(NativeUIError):owner.run()
        self.assertEqual(before,len(source.batches))


if __name__=='__main__':unittest.main()
