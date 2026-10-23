"""Actual host weak-object census, explicitly a model of native Qt operands."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
import weakref
from adapters.script_ui_root_ownership import LIMIT


class Root:
    def __init__(self,kind):
        self.kind=kind;self.source='qrc:/qml/'+('hifi/dialogs/TabletRunningScripts.qml' if kind=='manager' else 'dialogs/NativeFileBrowser.qml')


class RootCensus:
    def __init__(self):self.instance=uuid.uuid4().hex;self.sequence=0;self.elapsed=0;self.complete=True;self.rows=[]
    def tick(self):self.elapsed+=1;return 20000+self.elapsed
    def observe(self,root):
        for row,reference in self.rows:
            if reference() is root:return row['observedIdentity']
        if len(self.rows)>=64:self.complete=False;return ''
        row=dict(observedIdentity=uuid.uuid4().hex,kind=root.kind,componentSource=root.source,firstObservedSequence=len(self.rows)+1,
            firstObservedEpochMs=self.tick(),firstObservedMonotonicMs=self.elapsed,weakAlive=True,weakExpiredObservedEpochMs=0,weakExpiredObservedMonotonicMs=0)
        self.rows.append((row,weakref.ref(root)));return row['observedIdentity']
    def source(self,*,ready=True):
        self.sequence+=1
        for row,reference in self.rows:
            if reference() is None and row['weakAlive']:
                row.update(weakAlive=False,weakExpiredObservedEpochMs=self.tick(),weakExpiredObservedMonotonicMs=self.elapsed)
        value=dict(iosScriptUiRootOwnershipVersion=1,available=True,instance=self.instance,sequence=self.sequence,processId=31,
            capturedEpochMs=self.tick(),monotonicMs=self.elapsed,clockDomain='native-main-ios-script-ui-roots',complete=self.complete,
            wholeTreeReady=ready,observationSequence=len(self.rows),roots=[deepcopy(row) for row,_reference in self.rows])
        if len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())>LIMIT:
            self.complete=False;value.update(complete=False,roots=[])
        return value
