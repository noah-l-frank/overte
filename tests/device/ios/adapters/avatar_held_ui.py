"""Actual quiet Avatar/People roots retained until independent process end.

A rootId is an observed operand identity, never a constructor/destructor clock.
The complete native retained-root census and original current controls remain
independent; an empty visible input list cannot erase a detached cached root.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from feature_journeys.terminal import held
from feature_journeys.contract import identifier
from ios.adapters.avatar_ui_inventory import validate


def disposition(widgets,*,binding,run):
    from ios.adapters.normal_input import observation
    binding=context(binding);identifier(run);observation(widgets,int(binding['processIdentity']),widgets.get('sampleEpochMs'))
    inventory=validate(widgets['avatarInventory'])
    need(type(widgets.get('avatarControlsVersion')) is int and widgets['avatarControlsVersion']==1
        and widgets['processId']==int(binding['processIdentity']) and inventory['complete'] and not widgets['tabletShown']
        and not any(row['id'].startswith(('avatar.','people.')) for row in widgets['controls']))
    need(all(not root['visible'] and not any(root['panels'].values()) for root in inventory['roots']))
    groups=[]
    for role in ('avatar','people'):
        rows=[deepcopy(row) for row in inventory['roots'] if row['role']==role]
        if rows:
            original=dict(iosAvatarPanelHeldOriginalVersion=1,runId=run,binding=deepcopy(binding),nativeUiInstance=widgets['instance'],
                avatarGeneration=widgets['avatarGeneration'],panel=role,roots=rows)
            identity=digest(original);groups.append(dict(resource='panel:avatar-'+role+'-'+identity[:20],kind='qt-root',
                originalSha256=identity,original=original))
    held([{key:row[key] for key in ('resource','kind','originalSha256')} for row in groups])
    return dict(iosAvatarPanelDispositionVersion=1,originalSha256=digest(widgets),roots=deepcopy(inventory['roots']),holders=groups)
