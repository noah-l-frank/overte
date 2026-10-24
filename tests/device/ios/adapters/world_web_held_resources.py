"""Actual retained Web owners exposed until the separate OS death original.

An alias names a measured native lifetime group. Its hash pins the original
identity and counter operands; it neither retires nor allocates that lifetime.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from feature_journeys.terminal import held
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_resource_disposition import disposition
from ios.adapters.world_web_surface_lease import current as surface_current
from adapters.script_ui_root_ownership import membership as ui_membership,validate as ui_roots
from ios.adapters.world_web_held_groups import project as grouped,expand as members

_KINDS={'scenegraph-node':'qsg-root','native-bitmap':'qimage','offscreen-image':'qimage',
    'upload-image':'qimage','native-view':'wk-view'}


def primary(lease,reference):
    need(type(lease) is WorldWebLease)
    with lease.source.validation_round(),lease.validation_round():
        owned=lease.packet();need(owned['iosWorldWebLeaseVersion']==2)
        frame=lease.source.frame(reference);admitted=lease.source.frame(owned['after'])
        released,root=surface_current(owned['surfaceLease'],frame['originals']['surfaces'],live=False)
        need(not released['alive'] and (root['cached'] or not root['surfaceAlive']))
        raw=frame['originals']['closures'];proof=disposition(raw,admitted['originals']['closures'])
        identity=hashlib.sha256(('web-entity:'+owned['returned']['returned']['entityId']).encode()).hexdigest()
        rows=[]
        def append(kind,source,owner):
            # Aliases remain stable across fresh getter sequence/clock changes.
            identity_key=digest([lease.binding,lease.run,source,owner])
            alias='panel:world-web-'+kind+'-'+identity_key[:20]
            original=dict(iosWorldWebHeldResourceVersion=1,binding=deepcopy(lease.binding),runId=lease.run,
                source=source,owner=deepcopy(owner))
            rows.append(dict(resource=alias,kind=kind,originalSha256=digest(original),original=original))
        packet=frame['originals']['surfaces']
        base=dict(instance=packet['source']['instance'],processId=packet['processId'],surfaceBirth=root['birth'])
        if root['surfaceAlive']:append('qt-root','offscreen-surface',dict(base,birth=root['birth'],rootSource=root['rootSource']))
        if root['rootAlive']:append('qt-root','qml-root',dict(base,birth=root['rootBirth'],rootSource=root['rootSource']))
        for context in proof['contexts']:
            if context['descriptor']['identitySha256']!=identity:continue
            need(context['descriptor']['surface']=='world-entity')
            for name,counter in context['resources'].items():
                if counter['pending']:
                    need(name!='policy-grant')
                    append(_KINDS.get(name,'native-holder'),'web-'+name,dict(instance=raw['instance'],processId=raw['processId'],
                        contextId=context['id'],descriptor=deepcopy(context['descriptor']),counter=deepcopy(counter)))
        # Full Feature6 requires inventory2 before its first normal setup input.
        # Historical source/helper profiles retain their literal older shape;
        # they never supply ScriptUI weak-lifetime qualification.
        inventory=frame['originals']['widgets'].get('scriptInventory')
        if inventory is not None and inventory['inventoryVersion']==2:
            initial=lease.source.frame(owned['before'])['originals']['widgets']['scriptInventory']
            need(initial['inventoryVersion']==2)
            before=ui_membership(initial,pid=frame['originals']['world']['processId'])
            current=ui_membership(inventory,pid=frame['originals']['world']['processId'])
            ui_roots(current,pid=frame['originals']['world']['processId'],previous=before)
            old={row['observedIdentity'] for row in before['roots']}
            for retained in current['roots']:
                if retained['observedIdentity'] not in old and retained['weakAlive']:
                    need(retained['firstObservedEpochMs']>=before['capturedEpochMs'])
                    append('qt-root','script-ui-'+retained['kind'],dict(instance=current['instance'],processId=current['processId'],root=deepcopy(retained)))
        rows=grouped(rows);held([{key:row[key] for key in ('resource','kind','originalSha256')} for row in rows])
        lease.source.guard_originals();lease.header()
        return rows


def public(rows):
    members(rows)
    result=[{key:deepcopy(row[key]) for key in ('resource','kind','originalSha256')} for row in rows]
    held(result)
    for private,visible in zip(rows,result):
        need(same(visible,{key:private[key] for key in visible}) and digest(private['original'])==visible['originalSha256'])
    return result
