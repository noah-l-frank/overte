"""Owned private fixture inputs, never peer position or remote delivery proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import base64
import math
import os
import re
import uuid

from adapters.chat_actor_files import ChatActorFiles, encode, node, stamp, identity
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack,same

VERSION = 4
COMMAND = 'chat-peer-input.v1.json'
RECEIPT = 'chat-peer-input-receipt.v1.json'


def command(value):
    need(type(value) is dict and value.get('operation') in ('hold', 'send', 'restore', 'release', 'inspect'))
    operation = value['operation']
    exact(value, {'schemaVersion', 'commandId', 'runId', 'operation'}
        | ({'position'} if operation == 'hold' else {'channel', 'textKey'} if operation == 'send' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{32}', value[key]) for key in ('commandId', 'runId')))
    if operation == 'hold':
        exact(value['position'], {'x', 'y', 'z'})
        need(all(number(coordinate, -100000, 100000) for coordinate in value['position'].values()))
    elif operation == 'send':
        need(value['channel'] in ('local', 'domain') and value['textKey'] in ('reply', 'hidden'))
    return value


class ChatPeerInput:
    """Shares the independently qualified actor's original private file owner.

    Native receipts mean input consumption only. Every attempted operation stays
    in this journal; there is deliberately no success/retirement shortcut here.
    Failed receipt acquisition locks further input except one restoration.
    """
    def __init__(self, files, store, run):
        need(isinstance(files, ChatActorFiles) and type(run) is str and re.fullmatch('[0-9a-f]{32}', run)
            and store.path != files.store.path)
        files._check_source();owned=files._owned()
        need(not owned['closing'] and not owned['removed'] and owned['runId'] in (None,run))
        self.files, self.store, self.run = files, store, run
        self.disk = store.read();self.previous=None
        base = dict(chatPeerInputVersion=VERSION, binding=files.binding, sourceSha256=files.source_sha,
            root=files.root, runId=run, intents=[], commandStamp=None, receipt=None)
        if self.disk is None:
            need(not files._exists(COMMAND) and not files._exists(RECEIPT));self.write(base)
        else:
            try:self.reconstruct(base)
            except Exception:raise NativeUIError('Original peer input history cannot be resumed; ownership is retained') from None

    def reconstruct(self,base):
        files,run=self.files,self.run
        exact(self.disk,set(base));need(all(same(self.disk[key],base[key]) for key in set(base)-{'intents','commandStamp','receipt'}))
        intents=unpack(self.disk['intents']);need(len(intents)<=512)
        if not intents:
            need(self.disk['commandStamp'] is None and self.disk['receipt'] is None
                and not files._exists(COMMAND) and not files._exists(RECEIPT))
            self.previous={**deepcopy(self.disk),'intents':[]};return
        previous=None;seen=set()
        for index,row in enumerate(intents):
            exact(row,{'command','phase','requestedEpochMs','commandStamp','receipt'})
            request=command(row['command']);need(request['runId']==run and request['commandId'] not in seen and row['phase']=='consumed')
            seen.add(request['commandId']);self.admit(request['operation'],request,intents[:index])
            self.file_stamp(row['commandStamp']);evidence=row['receipt'];exact(evidence,{'base64','stamp','sha256'})
            self.file_stamp(evidence['stamp']);need(type(evidence['base64']) is str and len(evidence['base64'])<=5500)
            raw=base64.b64decode(evidence['base64'],validate=True)
            need(base64.b64encode(raw).decode('ascii')==evidence['base64'] and len(raw)<=4096
                and hashlib.sha256(raw).hexdigest()==evidence['sha256'])
            envelope=decode(raw.decode('utf-8'));exact(envelope,{'actorFileVersion','commandNode','resultNode','native'})
            need(type(envelope['actorFileVersion']) is int and envelope['actorFileVersion']==1
                and envelope['commandNode']=={key:row['commandStamp'][key] for key in ('device','inode')}
                and identity(envelope['resultNode'])=={key:evidence['stamp'][key] for key in ('device','inode')})
            self.historical_native(envelope['native'],request,index+1,row['requestedEpochMs'],previous)
            previous=envelope['native']
        need(same(self.disk['commandStamp'],intents[-1]['commandStamp']) and same(self.disk['receipt'],
            dict(native=previous,stamp=intents[-1]['receipt']['stamp'],sha256=intents[-1]['receipt']['sha256'])))
        self.previous={**deepcopy(self.disk),'intents':intents};self.check_command()
        raw,info=files._read(RECEIPT,4096)
        need(stamp(info)==self.previous['receipt']['stamp'] and hashlib.sha256(raw).hexdigest()==self.previous['receipt']['sha256']
            and raw==base64.b64decode(intents[-1]['receipt']['base64']) and files.released(node(info)) is False)
        files._check_source() # No native command or old receipt is replayed.

    @staticmethod
    def file_stamp(value):
        exact(value,{'device','inode','size','mtimeNs','ctimeNs'});identity({key:value[key] for key in ('device','inode')})
        need(all(integer(value[key],0,2**63-1) for key in ('size','mtimeNs','ctimeNs')))

    @staticmethod
    def admit(operation,inputs,old):
        need(operation=='inspect' or not any(row['command']['operation']=='release' for row in old))
        need(not old or old[-1]['phase']=='consumed' or operation=='restore')
        if operation in ('hold','restore'):need(not any(row['command']['operation']==operation for row in old))
        if operation=='restore':need(any(row['command']['operation']=='hold' for row in old))
        if operation=='release':need(not any(row['command']['operation']=='hold' for row in old)
            or any(row['command']['operation']=='restore' and row['phase']=='consumed' for row in old))
        if operation=='send':need(not any(row['command']['operation']=='send' and row['command']['channel']==inputs['channel']
            and row['command']['textKey']==inputs['textKey'] for row in old))

    def historical_native(self,value,request,sequence,requested,previous):
        version=value.get('peerInputVersion');optional={'avatarSha256','avatarPosition'} if version in (2,3) else set()
        if version==3:optional|={'scriptPolls','releaseConsumed'}
        exact(value,{'peerInputVersion','commandId','runId','operation','instance','sequence','processId','capturedEpochMs'}|optional)
        need(type(version) is int and version in (1,2,3) and all(value[key]==request[key] for key in ('commandId','runId','operation'))
            and integer(value['processId'],1) and value['processId']==self.files.pid and integer(value['sequence'],1,4096)
            and value['sequence']==sequence and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
            and integer(requested,self.files.source['configuredEpochMs']) and integer(value['capturedEpochMs'],requested))
        if optional:
            need(type(value['avatarSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['avatarSha256']))
            exact(value['avatarPosition'],{'x','y','z'});need(all(number(point,-100000,100000) for point in value['avatarPosition'].values()))
        if version==3:need(integer(value['scriptPolls'],0) and type(value['releaseConsumed']) is bool)
        if previous is not None:
            need(value['instance']==previous['instance'] and version>=previous['peerInputVersion'] and value['capturedEpochMs']>=previous['capturedEpochMs'])
            if previous['peerInputVersion']==version==3:need(value['scriptPolls']>=previous['scriptPolls'] and (not previous['releaseConsumed'] or value['releaseConsumed']))

    def write(self, value):
        need(same(self.store.read(),self.disk))
        disk={**value,'intents':pack(value['intents'])}
        self.store.write(disk,self.disk);need(same(self.store.read(),disk))
        self.disk=deepcopy(disk);self.previous=deepcopy(value)

    def check_command(self):
        raw, info = self.files._read(COMMAND, 2048)
        need(stamp(info) == self.previous['commandStamp'] and raw == encode(self.previous['intents'][-1]['command']))

    def issue(self, operation, **inputs):
        try:
            files = self.files; files._check_source();owned=files._owned()
            need(not owned['closing'] and not owned['removed'] and owned['runId'] in (None,self.run))
            need(same(self.store.read(),self.disk))
            request = command(dict(schemaVersion=1, commandId=uuid.uuid4().hex,
                runId=self.run, operation=operation, **inputs))
            old = self.previous['intents']
            need(len(old)<512);self.admit(operation,inputs,old)
            if self.previous['commandStamp'] is not None: self.check_command()
            else: need(not files._exists(COMMAND))
            intent = dict(command=request, phase='uncertain',requestedEpochMs=None,commandStamp=None,receipt=None)
            issued=files.monotonic();need(number(issued,0,1e15))
            requested=files.clock_ms();need(integer(requested,1))
            intent['requestedEpochMs']=requested
            fence=getattr(self,'phase_fence',None)
            if fence is not None and operation!='inspect':fence.mark()
            self.write({**self.previous, 'intents': old + [intent]})
            temporary = '.chat-peer-input-' + uuid.uuid4().hex
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600, dir_fd=files.fd)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(encode(request)); stream.flush(); os.fsync(stream.fileno())
                files._check_source()
                if fence is not None and operation!='inspect':fence.check()
                if self.previous['commandStamp'] is None:
                    os.link(temporary, COMMAND, src_dir_fd=files.fd, dst_dir_fd=files.fd, follow_symlinks=False)
                    os.unlink(temporary, dir_fd=files.fd)
                else:
                    # The previous file belongs to the previous input, whose
                    # immutable stamp was checked before persisting this intent.
                    raw, info = files._read(COMMAND, 2048)
                    need(stamp(info) == self.previous['commandStamp'] and raw == encode(old[-1]['command']))
                    if fence is not None and operation!='inspect':fence.check()
                    os.replace(temporary, COMMAND, src_dir_fd=files.fd, dst_dir_fd=files.fd)
                raw, info = files._read(COMMAND, 2048); need(raw == encode(request)); os.fsync(files.fd)
                intents=deepcopy(self.previous['intents']);intents[-1]['commandStamp']=stamp(info)
                self.write({**self.previous, 'intents':intents,'commandStamp': stamp(info)})
            finally:
                try: os.unlink(temporary, dir_fd=files.fd)
                except FileNotFoundError: pass
            started = previous = files.monotonic(); need(number(started, 0, 1e15))
            for attempt in range(31):
                files._check_source(); self.check_command()
                if files._exists(RECEIPT):
                    raw, info = files._read(RECEIPT, 4096); envelope = decode(raw.decode('utf-8'))
                    exact(envelope, {'actorFileVersion', 'commandNode', 'resultNode', 'native'})
                    need(type(envelope['actorFileVersion']) is int and envelope['actorFileVersion'] == 1
                        and identity(envelope['resultNode']) == node(info))
                    receipt = envelope['native']
                    if receipt.get('commandId') == request['commandId']:
                        optional = {'avatarSha256','avatarPosition'} if receipt.get('peerInputVersion') in (2,3) else set()
                        if receipt.get('peerInputVersion')==3:optional|={'scriptPolls','releaseConsumed'}
                        exact(receipt, {'peerInputVersion', 'commandId', 'runId', 'operation', 'instance',
                            'sequence', 'processId', 'capturedEpochMs'} | optional)
                        need(type(receipt['peerInputVersion']) is int and receipt['peerInputVersion'] in (1,2,3)
                            and all(receipt[key] == request[key] for key in ('commandId', 'runId', 'operation'))
                            and integer(receipt['processId'], 1) and receipt['processId'] == files.pid
                            and type(receipt['instance']) is str and re.fullmatch('[0-9a-f]{32}', receipt['instance'])
                            and integer(receipt['sequence'], 1, 4096) and receipt['sequence'] == len(self.previous['intents'])
                            and envelope['commandNode'] == {key: self.previous['commandStamp'][key] for key in ('device', 'inode')}
                            and files.released(node(info)) is False)
                        fresh(receipt['capturedEpochMs'], files.clock_ms())
                        need(receipt['capturedEpochMs'] >= max(files.source['configuredEpochMs'],requested))
                        if optional:
                            need(type(receipt['avatarSha256']) is str and re.fullmatch('[0-9a-f]{64}',receipt['avatarSha256']))
                            exact(receipt['avatarPosition'],{'x','y','z'})
                            need(all(number(value,-100000,100000) for value in receipt['avatarPosition'].values()))
                        if receipt['peerInputVersion']==3:
                            need(integer(receipt['scriptPolls'],0) and type(receipt['releaseConsumed']) is bool)
                        before = self.previous['receipt']
                        need(before is None or receipt['instance'] == before['native']['instance']
                            and receipt['peerInputVersion'] >= before['native']['peerInputVersion']
                            and receipt['capturedEpochMs'] >= before['native']['capturedEpochMs'])
                        if receipt['peerInputVersion']==3 and before is not None and before['native']['peerInputVersion']==3:
                            need(receipt['scriptPolls']>=before['native']['scriptPolls']
                                and (not before['native']['releaseConsumed'] or receipt['releaseConsumed']))
                        intents = deepcopy(self.previous['intents']); intents[-1]['phase'] = 'consumed'
                        intents[-1]['receipt']=dict(base64=base64.b64encode(raw).decode('ascii'),stamp=stamp(info),sha256=hashlib.sha256(raw).hexdigest())
                        self.write({**self.previous, 'intents': intents, 'receipt': dict(native=receipt,
                            stamp=stamp(info), sha256=hashlib.sha256(raw).hexdigest())})
                        observed=deepcopy(receipt);files._check_source()
                        final_started=files.monotonic();need(number(final_started,started,started+1.5))
                        final_epoch=files.clock_ms();fresh(receipt['capturedEpochMs'],final_epoch)
                        finished=files.monotonic()
                        need(number(finished,final_started,started+1.5)
                            and max(final_epoch-receipt['capturedEpochMs']+math.ceil((finished-final_started)*1000),
                                requested-receipt['capturedEpochMs']+math.ceil((finished-issued)*1000))<=1500)
                        return observed
                    old_receipt = self.previous['receipt']
                    need(old_receipt is not None and old_receipt['stamp'] == stamp(info)
                        and old_receipt['sha256'] == hashlib.sha256(raw).hexdigest())
                now = files.monotonic(); need(number(now, previous, started + 1.5)); previous = now
                if now - started >= 1.5 or attempt == 30: break
                files.sleep(min(.05, 1.5 - (now - started)))
            need(False)
        except Exception:
            raise NativeUIError('Chat peer input is unresolved; its original intent is retained without replay') from None
