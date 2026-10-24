"""Explicit restart lineage on the existing normal Pico runtime and SDK.

The historical generation never constructs a current Qt reader. A successor
uses separate host UI context files and the same original source classes; no
source is copied, re-timed or promoted from a restart acknowledgement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path

from adapters.android_process_query import AndroidProcessQuery
from adapters.native_feature_observation import need,exact
from adapters.navigation_arrival import NavigationArrival
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import normal_scripts
from adapters.pico4.navigation_continuation import NavigationContinuation
from adapters.pico4.navigation_history import NavigationHistory
from adapters.pico4.navigation_originals import verify as verify_originals
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource
from adapters.pico4.navigation_restart import NavigationRestart
from adapters.pico4.navigation_restart_input import issue_once
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.script_journey.history import same,unpack
from adapters.token_places_ui import TokenPlacesUI


def runtime(adapter,target,parent,inputs,state,*,input_owner=None):
    """New actual process, ordinary bridge, native/pose/UI/provider originals."""
    parent.lock.assert_held();plan=inputs.read();need(plan['phase'] in ('launch-issued','observed'))
    old=plan['oldBinding'];installed=adapter._installation(target)
    need(all(installed[key]==old[key] for key in ('sourceRevision','artifactSha256'))
        and hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest()==old['targetFingerprint'])
    identity=adapter.require_controlled_debug_identity(target)
    need(identity!=old['processIdentity'] and adapter.require_pico_session_identity(target)==identity)
    scene=normal_scripts.configuration(os.environ);need(scene==parent.source.inputs['sceneUrl'])
    path=parent.lock.path.with_name('navigation-prefix-generation-1-'+parent.role+'-ui.json')
    def no_input(*_args,**_kwargs):need(False)
    normal,_observe,binding=normal_scripts.runtime(adapter,target,scene,installed,identity,path,no_input)
    if input_owner is None:
        # Action 12 observes startup only. Later ordinary inputs require their
        # explicit G1 owner; none can be delivered by this read-only runtime.
        normal.io.navigation.io.bind_before_send(no_input)
        normal.io.navigation.io.bind_controller_admission(no_input,intent=no_input,before_publish=no_input)
    else:
        from adapters.pico4.navigation_generation_flow import NavigationGenerationFlow
        need(isinstance(input_owner,NavigationGenerationFlow) and input_owner.parent is parent
            and input_owner.restart.inputs is inputs and parent.role=='primary'
            and same(input_owner.binding,binding))
        input_owner.memory_control()
        normal.io.navigation.io.bind_before_send(input_owner.qml_callback)
        normal.io.navigation.io.bind_controller_admission(input_owner.controller_callback,
            intent=input_owner.intent_callback,before_publish=input_owner.publish_callback)
    need(all(binding[key]==old[key] for key in ('sourceRevision','artifactSha256','targetFingerprint'))
        and binding['sessionId']!=old['sessionId'])
    if plan['phase']=='observed':need(same(binding,plan['newBinding']))
    native=adapter._native_feature_observer(target)
    need(native.pid==int(identity.split(':',1)[0]))
    def guard():parent.lock.assert_held();native.guard();need(adapter._installation(target)==installed)
    def probe(after):
        guard();value=adapter.read_probe_snapshot(target,'org.overte.pico',after);guard();return value
    arrival=NavigationArrival(probe,adapter._graphics_subject_observer(target),native.clock_ms,guard,parent.run,binding,scene,monotonic=native.monotonic)
    source=NavigationPrefixSource(TokenPlacesUI(PicoPlacesIO(normal.io),no_input,parent.run,monotonic=native.monotonic,sleep=native.sleep),
        arrival,adapter._location_bookmarks(target),adapter._navigation_panels(target),adapter._navigation_environment(target),
        adapter._navigation_modals(target),adapter._navigation_directory_source(target),parent.source.status,
        parent.run,binding,parent.source.inputs,parent.source.provider_instance,parent.source.origin,parent.source.profile,
        native.clock_ms,guard,replies=adapter._navigation_replies(target))
    return dict(source=source,native=native,presence=adapter._process_presence(target),session=adapter.pico_input_session(target))


def compose(adapter,target,parent):
    """Attach the specific boundary ledger without rewriting the old prefix."""
    need(adapter.pico_configuration is not None
        and hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest()==parent.binding['targetFingerprint'])
    def factory(original):
        holder={}
        def candidate_guard(_plan):
            original.lock.assert_held();adapter.require(target)
            installed=adapter._installation(target)
            need(all(installed[key]==original.binding[key] for key in ('sourceRevision','artifactSha256'))
                and hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest()==original.binding['targetFingerprint'])
            return True
        def stopped():
            candidate_guard(None)
            old=original.binding['processIdentity'];query=AndroidProcessQuery(adapter.adb,'org.overte.pico',lambda:candidate_guard(None))
            packet=query.read(target,int(old.split(':',1)[0]))
            return dict(running=bool(packet['processIds']),identity=old if packet['processIds'] else None)
        store=PrivateFeatureState(original.lock.path.with_name('navigation-prefix-restart.json'))
        owner=NavigationRestart(original,store,
            # Historical IO is permanently unavailable. Already-issued cold
            # phases use the retained actual old packet, never read it again.
            None if isinstance(original,NavigationHistory) or store.read() is not None else adapter._native_feature_observer(target),
            outside_guard=candidate_guard,
            stop=lambda _fence:issue_once(adapter,target,'app.stop',holder['owner']),stopped=stopped,
            launch=lambda _fence:issue_once(adapter,target,'app.launch',holder['owner']),
            rebind=lambda inputs,authority:adapter._script_restart_recover_binding(target,restart_inputs=inputs,owner_check=authority),
            successor=lambda inputs,state:runtime(adapter,target,original,inputs,state))
        holder['owner']=owner;return owner
    def generation_factory(continuation):
        from adapters.navigation_bookmarks import NavigationBookmarks
        from adapters.navigation_bookmark_restart import adopt_restart
        from adapters.navigation_directory import NavigationDirectory
        from adapters.pico4.navigation_generation_flow import NavigationGenerationFlow
        from adapters.pico4.navigation_generation_open import NavigationGenerationOpen
        from adapters.pico4.navigation_generation_close import NavigationGenerationClose
        from adapters.pico4.tablet_home import bind_home
        def current(flow):
            return runtime(adapter,target,parent,flow.restart.inputs,flow.restart.state,
                input_owner=flow if parent.role=='primary' else None)
        def bookmark_factory(flow,adopt):
            source=flow.source();native=flow.runtime['native']
            def ui(intent):return TokenPlacesUI(source.normal.io,intent,flow.run,monotonic=native.monotonic,sleep=native.sleep)
            path=flow.lock.path.with_name('navigation-prefix-generation-1-bookmarks.json')
            if not adopt:
                need(PrivateFeatureState(path).read() is not None)
                return NavigationBookmarks(ui,source.readers['bookmarks'],path,flow.run,flow.binding,
                    monotonic=native.monotonic,sleep=native.sleep)
            # Reuse the actual shared proof transfer, with this already owned
            # new-process IO. The global G0 Script manager is never rebound.
            flow.fence()
            owner=adopt_restart(flow.restart.inputs,parent.bookmarks.store,PrivateFeatureState(path),
                flow.restart.state['oldNative'],flow.restart.state['oldBookmark'],ui,native,flow.runtime['presence'],
                source.readers['bookmarks'],flow.binding,flow.run,parent.phase,flow.lock)
            flow.adopted=owner;flow.fence();return owner
        def open_factory(flow):
            source=flow.source();native=flow.runtime['native']
            directory=NavigationDirectory(lambda intent:TokenPlacesUI(source.normal.io,intent,flow.run,
                monotonic=native.monotonic,sleep=native.sleep),source.readers['directory'],source.status,
                flow.lock.path.with_name('navigation-prefix-generation-1-directory.json'),flow.run,flow.binding,
                source.provider_instance,source.inputs,source.origin,source.profile,flow.fence,
                monotonic=native.monotonic,sleep=native.sleep)
            return NavigationGenerationOpen(flow,directory,bind_home(adapter,target,native),adapter._graphics_ui_observer(target),
                lambda:bookmark_factory(flow,True))
        def close_factory(flow):
            return NavigationGenerationClose(flow,bind_home(adapter,target,flow.runtime['native']),adapter._graphics_ui_observer(target))
        return NavigationGenerationFlow(continuation,current,open_factory,close_factory,bookmark_factory)
    return NavigationContinuation(parent,factory,generation_factory=generation_factory)


def history(root,run,phase,lock,*,role,status,provider_instance,inputs,origin,profile):
    """Cold admission before any normal live-runtime constructor or SDK read."""
    lock.assert_held();root=Path(root)
    disk=PrivateFeatureState(root/'navigation-prefix-restart.json').read()
    continuation=PrivateFeatureState(root/'navigation-prefix-restart-parent.json').read()
    if disk is None:
        # A parent intent without a complete predecessor capture is unresolved;
        # discovering a current app cannot manufacture its old runtime.
        need(continuation is None);return None
    exact(disk,{'navigationRestartVersion','runId','binding','parentScopeSha256','payload'})
    need(type(disk['navigationRestartVersion']) is int and disk['navigationRestartVersion']==1 and disk['runId']==run
        and continuation is not None)
    rows=unpack(disk['payload']);need(len(rows)==1);value=rows[0];scope=value['scope']
    need(scope['runId']==run and scope['fixtureUrl']==phase.fixture_url and scope['lockPath']==str(lock.path)
        and scope['path']==str(root/'navigation-prefix-owner.json') and same(scope['inputs'],inputs)
        and scope['providerInstance']==provider_instance and scope['origin']==origin and same(scope['profile'],profile))
    verify_originals(value['files'],root,run,value['normalUiPath'],lock)
    parent=NavigationHistory(scope,value['prefix'],value['normalUiPath'],value['profile'],phase,lock,role=role,files=value['files'],monotonic=phase.monotonic)
    # The new controlled provider is still the same independent fixture/source
    # channel. Historical frame validation never calls this live function.
    parent.source.status=status
    return parent
