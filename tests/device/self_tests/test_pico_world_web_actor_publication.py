"""Original Actor acquisition/publication and the real pre-Parent-CAS phase gap.

Native/Qt/V8 remain explicit analytical seams. HTTP receipts and durable source
histories execute; this suite does not claim separate-process/eye retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from self_tests import test_pico_world_web_normal_close as previous


class WorldWebActorPublicationTests(unittest.TestCase):
    setUp=previous.WorldWebNormalCloseTests.setUp
    run=previous.WorldWebNormalCloseTests.run
    stop=previous.WorldWebNormalCloseTests.stop
    activate=previous.WorldWebNormalCloseTests.activate
    call=previous.WorldWebNormalCloseTests.call
    baseline=previous.WorldWebNormalCloseTests.baseline
    cleanup_call=previous.WorldWebNormalCloseTests.cleanup_call

    def test_actual_fourteen_and_cleanup_actor_publications_keep_independent_retained_sources(self):
        self.primary.prepare();self.primary.observe();self.actor.publish()
        for index in range(14):
            call=self.call(index);self.primary.act(call)
            primary=self.primary.observe();actor=self.actor.publish()
            self.assertEqual(primary['state'],actor['state'])
            self.assertNotEqual(self.primary.history.last['native']['commandId'],self.actor.history.last['native']['commandId'])
        self.primary.normal_close(self.cleanup_call());self.primary.observe();last=self.actor.publish()
        self.assertIn('script:world-web-client',last['resources']);self.assertEqual([],last['artifacts'])
        with self.actor.lock.held():
            self.actor.history.verify();rows=self.actor.history.rows
            self.assertEqual(48,len(rows));self.assertEqual('accepted',self.actor.history.publication['phase'])
            self.assertEqual(16,len([row for row in rows if row['event']=='publication-accepted']))
        self.assertEqual(14,len(self.actor.state['completed']));self.assertEqual('source-stopped',self.actor.state['phase'])
        self.assertEqual(1,len([row for row in self.target.normal_inputs if row['controlId']=='scripts.stop.0']))

    def test_exact_next_activation_precedes_parent_cas_without_target_or_reading_intent(self):
        self.baseline();call=self.call(0)
        files={path.name:path.read_bytes() for path in self.target.feature_root.iterdir()}
        counters=(self.target.sequence,self.target.native_sequence,self.actor.vm)
        with self.assertRaises(PhasePending):self.actor.publish()
        self.assertEqual(counters,(self.target.sequence,self.target.native_sequence,self.actor.vm))
        self.assertEqual(files,{path.name:path.read_bytes() for path in self.target.feature_root.iterdir()})
        self.primary.act(call);actual=self.actor.publish();self.assertTrue(actual['state']['open'])

    def test_skipped_activation_is_error_before_any_target_or_history_intent(self):
        self.baseline();self.call(0);self.call(1)
        files={path.name:path.read_bytes() for path in self.target.feature_root.iterdir()};sequence=self.target.sequence
        with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual(sequence,self.target.sequence)
        self.assertEqual(files,{path.name:path.read_bytes() for path in self.target.feature_root.iterdir()})

    def test_next_phase_changes_on_real_outer_exit_is_unavailable_not_pending(self):
        self.baseline();self.call(0);held=self.target.lock.held;exits=[];sequence=self.target.sequence
        @contextmanager
        def release():
            with held():yield
            self.assertIsNone(self.target.lock._owner);exits.append(True);self.call(1)
        with patch.object(self.target.lock,'held',side_effect=release):
            with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual([True],exits);self.assertEqual(sequence,self.target.sequence);self.assertTrue(self.actor.failed)
        self.assertEqual(1,len(self.actor.history.rows))

    def test_applied_lost_http_publication_retains_intent_and_cold_never_resends(self):
        self.primary.prepare();request=self.actor.source.client.request;issued=[]
        def lost(path,*args,**kwargs):
            value=request(path,*args,**kwargs)
            if path=='/runs/'+self.run+'/samples':issued.append(deepcopy(args[0]));raise OSError('lost actual HTTP reply')
            return value
        with patch.object(self.actor.source.client,'request',side_effect=lost):
            with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual(1,len(issued));self.assertEqual('issued',self.actor.history.publication['phase'])
        old={path.name:path.read_bytes() for path in self.target.feature_root.iterdir()};sequence=self.target.sequence
        cold=self.facade.prefix(self.target.selector,self.actor.source,self.foreign,role='actor')
        with self.assertRaises(NativeUIError):cold.publish()
        self.assertEqual(sequence,self.target.sequence)
        self.assertEqual(old,{path.name:path.read_bytes() for path in self.target.feature_root.iterdir()})

    def test_landed_publication_cas_cannot_reset_original_host_capture_age(self):
        self.primary.prepare();original=self.actor.source.client.request;count=[];now=self.actor.source.monotonic;extra=[0]
        def request(path,*args,**kwargs):
            if path=='/runs/'+self.run+'/samples':count.append(True)
            return original(path,*args,**kwargs)
        from adapters.pico4.browser_history import PicoBrowserHistory
        finish=PicoBrowserHistory.finish
        def slow(history,value):
            finish(history,value)
            if history.disk['role']=='actor' and history.publication is not None and history.publication['phase']=='issued':extra[0]+=2
        with patch.object(self.actor.source,'monotonic',side_effect=lambda:now()+extra[0]), \
             patch.object(self.actor.source.client,'request',side_effect=request),patch.object(PicoBrowserHistory,'finish',new=slow):
            with self.assertRaises(NativeUIError):self.actor.publish()
        self.assertEqual([],count);self.assertEqual('issued',self.actor.history.publication['phase'])


if __name__=='__main__':unittest.main()
