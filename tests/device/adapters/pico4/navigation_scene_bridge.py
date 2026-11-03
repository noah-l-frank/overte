"""Passive original preparation bridge; historical files grant no input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.native_navigation_environment import validate as environment_packet,logged_out
from adapters.navigation_arrival import pose_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.navigation_originals import read_original
from adapters.script_journey.history import same,unpack
from openxr_input.controller_protocol import validate_envelope
from navigation_observation import owned_scene,viewpoint_urls

VERSION=2


def original(reference):
    need(reference.get('present') is True and same(read_original(reference['path']),reference))
    return PrivateFeatureState(reference['path']).read()


def chunk(reference,scope_sha):
    body=original(reference)
    exact(body,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
    need(type(body['chatSampleChunkVersion']) is int and body['chatSampleChunkVersion']==1
        and body['scopeSha256']==scope_sha and type(body['index']) is int and body['index']>=0)
    rows=unpack(body['transcript']);need(len(rows)==1);return rows[0]


def read_bridge(reference,parent):
    """Read versions' physical originals without querying a live source.

    Every actual intermediate envelope, its exact accepted sequence and sampled
    native neutral status remain required. There is no sequence-offset escape.
    Parent's ordinary live context/publish callbacks separately gate any input.
    """
    from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
    exact(reference,{'navigationPreparationBridgeVersion','scopeSha256','originalLease','bridge','origin','originPacket'})
    version=reference['navigationPreparationBridgeVersion']
    need(type(version) is int and version in (1,VERSION))
    lease=chunk(reference['originalLease'],reference['scopeSha256']);bridge=chunk(reference['bridge'],reference['scopeSha256'])
    need(type(lease.get('navigationSceneOriginalLeaseVersion')) is int and lease['navigationSceneOriginalLeaseVersion']==version
        and lease['scopeSha256']==bridge['scopeSha256']==reference['scopeSha256']
        and json_digest(lease['scope'])==reference['scopeSha256'] and lease['scope']['runId']==parent.run
        and same(lease['scope']['binding'],parent.binding) and same(lease['scope']['inputs'],parent.source.inputs)
        and lease['scope']['sourceLock']==str(parent.lock.path)
        and Path(reference['originalLease']['path']).parent==Path(reference['bridge']['path']).parent==parent.lock.path.parent)
    pid=int(parent.binding['processIdentity'].split(':',1)[0]);environment=lease['environment'];epoch=environment['capturedEpochMs']
    environment_packet(environment,dict(schemaVersion=1,commandId=environment['commandId'],action='feature-navigation-environment',runId=parent.run),pid,epoch)
    logged_out(environment);validate_snapshot(lease['ui'],pid,lease['ui']['updatedEpochMs'])
    original_scene=parent.source.inputs['sceneUrl'] if version==1 else lease['originalSceneUrl']
    if version==2:
        parsed=owned_scene(lease['originalUrl'],viewpoint_required=True)
        need(original_scene==parsed._replace(query='',fragment='').geturl()
            and lease['originalUrl'] in viewpoint_urls(original_scene).values())
    need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
        and environment['settings']['selectedType']=='string' and not environment['environmentOverride']
        and environment['selectedServer']==environment['effectiveServer'] and not lease['ui']['open']
        and pose_packet(lease['pose'],parent.run,parent.binding,original_scene,lease['pose']['subject']['capturedEpochMs']) is not None
        and lease['originalUrl']==lease['pose']['subject']['source']['sceneUrl'])
    need(bridge['kind']=='journey-open' and bridge['originalLease']==0 and bridge['controller']==bridge['controllers'][-1]
        and same(bridge['parentHome'],parent.state['home']) and same(bridge['parent']['scope'],parent.scope())
        and same(bridge['parentOrigin'],reference['origin']) and same(bridge['parent']['origin'],reference['origin'])
        and reference['origin']['path']==str(parent.origin.store.path)
        and same(read_original(parent.origin.store.path),reference['origin']))
    origin=original(reference['origin']);need(same(origin,parent.origin.disk_state))
    before=original(reference['originPacket'])
    need(reference['originPacket']['path']==str(parent.origin.packet_store(origin['original']['sha256']).path)
        and same(bridge['parent']['originPacket'],reference['originPacket'])
        and same(before,parent.origin.original_packet(origin['original'])))
    need(before['settings']['rawSettingsSha256']==environment['settings']['rawSettingsSha256']
        and before['selectedServer']==environment['selectedServer'] and before['otherSettingsSha256']==environment['otherSettingsSha256'])
    rows=bridge['controllers'];need(type(rows) is list and len(rows)==4)
    need([(row['phase'],row['kind']) for row in rows]==[('goto','tablet.open'),('home','input.primary'),('closing','tablet.close'),('opening','tablet.open')])
    parent_home=bridge['parentHome']['envelope'];session=lease['session']
    need(session['processIdentity']==parent.binding['processIdentity'] and type(session['nextSequence']) is int
        and session['nextSequence']>=1 and number(lease['hostMonotonic'],lease['scope']['startedMonotonic'],lease['scope']['deadlineMonotonic']))
    chain=[rows[0]['envelope'],rows[1]['envelope'],parent_home,rows[2]['envelope'],rows[3]['envelope']]
    for index,envelope in enumerate(chain):
        validate_envelope(envelope,parent.session.profile)
        need(envelope['sessionNonce']==session['sessionNonce'] and type(envelope['sequence']) is int
            and envelope['sequence']==session['nextSequence']+index and len(envelope['commands'])==1
            and envelope['commands'][0]['operation']==('tablet.open','input.primary','input.primary','tablet.close','tablet.open')[index])
    for envelope,statuses in [(row['envelope'],row.get('statuses')) for row in rows]+[(parent_home,bridge['parent']['homeStatuses'])]:
        need(type(statuses) is list and 1<=len(statuses)<=81)
        previous=None
        for item in statuses:
            exact(item,{'status','hostMonotonic'});need(number(item['hostMonotonic'],lease['scope']['startedMonotonic'],lease['scope']['deadlineMonotonic'])
                and (previous is None or item['hostMonotonic']>=previous));previous=item['hostMonotonic']
            status=item['status'];need(type(status) is dict and status.get('enabled') is True
                and type(status.get('acceptedSequence')) is int and status['acceptedSequence']==envelope['sequence']
                and status.get('acceptedNonce')=='[redacted]' and status.get('state') in ('accepted','active','neutral'))
        need(NavigationBookmarkJoin.neutral(statuses[-1]['status'],envelope))
    need(bridge['ui']['open'] and bridge['ui']['ready'] and bridge['ui']['bridgeId']==parent.binding['sessionId'])
    # All files are re-read after complete parsing. Historical originals remain
    # original; no current clock, native PID, or input authority is synthesized.
    for key in ('originalLease','bridge','origin','originPacket'):need(same(read_original(reference[key]['path']),reference[key]))
    return deepcopy(chain[-1])
