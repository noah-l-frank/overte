"""Private actor-host IPC for original Assignment Client Chat observations.

This transport never launches a process, supplies messages or reports delivery.
The caller owns executable/PID/start qualification and the independent receiver.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

from adapters.native_chat_observation import command, validate
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError

VERSION=1
SOURCE='chat-actor-source.v1.json'
COMMAND='chat-actor-command.v1.json'
RESULT='feature-chat-observation.json'


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')


def node(info):
    return dict(device=str(info.st_dev),inode=str(info.st_ino))


def stamp(info):
    return dict(node(info),size=info.st_size,mtimeNs=info.st_mtime_ns,ctimeNs=info.st_ctime_ns)


def identity(value):
    exact(value,{'device','inode'})
    need(all(type(value[k]) is str and re.fullmatch('0|[1-9][0-9]{0,24}',value[k]) for k in value))
    return value


class ChatActorFiles:
    """One owned native actor and one run; uncertain writes remain journalled.

    guard must requalify the actual actor process, start identity and executable.
    released(node) must inspect that actor's actual open-file inventory, returning
    True only after its original result FD has closed. Neither is an input ACK.
    """
    def __init__(self,directory,store,binding,script_sha256,guard,released,*,component_only=False,
                 clock_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        need(os.name=='posix' and all(callable(v) for v in (guard,released,clock_ms,monotonic,sleep))
             and type(script_sha256) is str and re.fullmatch('[0-9a-f]{64}',script_sha256))
        self.path=Path(directory);self.store=store;self.guard=guard;self.released=released
        self.clock_ms,self.monotonic,self.sleep=clock_ms,monotonic,sleep
        self.binding=deepcopy(context(binding,component_only=component_only));self.component_only=component_only
        pid=self.binding['processIdentity'].split(':',1)[0];need(re.fullmatch('[1-9][0-9]*',pid))
        self.pid=int(pid);self.fd=-1
        need(self.path.is_absolute() and self.path.resolve(strict=True)==self.path and self.guard() is not False)
        self.fd=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            info=os.fstat(self.fd);self.root=node(info);self._check_root()
            raw,source_info=self._read(SOURCE,4096)
            source=decode(raw.decode('utf-8'));exact(source,{'actorVersion','instance','processId','configuredEpochMs','scriptSha256'})
            need(type(source['actorVersion']) is int and source['actorVersion']==1
                 and type(source['instance']) is str and re.fullmatch('[0-9a-f]{32}',source['instance'])
                 and integer(source['processId'],1) and source['processId']==self.pid
                 and integer(source['configuredEpochMs'],1) and source['configuredEpochMs']<=self.clock_ms()+1000
                 and source['scriptSha256']==script_sha256)
            self.source=source;self.source_stamp=stamp(source_info);self.source_sha=hashlib.sha256(raw).hexdigest()
            value=self.store.read()
            if value is None:
                need(not self._exists(COMMAND) and not self._exists(RESULT))
                value=dict(actorFilesVersion=VERSION,binding=self.binding,root=self.root,source=source,
                    sourceStamp=self.source_stamp,sourceSha256=self.source_sha,runId=None,
                    pending=None,request=None,commandStamp=None,result=None,closing=False,removed=False)
                self.store.write(value,None)
            self._owned();self._check_source()
        except BaseException:
            self.detach();raise

    def detach(self):
        """Close this host handle only; never claim native cache/file cleanup."""
        if self.fd>=0:os.close(self.fd);self.fd=-1

    def _check_root(self):
        need(self.fd>=0 and self.guard() is not False and self.path.resolve(strict=True)==self.path)
        original=os.fstat(self.fd);current=self.path.lstat()
        need(node(original)==node(current)==self.root and stat.S_ISDIR(current.st_mode)
             and current.st_uid==os.geteuid() and stat.S_IMODE(current.st_mode)==0o700)

    def _exists(self,name):
        self._check_root()
        try:os.stat(name,dir_fd=self.fd,follow_symlinks=False);return True
        except FileNotFoundError:return False

    def _read(self,name,limit):
        self._check_root();descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=self.fd)
        try:
            before=os.fstat(descriptor)
            need(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600
                 and before.st_uid==os.geteuid() and before.st_nlink==1 and 0<before.st_size<=limit)
            raw=b''
            while len(raw)<=limit:
                part=os.read(descriptor,limit+1-len(raw))
                if not part:break
                raw+=part
            current=os.stat(name,dir_fd=self.fd,follow_symlinks=False)
            need(stamp(before)==stamp(os.fstat(descriptor))==stamp(current) and len(raw)==before.st_size)
            self._check_root();return raw,before
        finally:os.close(descriptor)

    def _check_source(self):
        raw,info=self._read(SOURCE,4096)
        need(stamp(info)==self.source_stamp and hashlib.sha256(raw).hexdigest()==self.source_sha
             and self.released(node(info)) is False)

    def _owned(self):
        self._check_root();value=self.store.read()
        exact(value,{'actorFilesVersion','binding','root','source','sourceStamp','sourceSha256','runId',
                     'pending','request','commandStamp','result','closing','removed'})
        need(type(value['actorFilesVersion']) is int and value['actorFilesVersion']==VERSION
             and value['binding']==self.binding and value['root']==self.root and value['source']==self.source
             and value['sourceStamp']==self.source_stamp and value['sourceSha256']==self.source_sha
             and type(value['closing']) is bool and type(value['removed']) is bool
             and (not value['removed'] or value['closing']))
        need(value['runId'] is None or type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId']))
        for key in ('pending','request'):
            if value[key] is not None:
                command(value[key]);need(value[key]['runId']==value['runId'])
        if value['commandStamp'] is not None:
            exact(value['commandStamp'],{'device','inode','size','mtimeNs','ctimeNs'})
            identity({k:value['commandStamp'][k] for k in ('device','inode')})
            need(all(integer(value['commandStamp'][k],0,2**63-1) for k in ('size','mtimeNs','ctimeNs')) and value['request'] is not None)
        if value['result'] is not None:
            result=value['result'];exact(result,{'stamp','sha256','commandId','retired'})
            exact(result['stamp'],{'device','inode','size','mtimeNs','ctimeNs'})
            identity({k:result['stamp'][k] for k in ('device','inode')})
            need(all(integer(result['stamp'][k],0,2**63-1) for k in ('size','mtimeNs','ctimeNs'))
                 and type(result['sha256']) is str and re.fullmatch('[0-9a-f]{64}',result['sha256'])
                 and type(result['commandId']) is str and re.fullmatch('[0-9a-f]{32}',result['commandId'])
                 and type(result['retired']) is bool)
        return value

    def _check_command(self,value):
        need(value['request'] is not None and value['commandStamp'] is not None)
        raw,info=self._read(COMMAND,2048)
        need(stamp(info)==value['commandStamp'] and raw==encode(value['request']))

    def send(self,request):
        command(request);self._check_source();previous=self._owned()
        need(not previous['closing'] and previous['pending'] is None and previous['runId'] in (None,request['runId'])
             and (previous['request'] is None or request['commandId']!=previous['request']['commandId']))
        if previous['request'] is not None:self._check_command(previous)
        else:need(not self._exists(COMMAND))
        # A journal write failure cannot be followed by even a query mutation.
        pending={**previous,'runId':request['runId'],'pending':deepcopy(request)};self.store.write(pending,previous)
        need(self.store.read()==pending)
        temporary='.chat-command-'+uuid.uuid4().hex
        descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.fd)
        try:
            raw=encode(request);need(len(raw)<=2048)
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            self._check_source()
            fence=getattr(self,'phase_fence',None)
            if fence is not None and request['operation']!='inspect':fence.check()
            if previous['request'] is None:
                os.link(temporary,COMMAND,src_dir_fd=self.fd,dst_dir_fd=self.fd,follow_symlinks=False)
                os.unlink(temporary,dir_fd=self.fd)
            else:
                self._check_command(previous)
                if fence is not None and request['operation']!='inspect':fence.check()
                os.replace(temporary,COMMAND,src_dir_fd=self.fd,dst_dir_fd=self.fd)
            actual,info=self._read(COMMAND,2048);need(actual==raw);os.fsync(self.fd)
            self.store.write({**pending,'pending':None,'request':deepcopy(request),'commandStamp':stamp(info)},pending)
        finally:
            try:os.unlink(temporary,dir_fd=self.fd)
            except FileNotFoundError:pass

    def read(self):
        self._check_source();previous=self._owned();need(previous['pending'] is None and not previous['closing'])
        if not self._exists(RESULT):
            need(previous['result'] is None);return None
        raw,info=self._read(RESULT,131072);envelope=decode(raw.decode('utf-8'))
        exact(envelope,{'actorFileVersion','commandNode','resultNode','native'})
        need(type(envelope['actorFileVersion']) is int and envelope['actorFileVersion']==VERSION
             and identity(envelope['resultNode'])==node(info));identity(envelope['commandNode'])
        frame=envelope['native'];need(type(frame) is dict and previous['request'] is not None)
        if frame.get('commandId')!=previous['request']['commandId']:
            # Only the original, previously acquired reply may remain while the
            # native timer processes a new query. Never adopt a foreign nonce.
            old=previous['result'];need(old is not None and old['stamp']==stamp(info)
                and old['sha256']==hashlib.sha256(raw).hexdigest() and old['commandId']==frame.get('commandId'))
            return encode(frame).decode('utf-8')
        self._check_command(previous)
        need(envelope['commandNode']=={k:previous['commandStamp'][k] for k in ('device','inode')})
        validate(frame,previous['request'],self.pid,self.clock_ms())
        need(frame['instance']==self.source['instance'] and frame['capturedEpochMs']>=self.source['configuredEpochMs']
             and self.released(node(info)) is False)
        result=dict(stamp=stamp(info),sha256=hashlib.sha256(raw).hexdigest(),commandId=frame['commandId'],
                    retired=frame['source']['retired'] and not frame['source']['scopePresent'] and frame['source']['events']==[])
        if previous['result']!=result:self.store.write({**previous,'result':result},previous)
        return encode(frame).decode('utf-8')

    def reconcile_pending(self,request):
        """Consume only the original actually processed pending transaction.

        No command write, input dispatch, unlink or result relabel occurs here.
        Unknown/unpublished/old replies keep their original pending journal.
        """
        command(request);need(not request['commandId'].startswith('ios-'))
        started=self.monotonic();need(number(started,0,1e15))
        self._check_source();previous=self._owned()
        need(not previous['closing'] and previous['pending']==request and previous['runId']==request['runId'])
        command_raw,command_info=self._read(COMMAND,2048);need(command_raw==encode(request))
        raw,info=self._read(RESULT,131072);envelope=decode(raw.decode('utf-8'))
        exact(envelope,{'actorFileVersion','commandNode','resultNode','native'})
        need(type(envelope['actorFileVersion']) is int and envelope['actorFileVersion']==VERSION
            and identity(envelope['commandNode'])==node(command_info) and identity(envelope['resultNode'])==node(info))
        frame=envelope['native'];validate(frame,request,self.pid,self.clock_ms())
        need(frame['chatVersion']==3 and frame['instance']==self.source['instance']
            and frame['capturedEpochMs']>=self.source['configuredEpochMs'] and self.released(node(info)) is False)
        source=frame['source']
        if request['operation']=='observe':need(source['scopePresent'] and source['openedCommandId']==request['commandId'])
        elif request['operation']=='retire':need(source['retired'] and not source['scopePresent'] and source['retiredCommandId']==request['commandId'])
        if previous['commandStamp'] is not None:
            # Original publication replaces the old node atomically. Its new
            # temporary inode exists before replacement; it cannot be the old
            # still-linked command inode even when bytes happen to match.
            need(node(command_info)!={key:previous['commandStamp'][key] for key in ('device','inode')})
        result=dict(stamp=stamp(info),sha256=hashlib.sha256(raw).hexdigest(),commandId=frame['commandId'],
            retired=source['retired'] and not source['scopePresent'] and source['events']==[])
        # Check the exact current originals again before consuming only this
        # pending publication. A copied/rewritten/foreign result is not a receipt.
        current_command,current_command_info=self._read(COMMAND,2048);current,current_info=self._read(RESULT,131072)
        need(current_command==command_raw and stamp(current_command_info)==stamp(command_info)
            and current==raw and stamp(current_info)==stamp(info) and self.store.read()==previous)
        self._check_source();fresh(frame['capturedEpochMs'],self.clock_ms())
        need(number(self.monotonic(),started,started+1.5) and self.released(node(info)) is False)
        updated={**previous,'pending':None,'request':deepcopy(request),'commandStamp':stamp(command_info),'result':result}
        self.store.write(updated,previous);need(self.store.read()==updated)
        # Copy before the last actual clock/guard/FD checks, never after them.
        value=encode(frame).decode('utf-8');self._check_source()
        after_command,after_command_info=self._read(COMMAND,2048);after,after_info=self._read(RESULT,131072)
        need(after_command==command_raw and stamp(after_command_info)==stamp(command_info)
            and after==raw and stamp(after_info)==stamp(info) and self.store.read()==updated and self.released(node(info)) is False)
        measured=self.monotonic();need(number(measured,started,started+1.5));epoch=self.clock_ms();fresh(frame['capturedEpochMs'],epoch)
        ended=self.monotonic();need(number(ended,measured,started+1.5)
            and epoch-frame['capturedEpochMs']+math.ceil((ended-measured)*1000)<=1500)
        return value

    def close(self):
        """After the owned cache's actual retirement, remove original IPC only.

        The global actor/source/root remains owned by the enclosing fixture.
        Closing an actor transport is never full feature cleanup by itself.
        """
        self._check_source();previous=self._owned();need(previous['pending'] is None)
        if not previous['closing']:
            frame=decode(self.read());previous=self._owned()
            need(previous['request']['operation'] in ('inspect','retire') and previous['result']['retired']
                 and frame['source']['retired'] and not frame['source']['scopePresent'])
            closing={**previous,'closing':True};self.store.write(closing,previous);previous=closing
        if not previous['removed']:
            self._check_command(previous)
            raw,info=self._read(RESULT,131072)
            need(stamp(info)==previous['result']['stamp'] and hashlib.sha256(raw).hexdigest()==previous['result']['sha256'])
            # The durable closing intent precedes deletion. A crash between an
            # unlink and its journal update remains unresolved, never adoption.
            os.unlink(RESULT,dir_fd=self.fd)
            os.unlink(COMMAND,dir_fd=self.fd);os.fsync(self.fd)
            updated={**previous,'removed':True};self.store.write(updated,previous);previous=updated
        need(not self._exists(COMMAND) and not self._exists(RESULT))
        started=prior=self.monotonic();need(number(started,0,1e15))
        for attempt in range(31):
            self._check_source()
            if self.released({k:previous['result']['stamp'][k] for k in ('device','inode')}) is True:
                self._check_source();need(not self._exists(COMMAND) and not self._exists(RESULT))
                self.store.discard(previous);self.detach();return
            now=self.monotonic();need(number(now,0,1e15) and prior<=now);prior=now
            if now-started>=1.5 or attempt==30:break
            self.sleep(min(.05,1.5-(now-started)))
        raise NativeUIError('Native Chat actor still retains its original result file')
