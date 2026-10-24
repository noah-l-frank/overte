"""Fully decode a frozen pair of current rooted ownership metadata snapshots.

Metadata comes only from exact supplied copies; native/source/peer/image and
publication originals are independently reopened at their original paths. No
runtime, SDK, native transport, phase query or metadata deletion is available.
This graph proves retained responsibility, not process death or final success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_final_inputs import validate as fixed_inputs
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_archive import reopen,capture
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_gpu import validate as gpu
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_rooted_responsibility import IOSEmoteRootedResponsibility
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_samples import IOSEmoteSamples
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.graphics_configuration import settings
from ios.adapters.peer_admission import validate as admitted


def metadata_paths(window,responsibilities):
    """Exact mutable owners reached by the already checked paired live cut."""
    need(type(window) is IOSEmoteTerminalWindow and type(responsibilities) is list and len(responsibilities)==2)
    by_role={item.flow.role:item for item in responsibilities};exact(by_role,{'primary','actor'})
    paths=set()
    for role,live in window.roles.items():
        responsibility=by_role[role];flow=responsibility.flow;responsibility.guard()
        need(live.owner is not None and flow.lock is live.lock and flow.primary_lock is live.primary_lock)
        owner=live.owner;snapshot=capture(owner,flow.state['cleanup'][-1]);rendered=owner.rendered_owner
        native=rendered.native_owner;rendered_ref=owner.original(snapshot['reference'])['renderedReference']
        raw=native.original(rendered.original(rendered_ref)['nativeReference'])
        paths.update(Path(path) for path in snapshot['paths'].values())
        paths.update(path for path in native.paths.values() if path is not None)
        paths.update(Path(path) for path in responsibility.values)
        paths.update((flow.store.path,live.store.path))
        for tail in ('marker','samples','observer','marker-files','marker-script'):
            paths.add(flow.store.path.with_name('ios-emote-'+role+'-'+tail+'.json'))
        if role=='primary':
            for tail in ('cleanup-inputs','inputs','background'):paths.add(flow.store.path.with_name('ios-emote-'+tail+'.json'))
        need(same(raw['scope'],PrivateFeatureState(flow.store.path.with_name('ios-emote-'+role+'-marker.json')).read()))
    return [PrivateFeatureState(path) for path in sorted(paths)]


class IOSEmoteRootedState:
    def __init__(self,copies,*,run,lock,actor_lock):
        need(type(copies) is dict and 1<=len(copies)<=256 and isinstance(lock,ScriptSourceLock)
            and isinstance(actor_lock,ScriptSourceLock) and lock.path!=actor_lock.path)
        lock.assert_held();actor_lock.assert_held()
        self.copies=deepcopy(copies);self.run=identifier(run);self.locks=dict(primary=lock,actor=actor_lock);self.used=set()
        for path,value in self.copies.items():
            need(type(path) is str and Path(path).is_absolute() and Path(path).resolve()==Path(path)
                and (value is None or type(value) is dict))
        self.runtime=SimpleNamespace(state_path=lambda role:self.locks[role].path.with_name('session.json'))

    def store(self,path):
        path=Path(path);key=str(path);need(key in self.copies);self.used.add(key)
        return Frozen(path,self.copies[key])

    def role(self,role):
        lock=self.locks[role];primary_lock=self.locks['primary']
        feature_store=self.store(lock.path.with_name('ios-emote-'+role+'-feature.json'));value=feature_store.read()
        exact(value,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
        need(type(value['iosEmoteFeatureVersion']) is int and value['iosEmoteFeatureVersion']==2
            and value['runId']==self.run and value['role']==role)
        policy=settings(dict(artifactRoot=value['artifactRoot'],imagePolicy=value['imagePolicy']))
        root=Path(policy['artifactRoot']);flow=object.__new__(IOSEmoteRootedFeature)
        flow.run,flow.role,flow.root,flow.policy=self.run,role,root,policy['imagePolicy']
        flow.lock,flow.primary_lock,flow.store=lock,primary_lock,feature_store
        flow.phase=SimpleNamespace(fixture_url=value['fixtureUrl']);flow.runtime=self.runtime
        flow.selector,flow.primary_selector=role,'primary';flow.load()
        need(flow.state['phase']=='cleaned' and flow.state['cleanup'])
        suffix='/runs/'+self.run+'/';need(value['fixtureUrl'].endswith(suffix))
        flow.client=SimpleNamespace(url=value['fixtureUrl'][:-len(suffix)])
        live_store=self.store(lock.path.with_name('ios-emote-'+role+'-'+self.run+'-terminal-live.json'))
        live=IOSEmoteRootedLive.archive(live_store.read(),store=live_store,lock=lock,primary_lock=primary_lock)
        need(live.state['pending'] is None and live.state['records'] and live.run==self.run and live.role==role
            and live.root==root and same(live.binding,flow.state['binding'])
            and same(live.primary_binding,flow.state['primaryBinding']) and same(live.policy,flow.policy)
            and live.fixture_url==flow.phase.fixture_url and live.phase_instance==flow.state['phaseInstance'])
        snapshot=live.read_frame(live.state['records'][-1])['snapshot']
        need(same(snapshot['reference'],flow.state['cleanup'][-1]))
        for name,path in snapshot['paths'].items():need(same(self.store(path).read(),snapshot['owners'][name]))
        historical=reopen(snapshot,lock=lock,primary_lock=primary_lock)
        owner=IOSEmoteRootedKeyedRetirement(self.store(snapshot['paths']['keyed']),historical.rendered_owner,historical.keys_owner)
        rendered=owner.rendered_owner;native=rendered.native_owner
        rendered_ref=owner.original(snapshot['reference'])['renderedReference']
        raw=native.original(rendered.original(rendered_ref)['nativeReference'])
        sources,peers,_decoder=native.owners(raw)
        for name,field in (('sources','sources'),('peers','peers'),('files','fileReceipts'),('entities','entities'),('pointers','pointers')):
            if native.paths[name] is not None:need(same(self.store(native.paths[name]).read(),raw[field]))
        scope_store=self.store(lock.path.with_name('ios-emote-'+role+'-marker.json'));need(same(scope_store.read(),raw['scope']))
        scope=IOSEmoteRootedMarkerScope.archive(scope_store.read(),root=root,binding=owner.binding,run=self.run,role=role,lock=lock)
        samples=object.__new__(IOSEmoteSamples)
        samples.root,samples.binding,samples.run,samples.role,samples.policy,samples.lock=root,owner.binding,self.run,role,owner.policy,lock
        samples.store=self.store(lock.path.with_name('ios-emote-'+role+'-samples.json'));need(same(samples.store.read(),raw['sampleOwners']))
        samples.state=samples.decode(samples.store.read());need(samples.state['phase']=='ready')
        observer=object.__new__(IOSEmoteRootedObserver)
        observer.root,observer.binding,observer.run,observer.role=root,owner.binding,self.run,role
        observer.sources,observer.peers,observer.samples,observer.policy,observer.lock=sources,peers,samples,owner.policy,lock
        observer.phase=SimpleNamespace(fixture_url=owner.fixture_url,previous=dict(instance=owner.phase_instance))
        observer.state=observer.decode(self.store(lock.path.with_name('ios-emote-'+role+'-observer.json')).read())
        need(observer.state['pending'] is None and observer.state['records']
            and same(observer.original(observer.state['records'][-1]),raw['observation']))
        responsibility=object.__new__(IOSEmoteRootedResponsibility);responsibility.flow=flow;responsibility.store_for=self.store
        fixed_inputs(responsibility,self.copies,raw)
        # Fixed-input validation indexes its supplied map directly. Record its
        # exact known metadata through the same closed store boundary as well.
        for tail in ('marker-files','marker-script'):self.store(lock.path.with_name('ios-emote-'+role+'-'+tail+'.json'))
        if role=='primary':
            for tail in ('cleanup-inputs','inputs','background'):self.store(lock.path.with_name('ios-emote-'+tail+'.json'))
        parts=dict(sources=sources,peers=peers,scope=scope,samples=samples,observer=observer,restoration=rendered.frames_owner)
        values=responsibility.metadata();responsibility.validate(values,parts,owner,live);gpu(flow,parts,store_for=self.store)
        return flow,live

    def read(self):
        self.used=set()
        roots={lock.path.parent for lock in self.locks.values()}
        for role,lock in self.locks.items():
            feature=self.copies.get(str(lock.path.with_name('ios-emote-'+role+'-feature.json')))
            need(type(feature) is dict and type(feature.get('artifactRoot')) is str)
            roots.add(Path(feature['artifactRoot']))
        leases=[EmoteOriginalLease(root,[]) for root in roots]
        roles={role:self.role(role) for role in ('primary','actor')}
        p,a=roles['primary'][0],roles['actor'][0]
        need(p.root!=a.root and p.phase.fixture_url==a.phase.fixture_url and p.state['phaseInstance']==a.state['phaseInstance']
            and same(admitted(p.state['actorAdmission'],p.state['binding']),a.state['binding'])
            and same(a.state['primaryBinding'],p.state['binding']))
        need(self.used==set(self.copies))
        for lease in leases:lease.guard()
        return IOSEmoteTerminalWindow(roles['primary'][1],roles['actor'][1])
