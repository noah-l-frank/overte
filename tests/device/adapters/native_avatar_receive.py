"""Actual sourced AvatarMixer receive originals; no outgoing or replica facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-avatar-receive.json'
LIMIT=262144
ACTION='feature-avatar-receive-observe'


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']==ACTION and type(value['commandId']) is str
        and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId']))
    return value


def history(value,epoch,pid):
    exact(value,{'avatarReceiveVersion','instance','processId','selfSha256','complete','receiveSequence','droppedRecords','records'})
    need(type(value['avatarReceiveVersion']) is int and value['avatarReceiveVersion']==1
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['processId'],1) and value['processId']==pid and sha(value['selfSha256'])
        and value['complete'] is True and integer(value['receiveSequence'],0,1_000_000_000)
        and integer(value['droppedRecords']) and type(value['records']) is list and len(value['records'])<=32
        and value['receiveSequence']==value['droppedRecords']+len(value['records']))
    previous=0
    for index,row in enumerate(value['records']):
        exact(row,{'receiveSequence','capturedEpochMs','avatarSha256','mixerSha256','recordSha256','recordBytes',
            'carriesJoints','jointCount','joints','advertisedModelUrl','targetScale'})
        need(type(row['receiveSequence']) is int and row['receiveSequence']==value['droppedRecords']+index+1
            and integer(row['capturedEpochMs'],max(1,previous),epoch)
            and sha(row['avatarSha256']) and row['avatarSha256']!=value['selfSha256']
            and sha(row['mixerSha256']) and sha(row['recordSha256']) and integer(row['recordBytes'],1,1048576)
            and type(row['carriesJoints']) is bool and integer(row['jointCount'],0,256)
            and type(row['joints']) is list and len(row['joints'])==min(32,row['jointCount'])
            and type(row['advertisedModelUrl']) is str and len(row['advertisedModelUrl'])<=4096
            and not any(ord(c)<32 or ord(c)==127 for c in row['advertisedModelUrl']) and number(row['targetScale'],.001,10000))
        for sampled,joint in enumerate(row['joints']):
            exact(joint,{'index','rotation','translation'})
            need(type(joint['index']) is int and joint['index']==sampled*row['jointCount']//len(row['joints']))
            for field,count in (('rotation',4),('translation',3)):
                data=joint[field]
                need(data is None or type(data) is list and len(data)==count and all(number(v) for v in data))
            if joint['rotation'] is not None:need(.9<=sum(v*v for v in joint['rotation'])<=1.1)
        previous=row['capturedEpochMs']
    return value


def validate(value,request,pid,epoch,*,previous=None):
    need(type(request) is dict and type(request.get('commandId')) is str)
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'avatarReceiveObservationVersion','commandId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['avatarReceiveObservationVersion']) is int and value['avatarReceiveObservationVersion']==1
        and value['commandId']==request['commandId'] and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1,1_000_000_000) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs'],value['requestedEpochMs']+1500))
    fresh(value['capturedEpochMs'],epoch);history(value['source'],value['capturedEpochMs'],pid)
    if previous is not None:
        validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action=ACTION),pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['requestedEpochMs']>=previous['capturedEpochMs'])
        accept(previous['source'],value['source'])
    return value


def accept(before,current):
    need(before['instance']==current['instance'] and before['processId']==current['processId']
        and before['selfSha256']==current['selfSha256']
        and current['receiveSequence']>=before['receiveSequence'] and current['droppedRecords']>=before['droppedRecords'])
    left={r['receiveSequence']:r for r in before['records']};right={r['receiveSequence']:r for r in current['records']}
    need(all(left[n]==right[n] for n in left.keys()&right.keys())
        and all(n<=current['droppedRecords'] for n in left.keys()-right.keys()))
    return deepcopy(current)


def motion(before,current,avatar):
    """Actual fresh remote joint changes, never an inferred Emote name/range."""
    need(sha(avatar));accept(before,current)
    need(current['droppedRecords']<=before['receiveSequence'])
    rows=[r for r in current['records'] if r['receiveSequence']>before['receiveSequence']
        and r['avatarSha256']==avatar and r['carriesJoints']]
    need(len(rows)>=2 and len({r['mixerSha256'] for r in rows})==1)
    for a,b in zip(rows,rows[1:]):
        need(a['jointCount']==b['jointCount'] and [j['index'] for j in a['joints']]==[j['index'] for j in b['joints']])
        for left,right in zip(a['joints'],b['joints']):
            for field in ('rotation','translation'):
                x,y=left[field],right[field]
                if x is None or y is None:continue
                delta=sum((c-d)**2 for c,d in zip(x,y))
                if field=='rotation':delta=min(delta,sum((c+d)**2 for c,d in zip(x,y)))
                if delta>1e-6:return deepcopy(rows)
    raise NativeUIError('Actual remote avatar received joints did not change')


class NativeAvatarReceive(NativeScriptRoots):
    """Same bounded nonce/read lifecycle, with the receive source grammar."""
    def restore(self,original):
        need(self.last is None and type(original) is dict)
        request=dict(schemaVersion=1,commandId=original.get('commandId'),action=ACTION)
        command(request,ios=self.ios);validate(original,request,self.pid,original.get('capturedEpochMs'));self.last=deepcopy(original)

    def read(self,after_sequence):
        # Reuse the existing tightly bounded implementation after substituting
        # only its closed protocol names through the explicit shared reader.
        from adapters.native_avatar_receive_transport import read
        return read(self,after_sequence)
