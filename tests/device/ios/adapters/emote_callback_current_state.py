"""Current copied ownership around an actual Callback Archive2/Scene4 cut.

No journal, broker, native request or result timestamp is created here. The
existing Live2 consumer uses this typed State/GPU join before its actual save.
Historical Sample3 duty remains pending; its separate original Drain4 carrier
must prove the later released owner before current metadata can match it.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.native_vulkan_world_frame import absent
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same,unpack
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_archive_round import scope as original_round
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackRetirementObserver
from ios.adapters import emote_callback_archive as archive
from ios.adapters import emote_callback_drain_originals as drains


def graph(snapshot,*,lock,primary_lock):
    keyed=archive.reopen(snapshot,lock=lock,primary_lock=primary_lock)
    rendered=keyed.rendered_owner;native=rendered.native_owner
    r=rendered.original(keyed.original(snapshot['reference'])['renderedReference'])
    raw=native.original(r['nativeReference'])
    sources,peers,_decoder=native.owners(raw)
    return keyed,raw,sources,peers


def selected_parents(keyed,raw,scope,samples):
    """Use actual Drain4 owner originals, never rewrite old Sample3 payloads."""
    original=raw['sampleOwners'];store=drains.store(keyed.root,keyed.binding,keyed.run,keyed.role,keyed.lock)
    need(same(original['samples'],samples.store.read()) and len(original['current'])==len(samples.state['rows']))
    parents={}
    for row,reference in zip(samples.state['rows'],original['current']):
        frame=drains.read_frame(store,reference)
        need(frame['kind']=='owner' and same(frame['row'],row))
        sample=samples.record(row);drains.sample_owner(frame['owner'],sample,keyed.root,keyed.binding,keyed.run,keyed.role,keyed.lock)
        need(row['requestId'] not in parents);parents[row['requestId']]=deepcopy(frame['owner'])
    frames=keyed.rendered_owner.frames_owner
    for reference in frames.state['records']:
        original=frames.original(reference);owners=unpack(original['owner']);need(len(owners)==1)
        request=original['requestId'];need(request not in parents);parents[request]=owners[0]
    return parents


def metadata_paths(keyed,raw,parents):
    native=keyed.rendered_owner.native_owner
    paths={part.store.path for part in (keyed,keyed.rendered_owner,native,keyed.rendered_owner.frames_owner,keyed.keys_owner)}
    paths.update(path for path in native.paths.values() if path is not None)
    paths.update(keyed.lock.path.with_name('ios-emote-'+keyed.role+'-'+tail+'.json') for tail in ('marker','samples','observer'))
    paths.update(keyed.lock.path.with_name('graphics-world-frame-'+keyed.role+'-0-'+request[4:]+'.json') for request in parents)
    need(len(paths)<=256)
    return paths


class CallbackCurrentState:
    """Same closed copied-store boundary as the existing rooted State reader."""
    def __init__(self,snapshot,copies,*,lock,primary_lock):
        need(type(copies) is dict and 1<=len(copies)<=256)
        self.snapshot,self.copies=deepcopy(snapshot),deepcopy(copies)
        self.lock,self.primary_lock,self.used=lock,primary_lock,set()
        for path,value in self.copies.items():
            need(type(path) is str and Path(path).is_absolute() and Path(path).resolve()==Path(path)
                and (value is None or type(value) is dict))

    def store(self,path):
        path=Path(path);key=str(path);need(key in self.copies);self.used.add(key)
        return Frozen(path,self.copies[key])

    def read(self):
        roots=[Path(self.snapshot['artifactRoot']),self.lock.path.parent,self.primary_lock.path.parent]
        return drains.checked_read(roots,self._read)

    def _read(self):
        with original_round(self.snapshot,lock=self.lock,primary_lock=self.primary_lock):
            keyed,raw,sources,peers=graph(self.snapshot,lock=self.lock,primary_lock=self.primary_lock)
            self.used=set();native=keyed.rendered_owner.native_owner;root,role,run=keyed.root,keyed.role,keyed.run
            for name,path in self.snapshot['paths'].items():need(same(self.store(path).read(),self.snapshot['owners'][name]))
            for name,field in (('sources','sources'),('peers','peers'),('files','fileReceipts'),('entities','entities'),('pointers','pointers')):
                if native.paths[name] is not None:need(same(self.store(native.paths[name]).read(),raw[field]))
            scope_store=self.store(self.lock.path.with_name('ios-emote-'+role+'-marker.json'))
            need(same(scope_store.read(),raw['scope']))
            scope=drains.projection(raw['sampleOwners'],root=root,binding=keyed.binding,run=run,role=role,lock=self.lock,policy=keyed.policy)
            need(same(scope.envelope(scope.state),raw['scope']))
            samples_store=self.store(self.lock.path.with_name('ios-emote-'+role+'-samples.json'))
            # These are distinct original DTOs. Do not compare Projection4 to
            # Samples3 or turn the historical sample's pending owner released.
            need(same(samples_store.read(),raw['sampleOwners']['samples']))
            samples,state=drains.sample_shell(samples_store.read(),root,keyed.binding,run,role,self.lock,keyed.policy)
            samples.store,samples.state=samples_store,state
            observer=object.__new__(IOSEmoteCallbackRetirementObserver)
            observer.root,observer.binding,observer.run,observer.role=root,keyed.binding,run,role
            observer.sources,observer.peers,observer.samples,observer.policy,observer.lock=sources,peers,samples,keyed.policy,self.lock
            observer.phase=SimpleNamespace(fixture_url=keyed.fixture_url,previous=dict(instance=keyed.phase_instance))
            observer.state=observer.decode(self.store(self.lock.path.with_name('ios-emote-'+role+'-observer.json')).read())
            need(observer.state['pending'] is None and observer.state['records']
                and same(observer.original(observer.state['records'][-1]),raw['observation']))
            drains.history(observer)
            parents=selected_parents(keyed,raw,scope,samples);current={}
            expected={self.lock.path.with_name('graphics-world-frame-'+role+'-0-'+request[4:]+'.json') for request in parents}
            need(set(self.lock.path.parent.glob('graphics-world-frame-'+role+'-0-*.json'))==expected)
            for request,original in parents.items():
                path=self.lock.path.with_name('graphics-world-frame-'+role+'-0-'+request[4:]+'.json')
                store=self.store(path);value=store.read();current[path]=value
                if original is None:need(value is None);continue
                need(value is not None and original['phase']=='released' and absent(original['absence']))
                owner=VulkanWorldFrameOwner(store,root,keyed.binding,run,role,0,request,
                    lambda *_:need(False),lambda:True,source_lock=self.lock)
                owner.verify_owned_artifact();need(same(owner.state,value))
                fixed=('vulkanWorldOwnerVersion','binding','runId','role','stage','requestId','root','name','ticket','file','frame')
                need(all(same(value[key],original[key]) for key in fixed))
                before,after=unpack(original['transcript']),unpack(value['transcript'])
                need(same(after[:len(before)],before))
                for row in after[len(before):]:need(row['command']['operation']=='inspect' and row['receipt'] is not None)
                need(same(store.read(),value))
            need(self.used==set(self.copies))
            return dict(keyed=keyed,sources=sources,peers=peers,scope=scope,samples=samples,observer=observer,currentGpu=current)


def collect(snapshot,*,lock,primary_lock):
    """Capture actual metadata copies, never infer a missing current entry."""
    roots=[Path(snapshot['artifactRoot']),lock.path.parent,primary_lock.path.parent]
    def captured():
        with original_round(snapshot,lock=lock,primary_lock=primary_lock):
            keyed,raw,_sources,_peers=graph(snapshot,lock=lock,primary_lock=primary_lock)
            scope=drains.projection(raw['sampleOwners'],root=keyed.root,binding=keyed.binding,run=keyed.run,
                role=keyed.role,lock=lock,policy=keyed.policy)
            samples,state=drains.sample_shell(raw['sampleOwners']['samples'],keyed.root,keyed.binding,keyed.run,keyed.role,lock,keyed.policy)
            samples.state=state;samples.store=Frozen(lock.path.with_name('ios-emote-'+keyed.role+'-samples.json'),raw['sampleOwners']['samples'])
            parents=selected_parents(keyed,raw,scope,samples);paths=metadata_paths(keyed,raw,parents)
            copies={str(path):PrivateFeatureState(path).read() for path in sorted(paths)}
            return CallbackCurrentState(snapshot,copies,lock=lock,primary_lock=primary_lock)
    return drains.checked_read(roots,captured)


def current(snapshot,*,lock,primary_lock):
    """Current metadata and typed originals in one full unchanged inventory.

    No copied metadata is accepted as an original read. Every referenced
    sample/PNG/chunk/drain/native/source/input file is literally redecoded.
    The outer guard spans BOTH actual metadata collection and typed replay.
    """
    roots=[Path(snapshot['artifactRoot']),lock.path.parent,primary_lock.path.parent]
    return drains.checked_read(roots,lambda:collect(snapshot,lock=lock,primary_lock=primary_lock).read())
