"""Full unchanged common Tablet journey through the actual direct factory.

Ordinary selected JS/WDA HTTP/private originals and a separate production
worker execute. UIKit/WK/Qt/OS producers and distinct clocks are explicit host
models. This does not qualify native/device execution or InstalledAdapter CLI
routing. Complete capability remains closed until all integration gates pass.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from feature_journeys.engine import Journey
from feature_journeys.terminal import PROFILE
from feature_journeys.evidence import read_private_artifact
from ios.self_tests.tablet_web_terminal_fixture import TerminalPairedTabletFixture,production_actor
from ios.self_tests.test_ios_tablet_web_sources import RUN


class PrefixFinishedBeforeNextInput(Exception):
    """Controlled host test refusal before the next actual product input."""


class TabletFullCurrentTests(unittest.TestCase):
    def test_common_all_current_steps_ordinary_inputs_independent_production_worker_and_terminal(self):
        self.run_current()
    def run_current(self,*,prefix=None):
        self.assertIn(prefix,(None,4));artifact_prefix='tablet-web-full-current' if prefix is None else 'tablet-web-prefix-four-current'
        fixture=TerminalPairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        matches=[(i,entry) for i,entry in enumerate(b.context_test._cleanups)
            if isinstance(getattr(entry[0],'__self__',None),tempfile.TemporaryDirectory)
            and entry[0].__self__.name==str(b.root) and entry[0].__name__=='cleanup']
        self.assertEqual(1,len(matches));i,entry=matches[0];entry[0].__self__._finalizer.detach();b.context_test._cleanups.pop(i)
        print('Actual full original root retained: '+str(b.root),flush=True)
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ctx=multiprocessing.get_context('spawn');receive,send=ctx.Pipe(duplex=False)
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        actor=ctx.Process(target=production_actor,args=(inputs,fixture.clock,send));actor.start();send.close();messages=[]
        def collect():
            while receive.poll(0):
                try:message=receive.recv()
                except EOFError:return
                messages.append(message);self.assertNotIn('error',message,message.get('traceback'))
                if 'workerReturned' in message:self.assertEqual(0,message['workerReturned'],message.get('diagnostics'))
        acts=[]
        def invoke(operation,values):
            collect();kind=operation.rsplit('.',1)[1]
            self.assertTrue(operation.startswith('feature.tablet-web.') and kind in ('act','observe','cleanup','terminal'))
            if kind=='act' and prefix is not None and len(acts)==prefix:
                raise PrefixFinishedBeforeNextInput('Planned host refusal before any fifth product input')
            result=getattr(primary,kind)(values)
            if kind=='act':acts.append(values['verb'])
            if kind!='observe':print('Actual public '+kind+' '+str(values.get('verb',values.get('stage','')))+' returned',flush=True)
            return result
        def witness():collect();return fixture.controller.request('/runs/'+RUN)
        def activate(ticket,verb='baseline',inputs=None):
            collect();return fixture.controller.request('/runs/'+RUN+'/active',dict(ticket=ticket,verb=verb,inputs=inputs or {}))
        def continuity(_stage,_verb):
            collect();base=primary.runtime.adapter
            client,session,state,target,_scope=primary.runtime._existing(primary.selector)
            gate=base._binding(primary.selector,client,session,state,target);actual=gate.continuity()
            self.assertEqual(int(b.binding['processIdentity']),actual['pid'])
        reports=[]
        def report(value):
            reports.append(value)
            Path('.ios-host-tmp/'+artifact_prefix+'-report.json').write_text(json.dumps(value,sort_keys=True))
        try:
            self.assertTrue(receive.poll(60));born=receive.recv();messages.append(born)
            self.assertNotIn('error',born,born.get('traceback'));self.assertNotEqual(os.getpid(),born['hostProcessId'])
            journey=Journey('tablet-web',RUN,b.source.fixture,invoke=invoke,witness=witness,activate=activate,
                read_artifact=lambda name:read_private_artifact(b.root,name),image_policy=dict(screen=fixture.settings['imagePolicy']),
                continuity=continuity,monotonic=b.mono,epoch_ms=b.host,sleep=primary.sleep,report=report,
                terminal_profile=PROFILE,retire_fixture=lambda:fixture.controller.request('/runs/'+RUN,method='DELETE'))
            if prefix is None:journey.execute()
            else:
                with self.assertRaises(PrefixFinishedBeforeNextInput):journey.execute()
                # The controlled refusal is expected. A real cleanup failure
                # still needs its original traceback in this private test log;
                # assertRaises otherwise hides its attached diagnostic note.
                if journey.cleanup_errors:raise journey.cleanup_errors[0]
            self.assertEqual(1,len(reports));result=reports[0]
            self.assertEqual(prefix is None,result['sequenceCompleted']);self.assertTrue(result['cleanupSucceeded'])
            if prefix is not None:
                self.assertEqual(['open','focus-type','submit','clear-text'],acts)
                for index,verb in enumerate(acts,1):self.assertTrue(any(row['phase']==format(index,'02d')+'-'+verb for row in result['phases']))
            end=time.monotonic()+60
            while actor.is_alive() and time.monotonic()<end:collect();actor.join(.05)
            collect();self.assertEqual(0,actor.exitcode);self.assertTrue(any(row.get('workerReturned')==0 for row in messages))
            for row in messages:
                if row.get('audit') is not None:
                    self.assertEqual([],row['audit']['drift']);self.assertEqual([],row['audit']['added'])
                    Path('.ios-host-tmp/'+artifact_prefix+'-actor-audit.json').write_text(json.dumps(row['audit'],sort_keys=True))
            self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in fixture.lifecycle.calls))
            self.assertEqual(1,sum(method=='DELETE' for method,_path in fixture.sdk.calls));self.assertFalse(fixture.sdk.present)
            before=list(fixture.sdk.calls);commands=list(b.commands)
            final=primary.terminal(dict(contractVersion=1,runId=RUN,stage='finish',seal=journey.terminal_seal))['end']
            self.assertEqual(journey.terminal_end,final);self.assertEqual(before,fixture.sdk.calls);self.assertEqual(commands,b.commands)
            self.assertEqual([],fixture.sdk.errors)
        finally:
            if actor.is_alive():actor.terminate();actor.join(5)  # Failed test teardown, no retirement claim.
            receive.close()


if __name__=='__main__':unittest.main()
