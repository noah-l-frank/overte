"""World-only ordinary Script setup with original camera preservation.

The Web Entity is placed by its normal Script using the actual current Camera.
The normal lifecycle owner keeps that camera instead of selecting look-at.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.original_marker_scope import OriginalMarkerScope


class IOSWorldWebScope(OriginalMarkerScope):
    PROFILE='worldweb'

    @classmethod
    def archive(cls,value,*,require_ready=False,**kwargs):
        result=super().archive(value,require_ready=False,**kwargs)
        if require_ready:
            state=result.state;need(state['phase']=='ready' and state['cleanupMode']=='full'
                and state['webAdmission'] is not None and state['pending'] is None)
            baseline=result.frames[state['baseline']-1]
            rows=[row for row in result.frames if row['label']=='view-ready'];need(len(rows)==1)
            result.components.view_preserved(baseline['world'],rows[0]['world']);result.ui_absent(rows[0])
            web=result.frames[state['webAdmission']-1]['web'];url=state['admission']['marker']['sourceUrl']
            contexts=[row for row in web['contexts'] if row['descriptor']['sourceUrl']==url]
            need(web['iosWebClosureVersion']>=5 and len(contexts)==1 and contexts[0]['descriptor']['surface']=='world-entity'
                and any(counter['created']>0 for counter in contexts[0]['callbacks'].values()))
        return result

    def prepare(self):
        self.bound()
        if self.state['phase']=='ready':return deepcopy(self.state['admission'])
        need(self.state['phase']=='new' and self.files.store.read() is None)
        before=self.capture('baseline');self.components.actual_domain(before['world']);self.ui_absent(before)
        need(before['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
        self.state.update(phase='preparing',baseline=len(self.frames));self.save()
        self.files.reserve_web(self.run,self.fixture_url,self.ticket)
        self.state['fileOwnership']=deepcopy(self.files.owned());self.save()
        self.state['directory']=self.once('stage-marker-files',self.files.stage_reserved);self.save()
        manager=self.manager();self.once('open-marker-manager',manager.open);self.once('open-marker-picker',manager.file_picker_open)
        barrier=self.capture('before-marker-load');self.state['loadBarrier']=barrier['clockJoin']['nativeAfter']['capturedEpochMs'];self.save()
        self.once('load-marker-script',lambda:manager.file_picker_choose('script-bundle/main.js'))
        # Hiding the tablet alone leaves its manager QML root alive. Close the
        # owned page through its ordinary Home control before hiding it.
        self.once('home-marker-manager',lambda:manager.ui.activate('tablet.home'))
        self.once('close-marker-manager',manager.close_tablet)
        after=self.capture('marker-loaded');owned=self.components.admitted(before['world'],after['world'],self.files.owned(),self.state['directory'],after_epoch=self.state['loadBarrier'])
        self.state.update(admission=owned,admissionFrame=len(self.frames));self.save()
        current=self.capture('view-ready',owned['manager'])
        self.components.body_preserved(before['world'],current['world']);self.components.view_preserved(before['world'],current['world']);self.ui_absent(current)
        self.state['phase']='ready';self.save();return deepcopy(owned)
