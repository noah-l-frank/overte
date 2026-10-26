"""Normal manager/picker/Home -> independent custody -> once ordinary Open.

The actor publishes baseline then performs one owned admission attempt;
it receives no expected facts. Native/UI producers and clocks are host models.
No page/PNG checkpoint, full Journey or retirement is qualified by this case.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import os
import tempfile
import traceback
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from feature_journeys.witness import Client
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.adapters.tablet_web_app_owner import input_scopes
from ios.adapters.tablet_web_app_readiness import ready
from ios.self_tests.tablet_web_host_clock import advance
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,ExistingAdapter,SELECTOR,ACTOR
from ios.self_tests.test_ios_tablet_web_sources import RUN


class AwaitingActor(InterruptedError):pass


def admission_actor(inputs,clock,channel):
    try:
        root,metadata,settings,fixture_url,base=inputs
        def mono():return clock.value
        def epoch():return base+round(clock.value*1000)+10000
        def sleep(seconds):advance(clock,seconds)
        runtime=IOSTabletWebRuntime(ExistingAdapter(root,metadata))
        actor=runtime._tablet_web_feature(SELECTOR,RUN,role='actor',client=Client(fixture_url,ACTOR,
            monotonic=mono,sleep=sleep),settings=settings)
        actor.monotonic,actor.epoch_ms,actor.sleep=mono,epoch,sleep
        result=actor.publish();channel.send(dict(hostProcessId=os.getpid(),publication=result))
        while True:
            command=channel.recv()
            if command=='retain-current':channel.send(dict(publication=actor.publish()))
            elif command=='end-component':return
            else:raise AssertionError('Unreviewed component scheduling command')
    except BaseException as error:
        channel.send(dict(error=type(error).__name__,traceback=traceback.format_exc()));raise
    finally:channel.close()


class TabletOpenAdmissionTests(unittest.TestCase):
    def test_normal_selection_waits_for_actual_independent_custody_then_resumes_same_Open_once(self):
        f=PairedTabletFixture(self);b=f.boundary;primary=f.primary
        matches=[(index,row) for index,row in enumerate(b.context_test._cleanups)
            if isinstance(getattr(row[0],'__self__',None),tempfile.TemporaryDirectory)
            and row[0].__self__.name==str(b.root) and row[0].__name__=='cleanup']
        self.assertEqual(1,len(matches));index,row=matches[0]
        row[0].__self__._finalizer.detach();b.context_test._cleanups.pop(index)
        print('Actual normal Open admission originals retained: '+str(b.root),flush=True)
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ticket='b'*32
        call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb='open',inputs={})
        journal=PrivateFeatureState(b.root/('tabletweb-actions-'+RUN+'.json'));sleep=primary.sleep
        def waiting(seconds):
            saved=journal.read()
            pending=None if saved is None else unpack(saved['payload'])[0]['pending']
            if pending is not None and pending['phase']=='waiting':raise AwaitingActor()
            sleep(seconds)
        ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe()
        process=ctx.Process(target=admission_actor,args=((str(b.root),f.metadata,f.settings,f.fixture_url,b.base),f.clock,child))
        process.start();child.close()
        try:
            self.assertTrue(parent.poll(60),'Independent original baseline did not return')
            actual=parent.recv();self.assertNotIn('error',actual,actual.get('traceback'))
            self.assertNotEqual(os.getpid(),actual['hostProcessId']);self.assertGreaterEqual(actual['publication'],1)
            f.fixture.journal.activate(RUN,ticket,'open',{});primary.sleep=waiting
            with self.assertRaises(AwaitingActor):primary.act(call)
            primary.sleep=sleep
            self.assertEqual(1,b.ui.file_ui.actions.count('script-file.confirm'));self.assertEqual(1,len(b.loaded))
            self.assertEqual([],b.host_app.call('read')['navigations'])
            saved=journal.path.read_bytes();inode=journal.path.stat().st_ino
            parent.send('retain-current');self.assertTrue(parent.poll(60),'Independent original custody did not return')
            retained=parent.recv();self.assertNotIn('error',retained,retained.get('traceback'));self.assertIsNone(retained['publication'])
            self.assertTrue(process.is_alive());self.assertEqual(saved,journal.path.read_bytes());self.assertEqual(inode,journal.path.stat().st_ino)
            with primary.operation(),primary.parts() as runtime:
                scopes=input_scopes(b.root,b.binding,RUN,ready_only=True);self.assertEqual(1,len(scopes));self.assertTrue(ready(runtime,scopes))
            self.assertEqual([],b.host_app.call('read')['navigations'])
            self.assertEqual(dict(performed=True),primary.act(call))
            self.assertEqual(1,len(b.host_app.call('read')['navigations']))
            loaded=len(b.loaded);confirms=b.ui.file_ui.actions.count('script-file.confirm')
            self.assertEqual(dict(performed=True),primary.act(call))
            self.assertEqual(loaded,len(b.loaded));self.assertEqual(confirms,b.ui.file_ui.actions.count('script-file.confirm'))
            self.assertEqual(1,len(b.host_app.call('read')['navigations']))
            self.assertEqual([],b.ui.lifecycle_inputs);self.assertEqual([],f.sdk.errors)
            self.assertFalse(any(method=='DELETE' for method,_path in f.sdk.calls))
            parent.send('end-component');process.join(10);self.assertEqual(0,process.exitcode)
        finally:
            primary.sleep=sleep
            if process.is_alive():process.terminate();process.join(5)  # Failed component teardown, not retirement.
            parent.close()


if __name__=='__main__':unittest.main()
