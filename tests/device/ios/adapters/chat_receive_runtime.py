"""Existing-candidate Chat receive components on two explicitly held locks.

The caller owns normal input and both scopes. Construction sends no Chat
command; the primary cache must be opened through its returned owned capture
before sampling the existing independent receiver. No feature is advertised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.independent_chat_receiver import IndependentChatReceiver
from adapters.native_chat_observation import ChatCaptureOwner
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.chat_session_owners import register_scope
from ios.adapters.peer_admission import admit_existing_peer,validate as admission_packet
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1


class IOSOwnedChatReceiver(IndependentChatReceiver):
    """The original independent reader, additionally bound to its primary owner."""
    def __init__(self,primary_capture,peer_capture,store,primary_binding):
        self.primary_capture=primary_capture
        super().__init__(primary_capture.reader,primary_binding,peer_capture,store,retain_originals=True)
        previous=self.owned()
        if previous is not None:
            originals=self.originals(previous)
            for key,capture in (('primary',primary_capture),('peer',peer_capture)):
                owned=capture.owner.match(originals[key]);need(owned['admitted'] and owned['active'])

    def sample(self):
        owned=self.primary_capture.owner.owned()
        need(owned is not None and owned['runId']==self.peer.run and owned['admitted'] and owned['active'])
        value=super().sample();self.primary_capture.owner.match(value['primary']);return value


def root_identity(root):
    root=Path(root);need(root.is_absolute() and root.resolve(strict=True)==root)
    PrivateFeatureState(root/'chat-receive-boundary.json')._parent();info=root.stat()
    return dict(path=str(root),device=info.st_dev,inode=info.st_ino)


def binding_record(value,primary_binding,peer_binding,run,primary_root,peer_root):
    exact(value,{'iosChatPeerBindingVersion','runId','primaryBinding','peerBinding',
        'primaryArtifactRoot','peerArtifactRoot','admission'})
    need(type(value['iosChatPeerBindingVersion']) is int and value['iosChatPeerBindingVersion']==VERSION
        and value['runId']==identifier(run) and same(context(value['primaryBinding']),primary_binding)
        and same(context(value['peerBinding']),peer_binding)
        and same(value['primaryArtifactRoot'],root_identity(primary_root))
        and same(value['peerArtifactRoot'],root_identity(peer_root))
        and same(admission_packet(value['admission'],primary_binding),peer_binding))
    return value


def receive_components(runtime,primary_selector,peer_selector,run,primary_root,peer_root,primary_lock,peer_lock):
    """Reuse already prepared physical candidates; never create/repair a session.

    Explicit shared lock objects permit composition with the same draft owner.
    Their caller controls acquisition order and keeps both held through input,
    sampling and each separate cache's cleanup.
    """
    need(isinstance(runtime,IOSScriptRuntime) and isinstance(primary_lock,ScriptSourceLock)
        and isinstance(peer_lock,ScriptSourceLock) and primary_lock.path!=peer_lock.path
        and primary_lock.path==runtime.state_path(primary_selector).with_name('script-feature-sources.lock')
        and peer_lock.path==runtime.state_path(peer_selector).with_name('script-feature-sources.lock'))
    primary_lock.assert_held();peer_lock.assert_held();identifier(run)
    primary_identity,peer_identity=root_identity(primary_root),root_identity(peer_root)
    need(primary_identity['path']!=peer_identity['path']
        and (primary_identity['device'],primary_identity['inode'])!=(peer_identity['device'],peer_identity['inode']))
    primary=runtime._sources(primary_selector)
    admission=admit_existing_peer(runtime,peer_selector,primary['binding'])
    peer=runtime._sources(peer_selector);need(same(peer['binding'],admission_packet(admission,primary['binding'])))
    need(primary['check']() is not False and peer['check']() is not False)
    store=PrivateFeatureState(runtime.state_path(peer_selector).with_name('ios-chat-receive-binding.json'))
    previous=store.read()
    if previous is None:
        previous=dict(iosChatPeerBindingVersion=VERSION,runId=run,primaryBinding=deepcopy(primary['binding']),
            peerBinding=deepcopy(peer['binding']),primaryArtifactRoot=primary_identity,peerArtifactRoot=peer_identity,
            admission=deepcopy(admission))
        binding_record(previous,primary['binding'],peer['binding'],run,primary_root,peer_root)
        store.write(previous,None);need(same(store.read(),previous))
    else:binding_record(previous,primary['binding'],peer['binding'],run,primary_root,peer_root)
    def bound():
        primary_lock.assert_held();peer_lock.assert_held()
        need(primary['check']() is not False and peer['check']() is not False and same(store.read(),previous))
        binding_record(previous,primary['binding'],peer['binding'],run,primary_root,peer_root)
        return True
    bound()
    for selector,source,root in ((primary_selector,primary,primary_root),(peer_selector,peer,peer_root)):
        register_scope(runtime.adapter,selector,source['binding'],run,root)
    captures=[]
    for selector,source,role in ((primary_selector,primary,'primary'),(peer_selector,peer,'peer')):
        owner=ChatCaptureOwner(PrivateFeatureState(runtime.state_path(selector).with_name('ios-chat-'+role+'-capture.json')),
            source['binding'],bound)
        owned=owner.owned();need(owned is None or owned['runId']==run)
        capture=source['observer'].chat_capture(owner,run);capture.reader.guard=bound;captures.append(capture)
    primary_capture,peer_capture=captures
    receiver=IOSOwnedChatReceiver(primary_capture,peer_capture,
        PrivateFeatureState(runtime.state_path(peer_selector).with_name('ios-chat-independent-receiver.json')),primary['binding'])
    bound()
    return dict(primary=primary,peer=peer,primary_capture=primary_capture,peer_capture=peer_capture,
        receiver=receiver,admission=deepcopy(admission),binding=deepcopy(previous),check=bound,
        primary_lock=primary_lock,peer_lock=peer_lock)
