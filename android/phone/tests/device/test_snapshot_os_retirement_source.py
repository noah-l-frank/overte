"""Readback-v2 original absence and readonly grammar counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
import test_snapshot_readback_source as base
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import command,source


def boundary():
    value=base.Boundary();value.complete();value.component.update(snapshotExportReadbacksVersion=2,copiesRetired=True,workersTerminated=True,files=[],removedCopies=[base.COPY])
    destination=value.component['destinations'][0]
    row=dict(request=base.REQUEST,inserted=True,phase='retired',identity=dict(uri=destination['uri'],providerUid=1000,ownerPackage='io.github.noah_be.overte.phone',displayName='original.png',device=1,inode=2),original=dict(bytes=4,sha256='1'*64),acquiredEpochMs=value.epoch-1,deleteId='9'*32,deleteIssued=True,deleteCount=1,checkedEpochMs=value.epoch,absent=True)
    value.component['osDestinations']=dict(snapshotOsDestinationsVersion=1,complete=True,pending=0,checkId='',checkedEpochMs=0,rows=[row])
    value.component['shareGrants']=dict(snapshotShareGrantsVersion=1,complete=True,checkId='',checkedEpochMs=0,rows=[])
    return value


class SnapshotOsRetirementSourceTests(unittest.TestCase):
    def test_fresh_inspection_is_separate_from_cleanup_ack_and_survives_copy_retirement(self):
        value=boundary();send=value.send;pending=[]
        def actual(request):
            if request['operation']=='inspect-destinations':pending.append(request['resourceId'])
            elif pending:
                component=value.component['osDestinations'];component.update(checkId=pending.pop(),checkedEpochMs=value.epoch+10);component['rows'][0]['checkedEpochMs']=value.epoch+10
            send(request)
        value.send=actual;proof=value.reader().require_os_retired(base.RUN)
        self.assertEqual('retired',proof['source']['source']['osDestinations']['rows'][0]['phase']);self.assertEqual(['inspect-destinations','observe'],[row['operation'] for row in value.sent])
    def test_old_absence_receipt_or_ack_cannot_complete_retirement(self):
        value=boundary()
        with self.assertRaises(NativeUIError):value.reader().require_os_retired(base.RUN)
        self.assertLessEqual(value.clock,5.1)
    def test_replaced_uri_missing_original_and_pending_close_are_rejected(self):
        for fault in ('uri','original','pending-close','foreign','unissued'):
            value=boundary();row=value.component['osDestinations']['rows'][0]
            if fault=='uri':row['identity']['uri']='content://media/external/images/media/999'
            elif fault=='original':row['original']=None
            elif fault=='pending-close':value.component['osDestinations']['complete']=False
            elif fault=='foreign':row['identity']['ownerPackage']='org.foreign.application'
            else:row['deleteIssued']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source(dict(accepted=True,source=value.component))
    def test_closed_only_existing_request_ids_and_readonly_observer_gate(self):
        from appium_adapter import readonly_feature_command
        request=dict(schemaVersion=1,commandId='4'*32,action='phone-snapshot-readback',runId=base.RUN,operation='inspect-destinations',exportRequest='',resourceId='5'*32)
        command(request);readonly_feature_command(request)
        mutation=dict(request,operation='remove-destination',exportRequest=base.REQUEST);command(mutation)
        with self.assertRaises((ValueError,RuntimeError)):readonly_feature_command(mutation)
        for field in ('uri','path','expected'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(dict(mutation,**{field:'foreign'}))


if __name__=='__main__':unittest.main()
