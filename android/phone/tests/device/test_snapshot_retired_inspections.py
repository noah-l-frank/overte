"""Fresh readonly OS/grant queries retain originals and reject old absence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from test_snapshot_share_grants_source import boundary
from test_snapshot_readback_source import RUN


def original_queries(fault=None):
    producer=boundary();send=producer.send;pending={}
    def actual(request):
        operation=request['operation']
        key={'inspect-destinations':'osDestinations','inspect-shares':'shareGrants'}.get(operation)
        if key and fault!='ignored':pending[key]=request['resourceId']
        elif operation=='observe':
            for name,nonce in list(pending.items()):
                if fault=='frozen':continue
                rows=producer.component[name]
                measured=producer.epoch+10 if fault!='before-request' else producer.epoch-1
                rows.update(checkId=nonce,checkedEpochMs=measured)
                for row in rows['rows']:row['checkedEpochMs']=measured if fault!='old-row' else producer.epoch-1
                del pending[name]
        send(request)
    producer.send=actual
    if fault=='foreign':producer.fault=lambda packet:packet.update(processId=32)
    if fault=='missing':producer.fault=lambda packet:packet['source']['source'].pop('shareGrants')
    return producer


class SnapshotRetiredInspectionTests(unittest.TestCase):
    def test_actual_new_queries_refresh_both_absences_without_rewriting_history(self):
        producer=original_queries();reader=producer.reader();first=reader.require_retired(RUN)
        old=deepcopy(first);old_queries=deepcopy(reader.inspections)
        second=reader.require_retired(RUN)
        self.assertEqual(old,first)
        self.assertEqual({'destinations','shares'},set(reader.inspections))
        for name,key in (('destinations','osDestinations'),('shares','shareGrants')):
            query=reader.inspections[name]
            self.assertNotEqual(old_queries[name]['request']['requestId'],query['request']['requestId'])
            self.assertEqual(query['command']['commandId'],query['request']['requestId'])
            self.assertEqual(query['command']['resourceId'],query['observation']['source']['source'][key]['checkId'])
            self.assertGreater(second['source']['source'][key]['checkedEpochMs'],old['source']['source'][key]['checkedEpochMs'])
            self.assertGreaterEqual(query['observation']['source']['source'][key]['checkedEpochMs'],query['request']['requestedEpochMs'])
        self.assertEqual(old['source']['source']['jobs'],second['source']['source']['jobs'])
        self.assertEqual(['inspect-destinations','observe','inspect-shares','observe']*2,[row['operation'] for row in producer.sent])

    def test_ack_frozen_old_inspection_or_time_before_new_request_is_not_current(self):
        for fault in ('ignored','frozen','before-request','old-row'):
            with self.subTest(fault=fault):
                producer=original_queries(fault);reader=producer.reader()
                with self.assertRaises(NativeUIError):reader.require_retired(RUN)
                self.assertEqual({},reader.inspections)
                self.assertLessEqual(producer.clock,5.1)

    def test_missing_or_foreign_originals_never_supply_absence(self):
        for fault in ('foreign','missing'):
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):original_queries(fault).reader().require_retired(RUN)

    def test_readonly_native_admission_keeps_removal_and_revocation_forbidden(self):
        from appium_adapter import readonly_feature_command
        from overte_phone_snapshot_readbacks import command
        base=dict(schemaVersion=1,commandId='4'*32,action='phone-snapshot-readback',runId=RUN,exportRequest='',resourceId='5'*32)
        for operation in ('inspect-destinations','inspect-shares'):
            readonly_feature_command(command(base|dict(operation=operation)))
        for operation in ('remove-destination','revoke-share'):
            request=command(base|dict(operation=operation,exportRequest='6'*32))
            with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request)


if __name__=='__main__':unittest.main()
