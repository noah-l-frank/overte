"""Actual original closure reader and held policy; native producer is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_disposition import disposition,unchanged
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.web_closures import drained_owned_resources,KINDS
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL


class EmoteMarkerDispositionTests(unittest.TestCase):
    def originals(self):
        source=ClosureBoundary();source.version=5;reader=source.reader();admitted=reader.read(RUN,URL)
        source.retired=1;source.resources['policy-grant']=dict(created=1,retired=1,pending=0)
        return source,reader,admitted

    def test_actual_cached_counters_remain_held_and_do_not_become_legacy_resource_absence(self):
        source,reader,admitted=self.originals();current=reader.read(RUN,URL);before=deepcopy(current)
        value=disposition(current,admitted);self.assertEqual('held',value['mode']);self.assertTrue(value['holders'])
        kinds={row['original']['resourceKind']:row for row in value['holders']}
        self.assertEqual('qimage',kinds['native-bitmap']['kind']);self.assertEqual('qsg-root',kinds['scenegraph-node']['kind'])
        self.assertEqual(1,kinds['vulkan-image']['original']['counter']['pending'])
        self.assertNotIn('policy-grant',kinds);self.assertEqual(before,current)
        with self.assertRaises(NativeUIError):drained_owned_resources(current,admitted)
        value['contexts'].clear();value['holders'][0]['original']['counter']['pending']=0
        self.assertTrue(disposition(current,admitted)['contexts']);self.assertEqual(before,current)
        following=reader.read(RUN,URL);self.assertTrue(unchanged(current,following))
        self.assertEqual([row['resource'] for row in disposition(current,admitted)['holders']],
            [row['resource'] for row in disposition(following,admitted)['holders']])
        for name in source.resources:source.resources[name]=dict(created=1,retired=1,pending=0)
        released=reader.read(RUN,URL);self.assertEqual('released',disposition(released,admitted)['mode'])
        with self.assertRaises(NativeUIError):unchanged(current,released)

    def test_every_actual_callback_and_policy_grant_must_retire_before_holder_classification(self):
        for kind in KINDS:
            source,reader,admitted=self.originals()
            def active(packet):packet['contexts'][0]['callbacks'][kind]=dict(created=1,retired=0,pending=1)
            source.mutate=active;current=reader.read(RUN,URL)
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):disposition(current,admitted)
        source,reader,admitted=self.originals();source.resources['policy-grant']=dict(created=1,retired=0,pending=1)
        with self.assertRaises(NativeUIError):disposition(reader.read(RUN,URL),admitted)

    def test_original_missing_render_admission_foreign_birth_and_counter_changes_are_refused(self):
        for fault in ('admission','version','incomplete','birth','context','scope'):
            source,reader,admitted=self.originals();current=reader.read(RUN,URL)
            if fault=='admission':admitted['contexts'][0]['resources']['offscreen-image']=dict(created=0,retired=0,pending=0)
            elif fault=='version':current['iosWebClosureVersion']=4
            elif fault=='incomplete':current['complete']=False
            elif fault=='birth':current['instance']='0'*32
            elif fault=='context':current['contexts'][0]['descriptor']['grant']+=1
            else:current['runId']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):disposition(current,admitted)

    def test_partial_setup_can_hold_real_objects_but_supplies_no_render_or_process_end_proof(self):
        source,reader,admitted=self.originals();empty=deepcopy(admitted);empty['contexts']=[]
        current=reader.read(RUN,URL);value=disposition(current,empty,partial=True)
        self.assertEqual('held',value['mode']);self.assertNotIn('complete',value);self.assertNotIn('processEnded',value)
        with self.assertRaises(NativeUIError):disposition(current,empty)
        # This policy facade receives original packets only; the full scope's
        # separate source/window decoders must still qualify native restoration.
        scope=object.__new__(IOSEmoteHeldMarkerScope);scope.run=RUN;scope.pid=42;scope.fixture_url=URL
        scope.state=dict(cleanupMode='unloaded')
        self.assertEqual(value,scope.quiet_web(dict(web=current),dict(web=empty)))
        scope.run='0'*32
        with self.assertRaises(NativeUIError):scope.quiet_web(dict(web=current),dict(web=empty))


if __name__=='__main__':unittest.main()
