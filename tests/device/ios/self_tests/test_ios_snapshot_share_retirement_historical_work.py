"""Actual source-retirement originals, default flow and fresh historical reads.

Host Node/files/unlinks and normal owner paths execute. Native/UIKit/SDK/OS
remain declared models. No whole End/old25 timing conclusion follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import ExitStack,contextmanager
import hashlib
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import collect,scope as read_scope
from ios.adapters.snapshot_share_source_retirement_owner import SnapshotShareSourceRetirementOwner,ShareSourceInspectAction
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.self_tests import test_ios_snapshot_share_source_retirement as existing


class SnapshotRetirementHistoricalWorkTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.SnapshotShareSourceRetirementTests();self.addCleanup(self.fixture.doCleanups)
        self.domain=self.fixture.prepared()
        with self.domain.owner() as share:
            self.expected=share.source_retirement_owner().cleanup()

    def held(self):
        stack=ExitStack();stack.enter_context(self.domain.main.ctx.lock.held());stack.enter_context(self.domain.archive.source_lock.held())
        return stack

    def effects(self):
        d=self.domain
        return deepcopy((d.main.commands,d.primary_ui.requests,d.archive.ui.requests,d.archive.requests,d.archive.sdk,
            d.archive.source_unlinks,d.archive.source_retire_calls,d.archive.node.call('stats')))

    def originals(self):
        roots=(self.domain.main.ctx.root,self.domain.archive.root)
        return {str(path):(path.stat().st_dev,path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns,
            path.stat().st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
            for root in roots for path in sorted(root.rglob('*')) if path.is_file()}

    @contextmanager
    def actual_read_hook(self):
        # One observational hook, no replaced code/return and no locals dump.
        # Counts ACTUAL function entries and captures ACTUAL scope yields.
        previous=sys.getprofile();self.assertIsNone(previous)
        observed_code=SnapshotShareSourceRetirementOwner.observed.__code__
        scope_code=read_scope.__wrapped__.__code__;artifact_code=SnapshotArtifact.read.__code__
        result=dict(observedCalls=0,scopes=[],closedScopes=[],openScopes=[],artifactEntries=[],artifactReads={})
        def hook(frame,event,arg):
            if event=='call' and frame.f_code is observed_code:result['observedCalls']+=1
            elif event=='return' and frame.f_code is scope_code:
                if type(arg) is set:
                    result['openScopes'].append((frame,arg))
                    if not any(value is arg for value in result['scopes']):result['scopes'].append(arg)
                elif arg is None:
                    for index,(origin,value) in enumerate(result['openScopes']):
                        if origin is frame:
                            result['closedScopes'].append((value,set(value)))
                            del result['openScopes'][index];break
            elif event=='call' and frame.f_code is artifact_code:
                # Save only this exact reader's original bounded bindings.
                # No path()/bound()/originals()/getter or other I/O here.
                owner=frame.f_locals['self'];self.assertIs(type(owner),SnapshotArtifact)
                store,state=owner.store,owner.state
                self.assertIs(type(store),PrivateFeatureState);self.assertIs(type(state),dict)
                name=state['name'];partial=frame.f_locals['partial']
                self.assertIs(type(name),str);self.assertIs(type(partial),bool)
                result['artifactEntries'].append((frame,owner,store,state,name,partial,store.path.parent/name))
            elif event=='return' and frame.f_code is artifact_code:
                for index,(origin,owner,store,state,name,partial,path) in enumerate(result['artifactEntries']):
                    if origin is frame:
                        del result['artifactEntries'][index]
                        if type(arg) is bytes:
                            # Only successful original read returns qualify;
                            # they have already performed identity/hash checks.
                            self.assertIs(owner,frame.f_locals['self'])
                            self.assertIs(store,owner.store);self.assertIs(state,owner.state)
                            self.assertEqual(name,state['name']);self.assertFalse(partial)
                            self.assertEqual(path,store.path.parent/name)
                            result['artifactReads'][path]=(len(arg),hashlib.sha256(arg).hexdigest())
                        break
        sys.setprofile(hook)
        try:yield result
        finally:sys.setprofile(previous)

    def external(self):
        directory=tempfile.TemporaryDirectory(prefix='share-retirement-original-witness-');self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def test_historical_load_and_proof_read_each_qualified_original_once_keep_default_and_return_original_values(self):
        effects=self.effects();before=self.originals()
        with self.held():
            with self.actual_read_hook() as loaded:reader=self.fixture.history(self.domain)
            # Three load rows plus three proof rows. Count ACTUAL unchanged
            # function executions, without replacing a decoder/guard method.
            self.assertEqual(6,loaded['observedCalls'])
            with self.actual_read_hook() as measured:
                with collect() as reads,read_scope(fresh=True) as membership:result=reader.proof()
            self.assertEqual(3,measured['observedCalls'])
            self.assertEqual(self.expected,result);self.assertTrue(reads)
            self.assertFalse(measured['openScopes']);self.assertFalse(measured['artifactEntries'])
            actual_scopes=measured['scopes'];closed=measured['closedScopes']
            self.assertTrue(any(value is membership for value in actual_scopes))
            self.assertTrue(any(value is membership and frozen==membership for value,frozen in closed))
            nested=[frozen for value,frozen in closed if value is not membership];self.assertTrue(nested)
            # Every membership is frozen at its actual decoder scope exit.
            # collect() includes all record() paths, while successful direct
            # artifact reads are explicitly added by child_responsibility.
            direct=measured['artifactReads'];self.assertTrue(direct)
            expected_artifacts={Path(name) for name in before
                if Path(name).parent==self.domain.main.ctx.root
                and Path(name).name.startswith('snapshot-'+existing.RUN+'-primary-') and Path(name).suffix=='.bytes'}
            self.assertEqual(1,len(expected_artifacts));self.assertEqual(expected_artifacts,set(direct))
            for path,(size,sha256) in direct.items():
                self.assertEqual((before[str(path)][2],before[str(path)][-1]),(size,sha256))
            self.assertFalse(set(direct)&reads)
            self.assertLessEqual(membership,reads)
            all_membership=set().union(*(frozen for _value,frozen in closed))
            self.assertEqual(reads|set(direct),all_membership)
            self.assertTrue(reads-membership)
            self.assertEqual((reads-membership)|set(direct),set().union(*nested)-membership)
            for row in reader.state['after']:
                if row['qualified'] is True:
                    action=reader.action(row,True)
                    self.assertIn(action.files.path(action.files.expand(action.state['proof'])),reads)
                    # Public qualified() still returns precisely its original
                    # absence packet, without introducing a tuple API.
                    self.assertEqual(reader.observed(row)[0],reader.qualified(row))
            result['fileQuiet']['requestIds'].clear();self.assertEqual(self.expected,reader.proof())
        self.assertEqual(effects,self.effects());self.assertEqual(before,self.originals())
        # The LIVE default retains its original qualified()+observed() calls.
        with self.domain.owner() as share:
            owner=share.source_retirement_owner();self.assertFalse(owner.historical)
            with self.actual_read_hook() as live:self.assertEqual(self.expected,owner.proof())
            self.assertEqual(6,live['observedCalls'])

    def test_same_bytes_new_original_inode_is_rejected_without_another_unlink_or_query(self):
        with self.held():
            reader=self.fixture.history(self.domain);self.assertEqual(self.expected,reader.proof())
            row=next(row for row in reader.state['after'] if row['qualified'] is True);action=reader.action(row,True)
            path=action.files.path(action.files.expand(action.state['proof']));raw=path.read_bytes();old_inode=path.stat().st_ino
            # Retain the actual original inode OUTSIDE the archive namespace;
            # membership cannot conceal the intended original-inode failure.
            original=self.external()/'inspection-original.json';path.rename(original);path.write_bytes(raw);path.chmod(0o600)
            self.assertNotEqual(old_inode,path.stat().st_ino);self.assertEqual(old_inode,original.stat().st_ino)
            effects=self.effects()
            with self.assertRaises(NativeUIError):reader.proof()
            self.assertEqual(effects,self.effects());self.assertEqual(raw,original.read_bytes())

    def test_byte_change_after_real_qualification_is_checked_by_the_same_retained_observation(self):
        with self.held():
            from ios.adapters.snapshot_photos_end_read_area import _ACTIVE
            self.assertIsNone(_ACTIVE.get(),'This default historical countercase must not be masked by an epoch guard')
            reader=self.fixture.history(self.domain);row=next(row for row in reader.state['after'] if row['qualified'] is True)
            action=reader.action(row,True);path=action.files.path(action.files.expand(action.state['proof']))
            raw=path.read_bytes();witness=self.external()/'inspection-before-corruption.json';witness.write_bytes(raw);witness.chmod(0o600)
            inode=path.stat().st_ino;qualified=ShareSourceInspectAction.qualified;changed=[];effects=self.effects()
            def actual(owner):
                result=qualified(owner)
                if owner.index==row['index'] and not changed:
                    # Only the actual original file is changed AFTER the
                    # real qualified guard has succeeded. No verdict stub.
                    path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'));changed.append(True)
                return result
            with patch.object(ShareSourceInspectAction,'qualified',actual),self.assertRaises(NativeUIError):reader.proof()
            self.assertEqual([True],changed);self.assertEqual(inode,path.stat().st_ino)
            self.assertEqual(raw,witness.read_bytes());self.assertEqual(effects,self.effects())

    def test_fresh_historical_load_rejects_new_unknown_owned_namespace_member(self):
        with self.held():
            reader=self.fixture.history(self.domain);self.assertEqual(self.expected,reader.proof())
            path=self.domain.archive.root/'share-source-retirement-unclaimed.json'
            PrivateFeatureState(path).write(dict(unknownResponsibility=True),None);before=self.originals();effects=self.effects()
            with read_scope(fresh=True),self.assertRaises(NativeUIError):self.fixture.history(self.domain)
            self.assertEqual(before,self.originals());self.assertEqual(effects,self.effects())


if __name__=='__main__':unittest.main()
