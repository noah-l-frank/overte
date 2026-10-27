"""Pure relation of two original empty Chat values, never a fresh end proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_chat_view import validate
from adapters.native_feature_observation import need
from adapters.script_feature.history import same


def unchanged_empty(before,after):
    """Require exact native value/type/presence hash and configuration equality.

    Callers still own original-file/source binding, fresh clock acquisition,
    normal restoration inputs, quiet/callback drainage and complete cleanup.
    This historical comparison neither queries nor mutates any source.
    """
    for value in (before,after):
        need(type(value) is dict)
        request=dict(schemaVersion=1,action='feature-chat-view-observe',commandId=value.get('commandId'),runId=value.get('runId'))
        validate(value,request,value.get('processId'),value.get('capturedEpochMs'));need(value['chatViewVersion']>=2)
    need(all(before[key]==after[key] for key in ('runId','instance','processId','chatViewVersion'))
        and after['sequence']>before['sequence'] and after['commandId']!=before['commandId']
        and after['capturedEpochMs']>=before['capturedEpochMs'])
    first,last=(value['source']['storage'] for value in (before,after))
    need(first['count']==first['unowned']==0 and first['events']==[] and same(first,last))
    return True
