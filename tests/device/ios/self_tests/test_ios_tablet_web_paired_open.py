"""Current public ordinary open and independent observer over one actual SDK.

Real host processes/HTTP/AFC/selected JS/original files execute. Native/renderer
and boundary clock operands remain explicit models. This open-only window
does not qualify complete cleanup, terminal OS/SDK closure or device behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import json
import os
from pathlib import Path
import time
import unittest
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.tablet_web_actor_fixture import actor_until_stopped
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletPairedOpenTests(unittest.TestCase):
    def test_public_normal_open_waits_for_independent_app_admission_then_both_own_page_and_screen(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary
        fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        context=multiprocessing.get_context('spawn');receive,send=context.Pipe(duplex=False);stop=context.Event()
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        actor=context.Process(target=actor_until_stopped,args=(inputs,fixture.clock,stop,send));actor.start();send.close()
        try:
            self.assertTrue(receive.poll(60));started=receive.recv();self.assertNotIn('error',started,started.get('traceback'))
            self.assertNotEqual(os.getpid(),started['hostProcessId'])
            ticket='b'*32;fixture.fixture.journal.activate(RUN,ticket,'open',{})
            call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb='open',inputs={})
            try:self.assertEqual(dict(performed=True),fixture.primary.act(call))
            except Exception as error:
                seen=set()
                while error.__context__ is not None and id(error) not in seen:seen.add(id(error));error=error.__context__
                raise AssertionError('Actual normal public open boundary') from error
            try:own=fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
            except Exception as error:
                seen=set()
                while error.__context__ is not None and id(error) not in seen:seen.add(id(error));error=error.__context__
                raise AssertionError('Actual normal public observe boundary') from error
            self.assertTrue(own['state']['open']);self.assertTrue(own['artifacts'])
            end=time.monotonic()+60
            while time.monotonic()<end:
                rows=fixture.fixture.journal.snapshot(RUN)['entries']
                if any(row['ticket']==ticket and row['facts']['open'] for row in rows):break
                if receive.poll(0):
                    message=receive.recv();self.assertNotIn('error',message,message.get('traceback'))
                time.sleep(.05)
            else:self.fail('Independent original observer did not publish the actual opened page')
            self.assertEqual(1,b.ui.file_ui.actions.count('script-file.confirm'));self.assertEqual(1,len(b.loaded))
            self.assertFalse(any(method=='POST' and path=='/session' or method=='DELETE' and path=='/session/'+b.binding['sessionId']
                for method,path in fixture.sdk.calls));self.assertEqual([],fixture.sdk.errors)
            self.assertEqual([],b.ui.lifecycle_inputs)
        finally:
            stop.set();actor.join(60)
            if actor.is_alive():actor.terminate();actor.join(5)
            else:
                while receive.poll(0):
                    try:message=receive.recv()
                    except EOFError:break
                    self.assertNotIn('error',message,message.get('traceback'))
                    if message.get('audit') is not None:
                        audit=message['audit'];self.assertEqual([],audit['drift']);self.assertEqual([],audit['added'])
                        Path('.ios-host-tmp/tablet-web-paired-open-actor-audit.json').write_text(json.dumps(audit,sort_keys=True))
            receive.close()


if __name__=='__main__':unittest.main()
