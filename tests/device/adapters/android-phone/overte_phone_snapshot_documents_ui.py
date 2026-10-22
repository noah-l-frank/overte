"""Ordinary SDK DocumentsUI input in the independently resolved Save activity.

The fixture root is selected through the actual OS accessibility tree. An
acknowledged touch or a returning picker never proves any saved file.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import context
from overte_phone_snapshot_resolution import SnapshotChooserResolution,resolved,package_uid
from overte_phone_snapshot_system_context import SnapshotSystemContext
from overte_phone_snapshot_system_ui import PhoneSnapshotSystemUI,tree,bounds,LABEL,PRIMARY

RESOLVE=('cmd','package','resolve-activity','--brief','--user','0','-a','android.intent.action.CREATE_DOCUMENT',
    '-c','android.intent.category.OPENABLE','-t','image/png')


def resolution(value):
    exact(value,{'snapshotDocumentResolutionVersion','component','uid','requestedEpochMs','capturedEpochMs','resolutionSha256','uidSha256'})
    need(type(value['snapshotDocumentResolutionVersion']) is int and value['snapshotDocumentResolutionVersion']==1
        and type(value['component']) is str and resolved(value['component'])==value['component'] and integer(value['uid'],1)
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<=1500
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('resolutionSha256','uidSha256')))
    return value


class SnapshotDocumentResolution(SnapshotChooserResolution):
    def read(self):
        try:
            need(self.guard() is not False);start=self.monotonic();need(number(start,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            raw=self._read(*RESOLVE);actual=resolved(raw);package=actual.split('/')[0]
            uid_raw=self._read('cmd','package','list','packages','-U','--user','0',package);uid=package_uid(uid_raw,package)
            need(resolved(self._read(*RESOLVE))==actual)
            captured=self.clock_ms();now=self.monotonic()
            need(integer(captured,requested) and captured-requested<=1500 and number(now,start,1e15) and now-start<=1.5)
            value=resolution(dict(snapshotDocumentResolutionVersion=1,component=actual,uid=uid,requestedEpochMs=requested,
                capturedEpochMs=captured,resolutionSha256=hashlib.sha256(raw.encode()).hexdigest(),uidSha256=hashlib.sha256(uid_raw.encode()).hexdigest()))
            if self.last is not None:need(value['component']==self.last['component'] and value['uid']==self.last['uid'])
            need(self.guard() is not False);self.last=dict(value);return dict(value)
        except Exception:raise NativeUIError('Original Snapshot document activity resolution is unavailable or changed') from None


class SnapshotDocumentContext(SnapshotSystemContext):
    def __init__(self,binding,documents,observe_binding,current_component,authority,*,monotonic=time.monotonic):
        context(binding);resolution(documents)
        need(all(callable(fn) for fn in (observe_binding,current_component,authority,monotonic)))
        self.binding,self.chooser=deepcopy(binding),deepcopy(documents)
        self.observe_binding,self.current_component,self.authority,self.monotonic=observe_binding,current_component,authority,monotonic
        self.last_clock=None
    def _allowed_component(self,actual):
        return actual==self.chooser['component']


class PhoneSnapshotDocumentsUI(PhoneSnapshotSystemUI):
    def capture(self):
        value=super().capture();value['snapshotDocumentUiVersion']=value.pop('snapshotSystemUiVersion')
        need(value['component']==self.chooser or value['component'].split('/')[0]==PRIMARY)
        return value
    def _intent(self,action,original,details):
        need(self.intent(dict(snapshotDocumentInputVersion=1,action=action,original=deepcopy(original),details=deepcopy(details))) is not False)
        current=self.capture();need(current['component']==original['component'] and current['sourceSha256']==original['sourceSha256']
            and 0<=current['capturedEpochMs']-original['capturedEpochMs']<=1500)
    def _tap(self,before,node,action):
        need(before['component']==self.chooser and node.get('package')==self.package
            and node.get('enabled')=='true' and node.get('displayed','true')=='true')
        area=bounds(node);x,y=(area[0]+area[2])//2,(area[1]+area[3])//2
        self._intent(action,before,dict(point=[x,y],resourceId=node.get('resource-id',''),text=node.get('text','')))
        try:
            self.ui._request('POST','/actions',{'actions':[dict(type='pointer',id='overte-snapshot-document',parameters={'pointerType':'touch'},
                actions=[dict(type='pointerMove',duration=0,origin='viewport',x=x,y=y),dict(type='pointerDown',button=0),
                    dict(type='pause',duration=50),dict(type='pointerUp',button=0)])]})
        finally:self.ui.release_actions()
    def _clickable(self,root,node):
        parents={child:parent for parent in root.iter() for child in parent};label=bounds(node)
        while node.get('clickable')!='true':need(node in parents);node=parents[node]
        area=bounds(node);need(area[0]<=label[0]<label[2]<=area[2] and area[1]<=label[1]<label[3]<=area[3])
        return node
    def select_root(self):
        try:
            before=self.capture();need(before['component']==self.chooser)
            if self._selected_root(before):return before
            for step in range(2):
                root=tree(before['xml']);rows=[node for node in root.iter() if node.get('package')==self.package
                    and node.get('text')==LABEL and node.get('enabled')=='true' and node.get('displayed','true')=='true']
                need(len(rows)<=1)
                if rows:
                    node=self._clickable(root,rows[0]);self._tap(before,node,'document-select-owned-root')
                    return self.wait(self._selected_root)
                need(step==0)
                navigation=[node for node in root.iter() if node.get('package')==self.package and node.get('enabled')=='true'
                    and node.get('displayed','true')=='true' and node.get('clickable')=='true'
                    and ((node.get('resource-id')=='android:id/home') or
                        (node.get('class')=='android.widget.ImageButton' and node.get('content-desc') in ('Show roots','Show navigation drawer')))]
                need(len(navigation)==1);self._tap(before,navigation[0],'document-show-roots');before=self.wait(lambda value:LABEL in value['xml'])
        except Exception:raise NativeUIError('Normal Snapshot owned document-root selection did not complete') from None
    def _selected_root(self,value):
        if value['component']!=self.chooser:return False
        root=tree(value['xml'])
        return any(node.get('package')==self.package and node.get('text')==LABEL
            and node.get('resource-id') in (self.package+':id/toolbar_title','android:id/title')
            and node.get('displayed','true')=='true' for node in root.iter())
    def save(self,display_name):
        try:
            need(type(display_name) is str and re.fullmatch(r'e2e-[0-9a-f]{32}-[A-Za-z0-9_-]{1,160}\.png',display_name))
            before=self.capture();need(self._selected_root(before));root=tree(before['xml'])
            names=[node for node in root.iter() if node.get('package')==self.package and node.get('class')=='android.widget.EditText'
                and node.get('resource-id') in ('android:id/title',self.package+':id/title',self.package+':id/edit_text')
                and node.get('displayed','true')=='true' and node.get('enabled')=='true']
            need(len(names)==1 and names[0].get('text')==display_name)
            saves=[node for node in root.iter() if node.get('package')==self.package and node.get('resource-id') in
                (self.package+':id/action_menu_save','android:id/button1') and node.get('enabled')=='true' and node.get('displayed','true')=='true']
            need(len(saves)==1);self._tap(before,self._clickable(root,saves[0]),'document-save')
            return self.wait(lambda value:value['component'].split('/')[0]==PRIMARY)
        except Exception:raise NativeUIError('Normal Snapshot document Save did not complete') from None
    def cancel(self):
        for attempt in range(3):
            before=self.capture()
            if before['component'].split('/')[0]==PRIMARY:
                need(attempt>0);return before
            need(before['component']==self.chooser);self._intent('document-cancel',before,{})
            self.ui._request('POST','/back',{})
            self.wait(lambda value:value['component'].split('/')[0]==PRIMARY or value['sourceSha256']!=before['sourceSha256'])
        return self.wait(lambda value:value['component'].split('/')[0]==PRIMARY)
