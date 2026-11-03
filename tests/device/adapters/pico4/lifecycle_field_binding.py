"""Passive UI2/Binding1 relation to the Pico shared native weak triple.

The producer adapts the fixed Phone GUI-only QPointer registry. UI's original
fieldId remains independent; only the new native-issued weak token is shared
with PendingWire1. This decoder never creates an identity or authorizes input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need

VERSION=1
KEYS={'lifecycleFieldBindingVersion','uiFieldId','pendingFieldToken','weakBirth','status'}


def validate(value,row):
    from adapters.pico4.lifecycle_source import nonce
    exact(value,KEYS)
    need(type(value['lifecycleFieldBindingVersion']) is int and value['lifecycleFieldBindingVersion']==VERSION
        and value['uiFieldId']==row['fieldId'] and nonce(value['uiFieldId'])
        and type(value['pendingFieldToken']) is str and value['weakBirth']==value['pendingFieldToken'])
    original=all(row[key] for key in ('fieldAlive','windowAlive','contextAlive'))
    if value['pendingFieldToken']:
        need(nonce(value['pendingFieldToken']) and value['status']==('linked' if original else 'retired'))
    else:need(not original and value['status']=='unobserved')
    return value


def advance(previous,current):
    need(all(current[key]==previous[key] for key in KEYS-{'status'}))
    need(current['status']==previous['status'] or previous['status']=='linked' and current['status']=='retired')


def pending_match(editor,pending):
    """Require both original native identities; never fieldId==token inference.

    Both complete surrounding originals and original clocks must already have
    passed their own reader validation. This is only their identity relation.
    """
    need(type(editor) is dict and editor['kind']=='scripts' and editor['current'] is True
        and all(editor[key] for key in ('fieldAlive','windowAlive','contextAlive')))
    relation=validate(editor.get('fieldBinding'),editor)
    need(relation['status']=='linked' and type(pending) is dict and pending['current']['status']=='ready'
        and relation['pendingFieldToken']==pending['current']['token'])
    return relation
