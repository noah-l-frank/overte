"""Actual API/Qt queued-copy/sink drainage for an originally returned Entity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.web_script_emissions import original,settled
from adapters.native_feature_observation import need


def drained(value,entity,manager,code):
    original(value);need(value['complete'])
    profile=dict(engineInstance=manager['instance'],assignedUrl=manager['url'],loadGeneration=manager['loadGeneration'],
        assignedEpochMs=manager['assignedEpochMs'],code=code)
    owned=set(settled(value,profile))
    for row in value['calls']:
        # Unknown caller is never reclassified as the owned VM. Its actual
        # native operand can still positively identify our Entity's queue.
        if row['surface']=='world' and entity is not None and row['target']==entity:
            need(row['returned'] is not None and row['finally'] is not None);owned.add(row['id'])
    for row in value['queues']:
        if row['call'] not in owned and not (row['call'] is None and row['route']=='world-surface'):continue
        need(not row['captureAlive'] and row['expired'] is not None
            and (row['entered'] is None or row['returned'] is not None and row['finally'] is not None))
    for row in value['sinks']:
        identity=row['identity']
        if row['call'] in owned or entity is not None and identity.get('sourceIdentity')=='web-entity:'+entity:
            need(row['returned'] is not None and row['finally'] is not None)
    return sorted(owned)
