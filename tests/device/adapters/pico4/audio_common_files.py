"""Original Audio file primitive with Pico archive custody and original OFDs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import hashlib
import stat
from adapters.original_audio_files import OriginalAudioFiles
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.native_fd_owner import OriginalDescriptor
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_fd_owner import require_directory
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical
from feature_journeys.contract import json_document

VERSION=2
MAX_WAVE=11*48000*2*2+44


class AudioEvidenceOriginal(ClosedOriginalFile):
    """The existing original-OFD carrier with the bounded PC WAV extent."""
    def read(self,validate=None):
        need(not self.failed and self.active is None)
        owner=None
        try:
            self.parent_guard()
            owner=self.active=object.__new__(OriginalDescriptor)
            OriginalDescriptor.__init__(owner,self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            info=os.fstat(owner.fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==self.mode
                and info.st_nlink==1 and 0<info.st_size<=MAX_WAVE)
            raw=os.pread(owner.fd,MAX_WAVE+1,0);original=signature(info)
            need(len(raw)==info.st_size and signature(self.path.lstat())==signature(os.fstat(owner.fd))==original)
            if self.stamp is not None:need(original==self.stamp and raw==self.raw)
            if validate is not None:validate(raw)
            self.parent_guard();owner.require(owner.fd)
            need(signature(self.path.lstat())==signature(os.fstat(owner.fd))==original)
            need(owner.close());self.active=None
            if self.stamp is None:self.stamp,self.raw=original,raw
            return raw,original
        except BaseException as error:
            self.failed=True;self.first_failure=(error,error.__traceback__)
            if owner is not None:
                try:
                    if owner.close():self.active=None
                except BaseException as closing:self.close_failure=(closing,closing.__traceback__)
            raise


class PicoAudioCommonFiles1:
    def __init__(self,actor):
        self.actor=actor;self.root=actor.store.path.parent
        self.scope=dict(audioCommonFilesVersion=VERSION,runId=actor.recipe.run,
            binding=deepcopy(actor.recipe.binding),originalActorHeader=deepcopy(actor.header_ref))
        self.scope_sha=json_digest(self.scope)
        self.store=PrivateFeatureState(self.root/'audio-common-files.json')
        self.state=None;self.physical=None;self.pins={};self.uncertain=[];self.operation=None;self.failed=False;self.failure=None
        try:
            with actor.raw_lock.held():
                self.archive_guard();need(self.store.read() is None)
                self.physical=object.__new__(LifecycleProcessFile);LifecycleProcessFile.__init__(self.physical,self.store)
                self.physical.write(dict(scope=self.scope,files=[]),None);self.state=deepcopy(self.store.read())
                self.files=OriginalAudioFiles(self.root,actor.recipe.run,'primary',self.intent,self.guard,actor.recipe.binding)
        except BaseException as error:self.poison(error);raise

    def poison(self,error):
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True;self.actor.raws.stopped=True

    def archive_guard(self):
        self.actor.raw_identity();require_directory(self.actor.raws.directory,self.root)
        need(not self.failed and json_digest(self.scope)==self.scope_sha)

    def guard(self):
        with self.actor.raw_lock.held():
            self.archive_guard();self.physical.guard();need(self.store.read()==self.state)

    def value(self,row):
        value=deepcopy(row['record']);value['provenance']=json_document(self.actor.raws.literal(row['provenance']))
        return value

    def intent(self,value):
        self.guard();need(self.operation is not None)
        compact=deepcopy(value);compact.pop('provenance')
        old=[row for row in self.state['files'] if row['record']['name']==value['name']];need(len(old)<=1)
        row=dict(record=compact,provenance=deepcopy(self.operation['provenance']),
            physical=None if not old else old[0]['physical'],
            retirement=None if not old else deepcopy(old[0]['retirement']))
        rows=deepcopy(self.state['files'])
        if old:rows[rows.index(old[0])]=row
        else:need(len(rows)<64);rows.append(row)
        body=dict(scope=deepcopy(self.scope),files=rows);need(len(canonical(body))+1<=65536)
        self.physical.write(body,self.state);self.state=deepcopy(body)

    def saved(self,source_id,kind):
        rows=[row for row in self.state['files'] if row['record']['sourceId']==source_id and row['record']['kind']==kind]
        need(len(rows)<=1);return None if not rows else rows[0]

    def write(self,ticket,kind,source_id,raw,provenance):
        try:
            with self.actor.raw_lock.held():
                self.guard();need(self.operation is None and type(raw) is bytes and 0<len(raw)<=11*48000*2*2+44)
                old=self.saved(source_id,kind)
                if old is not None:
                    value=self.value(old);need(self.read(value['name'])==raw);return value
                # The frozen file primitive receives already acquired original
                # bytes. Book the additional copy/file overlap before its IO.
                token=self.actor.raws.reserve('audio-common-file',dict(ticket=ticket,kind=kind,sourceId=source_id),1,side_bytes=2*len(raw))
                encoded=canonical(provenance).decode('utf-8');need(len(encoded.encode())<=262144)
                source_token=self.actor.raws.reserve('audio-common-file-provenance',dict(ticket=ticket,kind=kind,sourceId=source_id),262144)
                ref=self.actor.raws.retain(source_token,encoded)
                self.operation=dict(provenance=ref,token=token)
                value=self.files.write(ticket,kind,source_id,raw,provenance)
                pin=AudioEvidenceOriginal(self.root/value['name'],0o600,self.guard);self.pins[value['name']]=pin
                body,physical=pin.read();need(body==raw and physical==value['file']['signature'])
                rows=deepcopy(self.state['files']);row=next(row for row in rows if row['record']['name']==value['name'])
                row['physical']=physical;updated=dict(scope=deepcopy(self.scope),files=rows)
                self.physical.write(updated,self.state);self.state=deepcopy(updated)
                self.actor.raws.retain(token,None);self.operation=None;self.guard();return value
        except BaseException as error:self.poison(error);raise

    def read(self,name):
        try:
            with self.actor.raw_lock.held():
                self.guard();rows=[row for row in self.state['files'] if row['record']['name']==name];need(len(rows)==1)
                row=rows[0];value=self.value(row);need(value['phase']=='saved' and row['physical'] is not None and name in self.pins)
                raw,physical=self.pins[name].read();need(physical==row['physical']);self.files.content(value,raw)
                self.guard();return raw
        except BaseException as error:self.poison(error);raise

    def retire(self,name):
        """Preserve exact original WAV in the same bank before export deletion."""
        try:
            with self.actor.raw_lock.held():
                self.guard();need(self.operation is None)
                rows=[row for row in self.state['files'] if row['record']['name']==name];need(len(rows)==1)
                old=rows[0]
                if old['record']['phase']=='retired':
                    retirement=old['retirement'];need(type(retirement) is dict)
                    digest=hashlib.sha256();size=0
                    for reference in retirement['rawReferences']:
                        part=self.actor.raws.literal(reference);need(type(part) is bytes)
                        digest.update(part);size+=len(part)
                    need(size==retirement['bytes']==old['record']['bytes']
                        and digest.hexdigest()==retirement['sha256']==old['record']['sha256']
                        and not (self.root/name).exists() and not (self.root/name).is_symlink()
                        and self.pins[name].close())
                    self.guard();return self.value(old)
                need(old['record']['phase']=='saved' and old['retirement'] is None)
                raw=self.read(name);references=[]
                # Every exact retained source chunk stays charged after the
                # named export goes away. Unknown progress remains sticky.
                self.operation=dict(provenance=deepcopy(old['provenance']),retirement=references)
                for offset in range(0,len(raw),65536):
                    part=raw[offset:offset+65536]
                    command=dict(name=name,offset=offset,bytes=len(part),original=deepcopy(old['physical']))
                    token=self.actor.raws.reserve('audio-common-file-retirement',command,len(part),side_bytes=2*len(raw))
                    references.append(self.actor.raws.retain(token,part))
                updated=deepcopy(self.state)
                row=next(row for row in updated['files'] if row['record']['name']==name)
                row['retirement']=dict(rawReferences=deepcopy(references),bytes=len(raw),sha256=row['record']['sha256'])
                need(len(canonical(updated))+1<=65536)
                self.physical.write(updated,self.state);self.state=deepcopy(updated)
                value=self.files.retire(self.value(row))
                need(value['phase']=='retired' and not (self.root/name).exists()
                    and self.pins[name].close())
                self.operation=None;self.guard();return value
        except BaseException as error:self.poison(error);raise

    def close_host(self):
        owners=[*self.pins.values(),*self.uncertain]
        results=[owner.close() for owner in owners]
        if self.physical is not None:results.append(self.physical.close_host())
        return all(results)
