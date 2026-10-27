"""Independently owned original parents for Assets image acquisition/replay.

Retained ready marker data remains historical after actual marker retirement.
No SDK, current marker, image, lifetime absence or feature result is produced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import unpack,same
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput


def marker_original(owner,snapshot):
    """Verify a retained ready parent against its actual current child prefix.

    Paths and context come from the independently constructed typed parent,
    never from a filename/root in the supplied image/archive envelope.
    """
    need(isinstance(owner,OwnedAssetsMarker));owner.lock.assert_held()
    need(owner.previous is not None and same(owner.store.read(),owner.previous))
    current=owner.decode(owner.previous);need(current['child'] is not None)
    expected=owner.envelope();exact(snapshot,set(expected))
    need(all(same(snapshot[key],expected[key]) for key in expected if key!='payload'))
    states=unpack(snapshot['payload']);need(len(states)==1);state=states[0];exact(state,{'phase','pending','child'})
    need(state['phase']=='ready' and state['pending'] is None and state['child'] is not None)
    original=owner.archive(state['child'],ready=True)
    owner.prefix(state['child'],current['child'])
    actual=original.state['admission']['marker'];files=original.state['fileOwnership']
    return dict(nonce=files['nonce'],sourceUrl=actual['sourceUrl'],id=actual['id'])


def parsed_original(owner,snapshot):
    """Recompose the actual observed parser/baked-input owner, not a proof DTO."""
    need(isinstance(owner,OwnedAssetsParsedInput));owner.lock.assert_held()
    need(owner.previous is not None and same(owner.store.read(),owner.previous) and same(snapshot,owner.previous))
    owner.authoritative();state=owner.decode(snapshot);need(state['phase']=='observed' and state['result'] is not None)
    return deepcopy(state['result'])
