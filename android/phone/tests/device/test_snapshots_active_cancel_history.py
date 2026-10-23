"""Active foreground Cancel retains fresh sources and late original checks.

The public SDK26 fixture, actual TLS journal, immutable files and independent
Actor process execute here. Native, Android and render signals are explicit
host producers; these counters establish neither APK nor device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_read_ready_slot as slot
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_feature import PhoneSnapshotsFeature
from overte_phone_snapshots_role import PhoneSnapshotsRole


class SnapshotActiveCancelHistoryTests(unittest.TestCase):
    # Delegate support without inheriting the six slot or two closing tests.
    setUpClass=classmethod(slot.SnapshotReadReadySlotTests.setUpClass.__func__)
    tearDownClass=classmethod(slot.SnapshotReadReadySlotTests.tearDownClass.__func__)
    receive=slot.SnapshotReadReadySlotTests.receive
    step=slot.SnapshotReadReadySlotTests.step

    @contextmanager
    def cancelled_active(self):
        rig=self.fixture_type('test_normal_public_document_picker_open_cancel_and_success_acquires_original')
        rig.setUp()
        try:
            rig.client.activate('c'*32)
            first=rig.invoke('feature.snapshots.observe',dict(contractVersion=slot.harness.VERSION,
                runId=slot.harness.RUN,afterSequence=0))
            rig.act('open');rig.act('capture-cancel',dict(mode='animated',format='png'))
            cancelled=rig.invoke('feature.snapshots.observe',dict(contractVersion=slot.harness.VERSION,
                runId=slot.harness.RUN,afterSequence=first['sequence']))
            self.assertEqual(['pending','cancelled'],cancelled['state']['captureHistory'])
            self.assertEqual(0,cancelled['state']['files'])
            rig.act('capture',dict(mode='still',format='png'))
            rig.active_sequence=cancelled['sequence']
            rig.active_feature_store=rig.adapter.snapshots_feature_store('test-only-appium')
            owner=unpack(rig.active_feature_store.read()['payload'])[0]
            self.assertEqual('active',owner['phase']);self.assertIsNone(owner['current'])
            self.assertIsNone(owner['handoff']);self.assertEqual(1,len(owner['cancelJobs']))
            configuration=rig.root/'active-cancel-child.json'
            PrivateFeatureState(configuration).write(dict(targetUrl=rig.proxy.url,root=str(rig.root),
                fixtureUrl=rig.base,actorToken='a'*64),None)
            child=subprocess.Popen([sys.executable,'-B','-c',slot.CHILD,json.dumps(sys.path),str(configuration)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            rig.slot_child=child
            try:
                ready=self.receive(child);self.assertTrue(ready['ready']);self.assertEqual(child.pid,ready['pid'])
                observed=self.step(rig);self.assertEqual(1,observed['counts']['posts'])
                rig.active_actor_store=PrivateFeatureState(rig.root/'phone-snapshots-actor-lifecycle.json')
                rig.active_primary_store=PrivateFeatureState(rig.root/'phone-snapshots-primary-originals.json')
                peer=PrivateFeatureState(rig.root/'phone-snapshots-actor-originals.json').read()
                state=unpack(peer['payload'])[0]
                host=SnapshotsOriginals(rig.root,peer['binding'],slot.harness.RUN,'actor',
                    lambda:True,lambda *_:self.fail('Read-only peer history wrote an intent'),kind='snapshots')
                frame=host.restore(state['manifests'],state['sequence'])[-1]
                rig.active_peer_cancel=deepcopy(frame['measurement']['cancels'][-1])
                rig.active_actor_header=deepcopy(rig.active_actor_store.read())
                rig.active_peer_entries=deepcopy(rig.client.request('/runs/'+slot.harness.RUN)['entries'])
                self.assertEqual(1,len(rig.active_peer_entries))
                yield rig
            finally:
                if child.poll() is None:
                    child.stdin.write(json.dumps(dict(mode='exit'))+'\n');child.stdin.flush()
                timed_out=False
                try:_out,err=child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    timed_out=True;child.terminate()
                    try:_out,err=child.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill();_out,err=child.communicate(timeout=3)
                self.assertFalse(timed_out,'Independent Actor missed its exit deadline: '+err[-5000:])
                self.assertEqual(0,child.returncode,err[-5000:])
        finally:self.assertTrue(rig.doCleanups(),'Owned fixture cleanup failed')

    def observe_cancel(self,rig,*,remove_original=False):
        events=[];packets=[];counts=[];removed=[];seen=dict(result=None,error=None,current=[])
        active=dict(current=False,account=False,cancelled=False)
        read=PhoneSnapshotsRole.read;current_read=PhoneSnapshotsFeature.constructor_current_read
        input_originals=PhoneSnapshotsFeature.input_originals
        validate_account=PhoneSnapshotsFeature.validate_account
        foreground_count=PhoneSnapshotsRole.foreground_input_count
        cancel_factory=rig.adapter._snapshot_cancel
        def admitted(feature,call,history,role):
            seen.update(history=history,header=deepcopy(role.previous))
            self.assertFalse(history.cleanup);self.assertFalse(history.passive)
            return current_read(feature,call,history,role)
        def current(role,*args,**kwargs):
            if role.role!='primary' or role.feature.state['phase']!='active':return read(role,*args,**kwargs)
            role.feature.lock.assert_held();seen['current'].append(True);active['current']=True
            try:return read(role,*args,**kwargs)
            finally:active['current']=False
        def count(role):
            value=foreground_count(role)
            if active['current']:counts.append(value);events.append('bound-count')
            return value
        def originals(feature):
            observed=active['current'] and feature.role=='primary'
            if observed:
                events.append('account-originals' if active['account'] else 'other-originals')
                self.assertTrue(active['cancelled'],'Full input replay ran merely to bound a Cancel index')
            try:return input_originals(feature)
            except Exception:
                if observed and active['account']:events.append('account-originals-rejected')
                raise
        def account(feature,*args,**kwargs):
            observed=active['current'] and feature.role=='primary'
            if observed:events.append('account');active['account']=True
            try:return validate_account(feature,*args,**kwargs)
            finally:
                if observed:active['account']=False
        def factory(*args,**kwargs):
            reader=cancel_factory(*args,**kwargs);request=reader.request
            def fresh(*args,**kwargs):
                packet=request(*args,**kwargs)
                if active['current']:
                    events.append('fresh-cancel');packets.append(deepcopy(packet));active['cancelled']=True
                    if remove_original and not removed:
                        token=seen['history'];prefix='emote-frame-snapshots-input-'+slot.harness.RUN+'-primary-'
                        paths=sorted(path for path,receipt in token.files.items()
                            if receipt is not None and path.name.startswith(prefix))
                        self.assertTrue(paths,'Actual input-original receipt is missing from the admitted pass')
                        path=paths[0];self.assertIn((path,token.files[path]),token.file_seal)
                        removed.append(dict(path=path,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                        path.unlink();self.assertFalse(path.exists())
                return packet
            reader.request=fresh;return reader
        with patch.object(PhoneSnapshotsFeature,'constructor_current_read',admitted),\
                patch.object(PhoneSnapshotsRole,'read',current),\
                patch.object(PhoneSnapshotsRole,'foreground_input_count',count),\
                patch.object(PhoneSnapshotsFeature,'input_originals',originals),\
                patch.object(PhoneSnapshotsFeature,'validate_account',account),\
                patch.object(rig.adapter,'_snapshot_cancel',factory):
            try:seen['result']=rig.invoke('feature.snapshots.observe',dict(contractVersion=slot.harness.VERSION,
                runId=slot.harness.RUN,afterSequence=rig.active_sequence))
            except Exception as error:seen['error']=error
        owner=unpack(rig.active_feature_store.read()['payload'])[0]
        self.assertEqual([owner['inputSequence']],counts);self.assertEqual([True],seen['current'])
        self.assertEqual(1,len(packets));packet=packets[0]
        self.assertEqual(owner['cancelJobs'][0]['id'],packet['source']['job'])
        self.assertEqual('complete',packet['source']['phase']);self.assertFalse(packet['source']['timerActive'])
        self.assertNotEqual(rig.active_peer_cancel['requestId'],packet['requestId'])
        self.assertGreater(packet['sequence'],rig.active_peer_cancel['sequence'])
        self.assertLess(events.index('bound-count'),events.index('fresh-cancel'))
        self.assertLess(events.index('fresh-cancel'),events.index('account'))
        self.assertLess(events.index('account'),events.index('account-originals'))
        self.assertNotIn('other-originals',events)
        self.assertEqual(rig.active_actor_header,rig.active_actor_store.read())
        self.assertEqual(rig.active_peer_entries,rig.client.request('/runs/'+slot.harness.RUN)['entries'])
        seen['cancelPackets']=packets
        return seen,events,removed

    def test_active_foreground_keeps_fresh_cancel_and_full_later_account_replay(self):
        with self.cancelled_active() as rig:
            seen,events,removed=self.observe_cancel(rig)
            self.assertIsNone(seen['error'],repr(seen['error']));self.assertEqual([],removed)
            result=seen['result'];self.assertEqual(rig.active_sequence+1,result['sequence'])
            self.assertEqual(1,result['state']['files']);self.assertIn('cancelled',result['state']['captureHistory'])
            self.assertEqual(1,events.count('account-originals'));self.assertNotIn('account-originals-rejected',events)
            header=rig.active_primary_store.read();state=unpack(header['payload'])[0]
            def historical():
                self.assertEqual(header,rig.active_primary_store.read());return True
            host=SnapshotsOriginals(rig.root,header['binding'],slot.harness.RUN,'primary',historical,
                lambda *_:self.fail('Read-only result history wrote an intent'),kind='snapshots')
            frame=host.restore(state['manifests'],state['sequence'])[-1]
            self.assertEqual(seen['cancelPackets'],frame['measurement']['cancels'])
            self.assertEqual(result['state'],frame['state'])

    def test_late_input_original_loss_during_active_cancel_rejects_the_same_primary_observation(self):
        with self.cancelled_active() as rig:
            seen,events,removed=self.observe_cancel(rig,remove_original=True)
            self.assertIsInstance(seen['error'],NativeUIError);self.assertIsNone(seen['result'])
            self.assertEqual(1,len(removed));self.assertFalse(removed[0]['path'].exists())
            cause=seen['error'].__context__;self.assertIs(type(cause),FileNotFoundError)
            self.assertEqual(str(removed[0]['path']),cause.filename)
            self.assertEqual(1,events.count('account-originals-rejected'))
            actual=unpack(rig.active_primary_store.read()['payload'])[0]
            prepared=unpack(seen['header']['payload'])[0]
            self.assertEqual(prepared['sequence'],actual['sequence'])
            self.assertEqual('reading',actual['phase']);self.assertIsNone(actual['pending']['frame'])


if __name__=='__main__':unittest.main()
