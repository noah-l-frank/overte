"""Host weak operands around the explicit Qt/native authentication boundary.

Objects and QPointer rows are modeled. OAuth, original UI receipts and private
owner journals continue through their actual unchanged host implementations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import uuid
import weakref
from adapters.token_login_ui import IDS


class Root:pass


class LoginRoots:
    def __init__(self,native):
        self.native=native;self.instance=uuid.uuid4().hex;self.rows=[];self.operands=[];self.sequence=0
        observed=native.observed
        def capture():
            value=observed();value['controls'].sort(key=lambda row:row['id'])
            value['loginRootOwnership']=self.capture(value);return value
        native.observed=capture

    def add(self,epoch):
        root=Root();self.operands.append(root)
        row=dict(observedIdentity=uuid.uuid4().hex,kind='tablet',componentSource='qrc:/qml/dialogs/TabletLoginDialog.qml',
            firstObservedSequence=len(self.rows)+1,firstObservedEpochMs=epoch,firstObservedMonotonicMs=round(self.native.clock*1000),
            weakAlive=True,weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
        self.rows.append((weakref.ref(root),row));return row

    def release(self):self.operands.clear();gc.collect()

    def capture(self,original):
        self.sequence+=1;epoch=original['sampleEpochMs'];mono=round(self.native.clock*1000)
        controls=[row for row in original['controls'] if row['id'] in IDS and row['id']!='login.entry']
        active=next((row for weak,row in self.rows if weak() is not None),None)
        if controls and active is None:active=self.add(epoch)
        for weak,row in self.rows:
            if weak() is None and row['weakAlive']:
                row.update(weakAlive=False,weakExpiredObservedEpochMs=epoch,weakExpiredObservedMonotonicMs=mono)
        return dict(iosLoginUiRootsVersion=1,complete=True,ownership=dict(iosLoginUiRootOwnershipVersion=1,
            available=True,instance=self.instance,clockDomain='native-main-ios-login-ui-roots',sequence=self.sequence,
            processId=self.native.pid,capturedEpochMs=epoch,monotonicMs=mono,complete=True,wholeTreeReady=True,
            observationSequence=len(self.rows),roots=[deepcopy(row) for _weak,row in self.rows]),
            controls=sorted([dict(id=row['id'],token=row['token'],observedIdentity=active['observedIdentity']) for row in controls],key=lambda row:row['id']))
