"""Read actual passive AssetServer originals from its exclusive private file.

No backend state is inferred from commands, fixture inputs or server ACKs.
The original process/identity/freshness and every filesystem boundary are checked
on each read. This reader never starts a process or changes server mappings.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import re
import stat
import time
import uuid

from adapters.native_feature_observation import exact,integer,need,fresh
from feature_journeys.contract import identifier,json_document
from fixture.messages_mixer import start_identity


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def original(value,*,domain=None,process=None,epoch=None):
    exact(value,{'assetsBakeOriginalsVersion','instance','sequence','processId','processStart','domainId','assetServerId','capturedEpochMs','contextCapturedEpochMs','valid','jobs','mappings','blobs','pending'})
    need(type(value['assetsBakeOriginalsVersion']) is int and value['assetsBakeOriginalsVersion']==2 and value['valid'] is True)
    identifier(value['instance']);need(integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and type(value['processStart']) is str and value['processStart'].isdecimal())
    for key in ('domainId','assetServerId'):need(str(uuid.UUID(value[key]))==value[key] and uuid.UUID(value[key]).int!=0)
    need(domain is None or value['domainId']==domain)
    need(process is None or (value['processId'],value['processStart'])==(process.pid,start_identity(process.pid)))
    need(integer(value['capturedEpochMs'],1));captured=value['capturedEpochMs']
    need(integer(value['contextCapturedEpochMs'],1,captured))
    if epoch is not None:fresh(captured,epoch);fresh(value['contextCapturedEpochMs'],epoch)
    need(type(value['jobs']) is list and len(value['jobs'])<=64 and type(value['mappings']) is list and len(value['mappings'])<=4096
        and type(value['blobs']) is list and len(value['blobs'])<=4096 and integer(value['pending'],0,64))
    seen=set();pending=0
    for row in value['jobs']:
        exact(row,{'instance','hash','path','version','queuedEpochMs','startedEpochMs','runExitedEpochMs','ovenProcessId','ovenFinishedEpochMs','exitCode','exitStatus','terminalEpochMs','outcome','destroyedEpochMs'})
        identifier(row['instance']);need(row['instance'] not in seen);seen.add(row['instance'])
        need(digest(row['hash']) and type(row['path']) is str and row['path'].startswith('/') and integer(row['version'],0,65535) and integer(row['queuedEpochMs'],1,captured))
        if row['startedEpochMs'] is not None:need(integer(row['startedEpochMs'],row['queuedEpochMs'],captured))
        if row['runExitedEpochMs'] is not None:need(row['startedEpochMs'] is not None and integer(row['runExitedEpochMs'],row['startedEpochMs'],captured))
        if row['ovenProcessId'] is not None:need(row['startedEpochMs'] is not None and integer(row['ovenProcessId'],1))
        if row['ovenFinishedEpochMs'] is not None:need(row['ovenProcessId'] is not None and integer(row['ovenFinishedEpochMs'],row['startedEpochMs'],captured) and integer(row['exitCode'],-2**31,2**31-1) and integer(row['exitStatus'],0,1))
        else:need(row['exitCode'] is None and row['exitStatus'] is None)
        if row['terminalEpochMs'] is None:need(row['outcome'] is None);pending+=1
        else:need(integer(row['terminalEpochMs'],row['queuedEpochMs'],captured) and row['outcome'] in ('complete','failed','aborted'))
        if row['outcome']=='complete':need(row['ovenFinishedEpochMs'] is not None and row['exitCode']==0 and row['exitStatus']==0 and row['terminalEpochMs']>=row['ovenFinishedEpochMs'])
        if row['destroyedEpochMs'] is not None:need(row['terminalEpochMs'] is not None and integer(row['destroyedEpochMs'],row['terminalEpochMs'],captured))
    # All actual pending tasks must have one retained original. A lost or
    # destroyed task cannot disappear into a fabricated empty worker count.
    need(pending==value['pending'])
    for key,fields in (('mappings',{'path','hash'}),('blobs',{'hash','actualSha256','bytes'})):
        names=set()
        for row in value[key]:
            exact(row,fields);name=row['path'] if key=='mappings' else row['hash'];need(name not in names);names.add(name)
            need(digest(row['hash']))
            if key=='mappings':need(type(name) is str and len(name)<=1024 and name.startswith('/') and not name.endswith('/') and '\\' not in name and all(part not in ('','.','..') for part in name[1:].split('/')))
            else:need(row['actualSha256']==row['hash'] and integer(row['bytes'],1,1048576))
    return value


class AssetsOriginals:
    def __init__(self,directory,process,owned,domain,*,clock_ms=lambda:time.time_ns()//1000000):
        self.path=Path(directory);self.process,self.owned,self.domain,self.clock_ms=process,owned,domain,clock_ms
        self.start=start_identity(process.pid);self.root=self.path.lstat();self.file=None;self.last=None
        self._directory()
    def _directory(self):
        value=self.path.lstat();need(stat.S_ISDIR(value.st_mode) and not self.path.is_symlink() and value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o700
            and (value.st_dev,value.st_ino)==(self.root.st_dev,self.root.st_ino))
    def _process(self):
        need(self.process.poll() is None and self.owned(self.process.pid) is True and start_identity(self.process.pid)==self.start)
        raw=(Path('/proc')/str(self.process.pid)/'cmdline').read_bytes().split(b'\0')
        need(raw.count(b'-t')==1 and raw[raw.index(b'-t')+1]==b'3' and raw.count(b'--server-port')==1 and b'--pool' not in raw and b'--testScript' not in raw)
    def read(self,command):
        exact(command,{'schemaVersion','runId'});need(type(command['schemaVersion']) is int and command['schemaVersion']==1);identifier(command['runId'])
        self._directory();self._process()
        root=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            need((os.fstat(root).st_dev,os.fstat(root).st_ino)==(self.root.st_dev,self.root.st_ino))
            fd=os.open('assets-bakes.json',os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=root)
            try:
                fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB);info=os.fstat(fd);path=os.stat('assets-bakes.json',dir_fd=root,follow_symlinks=False)
                need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1 and stat.S_IMODE(info.st_mode)==0o600
                    and (info.st_dev,info.st_ino)==(path.st_dev,path.st_ino) and 0<info.st_size<=1048576)
                if self.file is not None:need((info.st_dev,info.st_ino)==self.file)
                raw=os.read(fd,1048577);after=os.fstat(fd);need(len(raw)==info.st_size and (info.st_size,info.st_mtime_ns,info.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns))
            finally:os.close(fd)
        finally:os.close(root)
        value=original(json_document(raw),domain=self.domain,process=self.process,epoch=self.clock_ms())
        self._directory();self._process()
        if self.last is not None:
            need(value['instance']==self.last['instance'] and value['assetServerId']==self.last['assetServerId'] and value['sequence']>=self.last['sequence'] and value['capturedEpochMs']>=self.last['capturedEpochMs'])
            need(len(value['jobs'])>=len(self.last['jobs']))
            for before,after in zip(self.last['jobs'],value['jobs']):
                need(all(after[key]==item for key,item in before.items() if item is not None))
        self.file=(info.st_dev,info.st_ino);self.last=deepcopy(value)
        return dict(schemaVersion=1,runId=command['runId'],source=deepcopy(value))
