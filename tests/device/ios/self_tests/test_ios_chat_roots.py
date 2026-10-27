"""Actual host weak expiry and original codecs; Qt/native remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from unittest.mock import patch
from adapters.chat_root_ownership import validate,selected,weakly_absent
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.self_tests.chat_roots_fixture import ChatRoots,Page,RootRestoreModel,RootBoundary
from ios.self_tests.test_ios_chat_history_cleanup import ChatHistoryCleanupTests


class ChatRootsTests(unittest.TestCase):
    def test_hidden_detached_page_and_models_stay_alive_until_actual_weak_expiry(self):
        source=ChatRoots();page=Page();first=source.capture([page]);validate(first,pid=31)
        identity=first['pages'][0]['page'];self.assertEqual(first['pages'][0],selected(first,identity))
        page.visible=False;page.in_tree=False;hidden=source.capture([page]);validate(hidden,pid=31,previous=first)
        self.assertEqual([],hidden['pages']);self.assertFalse(weakly_absent(hidden));self.assertTrue(all(row['weakAlive'] for row in hidden['roots']))
        del page;gc.collect();dead=source.capture([]);validate(dead,pid=31,previous=hidden);self.assertTrue(weakly_absent(dead))
        self.assertTrue(all(row['weakExpiredObservedEpochMs'] for row in dead['roots']));self.assertNotIn('birthEpochMs',dead['roots'][0])
        fresh=Page();later=source.capture([fresh]);validate(later,pid=31,previous=dead);self.assertNotEqual(identity,later['pages'][0]['page'])
    def test_visible_page_aliases_cannot_select_a_hidden_other_page_or_wrong_model_kind(self):
        source=ChatRoots();one,two=Page(),Page();two.visible=False;value=source.capture([one,two]);validate(value,pid=31)
        with self.assertRaises(NativeUIError):selected(value,value['pages'][1]['page'])
        for field in ('editor','localModel','domainModel','listModel'):
            bad=deepcopy(value);bad['pages'][0][field]=bad['pages'][0]['page']
            with self.subTest(field=field),self.assertRaises(NativeUIError):validate(bad,pid=31)
        bad=deepcopy(value);bad['pages'][1]['visible']=True
        with self.assertRaises(NativeUIError):validate(bad,pid=31)
    def test_pid_instance_sequence_source_clock_forgetting_and_resurrection_refuse(self):
        source=ChatRoots();page=Page();before=source.capture([page]);later=source.capture([page])
        for change in ('pid','instance','sequence','clock','source','forget'):
            value=deepcopy(later)
            if change=='pid':value['processId']=52
            elif change=='instance':value['instance']='f'*32
            elif change=='sequence':value['sequence']=before['sequence']
            elif change=='clock':value['clockDomain']='appium-node-host'
            elif change=='source':value['roots'][0]['componentSource']='qrc:/foreign.qml'
            else:value['roots']=[];value['pages']=[];value['observationSequence']=0
            with self.subTest(change=change),self.assertRaises(NativeUIError):validate(value,pid=31,previous=before)
        del page;gc.collect();dead=source.capture([]);changed=deepcopy(source.capture([]))
        changed['roots'][0].update(weakAlive=True,weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
        with self.assertRaises(NativeUIError):validate(changed,pid=31,previous=dead)
    def test_unavailable_or_incomplete_walk_cannot_prove_weak_absence(self):
        for value in (dict(iosChatRootOwnershipVersion=1,available=False),ChatRoots().capture([],ready=False)):
            validate(value,pid=31)
            with self.assertRaises(NativeUIError):weakly_absent(value)


class ChatRootReaderTests(unittest.TestCase):
    def test_actual_reader_keeps_original_weak_prefix_and_refuses_root_sequence_or_instance_changes(self):
        from self_tests.test_native_chat_view import RUN
        n=RootBoundary();reader=n.reader(ios=True);first=reader.read(RUN);n.qt_pages[0].in_tree=False
        later=reader.read(RUN);self.assertFalse(weakly_absent(later['source']['rootOwnership']))
        self.assertEqual(first['source']['rootOwnership']['roots'],later['source']['rootOwnership']['roots'])
        for key,value in (('sequence',first['source']['rootOwnership']['sequence']),('instance','f'*32)):
            n.final_mutate=lambda original,key=key,value=value:original['source']['rootOwnership'].update({key:value})
            with self.subTest(key=key),self.assertRaises(NativeUIError):reader.read(RUN)
    def test_closed_view_cannot_hide_a_visible_original_page(self):
        from self_tests.test_native_chat_view import RUN
        from adapters.native_chat_view import measured_view
        n=RootBoundary();reader=n.reader(ios=True);value=reader.read(RUN)
        self.assertFalse(measured_view(value)['open']);self.assertFalse(weakly_absent(value['source']['rootOwnership']))
        n.qt_pages[0].visible=True
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_visible_view_cannot_select_a_different_hidden_page(self):
        from self_tests.test_native_chat_view import Boundary,RUN
        n=RootBoundary();n.source=deepcopy(Boundary().source);n.qt_pages[0].visible=True
        hidden=Page();hidden.visible=False;n.qt_pages.append(hidden);reader=n.reader(ios=True)
        reader.read(RUN)
        n.final_mutate=lambda value:value['source']['ui'].update(rootIdentity=value['source']['rootOwnership']['pages'][1]['page'])
        with self.assertRaises(NativeUIError):reader.read(RUN)


class ChatRootOwnerTests(unittest.TestCase):
    def test_normal_send_erase_rebuild_close_retains_actual_cached_operands_and_pure_originals(self):
        f=ChatHistoryCleanupTests();f.setUp();self.addCleanup(f.doCleanups);f.m=f.f.model=RootRestoreModel()
        f.message();f.action('close');f.phase();result=f.restore();self.assertTrue(result['historyRestored'])
        with f.archive() as owner:
            original=owner.original(result['original']);roots=original['originals']['view']['source']['rootOwnership']
            self.assertTrue(all(row['weakAlive'] for row in roots['roots']));self.assertFalse(weakly_absent(roots))
            self.assertEqual([],roots['pages']);files={path:(path.stat().st_ino,path.read_bytes()) for path in f.f.root.iterdir() if path.is_file()}
            with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No historical write')):
                self.assertEqual(result,owner.restore_history(f.m.ticket))
            self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in f.f.root.iterdir() if path.is_file()})
        self.assertTrue(f.m.qt_pages);f.m.qt_pages.clear();gc.collect();f.m.sleep(.1)
        self.assertTrue(weakly_absent(f.m.roots.capture([])))


if __name__=='__main__':unittest.main()
