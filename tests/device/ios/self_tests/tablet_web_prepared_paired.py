"""Actual independent pair with an explicit prepared normal-file-load boundary.

The full ordinary file selection is separately qualified. This helper stages
and executes the same original files, records actual primary custody, and
requires the Actor to acquire its own live app originals before normal Open.
No page facts or expected effects are supplied to that observer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import json
import os
from pathlib import Path
import time
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.self_tests.tablet_web_actor_fixture import actor_until_stopped
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class PreparedTabletPair:
    def __init__(self,test,*,fixture_factory=PairedTabletFixture,load_normally=False):
        self.test=test;self.closed=False;self.pending_failure=False;self.fixture=fixture_factory(test);self.b=self.fixture.boundary
        primary=self.fixture.primary;primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ctx=multiprocessing.get_context('spawn');self.receive,send=ctx.Pipe(duplex=False);self.stop=ctx.Event()
        inputs=(str(self.b.root),self.fixture.metadata,self.fixture.settings,self.fixture.fixture_url,self.b.base)
        self.actor=ctx.Process(target=actor_until_stopped,args=(inputs,self.fixture.clock,self.stop,send));self.actor.start();send.close()
        test.addCleanup(self.close)
        test.assertTrue(self.receive.poll(60));birth=self.receive.recv();test.assertNotIn('error',birth,birth.get('traceback'))
        test.assertNotEqual(os.getpid(),birth['hostProcessId']);self.host=birth['hostProcessId']
        ticket='b'*32;self.fixture.fixture.journal.activate(RUN,ticket,'open',{})
        if load_normally:
            # Cleanup tests need the real manager/picker/Home custody chain,
            # not merely a prepared app and its independently measured effects.
            test.assertEqual(dict(performed=True),primary.act(dict(contractVersion=16,runId=RUN,ticket=ticket,
                fixtureUrl=self.b.source.fixture,verb='open',inputs={})))
            self.wait(ticket,lambda facts:facts['open']);return
        with primary.parts() as runtime:
            app=TabletWebAppOwner(runtime);name='tabletweb-app-files-'+RUN+'-1.json'
            owned=OwnedTabletWebAppFiles(None,PrivateFeatureState(self.b.root/name),self.b.binding).reserve_app(RUN,self.b.source.fixture,ticket)
            runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
            directory=self.b.directories[owned['runId']].as_uri();self.b.load(directory+'/script.js');self.b.ui.qt.opened=True
            admission=runtime.remember_app(owned)
            app.state['generations'].append(dict(index=1,ticket=ticket,ownerFile=name,reserved=True,ownership=owned,directory=directory,admission=admission,dialogBefore=None));app.save()
        ready=PrivateFeatureState(self.b.root/('tabletweb-app-ready-'+RUN+'-actor-'+owned['runId']+'.json'))
        end=time.monotonic()+60
        while ready.read() is None:
            self.errors();test.assertLess(time.monotonic(),end,'Independent actual Home original did not arrive');time.sleep(.05)
        # The ordinary action reuses this exact admitted input generation,
        # requalifies Actor readiness, journals and sends the normal click,
        # then durably records input return. A manual click would leave the
        # independent publisher without its required completed-input cue.
        test.assertEqual(dict(performed=True),primary.act(dict(contractVersion=16,runId=RUN,ticket=ticket,
            fixtureUrl=self.b.source.fixture,verb='open',inputs={})))
        self.wait(ticket,lambda facts:facts['open'])

    def __enter__(self):return self
    def __exit__(self,*_arguments):self.close()

    def errors(self):
        while self.receive.poll(0):
            try:message=self.receive.recv()
            except EOFError:self.test.fail('Independent Actor ended before the test boundary')
            self.test.assertNotIn('error',message,message.get('originalTraceback',message.get('traceback')))

    def wait(self,ticket,predicate):
        end=time.monotonic()+60
        while True:
            rows=self.fixture.fixture.journal.snapshot(RUN)['entries'];matches=[row for row in rows if row['ticket']==ticket]
            if matches and predicate(matches[-1]['facts']):return matches[-1]
            self.errors()
            if time.monotonic()>=end:self.pending_failure=True
            self.test.assertLess(time.monotonic(),end,'Independent original publication did not arrive');time.sleep(.05)

    def close(self):
        if self.closed:return
        self.closed=True
        self.stop.set();end=time.monotonic()+60;audited=False
        def message():
            nonlocal audited
            try:actual=self.receive.recv()
            except EOFError:return False
            self.test.assertNotIn('error',actual,actual.get('traceback'))
            if self.pending_failure and actual.get('pendingDiagnostics'):
                print('Actual bounded Actor pending diagnostics:\n'+json.dumps(actual['pendingDiagnostics'],indent=2),flush=True)
            if actual.get('audit') is not None:
                audit=actual['audit'];self.test.assertEqual([],audit['drift']);self.test.assertEqual([],audit['added'])
                Path('.ios-host-tmp/tablet-web-prepared-actor-audit.json').write_text(json.dumps(audit,sort_keys=True));audited=True
            return True
        while self.actor.is_alive() and time.monotonic()<end:
            if self.receive.poll(.05):
                if not message():break
            self.actor.join(.025)
        self.actor.join(.1)
        if self.actor.is_alive():self.actor.terminate();self.actor.join(5)
        while self.receive.poll(0):
            if not message():break
        self.receive.close()
        self.test.assertEqual(0,self.actor.exitcode,'Independent observer did not exit normally at the test boundary')
        if os.environ.get('OVT_TABLET_PROFILE_FREEZE'):self.test.assertTrue(audited,'Independent actor did not return its actual import audit')
