#!/usr/bin/env python3
"""Public cleanup observation yields only immutable history, never current facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
import subprocess
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_quiet_role_reuse as probe
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_measurements import SnapshotPending
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass
from overte_phone_snapshots_role import PhoneSnapshotsRole


LOCK_READER=r"""
import json,os,sys
sys.path[:0]=json.loads(sys.argv[1])
from snapshots_journey_producers import HostOnlyBoundary
with HostOnlyBoundary():
    from overte_phone_script_lock import PhoneScriptSourceLock
    with PhoneScriptSourceLock(sys.argv[2],timeout=.1).held():print(os.getpid())
"""


class SnapshotPrimaryCleanupStagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):probe.SnapshotQuietRoleReuseTests.setUpClass()
    @classmethod
    def tearDownClass(cls):probe.SnapshotQuietRoleReuseTests.tearDownClass()
    def setUp(self):
        self.fixture=probe.SnapshotQuietRoleReuseTests.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def exercise(self,mutation):
        h=probe.harness;f=self.fixture;prepared=probe.prepared_role(f);sequence=prepared['role'].state['sequence']
        factory=f.adapter._snapshots_feature;observed=[];foreign=[];yielded=[];roles=[]
        calls=len(f.model.product.calls);disposed={}
        release=PhoneSnapshotsRole._dispose_observation_graph
        def snapshot_and_release(role):
            # Observe the actual reader after all source/session guards, just
            # before its operation-owned references are intentionally released.
            # Files and headers are still re-read independently below.
            disposed[id(role)]=dict(state=deepcopy(role.state),frames=deepcopy(role.frames))
            return release(role)
        def create(*args,**kwargs):
            feature=factory(*args,**kwargs);sleep=feature.sleep;pin=feature.cleanup_observe_pin
            def pinned(role,previous=None):
                result=pin(role,previous);roles.append(role);return result
            feature.cleanup_observe_pin=pinned
            def between(seconds):
                if feature.lock._owner is None and not yielded:
                    yielded.append(True);self.assertIsNotNone(f.adapter._existing_input_scope)
                    if mutation.startswith('after-'):pass
                    elif mutation=='continue':
                        child=subprocess.run([sys.executable,'-c',LOCK_READER,json.dumps(sys.path),str(feature.lock.path)],
                            capture_output=True,text=True,timeout=3,check=True)
                        self.assertNotEqual(os.getpid(),int(child.stdout))
                    elif mutation in ('feature','feature-load'):
                        previous=deepcopy(feature.previous);state=unpack(previous['payload'])[0]
                        state['cleanupStages']['foreign-primary-stage']='e'*32;value=dict(previous,payload=pack([state]))
                        if mutation=='feature':PrivateFeatureState(feature.store.path).write(value,previous)
                        else:
                            read=feature.store.read;switched=[False]
                            def late_read():
                                actual=read()
                                if not switched[0]:switched[0]=True;PrivateFeatureState(feature.store.path).write(value,previous)
                                return actual
                            feature.store.read=late_read
                        foreign.append((feature.store.path,value))
                    elif mutation=='role':
                        role=roles[-1];previous=deepcopy(role.previous);state=unpack(previous['payload'])[0];state['phase']='retired'
                        value=dict(previous,payload=pack([state]));PrivateFeatureState(role.store.path).write(value,previous);foreign.append((role.store.path,value))
                    elif mutation=='memory':
                        roles[-1].state.update(sequence=0,manifests=[]);roles[-1].frames=[]
                    elif mutation=='closed':f.client.close()
                    elif mutation=='ticket':f.client.activate('e'*32,'cleanup',{})
                    elif mutation=='pid':f.setup.f.native.identity='32:foreign-start'
                    elif mutation=='late-file':(f.model.producer.directory/('e2e-'+h.RUN+'-late-primary.png')).write_bytes(f.model.raw_png)
                    elif mutation=='old-file':next(f.root.glob('emote-frame-snapshots-'+h.RUN+'-primary-*.json')).unlink()
                    elif mutation=='pending':
                        role=roles[-1];read=role.avatar.read;once=[False]
                        def missing():
                            if not once[0]:once[0]=True;raise SnapshotPending('Controlled original avatar read pending')
                            return read()
                        role.avatar.read=missing
                    else:raise RuntimeError('Unknown controlled stage mutation')
                return sleep(seconds)
            feature.sleep=between;observed.append(feature);return feature
        read_history=SnapshotHistoryReadPass.read;passes=[];invalid_current_reads=[];graph_checks=[]
        def historical(token):
            result=read_history(token);passes.append(token)
            if mutation.startswith('after-'):
                self.assertIsNone(token.feature.lock._owner)
                def forbidden(_after):
                    invalid_current_reads.append(True)
                    raise AssertionError('Current facts acquired after invalid historical pass')
                token.role.read=forbidden
                kind=mutation.removeprefix('after-')
                if kind in ('memory-graph','final-guard-memory-graph'):
                    # Preserve the actual owner/state/file identities. Only
                    # the reader's independently held graph is corrupted.
                    state=deepcopy(token.role.state)
                    headers=(deepcopy(token.feature.store.read()),deepcopy(token.role.store.read()))
                    bodies={path:None if signature is None else hashlib.sha256(path.read_bytes()).hexdigest()
                        for path,signature in token.files.items()}
                    changed=[]
                    def change_graph():
                        self.assertFalse(changed)
                        frames=deepcopy(token.role.frames);self.assertTrue(frames)
                        frames[-1]['unqualifiedMemoryGraphMutation']=True
                        token.role.frames=frames;changed.append(True)
                    if kind=='memory-graph':change_graph()
                    else:
                        finish=token.finish
                        def finish_with_original_guard():
                            bound=token.feature.bound
                            def actual_then_changed():
                                value=bound()
                                if not changed:change_graph()
                                return value
                            with patch.object(token.feature,'bound',side_effect=actual_then_changed):
                                return finish()
                        # The first finish memory check runs unchanged. Only
                        # its subsequent real native guard causes corruption;
                        # the final memory check must prevent current IO.
                        token.finish=finish_with_original_guard
                    graph_checks.append((token,state,headers,bodies,changed,token.role.store.path))
                elif kind in ('feature-aba','role-aba'):
                    store=token.feature.store if kind=='feature-aba' else token.role.store
                    value=deepcopy(store.read());store.write(value,value);foreign.append((store.path,value))
                else:
                    suffix='.png' if kind=='png-mode' else '.bin' if kind=='binary-link' else '.json'
                    path=next(path for path in token.files if
                        (path.name.startswith('emote-index-') if kind=='manifest' else path.suffix==suffix))
                    if kind=='png-mode':path.chmod(0o640)
                    elif kind=='binary-link':os.link(path,path.with_name(path.name+'.controlled'))
                    elif kind=='missing':path.unlink()
                    else:path.write_bytes(path.read_bytes()+b' ')
            return result
        with patch.object(f.adapter,'_snapshots_feature',side_effect=create),patch.object(SnapshotHistoryReadPass,'read',historical),\
                patch.object(PhoneSnapshotsRole,'_dispose_observation_graph',snapshot_and_release):
            if mutation in ('continue','pending'):
                value=f.invoke('feature.snapshots.observe',dict(contractVersion=h.VERSION,runId=h.RUN,afterSequence=sequence))
                self.assertEqual([],value['resources']);self.assertEqual(0,value['state']['files']);self.assertGreater(value['sequence'],sequence)
                if mutation=='pending':
                    self.assertGreaterEqual(len(roles),3);self.assertTrue(any(row.get('diagnostic') for row in disposed[id(roles[-1])]['frames']))
            else:
                with self.assertRaises((NativeUIError,FileNotFoundError)):
                    f.invoke('feature.snapshots.observe',dict(contractVersion=h.VERSION,runId=h.RUN,afterSequence=sequence))
        self.assertTrue(passes or not mutation.startswith('after-'))
        # The source lock translates exceptions. Its generic rejection alone
        # cannot prove that an invalid pass never reached a current reader.
        self.assertEqual([],invalid_current_reads)
        self.assertTrue(all(token.closed for token in passes))
        for token,state,headers,bodies,changed,role_path in graph_checks:
            self.assertEqual([True],changed)
            self.assertEqual(state,disposed[id(token.role)]['state'])
            self.assertEqual(headers,(token.feature.store.read(),PrivateFeatureState(role_path).read()))
            for path,digest in bodies.items():
                if digest is None:self.assertFalse(path.exists())
                else:self.assertEqual(digest,hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual([True],yielded);self.assertIsNone(f.adapter._existing_input_scope)
        for path,value in foreign:self.assertEqual(value,PrivateFeatureState(path).read())
        self.assertEqual(calls,len(f.model.product.calls))
        return observed

    def test_actual_separate_process_can_take_original_source_lock_between_history_and_fresh_read(self):self.exercise('continue')
    def test_valid_changed_feature_header_between_stages_is_preserved_and_red(self):self.exercise('feature')
    def test_valid_changed_role_header_between_stages_is_preserved_and_red(self):self.exercise('role')
    def test_valid_feature_header_replaced_after_comparison_is_red_after_load(self):self.exercise('feature-load')
    def test_joint_in_memory_state_and_frame_truncation_cannot_choose_a_shorter_history(self):self.exercise('memory')
    def test_changed_actual_kernel_pid_cannot_publish_a_cleanup_frame(self):self.exercise('pid')
    def test_closed_original_phase_does_not_turn_observe_into_finalize(self):self.exercise('closed')
    def test_new_actual_cleanup_activation_cannot_be_adopted(self):self.exercise('ticket')
    def test_actual_late_owned_file_is_not_hidden_by_the_prepared_history(self):self.exercise('late-file')
    def test_missing_actual_old_original_is_not_hidden_by_prepared_history(self):self.exercise('old-file')
    def test_actual_partial_read_archives_pending_then_reconstructs_only_known_owner(self):self.exercise('pending')


if __name__=='__main__':unittest.main()
