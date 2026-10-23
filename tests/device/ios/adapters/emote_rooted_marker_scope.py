"""Explicit Emote marker scope three requires original whole-tree UI roots.

Ordinary inputs, files, source acquisitions and Web quiet remain the existing
scope owners. This version retains actual weak roots and process responsibility;
it cannot discharge them or complete the feature without independent OS end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters import original_marker_holders as holders
from adapters.native_feature_observation import need
from adapters.script_ui_inventory import validate as inventory_packet
from adapters.script_ui_root_ownership import membership,validate as root_packet
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope

VERSION=3


class IOSEmoteRootedMarkerScope(IOSEmoteHeldMarkerScope):
    def envelope(self,state):
        value=super().envelope(state);value[self.components.scope_key]=VERSION;return value

    def validate_frame(self,frame,previous=None):
        result=super().validate_frame(frame,previous)
        before,after=(frame['clockJoin'][key]['capturedEpochMs'] for key in ('nativeBefore','nativeAfter'))
        inventory=inventory_packet(frame['widgets']['scriptInventory'],pid=self.pid,epoch=after)
        need(inventory['inventoryVersion']==2 and inventory['complete'])
        roots=membership(inventory,pid=self.pid,epoch=after)
        need(roots['available'] and roots['complete'] and roots['wholeTreeReady']
            and before<=roots['capturedEpochMs']<=after)
        if previous is not None:
            root_packet(roots,pid=self.pid,previous=membership(previous['widgets']['scriptInventory'],pid=self.pid))
        return result

    @classmethod
    def ui_absent(cls,frame):
        super().ui_absent(frame)
        holders.ui('emote',frame['widgets']['scriptInventory'],pid=frame['world']['processId'])

    def quiet_web(self,current,admitted,*,partial=False):
        result=super().quiet_web(current,admitted,partial=partial)
        holders.ui('emote',current['widgets']['scriptInventory'],pid=self.pid)
        if not getattr(self,'failed',True) and self.state['quiet']:
            self.unchanged_roots(self.frames[self.state['quiet'][-1]-1],current)
        return result

    def unchanged_roots(self,first,last):
        return holders.unchanged(first['web'],last['web'],
            membership(first['widgets']['scriptInventory'],pid=self.pid),
            membership(last['widgets']['scriptInventory'],pid=self.pid),pid=self.pid)

    def decode(self,value):
        state=super().decode(value)
        if state['phase'] in ('releasing-files','released'):
            frames=[self.frames[index-1] for index in state['quiet']]
            for frame in frames:self.ui_absent(frame)
            for first,last in zip(frames,frames[1:]):self.unchanged_roots(first,last)
        return state

    def held_originals(self):
        """Closed terminal projection with all actual contributing originals."""
        need(self.state['phase']=='released' and self.state['pending'] is None and len(self.state['quiet'])>=3)
        selected=self.state['baseline'] if self.state['cleanupMode']=='unloaded' else self.state['webAdmission']
        need(selected is not None and self.state['baseline'] is not None)
        admitted=self.frames[selected-1];current=self.frames[self.state['quiet'][-1]-1]
        web=holders.web('emote',current['web'],admitted['web'],partial=self.state['cleanupMode']!='full')
        ui=holders.ui('emote',current['widgets']['scriptInventory'],pid=self.pid)
        process=holders.process('emote',self.frames[self.state['baseline']-1]['clockJoin']['nativeBefore'],
            current['clockJoin']['nativeAfter'],binding=self.binding,run=self.run)
        rows=web['holders']+ui['holders']+[process]
        need(len({row['resource'] for row in rows})==len(rows))
        return deepcopy(sorted(rows,key=lambda row:row['resource']))
