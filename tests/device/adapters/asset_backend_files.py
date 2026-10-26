"""Private original IPC for an already owned native Assets backend.

An immutable host journal precedes delivery. Uncertain queries are observed,
never resent; rereading historical bytes never supplies a fresh acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid
from adapters import asset_backend_source as source
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same

VERSION=1
ADMISSION='asset-backend-admission.json'
CURRENT='asset-backend-query.json'
LIMIT=2097152


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def kernel(value,*,directory=False):
    result=dict(device=str(value.st_dev),inode=str(value.st_ino),uid=str(value.st_uid),mode=str(stat.S_IMODE(value.st_mode)),links=str(value.st_nlink),
        modifiedSeconds=str(value.st_mtime_ns//10**9),modifiedNanoseconds=str(value.st_mtime_ns%10**9),changedSeconds=str(value.st_ctime_ns//10**9),changedNanoseconds=str(value.st_ctime_ns%10**9))
    if not directory:result['bytes']=str(value.st_size)
    return result


class AssetsBackendFiles:
    """One run, original native source and append-only durable host journal.

process.guard() must requalify the actual owned PID/start/boot/executable/role,
source environment and owner. This transport starts or stops no process and
unlinks no original. detach() releases only its own directory descriptors.
"""
    def __init__(self,process,journal,run_id,*,epoch_ms=lambda:int(time.time()*1000),monotonic_ms=lambda:int(time.monotonic()*1000)):
        need(type(run_id) is str and re.fullmatch('[0-9a-f]{32}',run_id) is not None and callable(epoch_ms) and callable(monotonic_ms))
        self.process,self.path,self.journal,self.run_id=process,Path(process.path),Path(journal),run_id
        self.epoch_ms,self.monotonic_ms=epoch_ms,monotonic_ms;self.fd=self.journal_fd=-1;self.last_clock=None;self.rows=[];self.references=[]
        need(self.process.guard() is True and self.journal.is_absolute() and self.journal.resolve(strict=True)==self.journal
            and self.journal!=self.path and self.path not in self.journal.parents and self.journal not in self.path.parents)
        try:
            self.fd,self.root=self._open_root(self.path);self.journal_fd,self.journal_root=self._open_root(self.journal)
            raw,reference=self._read(self.fd,ADMISSION,8192);self.admission=source.admission(source.object_bytes(raw,8192),pid=process.pid,owner=process.owner_sha256)
            need(same(self.admission['sourceRootIdentity'],self.root));self.admission_ref=reference;self.admission_sha=reference['sha256']
            data=Path(self.admission['dataRoot']);need(data!=self.journal and data not in self.journal.parents and self.journal not in data.parents)
            self._restore()
            if not self.rows:
                need(self._names(self.fd)==[ADMISSION])
                self._append(dict(tag='bound',runId=run_id,processIdentity=process.process_identity,ownerSha256=process.owner_sha256,
                    executableSha256=process.sha256,root=self.root,journalRoot=self.journal_root,admission=reference))
            self._history();self.guard()
        except BaseException:self.detach();raise

    def _open_root(self,path):
        need(path.is_absolute() and path.resolve(strict=True)==path);fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            info=os.fstat(fd);need(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700 and info.st_uid==os.geteuid());return fd,{key:kernel(info,directory=True)[key] for key in ('device','inode')}
        except BaseException:os.close(fd);raise

    def _roots(self):
        need(self.process.guard() is True)
        for path,fd,identity in ((self.path,self.fd,self.root),(self.journal,self.journal_fd,self.journal_root)):
            need(fd>=0 and path.resolve(strict=True)==path);opened,current=os.fstat(fd),path.lstat()
            need(stat.S_ISDIR(current.st_mode) and current.st_uid==os.geteuid() and stat.S_IMODE(current.st_mode)==0o700
                and all(str(getattr(info,'st_'+key))==identity[field] for info in (opened,current) for key,field in (('dev','device'),('ino','inode'))))

    @staticmethod
    def _names(fd):
        # A directory FD can retain its enumeration offset after listdir().
        # A fresh open-file description starts every census at the beginning.
        scan=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
        try:names=sorted(os.listdir(scan));need(len(names)<=1024);return names
        finally:os.close(scan)

    def _read(self,root,name,limit):
        self._roots();need(type(name) is str and '/' not in name and name not in ('','.','..'));fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=root)
        try:
            before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1 and 0<before.st_size<=limit)
            raw=b''
            while len(raw)<=limit:
                part=os.read(fd,min(65536,limit+1-len(raw)))
                if not part:break
                raw+=part
            current=os.stat(name,dir_fd=root,follow_symlinks=False)
            need(stat.S_ISREG(current.st_mode) and kernel(before)==kernel(os.fstat(fd))==kernel(current) and len(raw)==before.st_size)
            self._roots();return raw,dict(name=name,identity=kernel(before),sha256=hashlib.sha256(raw).hexdigest())
        finally:os.close(fd)

    def _write(self,root,name,raw):
        self._roots();need(type(raw) is bytes and 0<len(raw)<=65536);fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=root)
        try:
            offset=0
            while offset<len(raw):
                count=os.write(fd,raw[offset:]);need(count>0);offset+=count
            os.fsync(fd)
        finally:os.close(fd)
        os.fsync(root);actual,reference=self._read(root,name,65536);need(actual==raw);return reference

    def _restore(self):
        names=self._names(self.journal_fd);need(len(names)<=512)
        for index,name in enumerate(names,1):
            need(name==f'asset-backend-host-{index:06d}.json');raw,reference=self._read(self.journal_fd,name,65536);row=source.object_bytes(raw,65536)
            exact(row,{'assetsBackendHostJournalVersion','sequence','previousSha256','event'})
            need(type(row['assetsBackendHostJournalVersion']) is int and row['assetsBackendHostJournalVersion']==VERSION
                and type(row['sequence']) is int and row['sequence']==index and row['previousSha256']==(self.references[-1]['sha256'] if self.references else None))
            self.rows.append(row);self.references.append(reference)

    def _append(self,event):
        self._roots();need(len(self.rows)<512)
        row=dict(assetsBackendHostJournalVersion=VERSION,sequence=len(self.rows)+1,previousSha256=self.references[-1]['sha256'] if self.references else None,event=deepcopy(event))
        reference=self._write(self.journal_fd,f'asset-backend-host-{len(self.rows)+1:06d}.json',encode(row));self.rows.append(row);self.references.append(reference)

    def _now(self):
        value=dict(hostEpochMs=self.epoch_ms(),hostMonotonicMs=self.monotonic_ms())
        need(all(integer(item,1) for item in value.values()) and (self.last_clock is None or all(value[key]>=self.last_clock[key] for key in value)))
        self.last_clock=deepcopy(value);return value

    def _history(self):
        need(bool(self.rows));header=self.rows[0]['event'];exact(header,{'tag','runId','processIdentity','ownerSha256','executableSha256','root','journalRoot','admission'})
        need(header==dict(tag='bound',runId=self.run_id,processIdentity=self.process.process_identity,ownerSha256=self.process.owner_sha256,
            executableSha256=self.process.sha256,root=self.root,journalRoot=self.journal_root,admission=self.admission_ref))
        pending=None;latest=None;seen=set();last_host=None
        for row in self.rows[1:]:
            event=row['event'];need(type(event) is dict);tag=event.get('tag')
            if tag=='intent':
                exact(event,{'tag','query','hostClock'});need(pending is None);source.query(event['query'],self.admission)
                need(event['query']['runId']==self.run_id and event['query']['commandId'] not in seen);seen.add(event['query']['commandId']);pending=deepcopy(event)
            elif tag=='published':
                exact(event,{'tag','requestId','command','hostClock'});need(pending is not None and event['requestId']==pending['query']['commandId'] and 'command' not in pending)
                exact(event['command'],{'name','identity','sha256'});source.stat(event['command']['identity'])
                need(event['command']['name']==CURRENT and event['command']['sha256']==hashlib.sha256(encode(pending['query'])).hexdigest());pending['command']=event['command']
            elif tag=='acquired':
                exact(event,{'tag','requestId','intent','original','saved','hostBefore','hostClock'});need(pending is not None and event['requestId']==pending['query']['commandId'])
                packet=self._packet(pending['query'],event);source.accept(latest,packet);latest=deepcopy(packet);pending=None
                self._host_clock(event['hostBefore'],last_host);self._host_clock(event['hostClock'],event['hostBefore'])
            else:need(False)
            self._host_clock(event['hostClock'],last_host);last_host=event['hostClock']
        self.pending,self.latest=pending,latest
        if self.last_clock is None:self.last_clock=deepcopy(last_host)
        elif last_host is not None:self._host_clock(self.last_clock,last_host)

    @staticmethod
    def _host_clock(value,previous):
        exact(value,{'hostEpochMs','hostMonotonicMs'});need(all(integer(item,1) for item in value.values()))
        if previous is not None:need(all(value[key]>=previous[key] for key in value))

    def _packet(self,query,event=None):
        name=query['commandId'];intent_raw,intent=self._read(self.fd,'asset-backend-query-'+name+'.json',4096);need(intent_raw==encode(query))
        raw,original=self._read(self.fd,'asset-backend-original-'+name+'.json',LIMIT);packet=source.object_bytes(raw,LIMIT);source.observation(packet,query,self.admission,self.admission_sha)
        saved_raw,saved=self._read(self.fd,'asset-backend-saved-'+name+'.json',8192);receipt=source.object_bytes(saved_raw,8192);source.saved(receipt,packet,raw)
        need(receipt['original']['identity']==original['identity'])
        if event is not None:need(all(same(event[key],value) for key,value in (('intent',intent),('original',original),('saved',saved))))
        return packet if event is not None else (packet,dict(intent=intent,original=original,saved=saved))

    def guard(self):
        self._roots();raw,reference=self._read(self.fd,ADMISSION,8192);need(reference==self.admission_ref and same(source.object_bytes(raw,8192),self.admission))
        need(self._names(self.journal_fd)==[reference['name'] for reference in self.references])
        for row,expected in zip(self.rows,self.references):
            raw,actual=self._read(self.journal_fd,expected['name'],65536);need(actual==expected and same(source.object_bytes(raw,65536),row))
        self._history();return True

    def send(self,query):
        """Save intent then deliver once. A thrown exception leaves that intent."""
        self.guard();source.query(query,self.admission);need(query['runId']==self.run_id and self.pending is None)
        previous_queries=[row['event']['query'] for row in self.rows if row['event']['tag']=='intent'];seen=[row['commandId'] for row in previous_queries];need(query['commandId'] not in seen and len(seen)<128)
        try:old,old_ref=self._read(self.fd,CURRENT,4096)
        except FileNotFoundError:need(not seen);old_ref=None
        else:
            need(bool(seen) and same(source.object_bytes(old,4096),previous_queries[-1]))
            published=[row['event']['command'] for row in self.rows if row['event']['tag']=='published' and row['event']['requestId']==seen[-1]]
            if published:need(old_ref==published[-1])
        self._append(dict(tag='intent',query=query,hostClock=self._now()));self._history()
        temporary='asset-backend-publish-'+query['commandId']+'.json';raw=encode(query);self._write(self.fd,temporary,raw)
        self.guard()
        if old_ref is None:
            os.link(temporary,CURRENT,src_dir_fd=self.fd,dst_dir_fd=self.fd,follow_symlinks=False);os.unlink(temporary,dir_fd=self.fd)
        else:
            _,actual=self._read(self.fd,CURRENT,4096);need(actual==old_ref);os.replace(temporary,CURRENT,src_dir_fd=self.fd,dst_dir_fd=self.fd)
        os.fsync(self.fd);actual,reference=self._read(self.fd,CURRENT,4096);need(actual==raw)
        self._append(dict(tag='published',requestId=query['commandId'],command=reference,hostClock=self._now()));self._history()

    def poll(self):
        """Acquire only a pending query; completed originals remain historical."""
        self.guard()
        if self.pending is None:return None
        before=self._now();query=self.pending['query'];name='asset-backend-saved-'+query['commandId']+'.json'
        try:os.stat(name,dir_fd=self.fd,follow_symlinks=False)
        except FileNotFoundError:return None
        packet,references=self._packet(query);source.accept(self.latest,packet)
        self._append(dict(tag='acquired',requestId=query['commandId'],**references,hostBefore=before,hostClock=self._now()));self._history();return deepcopy(packet)

    def historical(self):
        """Revalidate retained bytes, without assigning them any current clock."""
        self.guard();return deepcopy(self.latest)

    def export(self,request_id):
        """Return exact original bytes plus their retained acquisition brackets.

        Exporting is an original read, never a new sample or a clock refresh.
        All four source records are independently reread and inode-qualified.
        """
        self.guard();matches=[row['event'] for row in self.rows if row['event']['tag']=='acquired' and row['event']['requestId']==request_id]
        need(len(matches)==1);event=matches[0];result={}
        for key,reference in (('admission',self.admission_ref),('intent',event['intent']),('original',event['original']),('saved',event['saved'])):
            raw,actual=self._read(self.fd,reference['name'],LIMIT if key=='original' else 8192);need(actual==reference)
            result[key]=dict(reference=actual,base64=base64.b64encode(raw).decode('ascii'))
        return dict(assetBackendExportVersion=VERSION,processIdentity=self.process.process_identity,executableSha256=self.process.sha256,
            hostBefore=event['hostBefore'],hostAfter=event['hostClock'],**result)

    def detach(self):
        for key in ('fd','journal_fd'):
            fd=getattr(self,key)
            if fd>=0:os.close(fd);setattr(self,key,-1)
