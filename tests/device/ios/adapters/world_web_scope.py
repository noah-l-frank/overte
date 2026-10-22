"""World-only ordinary Script setup with original camera preservation.

The Web Entity is placed by its normal Script using the actual current Camera.
The normal lifecycle owner keeps that camera instead of selecting look-at.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.original_marker_scope import OriginalMarkerScope
from ios.adapters.world_web_resource_disposition import disposition


class IOSWorldWebScope(OriginalMarkerScope):
    PROFILE='worldweb'

    def envelope(self,state):
        value=super().envelope(state);value[self.components.scope_key]=getattr(self,'_scope_version',2);return value

    def decode(self,value):
        version=value.get(self.components.scope_key);need(type(version) is int and version in (1,2))
        self._scope_version=version;return super().decode(value)

    def quiet_web(self,current,admitted,*,partial=False):
        if getattr(self,'_scope_version',2)==1:return super().quiet_web(current,admitted,partial=partial)
        # Version 2 qualifies only ordinary-input/files/worker quiet. It does
        # not claim a cached QML root, original QImage or GPU holder died.
        return disposition(current['web'],admitted['web'],partial=partial or self.state['cleanupMode'] in ('partial-execution','finished-execution','unloaded'))

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
        if self.state['phase']=='ready':
            self.archive(self.previous,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
            return deepcopy(self.state['admission'])
        need(self.state['phase'] in ('new','preparing'))
        if self.state['phase']=='new':
            need(self.files.store.read() is None)
            before=self.capture('baseline');self.components.actual_domain(before['world']);self.ui_absent(before)
            need(before['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
            self.state.update(phase='preparing',baseline=len(self.frames));self.save()
        before=self.frames[self.state['baseline']-1]
        if self.state['fileOwnership'] is None:
            # A reserve whose durable write returned uncertain remains the
            # same actual file owner. It is never replaced with a new nonce.
            if self.files.store.read() is None:self.files.reserve_web(self.run,self.fixture_url,self.ticket)
            self.state['fileOwnership']=deepcopy(self.files.owned());self.save()
        need(self.state['fileOwnership']==self.files.owned())
        if self.state['directory'] is None:
            self.state['directory']=self.once('stage-marker-files',self.files.stage_reserved);self.save()
        manager=self.manager();self.once('open-marker-manager',manager.open);self.once('open-marker-picker',manager.file_picker_open)
        if self.state['loadBarrier'] is None:
            need(not any(row['label']=='load-marker-script' for row in self.state['operations']))
            barrier=self.capture('before-marker-load');self.state['loadBarrier']=barrier['clockJoin']['nativeAfter']['capturedEpochMs'];self.save()
        self.once('load-marker-script',lambda:manager.file_picker_choose('script-bundle/main.js'))
        # Hiding the tablet alone leaves its manager QML root alive. Close the
        # owned page through its ordinary Home control before hiding it.
        self.once('home-marker-manager',lambda:manager.ui.activate('tablet.home'))
        self.once('close-marker-manager',manager.close_tablet)
        loaded=[frame for frame in self.frames if frame['label']=='marker-loaded'];need(len(loaded)<=1)
        after=loaded[0] if loaded else self.capture('marker-loaded')
        owned=self.components.admitted(before['world'],after['world'],self.files.owned(),self.state['directory'],after_epoch=self.state['loadBarrier'])
        self.state.update(admission=owned,admissionFrame=self.frames.index(after)+1);self.save()
        ready=[frame for frame in self.frames if frame['label']=='view-ready'];need(len(ready)<=1)
        current=ready[0] if ready else self.capture('view-ready',owned['manager'])
        self.components.body_preserved(before['world'],current['world']);self.components.view_preserved(before['world'],current['world']);self.ui_absent(current)
        self.state['phase']='ready';self.save();return deepcopy(owned)
