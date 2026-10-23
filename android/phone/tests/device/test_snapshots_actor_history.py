"""Retained Actor history is unlocked storage work, never current authority.

The existing component fixture supplies explicit native/SDK host seams. Actual
private originals, separate process locks, current reads and HTTP journals run
unchanged. These counters do not qualify an Android APK or a physical device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor as component
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_actor_history import SnapshotActorHistoryPass
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_role import PhoneSnapshotsRole


LOCK_CHILD=r'''
import json,os,sys
sys.path[:0]=json.loads(sys.argv[1])
from snapshots_journey_producers import HostOnlyBoundary
with HostOnlyBoundary():
    from overte_phone_script_lock import PhoneScriptSourceLock
    with PhoneScriptSourceLock(sys.argv[2],timeout=.1).held():
        print(json.dumps(dict(pid=os.getpid(),held=True)),flush=True)
'''


class SnapshotActorHistoryTests(unittest.TestCase):
    @contextmanager
    def controlled(self,kind,*,timing='after-replay'):
        fixture=component.SnapshotsActorTests('test_cleanup_frontier_publishes_once_then_requires_new_own_read')
        fixture.setUp()
        shared=multiprocessing.get_context('fork').Array('i',[0]*9)
        durable_changes=multiprocessing.get_context('fork').Queue()
        original_read=SnapshotActorHistoryPass.read
        original_finish=SnapshotActorHistoryPass.finish
        original_file=SnapshotsOriginals.file
        selected=[None]

        def mark(index,value=1):
            with shared.get_lock():shared[index]+=value

        def mutate(token):
            f,a,r=token.feature,token.actor,token.role
            path=None
            if kind.startswith(('feature-','actor-','role-')):
                store={'feature':f.store,'actor':a.store,'role':r.store}[kind.split('-')[0]]
                before=deepcopy(store.read())
                if kind.endswith('-aba'):store.write(before,before)
                else:
                    state=unpack(before['payload'])[0]
                    if kind.startswith('feature-'):state['cleanupStages']['counterForeignOwner']=True
                    elif kind.startswith('actor-'):state['dropped'].append(dict(counterForeignOwner=True))
                    else:state['phase']='retired'
                    store.write(dict(before,payload=pack([state])),before)
                path=store.path
            elif kind in ('old-frame','manifest','missing'):
                prefix='emote-index-' if kind=='manifest' else 'emote-frame-'
                path=next(path for path,pinned in token.file_seal if pinned is not None and path.name.startswith(prefix))
                if kind=='missing':path.unlink()
                else:path.write_bytes(path.read_bytes()+b' ')
            elif kind=='graph':r.frames[0]['counterLateGraph']=True
            elif kind=='sdk-identity':f.adapter._existing_input_scope=dict(counterForeignScope=True)
            elif kind in ('quiet-restored','quiet-final-save'):a.state['quiet']['started']-=.125
            else:raise AssertionError('Unknown controlled history mutation')
            if path is not None:
                durable_changes.put((str(path),None if kind=='missing' else path.read_bytes()))
                mark(8)
            mark(2)

        def replay(token):
            if not shared[0]:return original_read(token)
            selected[0]=token
            def forbidden(*_args,**_kwargs):
                mark(6);raise AssertionError('Unlocked history requested current authority')
            # Every genuine history read runs with the same prohibitions. The
            # separate child acquires the actual OS lock inside a real file
            # reader, not during a synthetic pause before replay.
            with patch.object(token.feature,'bound',forbidden),patch.object(token.feature.phase,'status',forbidden),\
                    patch.object(PhoneSnapshotsRole,'read',forbidden),patch.object(PhoneSnapshotsRole,'batch',forbidden),\
                    patch.object(token.actor.client,'request',forbidden),patch.object(token.feature,'original',forbidden),\
                    patch.object(token.feature.adapter,'_native_feature_observer',forbidden):
                result=original_read(token)
            mark(1)
            if kind=='reuse-read':
                try:original_read(token)
                except NativeUIError:mark(7);raise
                raise AssertionError('One-use history was replayed twice')
            if kind=='closed-finish':token.close();mark(2)
            elif timing=='after-replay' and kind!='positive':
                with token.feature.lock.held():mutate(token)
            if kind=='quiet-restored':
                original=token.feature.restored
                def restored(*args,**kwargs):
                    result=original(*args,**kwargs);token.feature.lock.assert_held();mark(3)
                    if not shared[2]:mutate(token)
                    return result
                token.feature.restored=restored
            elif kind=='quiet-final-save':
                original=token.feature.bound
                def bound(*args,**kwargs):
                    result=original(*args,**kwargs)
                    caller=sys._getframe(1)
                    if caller.f_code.co_name=='save' and caller.f_locals.get('self') is token.actor:
                        token.feature.lock.assert_held();mark(3)
                        if not shared[2]:mutate(token)
                    return result
                token.feature.bound=bound
            return result

        def finish(token):
            if not shared[0]:return original_finish(token)
            f=token.feature
            if timing=='phase-callback':
                original=f.phase.status
                def phase(*args,**kwargs):
                    result=original(*args,**kwargs);f.lock.assert_held();mark(3)
                    if not shared[2]:mutate(token)
                    return result
                with patch.object(f.phase,'status',phase):return original_finish(token)
            if timing=='native-callback':
                original=f.bound
                def bound(*args,**kwargs):
                    result=original(*args,**kwargs);f.lock.assert_held();mark(3)
                    if not shared[2]:mutate(token)
                    return result
                with patch.object(f,'bound',bound):return original_finish(token)
            return original_finish(token)

        def actual_file(engine,path,descriptor,value):
            result=original_file(engine,path,descriptor,value)
            token=selected[0]
            if shared[0] and kind=='positive' and token is not None and not shared[4]:
                self.assertIsNone(token.feature.lock._owner)
                self.assertEqual(path.stat().st_ino,os.fstat(descriptor).st_ino)
                process=subprocess.run([sys.executable,'-B','-c',LOCK_CHILD,json.dumps(sys.path),str(token.feature.lock.path)],
                    capture_output=True,text=True,timeout=3,check=True)
                packet=json.loads(process.stdout)
                self.assertNotEqual(os.getpid(),packet['pid']);self.assertTrue(packet['held'])
                with shared.get_lock():shared[4]=packet['pid']
                mark(5)
            return result

        try:
            with patch.object(SnapshotActorHistoryPass,'read',replay),patch.object(SnapshotActorHistoryPass,'finish',finish),\
                    patch.object(SnapshotsOriginals,'file',actual_file):
                step=fixture.cleanup_frontier(slot_mode=True)
                first=step();self.assertIsNone(first['error'],first)
                self.assertEqual(1,first['counts']['reads']);self.assertEqual(0,first['counts']['posts'])
                self.assertFalse(first['state']['quiet']['complete'])
                self.assertIsNone(first['state']['last'])
                before=deepcopy(fixture.reader.request('/runs/'+component.RUN)['entries'])
                with shared.get_lock():shared[0]=1
                yield fixture,step,first,shared,before
                if shared[8]:
                    path,actual=durable_changes.get(timeout=2)
                    if actual is None:self.assertFalse(Path(path).exists(),'Rejected missing original was recreated')
                    else:self.assertEqual(actual,Path(path).read_bytes(),'Rejected foreign bytes were overwritten')
        finally:
            try:self.assertTrue(fixture.doCleanups(),'Owned Actor fixture cleanup failed')
            finally:durable_changes.close();durable_changes.join_thread()

    def assert_rejected_before_current(self,fixture,step,first,shared,entries,*,callback=False):
        value=step();self.assertEqual('NativeUIError',value['error']['error'],value)
        self.assertEqual(first['counts'],value['counts'])
        self.assertEqual(first['state']['last'],value['state']['last'])
        self.assertEqual(entries,fixture.reader.request('/runs/'+component.RUN)['entries'])
        self.assertEqual(1,shared[1],'Counter did not follow a complete actual replay')
        self.assertEqual(0,shared[6],'Replay attempted current authority outside lock')
        if callback:self.assertGreater(shared[3],0,'Fresh original callback was not reached')

    def test_actual_old_file_replay_allows_child_lock_and_then_new_current_read(self):
        with self.controlled('positive') as (fixture,step,first,shared,entries):
            value=step();self.assertIsNone(value['error'],value)
            self.assertEqual(first['counts']['reads']+1,value['counts']['reads'])
            self.assertEqual(first['counts']['posts'],value['counts']['posts'])
            old=unpack(first['roleHeader']['payload'])[0];new=unpack(value['roleHeader']['payload'])[0]
            self.assertEqual(old['sequence']+1,new['sequence'])
            self.assertEqual(new['sequence'],value['state']['quiet']['sequences'][-1])
            self.assertEqual(entries,fixture.reader.request('/runs/'+component.RUN)['entries'])
            self.assertEqual(1,shared[1]);self.assertEqual(1,shared[5]);self.assertGreater(shared[4],0)
            self.assertEqual(0,shared[6])

    def test_three_owner_headers_inodes_and_actual_old_files_reject_after_replay(self):
        for kind in ('feature-header','actor-header','role-header','feature-aba','actor-aba','role-aba',
                     'old-frame','manifest','missing'):
            with self.subTest(kind=kind),self.controlled(kind) as (fixture,step,first,shared,entries):
                self.assert_rejected_before_current(fixture,step,first,shared,entries)
                self.assertEqual(1,shared[2])

    def test_late_fresh_callbacks_cannot_change_graph_sdk_owner_or_old_original(self):
        for kind,timing in (('graph','native-callback'),('graph','phase-callback'),
                            ('sdk-identity','phase-callback'),('role-aba','phase-callback'),
                            ('old-frame','phase-callback')):
            with self.subTest(kind=kind,timing=timing),self.controlled(kind,timing=timing) as (fixture,step,first,shared,entries):
                self.assert_rejected_before_current(fixture,step,first,shared,entries,callback=True)
                self.assertEqual(1,shared[2])
        for kind in ('quiet-restored','quiet-final-save'):
            with self.subTest(kind=kind),self.controlled(kind,timing='after-current') as (fixture,step,first,shared,entries):
                value=step();self.assertEqual('NativeUIError',value['error']['error'],value)
                # The independent acquisition has already completed. Rejection
                # must prevent committing altered quiet progress or publishing
                # it; claiming zero current reads here would be incorrect.
                self.assertEqual(first['counts']['reads']+1,value['counts']['reads'])
                self.assertEqual(first['counts']['posts'],value['counts']['posts'])
                self.assertEqual(first['actorHeader'],value['actorHeader'])
                durable=unpack(value['actorHeader']['payload'])[0]
                self.assertEqual(first['state']['quiet'],durable['quiet'])
                self.assertEqual(entries,fixture.reader.request('/runs/'+component.RUN)['entries'])
                self.assertEqual(1,shared[1]);self.assertEqual(1,shared[2]);self.assertGreater(shared[3],0)
                self.assertEqual(0,shared[6])

    def test_complete_actual_replay_is_one_use_and_closed_pass_never_authorizes_read(self):
        for kind in ('reuse-read','closed-finish'):
            with self.subTest(kind=kind),self.controlled(kind) as (fixture,step,first,shared,entries):
                self.assert_rejected_before_current(fixture,step,first,shared,entries)
                if kind=='reuse-read':self.assertEqual(1,shared[7])


if __name__=='__main__':unittest.main()
