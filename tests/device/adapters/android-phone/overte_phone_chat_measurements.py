"""Compose actual Chat histories, UI, transport and independent peer originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_chat_view import measured_view,validate as view_packet
from adapters.native_chat_observation import validate as receive_packet
from adapters.native_chat_peer import validate as peer_packet
from adapters.native_chat_history import validate as history_packet
from adapters.native_script_observation import running_owned_engine,validate as script_packet
from adapters.native_script_roots import validate as roots_packet,root_url
from feature_journeys.contract import state as public_state


class ChatSettling(ValueError):
    """Original sources have not converged; never an empty successful result."""


def source_pins():
    root=Path(__file__).resolve().parents[4]
    value=json.loads((root/'tests/device/feature_journeys/chat-source-manifest.v1.json').read_text())
    exact(value,{'chatSourceManifestVersion','sources'});need(type(value['chatSourceManifestVersion']) is int and value['chatSourceManifestVersion']==1)
    exact(value['sources'],{'chat','peer'})
    for key,row in value['sources'].items():
        exact(row,{'path','utf8Sha256','codeUnits','sha256'})
        expected='scripts/communityScripts/armored-chat/armored_chat.js' if key=='chat' else 'tests/device/fixture/domain_peer_agent.js'
        need(row['path']==expected);raw=(root/expected).read_bytes();utf16=raw.decode('utf-8').encode('utf-16le')
        need(hashlib.sha256(raw).hexdigest()==row['utf8Sha256'] and hashlib.sha256(utf16).hexdigest()==row['sha256'] and len(utf16)//2==row['codeUnits'])
    return deepcopy(value['sources'])


def script_identity(roots,scripts,pins):
    roots_packet(roots,dict(schemaVersion=1,commandId=roots['commandId'],action='feature-script-roots-observe'),roots['processId'],roots['capturedEpochMs'])
    script_packet(scripts,scripts['requestId'],scripts['processId'],scripts['capturedEpochMs'])
    need(roots['processId']==scripts['processId'])
    url=root_url(roots['source']['defaultScriptsUrl'])+'communityScripts/armored-chat/armored_chat.js'
    engine=running_owned_engine(scripts,url);code=engine.get('code');compiled=engine.get('compiled')
    need(type(code) is dict and code['submitted'] and code['encoding']=='utf-16le-code-units'
         and code['codeUnits']==pins['codeUnits'] and code['sha256']==pins['sha256']
         and type(compiled) is dict and compiled['complete'])
    rows=[row for row in compiled['compilations'] if row['resourceName']==url and row['sha256']==pins['sha256'] and row['codeUnits']==pins['codeUnits']]
    need(len(rows)==1)
    return dict(url=url,manager=engine['required']['instance'],scriptId=rows[0]['scriptId'],sha256=rows[0]['sha256'])


def measurement(run,frame,*,cleaned=False):
    need(type(cleaned) is bool)
    view=frame['view'];primary=frame['primary'];peer=frame['peer'];control=frame['peerControl'];history=frame['history']
    for value,validate,action in ((view,view_packet,'feature-chat-view-observe'),(primary,receive_packet,'feature-chat-observe'),
            (peer,receive_packet,'feature-chat-observe'),(control,peer_packet,'feature-chat-peer'),(history,history_packet,'feature-chat-history')):
        request=dict(schemaVersion=1,action=action,**{k:value[k] for k in ('commandId','runId')})
        if action!='feature-chat-view-observe':request['operation']=value['operation']
        validate(value,request,value['processId'],value['capturedEpochMs']);need(value['runId']==run)
    need(view['processId']==primary['processId']==history['processId']==frame['native']['processId']==frame['avatar']['processId']
         and peer['processId']==control['processId'] and peer['processId']!=primary['processId']
         and primary['instance']!=peer['instance'] and peer['instance']==control['instance'])
    p,q=primary['source'],peer['source'];c=control['source'];saved=view['source']['storage'];h=history['source']
    need(p['selfSha256']!=q['selfSha256']==c['selfSha256'] and p['droppedEvents']==q['droppedEvents']==0
         and saved['unowned']==0)
    if not (p['mixerPresent']==q['mixerPresent']==c['mixerPresent']==frame['mixer']['running']):raise ChatSettling('Actual mixer sources have not converged')
    if p['mixerPresent'] and not(p['mixerSha256']==q['mixerSha256']==c['mixerSha256']):raise ChatSettling('Original mixer identities have not converged')
    if cleaned:
        need(all(source['retired'] and not source['scopePresent'] and not source['events'] for source in (p,q))
             and h['retired'] and h['restored'] and h['closed'] and h['currentSha256']==h['originalSha256']
             and c['restored'] and not c['leasePresent'] and saved['count']==0 and saved['kind']==h['originalKind'])
    else:need(p['scopePresent'] and q['scopePresent'] and not p['retired'] and not q['retired'] and h['scopePresent'] and not h['retired'])
    measured=measured_view(view);local=[];domain=[]
    for event in saved['events']:(local if event['channel']=='local' else domain).append(event['text'])
    if measured['open']:
        ui=view['source']['ui']
        if not (ui['localMessages']==local and ui['domainMessages']==domain and ui['localRowCount']==len(local) and ui['domainRowCount']==len(domain)):
            raise ChatSettling('Actual visible and stored histories have not converged')
    # Every persisted owned row must have a real native receipt, preserving
    # order and multiplicity. Distant raw receipts may be correctly rejected by
    # the original Local-distance filter, so the converse is deliberately false.
    cursor=0
    for row in saved['events']:
        found=False
        for event in p['events'][cursor:]:
            cursor+=1
            if event['text']==row['text'] and event['channel']==row['channel'] and event['senderSha256'] in (p['selfSha256'],q['selfSha256']):
                need(abs(event['capturedEpochMs']-row['timestamp'])<=1500);found=True;break
        if not found:raise ChatSettling('Stored owned history lacks a matching actual native receive')
    peer_messages=[event['text'] for event in q['events'] if event['senderSha256']==p['selfSha256'] and not event['localOnly']]
    value=dict(measured,localMessages=local,domainMessages=domain,peerMessages=peer_messages,mixerConnected=p['mixerPresent'])
    public_state('chat',value,run)
    return value
