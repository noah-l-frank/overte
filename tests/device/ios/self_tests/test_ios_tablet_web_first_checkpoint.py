"""Actual common first-open freshness with independently acquired Actor PNGs.

This focused regression executes the unchanged common baseline and first
checkpoint. Native/clock producers are explicit models; full journey and
terminal cleanup are separate qualifications.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import unittest
from feature_journeys.engine import Journey
from feature_journeys.evidence import read_private_artifact
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.self_tests.tablet_web_actor_fixture import actor_until_stopped
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletFirstCheckpointTests(unittest.TestCase):
    def test_current_common_baseline_then_first_open_uses_only_post_input_actor_originals(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        matches=[(i,entry) for i,entry in enumerate(b.context_test._cleanups)
            if isinstance(getattr(entry[0],'__self__',None),tempfile.TemporaryDirectory)
            and entry[0].__self__.name==str(b.root) and entry[0].__name__=='cleanup']
        self.assertEqual(1,len(matches));i,entry=matches[0]
        entry[0].__self__._finalizer.detach();b.context_test._cleanups.pop(i)
        print('Actual first-checkpoint root retained: '+str(b.root),flush=True)
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ctx=multiprocessing.get_context('spawn');receive,send=ctx.Pipe(duplex=False);stop=ctx.Event()
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        actor=ctx.Process(target=actor_until_stopped,args=(inputs,fixture.clock,stop,send));actor.start();send.close()
        messages=[]
        def collect():
            while receive.poll(0):
                try:value=receive.recv()
                except EOFError:break
                messages.append(value);self.assertNotIn('error',value,value.get('originalTraceback',value.get('traceback')))
        def invoke(operation,values):
            collect();return getattr(primary,operation.rsplit('.',1)[1])(values)
        def witness():collect();return fixture.controller.request('/runs/'+RUN)
        def activate(ticket,verb='baseline',inputs=None):
            collect();return fixture.controller.request('/runs/'+RUN+'/active',dict(ticket=ticket,verb=verb,inputs=inputs or {}))
        def continuity(_stage,_verb):
            client,session,state,target,_=primary.runtime._existing(primary.selector)
            actual=primary.runtime.adapter._binding(primary.selector,client,session,state,target).continuity()
            self.assertEqual(int(b.binding['processIdentity']),actual['pid'])
        try:
            self.assertTrue(receive.poll(60));born=receive.recv();messages.append(born)
            self.assertNotIn('error',born,born.get('traceback'));self.assertNotEqual(os.getpid(),born['hostProcessId'])
            journey=Journey('tablet-web',RUN,b.source.fixture,invoke=invoke,witness=witness,activate=activate,
                read_artifact=lambda name:read_private_artifact(b.root,name),image_policy=dict(screen=fixture.settings['imagePolicy']),
                continuity=continuity,monotonic=b.mono,epoch_ms=b.host,sleep=primary.sleep,report=lambda _value:None)
            scenario=SCENARIOS['tablet-web'];ticket=secrets.token_hex(16);activate(ticket);barrier=b.host()
            journey.wait('owned-clean-baseline',ticket,barrier,expand(scenario['baseline'],context(RUN)),['peer'])
            step=scenario['steps'][0];self.assertEqual('open',step['verb'])
            ticket=secrets.token_hex(16);activate(ticket,step['verb'],expand(step['inputs'],context(RUN)));barrier=b.host()
            journey.required_lifecycle=journey.lifecycle.copy()
            journey.browser_transition=(step['documentTransition'],journey.samples[-1]['state']['documentLoads'])
            continuity('before','open');journey.call('act',dict(verb='open',inputs=expand(step['inputs'],context(RUN)),ticket=ticket,fixtureUrl=b.source.fixture));continuity('after','open')
            journey.wait('01-open',ticket,barrier,expand(step['state'],context(RUN)),step['evidence'])
            self.assertEqual(['owned-clean-baseline','01-open'],[row['phase'] for row in journey.phases])
            self.assertTrue(journey.samples[-1]['evidence']);self.assertTrue(journey.samples[-1]['witness']['facts']['open'])
            self.assertEqual(1,b.ui.file_ui.actions.count('script-file.confirm'));self.assertEqual([],fixture.sdk.errors)
            Path('.ios-host-tmp/tablet-web-first-checkpoint-report.json').write_text(json.dumps(dict(phases=journey.phases,samples=journey.samples),sort_keys=True))
        finally:
            failed=sys.exc_info()[0] is not None
            stop.set();actor.join(60)
            if actor.is_alive():actor.terminate();actor.join(5);self.fail('Actual focused Actor did not exit its host loop')
            collect();receive.close();self.assertEqual(0,actor.exitcode)
            audits=[value['audit'] for value in messages if value.get('audit') is not None]
            if not failed or audits:
                self.assertEqual(1,len(audits));self.assertEqual([],audits[0]['drift']);self.assertEqual([],audits[0]['added'])
                Path('.ios-host-tmp/tablet-web-first-checkpoint-actor-audit.json').write_text(json.dumps(audits[0],sort_keys=True))


if __name__=='__main__':unittest.main()
