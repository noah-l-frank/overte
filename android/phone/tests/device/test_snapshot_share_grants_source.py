"""Original native grant inspection, not chooser ACK, qualifies retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
import test_snapshot_os_retirement_source as os_source
import test_snapshot_readback_source as base
from overte_phone_snapshot_readbacks import source,command
from adapters.normal_ui import NativeUIError


def boundary():
    value=os_source.boundary()
    value.component['shareGrants']['rows']=[dict(request='a'*32,uri='content://io.github.noah_be.overte.phone.snapshot.files/Snapshots/original.png',ownerUid=10001,component='org.overte.e2e.snapshotreceiver/org.overte.snapshot.SnapshotConsumer',receiverUid=10002,chooserComponent='android/com.android.internal.app.ChooserActivity',chooserUid=1000,revokeId='b'*32,revokeIssued=True,granted=False,chooserGranted=False,checkedEpochMs=value.epoch)]
    return value


class SnapshotShareGrantsSourceTests(unittest.TestCase):
    def test_fresh_grant_absence_after_copy_workers_retired(self):
        value=boundary();send=value.send;pending=[]
        def actual(request):
            if request['operation']=='inspect-shares':pending.append(request['resourceId'])
            elif pending:
                grants=value.component['shareGrants'];grants.update(checkId=pending.pop(),checkedEpochMs=value.epoch+10);grants['rows'][0]['checkedEpochMs']=value.epoch+10
            send(request)
        value.send=actual;value.reader().require_share_retired(base.RUN)
    def test_old_receipt_and_current_grant_cannot_retire(self):
        value=boundary()
        with self.assertRaises(NativeUIError):value.reader().require_share_retired(base.RUN)
        self.assertLessEqual(value.clock,5.1)
        for key in ('granted','chooserGranted'):
            value=boundary();value.component['shareGrants']['rows'][0][key]=True
            send=value.send
            def actual(request):
                grants=value.component['shareGrants']
                if request['operation']=='inspect-shares':grants.update(checkId=request['resourceId'],checkedEpochMs=value.epoch+10)
                send(request)
            value.send=actual
            with self.subTest(key=key),self.assertRaises(NativeUIError):value.reader().require_share_retired(base.RUN)
    def test_replaced_uid_and_unissued_revocation_are_rejected(self):
        for key,item in (('receiverUid',10001),('uri','content://foreign.provider/x'),('revokeIssued',False)):
            value=boundary();value.component['shareGrants']['rows'][0][key]=item
            with self.subTest(key=key),self.assertRaises(NativeUIError):source(dict(accepted=True,source=value.component))
    def test_readonly_may_inspect_but_cannot_revoke_owned_uri(self):
        from appium_adapter import readonly_feature_command
        request=dict(schemaVersion=1,commandId='4'*32,action='phone-snapshot-readback',runId=base.RUN,operation='inspect-shares',exportRequest='',resourceId='5'*32)
        command(request);readonly_feature_command(request)
        request.update(operation='revoke-share',exportRequest='a'*32);command(request)
        with self.assertRaises((RuntimeError,ValueError)):readonly_feature_command(request)

if __name__=='__main__':unittest.main()
