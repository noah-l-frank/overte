"""Actual imported entity identity and geometry, from existing native sources.

No requested UUID/name, dialog ACK or property string becomes a model/render
verdict. Sources remain historical originals until a separate fresh collector
and independent frame/peer publication joins them.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import create_state
from ios.adapters.assets_usage_controls import project as usage
from ios.adapters.assets_usage_owner import OwnedAssetsUsage

VERSION=1
FOREIGN=('id','hostType','name','type','modelURL','textures','sourceUrl','userData','collisionless','lastEditedBy','createdEpochUs','lastEditedEpochUs','locked','visible')


def owner(owned):
    need(isinstance(owned,OwnedAssetsUsage) and owned.state is not None and same(owned.store.read(),owned.previous)
        and same(owned.source.store.read(),owned.source.previous))
    owned.source.decode(owned.source.previous);owned.decode(owned.previous);return owned


def accepted(owned):
    owner(owned);entries=[entry for entry in owned.state['inputs'] if entry['slot']=='usage-accept-model']
    need(len(entries)==1 and entries[0]['id']=='assets.model.accept' and entries[0]['command'] is not None and entries[0]['resolvedBy'] is not None)
    entry=entries[0];before,after=owned.packet(entry['before']),owned.packet(entry['resolvedBy'])
    return entry,before,after,usage(before,owned.source.state['page']),usage(after,owned.source.state['page'])


def originals(before,after,run,pid):
    for packet in (before,after):
        create_state.original(packet);need(packet['iosCreateStateVersion']>=3 and packet['runId']==run and packet['processId']==pid and packet['source']['complete'])
    create_state.validate(after,dict(schemaVersion=1,action=create_state.ACTION,commandId=after['requestId'],runId=run),pid,previous=before)
    need(before['source']['localSessionId']==after['source']['localSessionId']);return before['source'],after['source']


def imported(owned,before,after):
    entry,ui_before,ui_after,first_ui,last_ui=accepted(owned);run=owned.source.files.run;pid=owned.source.clock.pid
    first,last=originals(before,after,run,pid)
    need(before['clockAfter']['epochMs']<=ui_before['sampleEpochMs'] and ui_after['sampleEpochMs']<=after['clockBefore']['epochMs']
        and first['domainId']==last['domainId']==first_ui['domainId']==last_ui['domainId']
        and first['localSessionId']==last['localSessionId']==first_ui['clientNodeId']==last_ui['clientNodeId'])
    old={row['id']:row for row in first['entities']};new={row['id']:row for row in last['entities']}
    need(set(old)<=set(new) and not any(row['modelURL']==owned.url() for row in old.values()))
    for id_,row in old.items():need(all(same(row[key],new[id_][key]) for key in FOREIGN))
    additions=[row for id_,row in new.items() if id_ not in old];need(len(additions)==1);actual=additions[0];model=entry['effect']['model']
    need(actual['type']=='Model' and actual['hostType']=='domain' and actual['lastEditedBy']==last['localSessionId'] and actual['modelURL']==owned.url()
        and actual['name']==model['name'] and actual['visible'] and not actual['locked']
        and ui_before['sampleEpochMs']*1000<=int(actual['createdEpochUs'])<=ui_after['sampleEpochMs']*1000
        and all(abs(actual['position'][index]-model['position'][axis])<=.0001 for index,axis in enumerate(('x','y','z'))))
    return dict(assetModelCreationProofVersion=VERSION,runId=run,processId=pid,domainId=last['domainId'],clientNodeId=last['localSessionId'],
        entityId=actual['id'],path=owned.path(),url=owned.url(),inputCommandId=entry['command']['commandId'],beforeRequestId=before['requestId'],requestId=after['requestId'],
        createdEpochUs=actual['createdEpochUs'],name=actual['name'],position=deepcopy(actual['position']))


def geometry(owned,before,after,original):
    """Observe actual wrapper geometry flags; resource origin stays separate."""
    creation=imported(owned,before,after)
    return _geometry_from_imported(owned,after,original,creation)


def _geometry_from_imported(owned,after,original,creation):
    """One synchronous decoder's just-validated imported result, never a cache.

    Only the Model decoder composes this immediately after imported() on the
    same immutable inputs. Public geometry() still performs its complete owner
    and original-parent read. No result survives a decode or mutation boundary.
    """
    create_state.original(original)
    if original['requestId']==after['requestId']:need(same(original,after))
    else:create_state.validate(original,dict(schemaVersion=1,action=create_state.ACTION,commandId=original['requestId'],runId=creation['runId']),creation['processId'],previous=after)
    need(original['iosCreateStateVersion']>=3 and original['runId']==creation['runId'] and original['processId']==creation['processId']==owned.source.clock.pid
        and original['source']['complete'] and original['source']['domainId']==creation['domainId'] and original['source']['localSessionId']==creation['clientNodeId'])
    rows=[row for row in original['source']['entities'] if row['id']==creation['entityId']];need(len(rows)==1);actual=rows[0];model=actual['model']
    need(actual['type']=='Model' and actual['hostType']=='domain' and actual['lastEditedBy']==creation['clientNodeId'] and actual['modelURL']==creation['url']
        and actual['createdEpochUs']==creation['createdEpochUs'] and actual['name']==creation['name'] and actual['position']==creation['position']
        and actual['visible'] and not actual['locked'] and model['present'] and model['loaded'] and model['addedToScene'] and not model['failed'])
    return dict(assetModelGeometryObservationVersion=VERSION,entityId=actual['id'],runId=original['runId'],processId=original['processId'],requestId=original['requestId'],
        domainId=creation['domainId'],url=actual['modelURL'],createdEpochUs=actual['createdEpochUs'])
