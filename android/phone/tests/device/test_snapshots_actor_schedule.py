"""Real-clock unit coverage of the cleanup scheduler, with synthetic readers.

This test qualifies scheduling only. Full source evidence belongs to the public
journey and separate-process actor tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import tempfile
import time
from types import MethodType,SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_actor  # Self-contained source import setup.
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshots_actor import PhoneSnapshotsActor,WITNESS_KEYS


class SnapshotActorSchedulingTests(unittest.TestCase):
    def test_fifth_actual_completed_sample_can_finish_quiet_before_yield(self):
        with tempfile.TemporaryDirectory(prefix='snapshots-scheduler-') as directory:
            lock=PhoneScriptSourceLock(Path(directory)/'sources.lock')
            ticket='a'*32;phase=dict(active=True,activations=[dict(ticket=ticket)])
            points=[];delivered=[]
            def held():lock.assert_held();return True
            def restored(**kwargs):
                held();time.sleep(.1);return dict(schedulerUnitOnly=True)
            feature=SimpleNamespace(bound=held,phase=SimpleNamespace(status=lambda:phase),
                restored=restored,monotonic=time.monotonic,sleep=time.sleep)
            role=SimpleNamespace(history_authority=held,frames=[],state=dict(sequence=0),restore_originals=lambda:role.frames)
            def read(after):
                held();self.assertEqual(after,role.state['sequence']);time.sleep(.75)
                role.state['sequence']+=1;role.frames.append(dict(ticket=ticket,phaseAfter=phase))
                return dict(resources=[],sequence=role.state['sequence'],capturedEpochMs=1,state={key:None for key in WITNESS_KEYS['snapshots']})
            role.read=read
            def save():
                held();quiet=actor.state['quiet']
                if quiet is not None and (not points or points[-1]['last']!=quiet['last']):points.append(dict(quiet))
            actor=SimpleNamespace(feature=feature,state=dict(quiet=None,pending=None,last=None),
                cleanup_phase=lambda actual,prepared:self.assertEqual(actual,prepared),save=save,
                deliver=lambda:delivered.append(time.monotonic()),retain_cleanup=lambda *_:held(),
                read_ready_mode=lambda:None,primary_continuity=lambda *_:held(),primary_cue=lambda *_:None)
            # This is an explicitly unenrolled scheduler unit, not a fabricated
            # Primary slot or native observation. Run the current original batch.
            actor._quiet_batch=MethodType(PhoneSnapshotsActor._quiet_batch,actor)
            started=time.monotonic()
            with lock.held():self.assertFalse(PhoneSnapshotsActor.quiet_batch(actor,role,dict(phase=phase),started))
            elapsed=time.monotonic()-started
            self.assertEqual(5,len(points));self.assertTrue(all(not row['complete'] for row in points[:4]))
            self.assertTrue(points[-1]['complete']);self.assertGreaterEqual(points[-1]['last']-points[-1]['started'],3)
            self.assertTrue(all(b['last']-a['last']<=1.5 for a,b in zip(points,points[1:])))
            self.assertEqual(1,len(delivered));self.assertLess(elapsed,5)
            # This is a real completed-observation schedule, with no clock
            # retiming and no claim about synthetic measurement content.
            self.assertGreaterEqual(points[3]['last']-started,3.5)


if __name__=='__main__':unittest.main()
