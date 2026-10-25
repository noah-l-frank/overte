"""Avatar scope two preserves actual quiet cache and observed Qt holders.

Scope one continues to require full resource drainage. This version never
retires its held objects: process/SDK end must independently close them.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters import original_marker_holders as holders
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from adapters.script_ui_inventory import validate as inventory_packet
from adapters.script_ui_root_ownership import membership,validate as root_packet
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope

VERSION=2


class IOSAvatarHeldMarkerScope(IOSAvatarMarkerScope):
    def envelope(self,state):
        value=super().envelope(state);value[self.components.scope_key]=VERSION;return value

    def validate_frame(self,frame,previous=None):
        result=super().validate_frame(frame,previous)
        epoch=frame['clockJoin']['nativeAfter']['capturedEpochMs']
        inventory=inventory_packet(frame['widgets']['scriptInventory'],pid=self.pid,epoch=epoch)
        need(inventory['inventoryVersion']==2 and inventory['complete'])
        roots=membership(inventory,pid=self.pid)
        need(roots['available'] and roots['complete'] and roots['wholeTreeReady']
            and frame['clockJoin']['nativeBefore']['capturedEpochMs']<=roots['capturedEpochMs']<=epoch)
        if previous is not None:
            root_packet(roots,pid=self.pid,previous=membership(previous['widgets']['scriptInventory'],pid=self.pid))
        return result

    @classmethod
    def ui_absent(cls,frame):
        super().ui_absent(frame)
        holders.ui('avatar',frame['widgets']['scriptInventory'],pid=frame['world']['processId'])

    @staticmethod
    def quiet_interval(first,last):
        if not IOSAvatarMarkerScope.quiet_interval(first,last):return False
        a,b=first['clockJoin'],last['clockJoin'];x,y=first['world'],last['world']
        gaps=[(b['hostBeforeMonotonic']-a['hostAfterMonotonic'])*1000,
            b['hostBeforeEpochMs']-a['hostAfterEpochMs'],
            y['clockBefore']['monotonicMs']-x['clockAfter']['monotonicMs'],
            y['clockBefore']['epochMs']-x['clockAfter']['epochMs']]
        return all(3000<=gap<60000 for gap in gaps) and max(gaps)-min(gaps)<=500

    def dispositions(self,current,admitted,*,partial=False):
        need(all(row['web']['runId']==self.run and row['web']['processId']==self.pid
            and row['web']['fixtureUrl']==self.fixture_url for row in (current,admitted)))
        web=holders.web('avatar',current['web'],admitted['web'],partial=partial)
        ui=holders.ui('avatar',current['widgets']['scriptInventory'],pid=self.pid)
        process=holders.process('avatar',self.frames[self.state['baseline']-1]['clockJoin']['nativeBefore'],
            current['clockJoin']['nativeAfter'],binding=self.binding,run=self.run)
        return dict(web=web,ui=ui,process=process)

    @staticmethod
    def unchanged(first,last,pid):
        return holders.unchanged(first['web'],last['web'],
            membership(first['widgets']['scriptInventory'],pid=pid),
            membership(last['widgets']['scriptInventory'],pid=pid),pid=pid)

    def quiet_web(self,current,admitted,*,partial=False):
        result=self.dispositions(current,admitted,partial=partial or self.state['cleanupMode']!='full')
        if not getattr(self,'failed',True):
            need(self.frames and same(current,self.frames[-1]))
            if self.state['quiet']:self.unchanged(self.frames[self.state['quiet'][-1]-1],current,self.pid)
        return result

    def decode(self,value):
        state=super().decode(value)
        if state['phase'] in ('releasing-files','released'):
            indices=state['quiet'];need(len(indices)>=3 and indices==sorted(set(indices)))
            frames=[self.frames[index-1] for index in indices]
            need(self.quiet_interval(frames[0],frames[-1]))
            selected=state['baseline'] if state['cleanupMode']=='unloaded' else state['webAdmission']
            need(selected is not None);baseline=self.frames[selected-1]
            # Decode is also called before self.state exists during archive.
            old=getattr(self,'state',None);self.state=state
            try:
                for frame in frames:self.ui_absent(frame);self.dispositions(frame,baseline,partial=state['cleanupMode']!='full')
                for first,last in zip(frames,frames[1:]):self.unchanged(first,last,self.pid)
            finally:
                if old is None:del self.state
                else:self.state=old
        return state

    def held_originals(self):
        """Actual outstanding resources; no assertion of object destruction."""
        need(self.state['phase']=='released' and self.state['pending'] is None and len(self.state['quiet'])>=3)
        selected=self.state['baseline'] if self.state['cleanupMode']=='unloaded' else self.state['webAdmission']
        need(selected is not None)
        current=self.frames[self.state['quiet'][-1]-1]
        value=self.dispositions(current,self.frames[selected-1],partial=self.state['cleanupMode']!='full')
        result=value['web']['holders']+value['ui']['holders']+[value['process']]
        need(len({row['resource'] for row in result})==len(result));return deepcopy(sorted(result,key=lambda row:row['resource']))
