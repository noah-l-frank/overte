"""Actual existing-SDK two-role production worker through unused terminal end.

This is the unloaded/never-staged setup branch, not the active 26-step journey.
Native and OS producers plus their distinct clocks are models. All source/
tail/publication/terminal/Stop/OS/SDK/archive implementations execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from feature_journeys import terminal as protocol
from feature_journeys.witness import projection
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.adapters.tablet_web_terminal import TabletWebTerminal
from ios.self_tests.tablet_web_terminal_fixture import TerminalPairedTabletFixture,production_actor
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletTerminalUnloadedFlowTests(unittest.TestCase):
    def test_real_production_worker_paired_unused_quiet_seal_once_Stop_OS_SDK_and_repeat(self):
        fixture=TerminalPairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        # Retain this exact original inode graph, even at a failed boundary.
        # Only the TemporaryDirectory that actually owns this test root is
        # detached; no foreign directory/cleanup registration is touched.
        matches=[(i,entry) for i,entry in enumerate(b.context_test._cleanups)
            if isinstance(getattr(entry[0],'__self__',None),tempfile.TemporaryDirectory)
            and entry[0].__self__.name==str(b.root) and entry[0].__name__=='cleanup']
        self.assertEqual(1,len(matches));i,entry=matches[0];entry[0].__self__._finalizer.detach();b.context_test._cleanups.pop(i)
        print('Actual original root retained: '+str(b.root),flush=True)
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ctx=multiprocessing.get_context('spawn');receive,send=ctx.Pipe(duplex=False)
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        actor=ctx.Process(target=production_actor,args=(inputs,fixture.clock,send));actor.start();send.close();messages=[]
        def receive_actual():
            while receive.poll(0):
                try:message=receive.recv()
                except EOFError:return
                messages.append(message);self.assertNotIn('error',message,message.get('traceback'))
                if 'workerReturned' in message:self.assertEqual(0,message['workerReturned'],message.get('diagnostics'))
        def peer(ticket,after=0,facts=None,barrier=None):
            end=time.monotonic()+60
            while True:
                rows=fixture.fixture.journal.snapshot(RUN)['entries']
                matched=[row for row in rows if row['ticket']==ticket and row['actorSequence']>after
                    and (facts is None or row['facts']==facts) and (barrier is None or row['capturedEpochMs']>=barrier)
                    and b.host()-1500<=row['capturedEpochMs']<=b.host()+250]
                if matched:return deepcopy(matched[-1])
                receive_actual();self.assertTrue(actor.is_alive(),messages)
                self.assertLess(time.monotonic(),end,'Actual independent production publication not available');time.sleep(.05)
        try:
            self.assertTrue(receive.poll(60));born=receive.recv();messages.append(born)
            self.assertNotIn('error',born,born.get('traceback'));self.assertNotEqual(os.getpid(),born['hostProcessId'])
            peer('f'*32);print('Actual production Actor baseline published',flush=True)
            ticket='e'*32;fixture.fixture.journal.activate(RUN,ticket,'cleanup',{});barrier=b.host()
            self.assertEqual(dict(performed=True),primary.cleanup(dict(contractVersion=16,runId=RUN)))
            result=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
            print('Actual primary unused native/host quiet acquired',flush=True)
            first_peer=peer(ticket,facts=projection('tablet-web',result['state']))
            print('Actual Actor unused native/host quiet published',flush=True)
            request=dict(contractVersion=1,runId=RUN,stage='inspect')
            descriptor=primary.terminal(request)['description'];self.assertEqual([],descriptor['roles']['primary']['heldResources'])
            samples=[];last=0
            while True:
                own=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
                remote=peer(ticket,last,projection('tablet-web',own['state']),barrier);last=remote['actorSequence']
                samples.append(dict(primary=own,actor=remote))
                if len(samples)>=3 and all(samples[-1][role]['capturedEpochMs']-samples[0][role]['capturedEpochMs']>=3000 for role in ('primary','actor')):break
                self.assertLess(len(samples),81);primary.sleep(.25)
            protocol.window(samples,descriptor)
            seal=primary.terminal(dict(contractVersion=1,runId=RUN,stage='seal',description=descriptor,samples=samples))['seal']
            print('Actual paired original live terminal seal complete',flush=True)
            fixture.fixture.journal.close(RUN);b.browser.close(RUN)
            final=primary.terminal(dict(contractVersion=1,runId=RUN,stage='finish',seal=seal))['end'];protocol.ended(final,seal)
            print('Actual Primary once Stop + both OS + once SDK end archived',flush=True)
            end=time.monotonic()+60
            while actor.is_alive() and time.monotonic()<end:receive_actual();actor.join(.05)
            receive_actual();self.assertEqual(0,actor.exitcode);self.assertTrue(any(row.get('workerReturned')==0 for row in messages))
            for row in messages:
                if row.get('audit') is not None:
                    self.assertEqual([],row['audit']['drift']);self.assertEqual([],row['audit']['added'])
                    Path('.ios-host-tmp/tablet-web-terminal-unloaded-actor-audit.json').write_text(json.dumps(row['audit'],sort_keys=True))
            self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in fixture.lifecycle.calls))
            self.assertEqual(1,sum(method=='DELETE' for method,_path in fixture.sdk.calls));self.assertFalse(fixture.sdk.present)
            before=list(fixture.sdk.calls);commands=list(b.commands)
            self.assertEqual(final,primary.terminal(dict(contractVersion=1,runId=RUN,stage='finish',seal=seal))['end'])
            self.assertEqual(before,fixture.sdk.calls);self.assertEqual(commands,b.commands);self.assertEqual([],fixture.sdk.errors)
        except BaseException as error:
            seen=set();original=error
            while original.__context__ is not None and id(original) not in seen:seen.add(id(original));original=original.__context__
            if original is not error:raise AssertionError('Actual first Tablet terminal boundary') from original
            raise
        finally:
            if actor.is_alive():actor.terminate();actor.join(5)  # Failed test teardown, never qualified worker retirement.
            receive.close()


if __name__=='__main__':unittest.main()
