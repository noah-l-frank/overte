"""Closing Cancel keeps fresh sources and the later original-file check.

The public SDK26 fixture, actual TLS receipts, independent Actor and private
files run here. Android/native/render producers are explicit host simulations;
these counters establish test logic, not APK or physical-device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_read_ready_slot as slot
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack
from overte_phone_snapshots_feature import PhoneSnapshotsFeature
from overte_phone_snapshots_role import PhoneSnapshotsRole


class SnapshotClosingCancelHistoryTests(unittest.TestCase):
    # Delegate support methods without inheriting/discovering the six existing
    # read-ready tests or changing their fixture and independent child program.
    setUpClass=classmethod(slot.SnapshotReadReadySlotTests.setUpClass.__func__)
    tearDownClass=classmethod(slot.SnapshotReadReadySlotTests.tearDownClass.__func__)
    receive=slot.SnapshotReadReadySlotTests.receive
    step=slot.SnapshotReadReadySlotTests.step
    launch=slot.SnapshotReadReadySlotTests.launch
    good=slot.SnapshotReadReadySlotTests.good

    @contextmanager
    def cancelled_cleaned(self):
        act=self.fixture_type.act;seeded=[]
        def actual_cancel_before_capture(rig,verb,inputs=None):
            if verb=='capture' and not seeded:
                seeded.append(True)
                act(rig,'capture-cancel',dict(mode='animated',format='png'))
                observed=rig.invoke('feature.snapshots.observe',dict(
                    contractVersion=slot.harness.VERSION,runId=slot.harness.RUN,afterSequence=0))
                self.assertEqual(['pending','cancelled'],observed['state']['captureHistory'])
                self.assertEqual(0,observed['state']['files'])
            return act(rig,verb,inputs)
        with patch.object(self.fixture_type,'act',actual_cancel_before_capture):
            with slot.SnapshotReadReadySlotTests.cleaned(self) as rig:
                owner=unpack(rig.slot_feature_store.read()['payload'])[0]
                self.assertEqual([True],seeded)
                self.assertEqual(1,len(owner['cancelJobs']))
                self.assertGreater(owner['cancelJobs'][0]['retirementIndex'],0)
                yield rig

    def observe_cancel(self,rig,*,remove_original=False):
        events=[];packets=[];counts=[];context={};removed=[]
        active=dict(current=False,account=False,cancelled=False)
        read=PhoneSnapshotsRole.read
        input_originals=PhoneSnapshotsFeature.input_originals
        validate_account=PhoneSnapshotsFeature.validate_account
        closing_count=PhoneSnapshotsRole.closing_input_count
        cancel_factory=rig.adapter._snapshot_cancel
        def current(role,*args,**kwargs):
            if role.role!='primary' or role.feature.state['phase']!='cleaned':
                return read(role,*args,**kwargs)
            role.feature.lock.assert_held();active['current']=True
            try:return read(role,*args,**kwargs)
            finally:active['current']=False
        def count(role):
            value=closing_count(role)
            if active['current']:
                counts.append(value);events.append('bound-count')
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
                        token=context['seen']['history']
                        prefix='emote-frame-snapshots-input-'+slot.harness.RUN+'-primary-'
                        paths=sorted(path for path,receipt in token.files.items()
                            if receipt is not None and path.name.startswith(prefix))
                        self.assertTrue(paths,'Actual input-original receipt is missing from the admitted pass')
                        path=paths[0];self.assertIn((path,token.files[path]),token.file_seal)
                        raw=path.read_bytes();removed.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest()))
                        path.unlink();self.assertFalse(path.exists())
                return packet
            reader.request=fresh;return reader
        def after_wait(seen):
            context['seen']=seen
            context['peerEntries']=deepcopy(rig.client.request('/runs/'+slot.harness.RUN)['entries'])
            self.assertEqual(2,len(context['peerEntries']))
        with patch.object(PhoneSnapshotsRole,'read',current),patch.object(PhoneSnapshotsRole,'closing_input_count',count),\
                patch.object(PhoneSnapshotsFeature,'input_originals',originals),\
                patch.object(PhoneSnapshotsFeature,'validate_account',account),\
                patch.object(rig.adapter,'_snapshot_cancel',factory):
            seen=self.launch(rig,after_wait=after_wait)
        owner=unpack(rig.slot_feature_store.read()['payload'])[0]
        self.assertEqual([owner['inputSequence']],counts)
        self.assertEqual(1,len(packets))
        self.assertTrue(packets[0]['source']['retired'])
        self.assertFalse(packets[0]['source']['timerActive'])
        self.assertEqual('complete',packets[0]['source']['phase'])
        self.assertLess(events.index('bound-count'),events.index('fresh-cancel'))
        self.assertLess(events.index('fresh-cancel'),events.index('account'))
        self.assertLess(events.index('account'),events.index('account-originals'))
        self.assertNotIn('other-originals',events)
        self.assertEqual(context['peerEntries'],rig.client.request('/runs/'+slot.harness.RUN)['entries'])
        return seen,events,removed

    def test_closing_foreground_reads_fresh_retired_cancel_and_replays_account_originals_afterwards(self):
        with self.cancelled_cleaned() as rig:
            seen,events,removed=self.observe_cancel(rig)
            self.good(rig,seen)
            self.assertEqual([],removed)
            self.assertEqual(1,events.count('account-originals'))
            self.assertNotIn('account-originals-rejected',events)

    def test_late_input_original_loss_during_fresh_cancel_rejects_the_same_primary_observation(self):
        with self.cancelled_cleaned() as rig:
            seen,events,removed=self.observe_cancel(rig,remove_original=True)
            self.assertIsInstance(seen['error'],NativeUIError)
            self.assertIsNone(seen['result']);self.assertEqual([True],seen['current'])
            self.assertEqual(1,len(removed));self.assertFalse(removed[0]['path'].exists())
            # The real SourceLock context wraps the original open failure.
            # Keep its exact missing-file cause rather than accepting any
            # ownership error or mistaking a later finalizer for this read.
            cause=seen['error'].__context__
            self.assertIs(type(cause),FileNotFoundError)
            self.assertEqual(str(removed[0]['path']),cause.filename)
            self.assertEqual(1,events.count('account-originals-rejected'))
            actual=unpack(rig.slot_primary_store.read()['payload'])[0]
            prepared=unpack(seen['header']['payload'])[0]
            self.assertEqual(prepared['sequence'],actual['sequence'])
            self.assertEqual('reading',actual['phase']);self.assertIsNone(actual['pending']['frame'])
            actor=unpack(rig.slot_actor_store.read()['payload'])[0]
            self.assertEqual(seen['header'],actor['primaryCue']['header'])
            self.assertIsNotNone(actor['last']);self.assertIsNone(actor['pending'])


if __name__=='__main__':unittest.main()
