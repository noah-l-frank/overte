"""Actual two-host OS/SDK/worker suffix, prior complete native seal modeled.

No actual Tablet live graph or full canonical final archive is manufactured.
The two real host processes, HTTP/phase/Stop/OS/deletion/CAS and worker marker
after that explicit precondition run through existing production classes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
import os
import tempfile
import unittest

from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.adapters.tablet_web_terminal_finish import worker_store
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,SELECTOR
from ios.self_tests.tablet_web_lifecycle_fixture import attach
from ios.self_tests.tablet_web_retired_fixture import TabletRetiredModel
from ios.self_tests import tablet_web_end_suffix_fixture as component
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletEndSuffixTests(unittest.TestCase):
    def test_actual_once_Stop_two_host_OS_quiet_SDK_end_and_own_worker_without_new_native_queries(self):
        f=PairedTabletFixture(self);b=f.boundary;model=attach(f,model_type=TabletRetiredModel)
        matches=[(index,row) for index,row in enumerate(b.context_test._cleanups)
            if isinstance(getattr(row[0],'__self__',None),tempfile.TemporaryDirectory)
            and row[0].__self__.name==str(b.root) and row[0].__name__=='cleanup']
        self.assertEqual(1,len(matches));index,row=matches[0]
        row[0].__self__._finalizer.detach();b.context_test._cleanups.pop(index)
        print('Actual small suffix originals retained: '+str(b.root),flush=True)
        ticket='e'*32;f.fixture.journal.activate(RUN,ticket,'cleanup',{})
        lock=ScriptSourceLock(b.root/'script-feature-sources.lock')
        with lock.held():component.phase_floor(f.primary,lock)
        ctx=multiprocessing.get_context('spawn');parent,child=ctx.Pipe()
        worker=ctx.Process(target=component.actor,args=((str(b.root),f.metadata,f.settings,f.fixture_url,b.base),f.clock,child))
        worker.start();child.close()
        def response():
            self.assertTrue(parent.poll(15),'Actual suffix worker did not answer')
            value=parent.recv();self.assertNotIn('error',value,value.get('traceback'));return value
        try:
            born=response();self.assertEqual('ready',born['kind']);self.assertNotEqual(os.getpid(),born['hostProcessId'])
            marker=PrivateFeatureState(b.root/'component-prior-native-seal.json')
            marker.write(dict(componentPriorNativeSealVersion=1,runId=RUN,ticket=ticket,
                note='Earlier complete native Tablet seal is explicitly modeled, not a production terminal carrier'),None)
            f.controller.request('/runs/'+RUN,method='DELETE')
            with f.primary.operation(),lock.held():
                owner=component.process(f.primary,lock);owner.prepare();owner.stop()
            self.assertFalse(model.running);self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in model.calls))
            native_queries=list(b.commands)
            for _round in range(3):
                with f.primary.operation(),lock.held():component.process(f.primary,lock).advance('primary')
                parent.send('advance');self.assertEqual('advanced',response()['kind'])
                b.sleep(1.6)
            with f.primary.operation(),lock.held():
                owner=component.process(f.primary,lock);owner.advance('primary');owner.verify()
                self.assertEqual('complete',owner.state['phase'])
                for role,pid in (('primary',os.getpid()),('actor',born['hostProcessId'])):
                    self.assertTrue(owner.state['roles'][role]['issuers'])
                    self.assertTrue(all(row['hostProcessId']==pid for row in owner.state['roles'][role]['issuers']))
                    self.assertGreaterEqual(owner.role_os(role)['samples'],3)
                session=TabletWebSessionEnd(owner);original=session.advance();self.assertIsNotNone(original)
                self.assertEqual(original,TabletWebSessionEnd(owner).advance())
                self.assertIsNone(f.primary.runtime.adapter.read_session(SELECTOR))
                self.assertIsNone(f.primary.runtime.adapter._binding_store(SELECTOR).read())
            requests=list(f.sdk.calls);os_queries=len(model.originals)
            parent.send('retire');retired=response();self.assertEqual('retired',retired['kind'])
            worker.join(10);self.assertEqual(0,worker.exitcode)
            value=worker_store(f.primary).read();self.assertEqual(born['hostProcessId'],value['hostProcessId'])
            self.assertEqual(retired['sha256'],digest(value));self.assertEqual(requests,f.sdk.calls)
            self.assertEqual(os_queries,len(model.originals));self.assertEqual(native_queries,b.commands)
            self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in model.calls))
            self.assertEqual(1,sum(method=='DELETE' for method,_ in f.sdk.calls));self.assertFalse(f.sdk.present)
            self.assertEqual([],f.sdk.errors);self.assertFalse((b.root/('tabletweb-final-archive-'+RUN+'.json')).exists())
        finally:
            if worker.is_alive():worker.terminate();worker.join(5)  # Failed component teardown, not native retirement.
            parent.close()


if __name__=='__main__':unittest.main()
