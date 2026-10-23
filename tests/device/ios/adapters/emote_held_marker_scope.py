"""Explicit marker-scope version two retains quiet cached native resources.

The existing version-one facade and its full-drain readers remain unchanged.
Whole Emote end must separately join these held originals to process/SDK end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_marker_disposition import disposition,unchanged
from adapters.native_feature_observation import need
from adapters.script_feature.history import same

VERSION=2


class IOSEmoteHeldMarkerScope(IOSEmoteMarkerScope):
    @staticmethod
    def quiet_interval(first,last):
        if not IOSEmoteMarkerScope.quiet_interval(first,last):return False
        a,b=first['clockJoin'],last['clockJoin'];x,y=first['world'],last['world']
        gaps=[(b['hostBeforeMonotonic']-a['hostAfterMonotonic'])*1000,
            b['hostBeforeEpochMs']-a['hostAfterEpochMs'],
            y['clockBefore']['monotonicMs']-x['clockAfter']['monotonicMs'],
            y['clockBefore']['epochMs']-x['clockAfter']['epochMs']]
        return all(3000<=gap<60000 for gap in gaps) and max(gaps)-min(gaps)<=500

    def envelope(self,state):
        value=super().envelope(state);value[self.components.scope_key]=VERSION;return value

    def quiet_web(self,current,admitted,*,partial=False):
        need(all(row['web']['runId']==self.run and row['web']['processId']==self.pid
            and row['web']['fixtureUrl']==self.fixture_url for row in (current,admitted)))
        result=disposition(current['web'],admitted['web'],partial=partial or self.state['cleanupMode'] in
            ('partial-execution','finished-execution','unloaded'))
        if not getattr(self,'failed',True):
            need(self.frames and same(current,self.frames[-1]))
            if self.state['quiet']:unchanged(self.frames[self.state['quiet'][-1]-1]['web'],current['web'])
        return result

    def decode(self,value):
        state=super().decode(value)
        if state['phase'] in ('releasing-files','released'):
            indices=state['quiet'];need(len(indices)>=3 and indices==sorted(set(indices)))
            frames=[self.frames[index-1] for index in indices]
            need(self.quiet_interval(frames[0],frames[-1]))
            selected=state['baseline'] if state['cleanupMode']=='unloaded' else state['webAdmission']
            need(selected is not None);baseline=self.frames[selected-1]
            partial=state['cleanupMode']!='full'
            for frame in frames:disposition(frame['web'],baseline['web'],partial=partial)
            for first,last in zip(frames,frames[1:]):unchanged(first['web'],last['web'])
        return state
