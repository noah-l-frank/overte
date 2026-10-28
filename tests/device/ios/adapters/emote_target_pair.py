"""Explicit original Emote selectors and roots; never inferred from identities.

Configuration selects the pair before owner birth. Feature3 stores the actual
SDK roots and original admitted bindings. These are routing/ownership inputs,
not native absence or permission to Stop/delete a process/session.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.emote_configuration import selector
from ios.adapters.peer_admission import validate as admitted

VERSION=1
CONFIG_KEYS={'primaryTarget','actorTarget','primaryArtifactRoot','actorArtifactRoot'}
ORIGINAL_KEYS=CONFIG_KEYS|{'iosEmoteTargetPairVersion','primaryStateRoot','actorStateRoot','primaryBinding','actorBinding'}


def root(value):
    need(type(value) is str);path=Path(value)
    need(path.is_absolute() and path.resolve(strict=True)==path and path.is_dir())
    PrivateFeatureState(path/'emote-target-pair-boundary.json')._parent();return path


def separated(primary,actor):
    # Both arguments were canonicalized against actual existing directories.
    # Same-role layouts may overlap; no cross-role owner may contain another.
    return primary!=actor and not primary.is_relative_to(actor) and not actor.is_relative_to(primary)


def configuration(value):
    exact(value,CONFIG_KEYS);selector(value['primaryTarget']);selector(value['actorTarget'])
    need(value['primaryTarget']!=value['actorTarget'] and separated(root(value['primaryArtifactRoot']),root(value['actorArtifactRoot'])))
    return deepcopy(value)


def original(value):
    exact(value,ORIGINAL_KEYS);configuration({key:value[key] for key in CONFIG_KEYS})
    need(type(value['iosEmoteTargetPairVersion']) is int and value['iosEmoteTargetPairVersion']==VERSION
        and root(value['primaryStateRoot'])!=root(value['actorStateRoot']))
    primary=[root(value[key]) for key in ('primaryStateRoot','primaryArtifactRoot')]
    actor=[root(value[key]) for key in ('actorStateRoot','actorArtifactRoot')]
    need(all(separated(p,a) for p in primary for a in actor))
    p,a=context(value['primaryBinding']),context(value['actorBinding'])
    need(p['sessionId']!=a['sessionId'] and p['targetFingerprint']!=a['targetFingerprint']
        and all(p[key]==a[key] for key in ('sourceRevision','artifactSha256')))
    return value


def selected(value):
    original(value);return configuration({key:value[key] for key in CONFIG_KEYS})


def bind(flow,state):
    chosen=configuration(flow.configured_pair);role=flow.role;need(role in ('primary','actor'))
    need(flow.selector==chosen[role+'Target'] and flow.primary_selector==chosen['primaryTarget']
        and (role=='actor' or flow.actor_selector==chosen['actorTarget'])
        and flow.root==root(chosen[role+'ArtifactRoot']))
    roots={key:flow.runtime.state_path(chosen[key+'Target']).parent for key in ('primary','actor')}
    need(all(root(str(value))==value for value in roots.values()) and roots['primary']!=roots['actor']
        and flow.lock.path.parent==roots[role] and flow.primary_lock.path.parent==roots['primary'])
    primary=state['primaryBinding'];actor=state['binding'] if role=='actor' else admitted(state['actorAdmission'],state['binding'])
    if role=='primary':need(same(primary,state['binding']))
    value=dict(chosen,iosEmoteTargetPairVersion=VERSION,primaryStateRoot=str(roots['primary']),actorStateRoot=str(roots['actor']),
        primaryBinding=deepcopy(primary),actorBinding=deepcopy(actor));original(value)
    return value
