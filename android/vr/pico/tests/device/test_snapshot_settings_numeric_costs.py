"""Source2 numerical reuse on the same warm Parent; Native/Qt remain models.

Every current namespace read still uses real files, original OFDs and eight
physical fields. Saturation/retained-memory stress are explicit Host fixtures,
not claims of a device producing 512 historical entries or a 16MiB response.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.pico_snapshot_settings_scope2_fixture import Scope2Boundary
from adapters.normal_ui import NativeUIError
from adapters.pico4 import snapshot_settings_namespace as module
from adapters.pico4.snapshot_settings_query_originals import UNRESOLVED
from adapters.script_journey.history import MAX_RAW


class SnapshotSettingsNumericCostsTests(unittest.TestCase):
    def prepared(self):
        model=Scope2Boundary(self);lease=model.attach();model.parent.prepare()
        model.h.activate('open');model.parent.open()
        return model,lease,lease.raw.namespace

    def no_next_query(self,model,lease,mutate):
        calls=len(model.sdk_calls);sequence=model.sequence;mutate()
        with self.assertRaises((NativeUIError,ValueError,AttributeError)):lease.observe()
        self.assertEqual(calls,len(model.sdk_calls));self.assertEqual(sequence,model.sequence)
        self.assertTrue(lease.raw.failed);self.assertFalse(lease.raw.close_host())

    def test_same_warm_owner_full_current_file_windows_and_equal_numeric_bill(self):
        model,lease,namespace=self.prepared();read=namespace.read;windows=[]
        def observed(*args,**kwargs):
            result=read(*args,**kwargs);windows.append(args[0]);return result
        with lease.lock.held(),patch.object(namespace,'read',side_effect=observed):
            first=namespace.measure(lease);first_windows=list(windows);windows.clear()
            hits=namespace.costs.hits;second=namespace.measure(lease)
            self.assertEqual(first,second);self.assertEqual(first_windows,windows)
            self.assertTrue(first_windows);self.assertGreater(namespace.costs.hits,hits)
            self.assertEqual(4096+768*len(namespace.costs.rows),namespace.costs.metadata_bytes())
            self.assertTrue(lease.raw.close_host())
        self.assertEqual(2,len(model.sdk_calls));self.assertEqual(['tablet.open'],model.h.adb.controllers)

    def test_real_same_inode_changed_original_child_cannot_reuse_cost(self):
        model,lease,namespace=self.prepared();path=lease.raw.children[0].path
        before=path.stat();data=path.read_bytes();path.write_bytes(data.replace(b'"',b' ',1))
        self.assertEqual(before.st_ino,path.stat().st_ino)
        self.no_next_query(model,lease,lambda:None)
        self.assertEqual(data.replace(b'"',b' ',1),path.read_bytes())

    def test_foreign_equal_parser_never_called_before_refusal(self):
        model,lease,namespace=self.prepared();calls=[]
        class Foreign:
            def __eq__(self,other):calls.append('equal');return True
            def __call__(self,*args):calls.append('call');return {}
        with patch.object(module,'strict',Foreign()):self.no_next_query(model,lease,lambda:None)
        self.assertEqual([],calls)

    def test_same_parser_function_with_changed_code_refuses_before_query(self):
        model,lease,namespace=self.prepared();original=module.strict.__code__
        def replaced(raw):return {}
        try:
            module.strict.__code__=replaced.__code__
            self.no_next_query(model,lease,lambda:None)
        finally:module.strict.__code__=original

    def test_numeric_row_alias_substitution_refuses_before_query(self):
        model,lease,namespace=self.prepared();original=namespace.costs.rows
        self.no_next_query(model,lease,lambda:setattr(namespace.costs,'rows',tuple(list(original))))
        self.assertIs(namespace.costs._rows,original)

    def test_full_memo_uses_original_expansion_without_reset_or_new_budget(self):
        model,lease,namespace=self.prepared();costs=namespace.costs
        # Explicit numerical-table saturation precondition. These rows grant
        # no file admission: actual namespace known()/read() still owns ALL
        # current files and new entries must use the original unpack path.
        with lease.lock.held():
            while len(costs.rows)<512:
                index=len(costs.rows);key=('numeric-stress-'+str(index),hashlib.sha256(str(index).encode()).hexdigest(),1)
                current=namespace.measure(lease)
                self.assertLessEqual(current['decodedBytes']+current['transientBytes']+2097152+768,MAX_RAW)
                ticket=costs.begin(key);costs.finish(ticket,0,0)
            before=costs.rows;calls=[];unpack=module.unpack
            # Use the actual original decoder; counting its calls cannot alter
            # function identity used by the memo. Python profiling is local.
            def count(frame,event,arg):
                if event=='call' and frame.f_code is unpack.__code__:calls.append(1)
            import sys
            old=sys.getprofile()
            try:
                sys.setprofile(count);lease.observe();bill=namespace.measure(lease)
            finally:sys.setprofile(old)
            self.assertIs(before,costs.rows);self.assertEqual(512,len(costs.rows));self.assertTrue(calls)
            self.assertEqual(4096+512*768,costs.metadata_bytes())
            self.assertLessEqual(bill['decodedBytes']+bill['transientBytes'],MAX_RAW)
            self.assertTrue(lease.raw.close_host())
        self.assertEqual(3,len(model.sdk_calls))

    def test_actual_retained_host_bytes_exhaust_same_global_bill_before_getter(self):
        model,lease,namespace=self.prepared()
        # Host-retention stress, not a Native return: acquired bytes are kept
        # in the actual owner and charged in the SAME existing namespace bill.
        retained=b'x'*MAX_RAW
        self.assertGreaterEqual(len(retained),MAX_RAW)
        self.no_next_query(model,lease,lambda:setattr(lease.raw,'acquired',retained))
        gc.collect();self.assertIs(lease.raw.acquired,retained);self.assertIn(lease.raw,UNRESOLVED)

    def test_interrupted_actual_new_entry_keeps_pending_and_original_raw_owner(self):
        model,lease,namespace=self.prepared();costs=namespace.costs;finish=costs.finish;attempts=[]
        original=deepcopy(lease.raw.state);wire=model.outputs[0]
        def interrupted(ticket,delta,largest):
            attempts.append(ticket);raise OSError('Actual numeric admission completion interrupted')
        with patch.object(costs,'finish',side_effect=interrupted):
            calls=len(model.sdk_calls);native=model.sequence
            with self.assertRaises(NativeUIError):lease.observe()
        self.assertTrue(attempts);self.assertIs(costs.pending,attempts[0])
        self.assertEqual(calls,len(model.sdk_calls));self.assertEqual(native,model.sequence)
        self.assertTrue(lease.raw.failed);self.assertFalse(lease.raw.close_host());self.assertIn(lease.raw,UNRESOLVED)
        with lease.lock.held():
            reference=dict(snapshotSettingsRawReferenceVersion=2,bundle=0,sha256=original['bundles'][0]['sha256'])
            self.assertEqual(wire,lease.raw.literal(reference))


if __name__=='__main__':unittest.main()
