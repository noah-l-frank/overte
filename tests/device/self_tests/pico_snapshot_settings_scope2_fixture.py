"""Source2 extension of the existing ordinary Snapshot fixture.

Actual Python factories/Session/archive/binary SDK entry execute. Qt settings,
JNI/native process, typed Qt streams and shell dispatch remain declared models.
This supplies no fabricated restoration, upload, OS chooser or GPU success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
from types import MethodType
from unittest.mock import patch

from adb_transport import AdbTransport
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from adapters.pico4.snapshot_settings_originals import ACTION
from adapters.pico4.snapshot_settings_transport import HEAD,TAIL,READ_SCRIPT
from adapters.script_journey.history import canonical
from test_snapshot_settings_baseline import BaselineBoundary


class Scope2Boundary(BaselineBoundary):
    def __init__(self,test,**options):
        super().__init__(test,**options)
        self.sdk_calls=[];self.outputs=[];self.fault=None;self.native_copies=[]
        self.test=test;self.raw_duration=None;self.duration_value=-0.0
        self.endpoint=self.h.adb.app/'files/overte-e2e/feature-pico-snapshot-settings-originals.json'
        self.endpoint.parent.mkdir(mode=0o700,exist_ok=True);self.endpoint.parent.chmod(0o700)
        self.command_originals=self.endpoint.parent/'scope2-command-originals';self.command_originals.mkdir(mode=0o700)
        original_write=self.h.adb.write_debug_app_file
        def write(target,package,path,text):
            command=json.loads(text)
            if path==ANDROID_CONTROL_COMMAND and command.get('action')==ACTION:
                assert command.get('settingsScope')==2
                original_write(target,package,path,text)
                initialized=self.h.adb.captures>0
                # Actual Manager::loadSetting uses _settings[key]: a missing
                # duration becomes present with an invalid QVariant on first
                # Handle.get(), while the independent handle remains unset.
                source=self.packet['source'];present=self.raw_duration is not None or initialized
                source['durationEntry']=dict(present=present,original=self.typed(self.raw_duration,absent=not present))
                source['durationCache']=dict(initialized=initialized,set=False,
                    value=self.typed(self.duration_value),defaultValue=self.typed(4.0))
                self.packet['snapshotSettingsOriginalsVersion']=2
                # The bytes deliberately identify the Qt serialization model;
                # they are not described as actual QDataStream evidence.
                blob=b'declared-qt-typed-stream-model:'+canonical({key:value for key,value in source.items()
                    if key in ('entries','formatCache','durationEntry','durationCache')})
                source['typedSerializedBase64']=base64.b64encode(blob).decode();source['typedSha256']=hashlib.sha256(blob).hexdigest()
                self.endpoint.write_bytes(canonical(self.packet));self.endpoint.chmod(0o600)
                raw=canonical(command);self.native_copies.append(raw)
                saved=self.command_originals/(command['commandId']+'.json');saved.write_bytes(raw);saved.chmod(0o600)
                return
            return original_write(target,package,path,text)
        self.original_run=subprocess.run
        original_binary=self.h.adb.execute_bytes
        self.binary_backend=AdbTransport('declared-snapshot-settings2-sdk-never-executed')
        def binary(_sdk,args,**options):
            words=shlex.split(args[1]) if len(args)==2 and args[0]=='exec-out' else []
            if len(words)>5 and words[4]==READ_SCRIPT and words[5]=='overte-snapshot-settings2':
                return self.binary_backend.execute_bytes(args,**options)
            return original_binary(args,**options)
        for change in (patch.object(self.h.adb,'write_debug_app_file',side_effect=write),
                patch.object(self.h.adb,'execute_bytes',MethodType(binary,self.h.adb)),
                patch('adb_transport.subprocess.run',side_effect=self.sdk)):
            change.start();test.addCleanup(change.stop)
        # Retain actual private originals even after negative or failed runs.
        temporary=self.h.h.h.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None

    @staticmethod
    def typed(value,*,absent=False):
        if value is None:type_id,name,raw=0,None,b'declared-invalid-qvariant-model'
        elif type(value) is str:type_id,name,raw=10,'QString',b'declared-QString-model:'+value.encode()
        else:type_id,name,raw=38,'float',b'declared-float-model:'+struct.pack('>f',value)
        return dict(present=not absent,typeId=type_id,typeName=name,base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())

    @staticmethod
    def stamp(path):
        value=path.stat()
        def date(ns):return datetime.fromtimestamp(ns//10**9,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')+f'.{ns%10**9:09d} +0000'
        return f'{value.st_dev} {value.st_ino} {value.st_mode:x} {value.st_uid} {value.st_nlink} {value.st_size} {date(value.st_mtime_ns)} {date(value.st_ctime_ns)}'

    def sdk(self,args,**options):
        if not args or args[0]!='declared-snapshot-settings2-sdk-never-executed':return self.original_run(args,**options)
        assert args[1:4]==['-s',self.h.adb.target,'exec-out'] and len(args)==5
        assert 'text' not in options and 'input' not in options
        words=shlex.split(args[4]);assert words[:4]==['run-as','org.overte.pico','sh','-c']
        assert words[4]==READ_SCRIPT and words[5]=='overte-snapshot-settings2' and len(words)==11
        pid,start,requested,deadline,nonce=words[6:]
        assert pid+':'+start==self.h.adb.identity and int(deadline)-int(requested)==1500
        self.sdk_calls.append(dict(commandId=nonce,timeout=options['timeout']))
        data=self.endpoint.read_bytes();description=self.stamp(self.endpoint).encode('ascii')
        output=HEAD+nonce.encode()+b'\n'+description+b'\n'+data+TAIL+nonce.encode()+b'\n'+description+b'\n'
        if self.fault is not None:output=self.fault(output,nonce)
        self.outputs.append(output)
        return subprocess.CompletedProcess(args,0,stdout=output,stderr=b'')

    def wire_bytes(self,raw,nonce):
        self.endpoint.write_bytes(raw);self.endpoint.chmod(0o600)
        description=self.stamp(self.endpoint).encode('ascii')
        return HEAD+nonce.encode()+b'\n'+description+b'\n'+raw[:65537]+TAIL+nonce.encode()+b'\n'+description+b'\n'

    def attach(self):
        return self.h.adapter._snapshot_settings_scope2_baseline(self.h.adb.target,self.parent.run,self.h.phase,
            parent=self.parent,source_lock=self.h.lock)
