"""Fresh passive G1 stereo on the actual completed normal Close lineage.

The completed Close stays physically immutable. Its exact historical baseline
is explicitly linked to a separate typed observation continuation; copying that
baseline grants no new input, sampling epoch, controller or quiet-window proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import exact,need
from adapters.navigation_frames import NavigationFrames
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.navigation_generation_page import NavigationGenerationPage
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_originals import read_original
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import same
from adapters.token_script_ui import TokenScriptUI

VERSION=1


def no_input(*_args,**_kwargs):need(False)


class ReadOnlyScriptIO(PicoScriptIO):
    activate=replace=submit=select_index=tablet=release=no_input


class ReadOnlyHome(PicoTabletHome):
    ensure=no_input


class NavigationFrameClose(NavigationTabletClose):
    close=no_input


class NavigationGenerationFrames:
    def __init__(self,parent,factory,artifact_root):
        from adapters.pico4.navigation_generation_flow import NavigationGenerationFlow
        need(isinstance(parent,NavigationGenerationFlow) and callable(factory))
        self.parent,self.factory=parent,factory;self.root=Path(artifact_root)
        self.role=parent.parent.role;self.lock=parent.lock
        need(self.root==parent.lock.path.with_name('navigation-prefix-generation-1-'+self.role+'-images'))
        self.link=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-'+self.role+'-frame-close-link.json'))
        self.close_path=self.link.path.with_name('navigation-prefix-generation-1-'+self.role+'-frame-close.json')
        self.frames_path=self.link.path.with_name('navigation-prefix-generation-1-'+self.role+'-frames.json')
        self.status_store=PrivateFeatureState(self.link.path.with_name('navigation-prefix-generation-1-'+self.role+'-frame-statuses.json'))
        self.closed=self.frames=None;self.pins=None;self.link_pin=None
        self.namespace=(self.role,self.root,self.link.path,self.close_path,self.frames_path,self.status_store.path)

    def control(self):
        p=self.parent;p.fence()
        need(self.namespace==(self.role,self.root,self.link.path,self.close_path,self.frames_path,self.status_store.path))
        need(p.state is not None and p.state['phase']=='ready' and p.state['active'] is None
            and [row['verb'] for row in p.state['completed']]==['open','bookmark-delete','close'])
        p.validate_links(p.state)
        if self.pins is not None:
            need(same(self.originals(),self.pins))
        if self.link_pin is not None:need(same(read_original(self.link.path),self.link_pin))
        return True

    def originals(self):
        return [read_original(self.lock.path.with_name('navigation-prefix-generation-1-'+name+'.json'))
            for name in ('close-join','tablet-close')]

    def prepare(self):
        self.control();p=self.parent
        if p.close_owner is None:p.close_owner=p.close_factory(p)
        original=p.close_owner.close_owner()
        need(original.state['phase']=='closed' and original.state['quiet'])
        pins=self.originals();need(all(row['present'] for row in pins))
        expected=dict(navigationGenerationFrameCloseVersion=VERSION,scope=p.scope(),role=self.role,
            artifactRoot=str(self.root),originals=pins,original=deepcopy(original.disk),
            continuationPath=str(self.close_path),framesPath=str(self.frames_path),statusPath=str(self.status_store.path))
        body=self.link.read()
        if body is None:
            # An orphan continuation is unresolved ownership, never an implicit
            # permission to adopt, overwrite, restart or repeat a Close.
            need(self.close_path.exists() is False and self.frames_path.exists() is False)
            try:self.root.mkdir(mode=0o700)
            except FileExistsError:pass
            PrivateFeatureState(self.root/'boundary.json')._parent();need(not any(self.root.iterdir()))
            self.link.write(expected,None);body=expected
        exact(body,set(expected));need(same(body,expected));self.pins=deepcopy(pins);self.link_pin=read_original(self.link.path)
        if self.close_path.exists() is False:
            # A link without its next CAS is an unresolved original operation.
            # Only the owner that just created this link may seed its baseline.
            need(body is expected);self.control()
            PrivateFeatureState(self.close_path).write(original.disk,None)
        home=ReadOnlyHome(original.transit.home.source,no_input)
        page=NavigationGenerationPage(p,home,original.transit.before,original.transit.after,
            before_sample=self.quiet_status)
        normal=TokenScriptUI(ReadOnlyScriptIO(page.navigation),monotonic=p.runtime['native'].monotonic,sleep=p.runtime['native'].sleep)
        self.closed=NavigationFrameClose(page,normal,original.graphics,self.close_path,self.control,
            monotonic=p.parent.monotonic,sleep=p.runtime['native'].sleep)
        self.baseline(original)
        frames=self.factory(p,self.closed,self.frames_path,self.root,self.role)
        need(isinstance(frames,NavigationFrames) and frames.closed is self.closed and frames.role==self.role
            and frames.binding==p.binding and frames.run==p.run and frames.root==self.root and frames.store.path==self.frames_path)
        self.frames=frames;self.control()

    def statuses(self):
        p=self.parent;scope=dict(scope=p.scope(),role=self.role,originals=self.pins)
        body=self.status_store.read();chunks=ChatSourceChunks(self.status_store,scope)
        manifest=[] if body is None else body['chunks']
        rows=chunks.load(manifest)
        if body is not None:
            exact(body,{'navigationGenerationFrameStatusesVersion','scope','phase','chunks'})
            need(type(body['navigationGenerationFrameStatusesVersion']) is int and body['navigationGenerationFrameStatusesVersion']==VERSION
                and same(body['scope'],scope) and body['phase']=='ready')
        envelope=p.close_owner.state['controller']['envelope'];previous=None
        for row in rows:
            exact(row,{'status','hostMonotonic'})
            need(NavigationBookmarkJoin.neutral(row['status'],envelope)
                and (previous is None or row['hostMonotonic']>=previous));previous=row['hostMonotonic']
        return body,chunks,scope,manifest

    def quiet_status(self):
        self.control();p=self.parent;body,chunks,scope,manifest=self.statuses()
        reading=dict(navigationGenerationFrameStatusesVersion=VERSION,scope=scope,phase='reading',chunks=manifest)
        self.status_store.write(reading,body)
        envelope=p.close_owner.state['controller']['envelope']
        answer=p.runtime['session'].observe_owned_status(p.binding['processIdentity'],envelope)
        manifest=chunks.append(dict(status=deepcopy(answer),hostMonotonic=p.parent.now()),manifest)
        ready=deepcopy(reading);ready.update(phase='ready',chunks=manifest);self.status_store.write(ready,reading)
        chunks.verify();self.control();need(NavigationBookmarkJoin.neutral(answer,envelope))

    def baseline(self,original):
        self.control();old,new=original.state,self.closed.state
        need(new is not None and new['phase']=='closed' and new['ticket']==old['ticket']
            and same(new['before'],old['before']) and same(new['quiet'],old['quiet'])
            and new['queries'][:len(old['queries'])]==old['queries'] and self.closed.origin==original.origin)
        if not same(new['last'],old['last']):self.closed.advance(old['last'],new['last'])

    def evidence(self):
        paths=[self.link.path,self.close_path,self.frames_path]
        body,chunks,_scope,manifest=self.statuses()
        need(body is not None);paths.append(self.status_store.path)
        paths.extend(chunks._path(index) for index in range(len(manifest)))
        paths.extend(self.root/row['name'] for record in self.frames.state['records']
            for row in self.frames.owner(record['journalId']).artifacts(record['sequence']))
        need(len(set(paths))==len(paths))
        need(set(self.root.iterdir())=={path for path in paths if path.parent==self.root})
        return [read_original(path) for path in paths]

    def read(self,after_sequence):
        p=self.parent;need(self.lock._owner is None)
        with self.lock.held():
            self.prepare();runtime=p.runtime;started=p.parent.now();requested=runtime['native'].clock_ms()
            ticket=p.state['completed'][-1]['ticket'];answer=self.frames.read(ticket,after_sequence)
            self.control();self.baseline(p.close_owner.close_owner())
            guards=(runtime['source'].guard,runtime['native'].guard);pins=p.pin_current(runtime)
            evidence=self.evidence();captured=answer['capturedEpochMs']
        # No fresh query, new source or retiming after the actual outer exit.
        p.finalize(runtime,requested,started,captured,guards,pins)
        need(same(self.originals(),self.pins)
            and same([read_original(row['path']) for row in evidence],evidence))
        p.finalize(runtime,requested,started,captured,guards,pins)
        return answer
