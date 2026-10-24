"""Historical Navigation validators with permanently unavailable live IO.

An original generation keeps its PID/bridge, files, clocks and ordinary input
records. No newer application is queried through this historical authority.
This is preparation for the explicit v16 restart join, not a live publisher.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.chat_journey.source_chunks import json_digest,ChatSourceChunks
from adapters.native_feature_observation import NativeFeatureObservation,need,exact
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.native_navigation_directory import NativeNavigationDirectory
from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.native_navigation_modals import NativeNavigationModals
from adapters.native_navigation_panels import NativeNavigationPanels
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.navigation_arrival import NavigationArrival
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.navigation_directory import NavigationDirectory
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.navigation_missing import NavigationMissing
from adapters.navigation_origin import NavigationOrigin
from adapters.navigation_stereo import NavigationStereo
from adapters.navigation_transit import NavigationTransit
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_source import PicoGraphicsSource
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_dismissal_join import NavigationDismissalJoin
from adapters.pico4.navigation_lookup import PicoNavigationLookup
from adapters.pico4.navigation_missing_join import NavigationMissingJoin
from adapters.pico4.navigation_prefix import NavigationPrefix
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource
from adapters.pico4.navigation_originals import verify as verify_originals
from adapters.pico4.navigation_transit_join import NavigationTransitJoin
from adapters.pico4.normal_navigation_origin import PicoNavigationOriginIO
from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoHomeSource,PicoTabletHome
from adapters.script_journey.history import same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
from adapters.token_places_ui import TokenPlacesUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.stereo_navigation_evidence import original_name
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_profile


def unavailable(*_args,**_kwargs):
    raise NativeUIError('The original Navigation generation is historical only')


class HistoricalIO(NativeNavigationIO):
    """Configuration for retained decoders, never an Android transport."""
    def __init__(self,identity):
        super().__init__(None,'historical-navigation',identity,unavailable)
    bind_input=guard=read=send=clear_private_input=input=controller=unavailable


class HistoricalSession(PicoOpenXrAdapterSession):
    def __init__(self,profile):
        validate_profile(profile);self.profile=deepcopy(profile)
    begin=is_unbound=require_process_identity=bound_process_identity=stage=unavailable
    require_owned_neutral=observe_owned_status=neutralize_owned=cleanup=discard_local_state=unavailable
    _load=_save=_lock=unavailable


class FrozenHeader(PrivateFeatureState):
    def __init__(self,path,value):
        super().__init__(path);self.value=deepcopy(value);self.digest=json_digest(self.value)
    def read(self):
        need(json_digest(self.value)==self.digest);return deepcopy(self.value)
    write=discard=unavailable


class ReadOnlyOriginal(PrivateFeatureState):
    def __init__(self,path):
        super().__init__(path);value=super().read();need(value is not None)
        self.original_sha=json_digest(value)
    def read(self):
        value=super().read();need(json_digest(value)==self.original_sha);return value
    write=discard=unavailable


def readonly(owner):
    if not isinstance(owner.store,ReadOnlyOriginal):owner.store=ReadOnlyOriginal(owner.store.path)
    owner.save=owner._save=owner.archive_packet=unavailable
    for name in ('act','close','acquire','release','cleanup','restore','select','retire'):
        if callable(getattr(owner,name,None)):setattr(owner,name,unavailable)
    return owner


class NavigationHistory(NavigationPrefix):
    """Reuse the same owner grammars with explicit read-only original scopes.

    The restart owner supplies an independently pinned original scope/header.
    Existing file and PNG validators still read their actual original files.
    Every method capable of obtaining a new client sample or input refuses.
    """
    def __init__(self,scope,header,normal_ui_path,profile,phase,source_lock,*,role,files,monotonic=time.monotonic):
        exact(scope,{'runId','binding','sourceBinding','inputs','providerInstance','origin','profile','fixtureUrl','path','lockPath'})
        binding=context(scope['binding']);need(same(binding,scope['sourceBinding'])
            and isinstance(source_lock,ScriptSourceLock) and isinstance(phase,PhaseFixtureReader)
            and source_lock.path==Path(scope['lockPath']) and role in ('primary','actor')
            and Path(scope['path'])==source_lock.path.with_name('navigation-prefix-owner.json')
            and phase.run==scope['runId'] and phase.area=='world-navigation' and phase.fixture_url==scope['fixtureUrl'])
        source_lock.assert_held();pid=int(binding['processIdentity'].split(':',1)[0]);root=source_lock.path.parent
        normal_ui_path=Path(normal_ui_path)
        need(normal_ui_path.is_absolute() and normal_ui_path.parent in (root,root.parent))
        verify_originals(files,root,scope['runId'],normal_ui_path,source_lock)
        need(same(PrivateFeatureState(scope['path']).read(),header))
        def historical_guard():
            # Ownership of immutable originals, expressly not live process,
            # Qt or resource-presence evidence. Every actual IO stays blocked.
            verify_originals(files,root,scope['runId'],normal_ui_path,source_lock)
            need(same(PrivateFeatureState(scope['path']).read(),header));return True
        # This actual normal navigation decoder can inspect only its old host
        # context. No current UI frame is manufactured to initialize its bridge.
        transport=HistoricalIO(binding['processIdentity'])
        installed=dict(schemaVersion=1,sourceRevision=binding['sourceRevision'],artifactSha256=binding['artifactSha256'],installedCandidateVerified=True)
        navigation=PicoNavigation(transport,normal_ui_path,installed,binding['processIdentity'],scope['inputs']['sceneUrl'])
        ordinary=object.__new__(PicoScriptIO);ordinary.navigation=navigation;ordinary.bridge=binding['sessionId']
        def ui(intent):return TokenPlacesUI(PicoPlacesIO(ordinary),intent,scope['runId'])
        def reader(kind):return kind(unavailable,unavailable,unavailable,unavailable,pid)
        native=reader(NativeFeatureObservation)
        def home():return PicoTabletHome(PicoHomeSource(None,'historical-navigation',native),unavailable)
        environment=reader(NativeNavigationEnvironment);storage=reader(NativeLocationBookmarks)
        directory_source=reader(NativeNavigationDirectory);panels=reader(NativeNavigationPanels)
        modals=reader(NativeNavigationModals);replies=reader(NativeNavigationReplies)
        subject=NativeGraphicsSubject(unavailable,unavailable,unavailable,unavailable,pid,require_framework=True)
        arrival=NavigationArrival(unavailable,subject,unavailable,unavailable,scope['runId'],binding,scope['inputs']['sceneUrl'])
        origin=NavigationOrigin(PicoNavigationOriginIO(ordinary),environment,root/'navigation-prefix-origin.json',
            scope['runId'],binding,unavailable,home=home())
        directory=NavigationDirectory(ui,directory_source,unavailable,root/'navigation-prefix-directory.json',scope['runId'],binding,
            scope['providerInstance'],scope['inputs'],scope['origin'],scope['profile'],unavailable)
        bookmarks=NavigationBookmarks(ui,storage,root/'navigation-prefix-bookmarks.json',scope['runId'],binding)
        source=NavigationPrefixSource(ui(unavailable),arrival,storage,panels,environment,modals,directory_source,unavailable,
            scope['runId'],binding,scope['inputs'],scope['providerInstance'],scope['origin'],scope['profile'],unavailable,unavailable,replies=replies)
        for owner in (origin,directory,bookmarks):readonly(owner)
        self.store=FrozenHeader(scope['path'],header);self.source,self.phase,self.lock=source,phase,source_lock
        self.origin,self.directory,self.bookmarks=origin,directory,bookmarks;self.run,self.binding=scope['runId'],deepcopy(binding)
        self.monotonic=monotonic;self.clock=None;self.role=role;self.role_sha=json_digest(role)
        self.session=HistoricalSession(profile);self.scope_sha=json_digest(scope)
        self.transport=transport;self.home_anchor=self.home_anchor_sha=None
        self.open_ui=ui(unavailable);self.disk=self.state=None
        self.transit_join=self.missing_join=self.dismissal_join=self.bookmark_join=None
        normal=TokenScriptUI(ordinary);graphics=PicoGraphicsSource(None,'historical-navigation',native)
        def transit_factory(parent,*,kind='directory',prior=None):
            stem='navigation-prefix-transit' if kind=='directory' else 'navigation-prefix-bookmark-transit'
            images=root/'navigation-prefix-images'
            def stereo(ticket):
                return readonly(NavigationStereo(arrival,unavailable,images/original_name(self.run,'primary',ticket),images,
                    self.run,binding,source_lock,unavailable,journal_id=ticket))
            transit=NavigationTransit(ui,arrival,directory_source,storage,stereo,root/(stem+'.json'),self.run,binding,
                scope['inputs']['sceneUrl'],unavailable,directory=directory,home=home(),panels=panels,defer_stereo_until_close=True)
            readonly(transit)
            owner=readonly(NavigationTransitJoin(parent,transit,normal,graphics,root/(stem+'-join.json'),kind=kind,prior=prior))
            original_close=owner.close_original
            def close():return readonly(original_close())
            owner.close_original=close;return owner
        def missing_factory(parent):
            lookup=NavigationMissing(lambda intent:PicoNavigationLookup(normal,panels,intent,self.run),arrival,home(),storage,replies,modals,
                unavailable,root/'navigation-prefix-missing.json',self.run,binding,scope['providerInstance'],scope['inputs'],scope['origin'],historical_guard)
            readonly(lookup)
            return readonly(NavigationMissingJoin(parent,lookup,root/'navigation-prefix-missing-join.json'))
        def dismissal_factory(parent):
            child=NavigationErrorDismissal(lambda intent:TokenNavigationErrorUI(PicoNavigationErrorIO(ordinary),intent,self.run),replies,modals,
                unavailable,root/'navigation-prefix-dismissal.json',self.run,binding,scope['providerInstance'],scope['inputs'],scope['origin'],historical_guard)
            readonly(child)
            owner=readonly(NavigationDismissalJoin(parent,parent.missing(),child,normal,graphics,root/'navigation-prefix-dismissal-join.json'))
            original_close=owner.close_original
            def close():return readonly(original_close())
            owner.close_original=close;return owner
        def bookmark_factory(parent):
            return readonly(NavigationBookmarkJoin(parent,lambda prior:transit_factory(parent,kind='bookmark',prior=prior),root/'navigation-prefix-bookmark-join.json'))
        self.transit_factory,self.missing_factory,self.dismissal_factory,self.bookmark_factory=transit_factory,missing_factory,dismissal_factory,bookmark_factory
        self.load()
        need(self.state['phase']=='ready' and len(self.state['completed'])==11 and self.state['completed'][-1]['verb']=='bookmark-visit')
        for owner in (self.transit(),self.missing(),self.dismiss(),self.bookmark_visit()):owner.validate(owner.state)
        self.validate_roles()
        need(self.transit_join.state['phase']==self.dismissal_join.state['phase']==self.bookmark_join.state['phase']=='closed'
            and self.missing_join.state['phase']=='visible')
        verify_originals(files,root,self.run,normal_ui_path,source_lock)

    def validate_roles(self):
        for role in ('primary','actor'):
            store=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-'+role+'-sources.json'));body=store.read()
            exact(body,{'navigationPrefixSamplesVersion','runId','binding','role','phase','chunks'})
            need(type(body['navigationPrefixSamplesVersion']) is int and body['navigationPrefixSamplesVersion']==1
                and body['runId']==self.run and same(body['binding'],self.binding) and body['role']==role and body['phase']=='ready')
            chunks=ChatSourceChunks(store,dict(runId=self.run,binding=self.binding,role=role));frames=chunks.load(body['chunks'])
            need(frames)
            for index,frame in enumerate(frames):
                self.source.project(frame);self.original_facts(frame)
                if index:self.source.advance_frames(frames[index-1],frame)
            need(same(frames[-1]['phase']['activations'],self.state['fixture']['activations'])
                and self.source.project(frames[-1])['location']=='A')
            tickets={frame['phase']['activations'][-1]['ticket'] for frame in frames}
            need(all(row['ticket'] in tickets for row in self.state['completed']));chunks.verify()

    prepare=act=observe=fence=save=home_stage=admit_qml=before_controller=controller_stage_intent=controller_before_publish=unavailable
