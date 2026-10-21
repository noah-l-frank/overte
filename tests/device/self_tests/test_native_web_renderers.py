"""Synthetic renderer/queue originals; no JVM, EGL, native build or hardware."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_web_runtime import NativeWebRuntime,active_marker,released
from adapters.normal_ui import NativeUIError
from self_tests.test_native_web_runtime import Boundary,RUN,ROOT,URL,SHA


class RendererBoundary(Boundary):
    def __init__(self):
        super().__init__();self.renderer=dict(id='e'*32,handle='1',creation=1,sourceOwned=True,sourceSha256=SHA,
            objectAlive=True,threadAlive=True,mainCallbacks=0,glCallbacks=0,retainedCallbacks=0,
            closed=False,released=False,releaseSucceeded=True)
    def send(self,request):
        super().send(request)
        if self.pending is not None:self.pending['webRuntimeVersion']=2
    def packet(self):
        packet=super().packet();packet['webRuntimeVersion']=2
        packet['source']['java'].update(javaWebRuntimeVersion=2,renderers=[deepcopy(self.renderer)])
        return packet
    def reader(self):
        return NativeWebRuntime(self.send,self.original,self.now,self.guard,31,require_renderers=True,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def close(self):
        self.revoked=True;self.renderer.update(closed=True,released=True,threadAlive=False)


class WebRendererTests(unittest.TestCase):
    def test_marker_requires_original_same_handle_creation_and_running_renderer(self):
        source=RendererBoundary();value=source.reader().read(RUN,ROOT)
        self.assertEqual(source.renderer,value['source']['java']['renderers'][0])
        self.assertEqual('1',active_marker(value,URL)['native']['handle'])
        self.assertNotIn('renderer',source.commands[0])

    def test_legacy_inventory_is_readable_but_cannot_supply_required_renderer_evidence(self):
        source=Boundary();reader=source.reader();reader.require_renderers=True
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(1,len(source.commands));self.assertIsNone(reader.last)
        value=Boundary().reader().read(RUN,ROOT)
        with self.assertRaises(NativeUIError):released(value,require_renderers=True)

    def test_view_absence_or_revocation_does_not_hide_original_live_worker_or_callbacks(self):
        changes=[dict(threadAlive=True),dict(mainCallbacks=1),dict(glCallbacks=1),dict(retainedCallbacks=1),
            dict(released=False),dict(releaseSucceeded=False),dict(closed=False,released=False)]
        for change in changes:
            source=RendererBoundary();source.close();source.renderer.update(change)
            with self.subTest(change=change):
                value=source.reader().read(RUN,ROOT)
                with self.assertRaises(NativeUIError):released(value,require_renderers=True)
                self.assertEqual(change,{key:value['source']['java']['renderers'][0][key] for key in change})

    def test_original_release_and_terminated_worker_can_retire_with_a_still_reachable_renderer_shell(self):
        source=RendererBoundary();reader=source.reader();reader.read(RUN,ROOT);source.close()
        value=reader.read(RUN,ROOT);proof=released(value,require_renderers=True)
        self.assertTrue(proof['java']['renderers'][0]['objectAlive'])
        self.assertFalse(proof['java']['renderers'][0]['threadAlive'])
        source.renderer['objectAlive']=False;released(reader.read(RUN,ROOT),require_renderers=True)

    def test_native_callback_count_includes_original_expiry_lease_after_result_delivery(self):
        source=RendererBoundary();source.close()
        def retained(value):
            for key in ('nativeBefore','nativeAfter'):value['source'][key]['views'][0]['callbacks']=1
        source.edit=retained;value=source.reader().read(RUN,ROOT)
        with self.assertRaises(NativeUIError):released(value,require_renderers=True)

    def test_renderer_readiness_cannot_borrow_another_handle_creation_document_or_closed_worker(self):
        changes=[dict(handle='2'),dict(creation=2),dict(sourceSha256='f'*64),dict(sourceOwned=False),
            dict(objectAlive=False),dict(threadAlive=False),dict(closed=True)]
        for change in changes:
            source=RendererBoundary();source.renderer.update(change)
            with self.subTest(change=change):
                value=source.reader().read(RUN,ROOT)
                with self.assertRaises(NativeUIError):active_marker(value,URL)

    def test_renderer_history_cannot_disappear_change_owner_revive_or_repair_failed_release(self):
        for fault in ('drop','identity','handle','creation','source','revive-object','revive-thread','reopen','unrelease','repair'):
            source=RendererBoundary();source.close();source.renderer.update(objectAlive=False,releaseSucceeded=False)
            reader=source.reader();reader.read(RUN,ROOT)
            def changed(value):
                row=value['source']['java']['renderers'][0]
                if fault=='drop':value['source']['java']['renderers']=[]
                elif fault=='identity':row['id']='f'*32
                elif fault=='handle':row['handle']='2'
                elif fault=='creation':row['creation']=2
                elif fault=='source':row['sourceSha256']='f'*64
                elif fault=='revive-object':row['objectAlive']=True
                elif fault=='revive-thread':row['threadAlive']=True
                elif fault=='reopen':row.update(closed=False,released=False)
                elif fault=='unrelease':row['released']=False
                else:row['releaseSucceeded']=True
            source.edit=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,ROOT)

    def test_empty_never_observed_renderer_inventory_cannot_prove_its_own_release(self):
        source=RendererBoundary();source.close();source.edit=lambda v:v['source']['java'].update(renderers=[])
        value=source.reader().read(RUN,ROOT)
        with self.assertRaises(NativeUIError):released(value,require_renderers=True)

    def test_reader_cannot_rebind_scope_even_after_an_ignored_original_request(self):
        for ignored in (False,True):
            source=RendererBoundary();source.ignore=ignored;reader=source.reader()
            if ignored:
                with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
            else:reader.read(RUN,ROOT)
            before=len(source.commands)
            for run,root in ((RUN,ROOT.replace('controlled.invalid','other.invalid')),('f'*32,ROOT.replace(RUN,'f'*32))):
                with self.subTest(ignored=ignored,run=run),self.assertRaises(NativeUIError):reader.read(run,root)
                self.assertEqual(before,len(source.commands))

    def test_shape_boolean_integer_quota_and_version_downgrade_are_closed(self):
        faults=[lambda v:v['source']['java'].pop('renderers'),lambda v:v['source']['java'].update(javaWebRuntimeVersion=1),
            lambda v:v['source']['java']['renderers'][0].update(mainCallbacks=True),
            lambda v:v['source']['java']['renderers'][0].update(glCallbacks=-1),
            lambda v:v['source']['java']['renderers'][0].update(retainedCallbacks=129),
            lambda v:v['source']['java']['renderers'][0].update(closed=1),
            lambda v:v['source']['java']['renderers'].append(deepcopy(v['source']['java']['renderers'][0])),
            lambda v:v['source']['java'].update(renderers=v['source']['java']['renderers']*129)]
        for edit in faults:
            source=RendererBoundary();source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)


if __name__=='__main__':unittest.main()
