"""Original Pico factory/runtime; actual device/native producers remain seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

import test_normal_scripts as pico_seams
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_native_chat_observation import Boundary as ChatBoundary,RUN


class PicoChatApplicationFactoryTests(unittest.TestCase):
    def setUp(self):
        self.pico=pico_seams.PicoNormalScriptsTests();self.pico.setUp();self.addCleanup(self.pico.doCleanups)
        self.instance,self.native=self.pico.instance,self.pico.native
        self.old=self.instance._scripts(self.native.target).binding;state,ui=self.instance._script_paths(self.native.target)
        self.originals={path:path.read_bytes() for path in (state,ui) if path.exists()}
        root=self.pico.fixture.state_root/'original-postrestart-session';root.mkdir(mode=0o700)
        self.session=PicoOpenXrAdapterSession(object(),self.native.target,root);self.session.begin('789:999')
        self.native.identity='789:999';self.native.bridge_id='22222222-2222-4222-8222-222222222222'
        snapshot=self.native.snapshot
        def current():value=snapshot();value['processId']=789;return value
        self.native.snapshot=current
        read=self.native.read_debug_app_file
        def original(target,package,path,**options):
            raw=read(target,package,path,**options)
            if path==pico_seams.adapter.ANDROID_CONTROL_MARKER:
                value=json.loads(raw);value['processId']=789;return json.dumps(value)
            return raw
        self.native.read_debug_app_file=original
        self.locks=(ScriptSourceLock(state.with_name('script-sources.lock')),ScriptSourceLock(root/'script-sources.lock'))
        boundary=ChatBoundary();self.peer=boundary.reader();self.peer.pid=456;self.peer._chat_transport=SimpleNamespace()
        self.peer_binding=self.old|dict(processIdentity='456:777',targetFingerprint='f'*64)
        for name,value in (('pico_input_session',lambda target:self.session),('_scripts',lambda target:(_ for _ in ()).throw(AssertionError('Old journals must not be reconstructed')))):
            p=patch.object(self.instance,name,value);p.start();self.addCleanup(p.stop)
    def sources(self):
        with self.locks[0].held(),self.locks[1].held():
            return self.instance._chat_postrestart_sources(self.native.target,RUN,'789:999',self.peer,self.peer_binding,
                source_lock=self.locks[0],peer_lock=self.locks[1])
    def test_original_factory_constructs_distinct_new_readonly_roles_without_old_manager_or_target_input(self):
        binding,roles=self.sources();self.assertEqual('789:999',binding['processIdentity']);self.assertNotEqual(self.old['sessionId'],binding['sessionId'])
        self.assertEqual(2,len(roles));self.assertEqual(4,len({role.store.path for role in roles}|{role.script_source.store.path for role in roles}))
        self.assertTrue(all(role.locks[0] is self.locks[0] and role.locks[1] is self.locks[1] and role.primary.pid==789 for role in roles))
        self.assertTrue(all(role.peer._chat_transport is self.peer._chat_transport for role in roles));self.assertIsNot(roles[0].peer,roles[1].peer)
        for role in roles:
            with self.assertRaises(ValueError):role.primary.send(dict(operation='observe'))
        self.assertEqual(self.originals,{path:path.read_bytes() for path in self.originals});self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
    def test_original_factory_rejects_foreign_retained_successor_journal_before_adopting_sources(self):
        store=self.instance._chat_postrestart_store(self.native.target,'primary-code');store.write(dict(foreign=True),None)
        with self.assertRaises(RuntimeError):self.sources()
        self.assertEqual(dict(foreign=True),store.read());self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
    def test_original_factory_refuses_lifetime_wrapped_reader_without_unwrapping_callback_ownership(self):
        self.peer._chat_cache_lifetime_owned=True
        with self.assertRaises(RuntimeError):self.sources()
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def completed_scope_archive(self,*,bounded,fenced=False,plan_version=2):
        from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive
        state,_=self.instance._script_paths(self.native.target);key=state.stem.removeprefix('normal-script-state-')
        source=PrivateFeatureState(state.with_name('closed-original.json'));source.write(dict(original='already-consumed-scope-seam'),None)
        catalog=ChatArchiveCatalog(hold_files=not bounded);self.addCleanup(catalog.close_host)
        catalog.add('primary/'+source.path.name,source,source.read())
        directory=state.parent/('chat-evidence-'+key+'-'+RUN);ledger=self.instance._chat_archive_retirement_store(self.native.target)
        def inventory(expected):self.assertEqual(expected,{source.path} if source.path.exists() else set())
        proof=dict(original='cold-scope-only-no-current-target-claim')
        def guard(original=None):
            if original is not None:self.assertEqual(proof,original)
            return proof.copy()
        fence=SimpleNamespace(guard=guard,prepare=lambda:dict(original='source-fence-seam'),check=lambda token:None,complete=lambda token:None) if fenced else None
        archive=ChatEvidenceArchive(catalog,directory,ledger,dict(picoChatArchivePlanVersion=plan_version,runId=RUN,
            oldBinding=self.old,newBinding=self.old),guard,inventory,unlink_fence=fence)
        self.addCleanup(archive.close_host);self.addCleanup(lambda:directory.chmod(0o700) if directory.exists() else None)
        archive.retire();return directory

    def test_actual_scope_reader_accepts_sealed_v2_bounded_originals_without_target_release_claim(self):
        self.completed_scope_archive(bounded=True)
        self.assertFalse(self.instance._chat_application_retained(self.native.target))
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_actual_scope_reader_rejects_plan2_relabelled_legacy_fd_receipt(self):
        self.completed_scope_archive(bounded=False)
        with self.assertRaises(ValueError):self.instance._chat_application_retained(self.native.target)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_actual_scope_reader_accepts_explicit_v3_without_claiming_current_target_release(self):
        self.completed_scope_archive(bounded=True,fenced=True,plan_version=3)
        self.assertFalse(self.instance._chat_application_retained(self.native.target))
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_actual_scope_reader_refuses_plan3_relabelled_v2_without_unlink_policy(self):
        self.completed_scope_archive(bounded=True,plan_version=3)
        with self.assertRaises(ValueError):self.instance._chat_application_retained(self.native.target)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)

    def test_legacy_parent_cannot_adopt_deferred_restart_admission(self):
        from adapters.pico4.chat_composition import record
        from adapters.normal_ui import NativeUIError
        base=dict(picoChatCompositionVersion=5,runId=RUN,binding=self.old,peerBinding=self.peer_binding,
            fixtureUrl='http://controlled.test/runs/'+RUN+'/',phase='caches-retired',
            peerOriginBasis='native-configured-metadata-only',completedSteps=26)
        self.assertEqual(base,record(deepcopy(base)))
        for version in (1,2,3,4):
            with self.subTest(version=version),self.assertRaises(NativeUIError):record(base|dict(picoChatCompositionVersion=version))

    def test_generic_cleanup_detects_rootless_new_sources_and_incomplete_evidence_directory(self):
        store=self.instance._chat_postrestart_store(self.native.target,'actor-code')
        child=PrivateFeatureState(store.path.with_name(store.path.name+'.frame-000.json'));child.write(dict(unresolved=True),None)
        self.assertTrue(self.instance._chat_application_retained(self.native.target));self.assertIsNotNone(child.read())
        child.discard(child.read());state,_=self.instance._script_paths(self.native.target)
        key=state.stem.removeprefix('normal-script-state-');directory=state.parent/('chat-evidence-'+key+'-'+'a'*32);directory.mkdir(mode=0o700)
        with self.assertRaises(RuntimeError):self.instance._chat_application_retained(self.native.target)


if __name__=='__main__':unittest.main()
