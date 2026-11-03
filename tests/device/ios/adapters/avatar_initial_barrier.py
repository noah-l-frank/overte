"""Paired-lock immutable initial admission; no peer SDK input or factory.

The restricted writer changes only one initial-barrier reference and appends
its original snapshot through the existing birth/inode WAL. Reopening that
saved initial uses the consumer's real held lock and immutable archive APIs;
no peer live metadata or current product fact is returned.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,unpack
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
from ios.adapters.avatar_world import actual_domain
from ios.adapters.avatar_peer import session_sha


def original(feature):
    """Independently validate the retained immutable peer initial, own lock.

    The generic immutable restoration/Vulkan archive accepts this actual held
    consumer lock. It reads the exact retained peer PNG/root/inode/hashes; no
    lock is forged, no native transport is exposed and no clock is renewed.
    """
    from ios.adapters.avatar_feature import Frozen
    feature.lock.assert_held();barrier=feature.state['initialBarrier'];need(barrier is not None)
    other='actor' if feature.role=='primary' else 'primary';need(barrier['subject']==other)
    value=feature.kept(barrier['owner']);exact(value,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
    need(value['iosAvatarFeatureVersion']==1 and type(value['iosAvatarFeatureVersion']) is int
        and value['runId']==feature.run and value['role']==other and value['selectors']==feature.selectors
        and value['fixtureUrl']==feature.phase.fixture_url)
    rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
    need(same(state['bindings'],feature.state['bindings']) and state['phaseInstance']==feature.state['phaseInstance']
        and state['initialTicket']==feature.state['initialTicket'] and state['initial'] is not None
        and state['initial']['reference']==barrier['reference'])
    root=Path(value['artifactRoot']);need(root.is_absolute() and root.resolve(strict=True)==root)
    def guard():feature.lock.assert_held();need(same(feature.store.read(),feature.previous));return True
    def no_write():need(False)
    snapshots=AvatarWholeSnapshots(root,state['bindings'][other],feature.run,other,lambda:state['snapshots'],guard,no_write)
    kept=snapshots.read(state['initial']['owner'])
    path=feature.runtime.state_path(feature.selectors[other]).with_name('ios-avatar-'+other+'-restoration-frames.json')
    archive=IOSAvatarRestorationFrames.archive(kept,store=Frozen(path,kept),root=root,binding=state['bindings'][other],
        run=feature.run,role=other,lock=feature.lock)
    need(archive.state['pending'] is None and archive.state['records']==[state['initial']['reference']]
        and archive.original(state['initial']['reference'])['kind']=='initial')
    frame,_raw=archive.frame(state['initial']['reference'])
    need(actual_domain(frame['worldBefore'])['domainId']==actual_domain(frame['worldAfter'])['domainId']
        ==feature.state['sessions']['input']['domain'])
    for name in ('worldBefore','worldAfter'):
        need(actual_domain(frame[name])['selfSha256']==session_sha(feature.state['sessions']['input']['sessions'][other]))
    return frame


def bilateral(feature):
    """Current immutable-reference handoff only, never peer live SDK facts.

    The current PFS header is atomic coordination metadata. Both original
    images and the opposite retained header are independently byte-validated;
    no SDK lock alias, current-frame cache or peer transport is introduced.
    """
    feature.lock.assert_held();original(feature)
    other='actor' if feature.role=='primary' else 'primary'
    path=feature.runtime.state_path(feature.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
    value=PrivateFeatureState(path).read()
    if value is None:return False
    old=feature.kept(feature.state['initialBarrier']['owner'])
    need(set(value)==set(old) and all(same(value[key],old[key]) for key in value if key!='payload'))
    rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];before=unpack(old['payload'])[0]
    need(state['phase'] in ('preparing','ready') and same(state['bindings'],feature.state['bindings'])
        and state['phaseInstance']==feature.state['phaseInstance'] and state['initialTicket']==feature.state['initialTicket']
        and same(state['initial'],before['initial']))
    barrier=state['initialBarrier']
    if barrier is None:return False
    exact(barrier,{'subject','owner','reference'})
    need(barrier['subject']==feature.role and barrier['reference']==feature.state['initial']['reference'])
    def guard():feature.lock.assert_held();need(same(feature.store.read(),feature.previous));return True
    def no_write():need(False)
    snapshots=AvatarWholeSnapshots(Path(value['artifactRoot']),state['bindings'][other],feature.run,other,
        lambda:state['snapshots'],guard,no_write)
    own=snapshots.read(barrier['owner'])
    need(set(own)==set(feature.previous) and all(same(own[key],feature.previous[key]) for key in own if key!='payload'))
    saved=unpack(own['payload']);need(len(saved)==1)
    need(same(saved[0]['bindings'],feature.state['bindings']) and same(saved[0]['initial'],feature.state['initial'])
        and saved[0]['phaseInstance']==feature.state['phaseInstance'] and saved[0]['initialTicket']==feature.state['initialTicket'])
    return True


class RestrictedWriter:
    def __init__(self,feature,peer):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(type(feature) is IOSAvatarFeature and type(peer) is IOSAvatarFeature)
        for lock in feature.locks.values():lock.assert_held()
        need(peer.role!=feature.role and peer.run==feature.run and peer.selectors==feature.selectors
            and peer.state['phase']=='preparing' and peer.state['initial'] is not None and peer.state['initialBarrier'] is None
            and same(peer.state['bindings'],feature.state['bindings'])
            and peer.state['phaseInstance']==feature.state['phaseInstance'] and peer.state['initialTicket']==feature.state['initialTicket'])
        self.feature,self.peer=feature,peer;self.state=deepcopy(peer.state);self.prefix=deepcopy(peer.state);self.permitted_barrier=None
        need(all(row['phase']=='saved' for row in self.state['snapshots']))
        self.store=PrivateFeatureState(feature.runtime.state_path(peer.selector).with_name('ios-avatar-'+peer.role+'-feature.json'))
        self.previous=self.store.read();need(same(self.previous,peer.previous))
        # These are real original-frame/PNG validations while both exact SDK
        # locks are held, before any new peer metadata is issued.
        feature.initial_original();peer.initial_original()
        self.ledger=AvatarWholeSnapshots(peer.root,peer.state['bindings'][peer.role],peer.run,peer.role,
            lambda:self.state['snapshots'],self.guard,self.save)
    def guard(self):
        for lock in self.feature.locks.values():lock.assert_held()
        need(same(self.store.read(),self.previous) and same(self.feature.store.read(),self.feature.previous))
        need(all(same(self.state[k],v) for k,v in self.prefix.items() if k not in ('snapshots','initialBarrier'))
            and same(self.state['snapshots'][:len(self.prefix['snapshots'])],self.prefix['snapshots']))
        barrier=self.state['initialBarrier']
        if barrier is not None:
            exact(barrier,{'subject','owner','reference'})
            need(barrier['subject']==self.feature.role and same(barrier['reference'],self.feature.state['initial']['reference'])
                and same(barrier,self.permitted_barrier))
        return True
    def save(self):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        self.guard();value=self.peer.envelope(self.state)
        # Full typed archive/known-original validation precedes each CAS,
        # including the planned/opened/saved original-file transitions.
        IOSAvatarFeature.archive(self.feature.runtime,value,self.feature.client,self.feature.locks)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def publish(self):
        self.guard();need(self.state['initialBarrier'] is None)
        ref=self.ledger.retain(self.feature.previous);need(same(self.ledger.read(ref),self.feature.previous))
        self.permitted_barrier=dict(subject=self.feature.role,owner=ref,reference=deepcopy(self.feature.state['initial']['reference']))
        self.state['initialBarrier']=deepcopy(self.permitted_barrier)
        self.save();return deepcopy(self.previous)


def publish_peer(feature,peer):
    """Complete the other metadata reference while the existing pair is held."""
    from ios.adapters.avatar_feature import IOSAvatarFeature
    for lock in feature.locks.values():lock.assert_held()
    if peer.state['initialBarrier'] is None:
        value=RestrictedWriter(feature,peer).publish()
        peer=IOSAvatarFeature.archive(feature.runtime,value,feature.client,feature.locks)
    barrier=peer.state['initialBarrier'];need(barrier is not None and barrier['subject']==feature.role
        and barrier['reference']==feature.state['initial']['reference'])
    original(peer);return peer
