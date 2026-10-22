"""Nested source rollback counterexamples at explicit synthetic VM seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent))
from test_snapshot_handoff import Boundary
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_loads import history as loads
from self_tests.test_native_script_observation import effect_source


class SnapshotHandoffAuditTests(unittest.TestCase):
    def test_outer_progress_cannot_erase_original_require_compilation_load_or_effect_history(self):
        for fault in ('require','compiled','loads','effects','root'):
            b=Boundary();reader=b.reader();script=b.packet['source']['source']['group']['script']
            if fault=='require':script['source']['engines'][0]['required'].update(sequence=1,modules=[dict(url='file:///actual/scripts/companion.js',loaded=True,cached=False,sequence=1,capturedEpochMs=17000)])
            elif fault=='compiled':
                extra=deepcopy(script['source']['engines'][0]['compiled']['compilations'][0]);extra.update(scriptId=6,resourceName='file:///actual/scripts/other.js')
                script['source']['engines'][0]['compiled']['compilations'].append(extra)
            elif fault=='loads':loads(script)
            elif fault=='effects':effect_source(script)
            reader.read();b.packet=b.frame();group=b.packet['source']['source']['group'];script=group['script']
            if fault=='require':script['source']['engines'][0]['required'].update(sequence=0,modules=[])
            elif fault=='loads':loads(script,[])
            elif fault=='root':
                for key in ('rootsBefore','rootsAfter'):
                    value=group[key]['source']['defaultScriptsUrl'];group[key]['source']['defaultScriptsUrl']=value.rstrip('/') if value.endswith('/') else value+'/'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read()

    def test_original_retired_manager_cannot_resurrect_after_an_intermediate_frame(self):
        b=Boundary();reader=b.reader();source=b.packet['source']['source']['group']['script']['source']
        engine=deepcopy(source['engines'][0]);engine['required']['instance']='9'*32;engine['url']='file:///actual/scripts/other.js'
        manager=deepcopy(source['membership']['managers'][0]);manager.update(instance='9'*32,url=engine['url'])
        source['engines'].append(engine);source['membership']['managers'].append(manager);source['membership']['revision']=2
        reader.read();b.packet=b.frame();b.packet['source']['source']['group']['script']['source']['membership']['revision']=3;reader.read()
        b.packet=b.frame();source=b.packet['source']['source']['group']['script']['source'];source['engines'].append(engine)
        source['membership']['managers'].append(manager);source['membership']['revision']=4
        with self.assertRaises(NativeUIError):reader.read()

    def test_reconstruction_replays_full_original_history_without_treating_it_as_current(self):
        b=Boundary();source=b.packet['source']['source']['group']['script']['source']
        engine=deepcopy(source['engines'][0]);engine['required']['instance']='9'*32;engine['url']='file:///actual/scripts/other.js'
        manager=deepcopy(source['membership']['managers'][0]);manager.update(instance='9'*32,url=engine['url'])
        source['engines'].append(engine);source['membership']['managers'].append(manager);source['membership']['revision']=2
        originals=[deepcopy(b.packet)];b.packet=b.frame();b.packet['source']['source']['group']['script']['source']['membership']['revision']=3;originals.append(deepcopy(b.packet))
        reader=b.reader();reader.restore_history(originals)
        with self.assertRaises(NativeUIError):reader.read()
        b.packet=b.frame();source=b.packet['source']['source']['group']['script']['source'];source['engines'].append(engine);source['membership']['managers'].append(manager);source['membership']['revision']=4
        with self.assertRaises(NativeUIError):reader.read()

    def test_control_cannot_erase_retired_jobs_under_an_unchanged_native_sample(self):
        b=Boundary();controller=b.controller();send=b.send
        def with_original_job(request):
            send(request);b.result['jobs'].append(dict(b.result['jobs'][0],handoffId='c'*32,instance='c'*32,retired=True,timerActive=False))
        controller.send=with_original_job;controller.request(b.owner['runId'],'start',b.owner['handoffId']);previous=deepcopy(controller.last)
        def cached(request):
            send(request);b.result['source']=deepcopy(previous['source']);b.result['jobs']=previous['jobs'][:1]
        controller.send=cached
        with self.assertRaises(NativeUIError):controller.request(b.owner['runId'],'observe',b.owner['handoffId'])

    def test_restored_originals_require_and_accept_an_actually_new_native_acquisition(self):
        b=Boundary();reader=b.reader();reader.restore_history([deepcopy(b.packet)]);b.packet=b.frame()
        self.assertEqual(b.packet['source']['source'],reader.read())
        with self.assertRaises(NativeUIError):reader.restore_history([])

    def test_control_rejects_clock_rollback_before_reading_another_source(self):
        b=Boundary();controller=b.controller();controller.request(b.owner['runId'],'start',b.owner['handoffId']);b.time=-1
        with self.assertRaises(NativeUIError):controller.request(b.owner['runId'],'observe',b.owner['handoffId'])
        self.assertEqual(1,len(b.commands))


if __name__=='__main__':unittest.main()
