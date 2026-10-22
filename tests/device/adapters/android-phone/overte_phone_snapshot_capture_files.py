"""Owned original capture files, using the existing private Snapshot transport.

Native IDs select original files; no caller pathname is a delete authority.
Target and host journals retain partial outputs and one-send cleanup intent.
The supported namespace is exclusive to the cooperating normal capture producer.
POSIX stat/unlink cannot exclude an arbitrary external rename between calls.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import uuid

from adapters.android_snapshot_files import AndroidSnapshotFiles
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from overte_phone_script_lock import PhoneScriptSourceLock,PhoneScriptSourceBusy
from overte_phone_snapshot_capture_source import prefix,nonce,path as native_path
from snapshot_observation import MAX_BYTES

SCAN_SCRIPT=r'''
[ -d files ] && [ ! -L files ] && [ -r files ] && [ -x files ] || exit 1
capture_uid=$(id -u) || exit 1
[ "$(stat -c %u files)" = "$capture_uid" ] || exit 1
capture_root=files/Snapshots
printf 'OVT_CAPTURE_SCAN_V1\n'
if [ ! -e "$capture_root" ] && [ ! -L "$capture_root" ]; then
    printf 'absent\nOVT_CAPTURE_SCAN_END_V1\n'; exit 0
fi
[ -d "$capture_root" ] && [ ! -L "$capture_root" ] && [ -r "$capture_root" ] && [ -x "$capture_root" ] || exit 1
capture_root_meta=$(stat -c '%d:%i:%u' "$capture_root") || exit 1
[ "$(stat -c %u "$capture_root")" = "$capture_uid" ] || exit 1
printf '%s\n' "$capture_root_meta"
capture_count=0
for capture_path in "$capture_root"/"$1"-*; do
    if [ ! -e "$capture_path" ] && [ ! -L "$capture_path" ]; then continue; fi
    [ -f "$capture_path" ] && [ ! -L "$capture_path" ] || exit 1
    capture_count=$((capture_count + 1)); [ "$capture_count" -le 64 ] || exit 1
    capture_meta=$(stat -c '%d:%i:%s:%u:%h' "$capture_path") || exit 1
    [ "$(stat -c %u "$capture_path")" = "$capture_uid" ] && [ "$(stat -c %h "$capture_path")" = 1 ] || exit 1
    [ "$(stat -c %s "$capture_path")" -le "$2" ] || exit 1
    capture_sha=$(sha256sum "$capture_path") || exit 1
    [ "$(stat -c '%d:%i:%s:%u:%h' "$capture_path")" = "$capture_meta" ] || exit 1
    capture_sha=${capture_sha%% *}; capture_name=${capture_path##*/}
    printf '%s\t%s\t%s\n' "$capture_name" "$capture_meta" "$capture_sha"
done
[ "$(stat -c '%d:%i:%u' "$capture_root")" = "$capture_root_meta" ] || exit 1
printf 'OVT_CAPTURE_SCAN_END_V1\n'
'''.strip()


class CaptureFileTransport(AndroidSnapshotFiles):
    def scan(self,name):
        need(prefix(name));raw=self._execute(SCAN_SCRIPT,name,str(MAX_BYTES))
        need(type(raw) is bytes and len(raw)<=32768)
        lines=raw.decode('ascii').splitlines()
        need(len(lines)>=3 and lines[0]=='OVT_CAPTURE_SCAN_V1' and lines[-1]=='OVT_CAPTURE_SCAN_END_V1')
        if lines[1]=='absent':need(len(lines)==3);return dict(root=None,files={})
        def numbers(value,count):
            parts=value.split(':');need(len(parts)==count and all(re.fullmatch('[0-9]{1,20}',item) for item in parts))
            return [int(item) for item in parts]
        device,inode,uid=numbers(lines[1],3);need(inode>0)
        result={};need(len(lines)<=67)
        for line in lines[2:-1]:
            parts=line.split('\t');need(len(parts)==3)
            basename,values,digest=parts
            need(re.fullmatch(re.escape(name)+r'-[A-Za-z0-9_-]{1,160}\.(png|jpg|gif)',basename) and basename not in result
                and re.fullmatch('[0-9a-f]{64}',digest))
            dev,ino,size,user,links=numbers(values,5)
            need(ino>0 and user==uid and links==1 and 0<=size<=MAX_BYTES)
            result[basename]=dict(device=dev,inode=ino,bytes=size,uid=user,links=links,sha256=digest)
        return dict(root=dict(device=device,inode=inode,uid=uid),files=result)


class PhoneSnapshotCaptureFiles:
    """A separate persisted scope is required for foundation and extended runs.

    The caller serializes the shared probe source channel. This instance locks
    only its ownership journal, never recursively locks that shared channel.
    Native terminal/file-close and namespace seals supplement, rather than
    replace, the public facade's render/encoder/native-Core quiet checks.
    """
    def __init__(self,transport,source,binding,owner_path,*,read_only=False,clock_ms=None):
        need(isinstance(transport,AndroidSnapshotFiles) and type(read_only) is bool)
        self.transport,self.source,self.context=transport,source,deepcopy(context(binding))
        need(str(source.pid)==self.context['processIdentity'].split(':')[0] and source.read_only==read_only)
        self.store=PrivateFeatureState(owner_path);self.store._parent()
        self.lock=PhoneScriptSourceLock(str(owner_path)+'.lock');self.read_only=read_only
        self.clock_ms=clock_ms or source.clock_ms;self.state=None

    @contextmanager
    def held(self):
        try:
            with self.lock.held():
                self.transport._check();self.state=self.store.read()
                if self.state is not None:self.validate(self.state)
                yield
                self.transport._check()
        except PhoneScriptSourceBusy:raise
        except Exception:raise NativeUIError('Original Phone Snapshot file ownership or retirement is unavailable') from None

    def validate(self,value):
        exact(value,{'snapshotCaptureOwnerVersion','binding','scope','native','plans','rows','artifacts','artifactRoot','readOnly','retired'})
        need(type(value['snapshotCaptureOwnerVersion']) is int and value['snapshotCaptureOwnerVersion']==1
            and context(value['binding'])==self.context and nonce(value['scope']) and value['readOnly'] is self.read_only
            and type(value['retired']) is bool)
        exact(value['native'],{'instance','sourceInstance'})
        need(all(nonce(item) for item in value['native'].values()))
        exact(value['artifactRoot'],{'device','inode'});info=self.transport.artifacts.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o077
            and integer(value['artifactRoot']['device']) and integer(value['artifactRoot']['inode'],1)
            and (info.st_dev,info.st_ino)==(value['artifactRoot']['device'],value['artifactRoot']['inode']))
        for key in ('plans','rows','artifacts'):need(type(value[key]) is dict and len(value[key])<=64)
        for name,row in value['plans'].items():
            exact(row,{'id','issued','sealId','sealIssued','original'})
            need(prefix(name) and nonce(row['id']) and type(row['issued']) is bool and type(row['sealIssued']) is bool
                and (row['sealId']=='' or nonce(row['sealId'])) and (not row['sealIssued'] or nonce(row['sealId'])))
            need(row['original'] is None or type(row['original']) is dict and row['original'].get('id')==row['id'])
        for id,row in value['rows'].items():
            exact(row,{'original','retireId','issued'})
            need(nonce(id) and type(row['original']) is dict and row['original'].get('id')==id
                and row['original'].get('runId')==value['scope'] and type(row['issued']) is bool
                and (row['retireId']=='' or nonce(row['retireId'])) and (not row['issued'] or nonce(row['retireId'])))
        for id,row in value['artifacts'].items():
            exact(row,{'name','bytes','sha256','phase','file','removeIntent'})
            need(id in value['rows'] and row['name']=='snapshot-owned-'+value['scope']+'-'+id+'.bin'
                and integer(row['bytes'],1,MAX_BYTES) and re.fullmatch('[0-9a-f]{64}',row['sha256'])
                and row['phase'] in ('planned','opened','saved','removed') and type(row['removeIntent']) is bool
                and (row['phase']!='removed' or row['removeIntent']))
            if row['phase']=='planned':need(row['file'] is None)
            else:
                exact(row['file'],{'device','inode'});need(integer(row['file']['device']) and integer(row['file']['inode'],1))

    def save(self):
        self.validate(self.state);before=self.store.read();need(before is None or before['binding']==self.context)
        self.store.write(self.state,before)

    def observe(self,scope=None):
        scope=scope or self.state['scope'];need(nonce(scope));packet=self.source.request(scope)
        if self.state is not None:
            need(self.state['scope']==scope and self.state['native']==dict(instance=packet['instance'],sourceInstance=packet['source']['instance']))
            plans={row['id']:row for row in packet['source']['plans']}
            rows={row['id']:row for row in packet['source']['rows']}
            changed=False
            for item in self.state['plans'].values():
                current=plans.get(item['id'])
                if item['original'] is not None:
                    need(current is not None and all(current[key]==value for key,value in item['original'].items() if key not in ('sealed','sealId','sealedEpochMs')))
                    if item['original']['sealed']:need(item['original']==current)
                if current is not None:
                    if self.read_only and current['sealed'] and not item['sealId']:item['sealId']=current['sealId'];changed=True
                    need(current['runId']==scope and (not current['sealed'] or current['sealId']==item['sealId']))
                    if item['original']!=current:item['original']=deepcopy(current);changed=True
            for id,item in self.state['rows'].items():
                old=item['original'];new=rows.get(id);need(new is not None)
                fixed=('id','captureId','path','planId','runId','preexisting','rootDevice','rootInode','createdEpochMs')
                need(all(old[key]==new[key] for key in fixed))
                if old['opened']:need(new['opened'] and all(old[key]==new[key] for key in ('device','inode','uid','links')))
                if old['closed']:need(new['closed'] and all(old[key]==new[key] for key in ('bytes','sha256','closedEpochMs')))
                if self.read_only and new['retireId'] and not item['retireId']:item['retireId']=new['retireId'];changed=True
                if new['retireId']:need(new['retireId']==item['retireId'] and (item['issued'] or self.read_only))
                if old['retireId']:need(new['retireId']==old['retireId'] and new['absent'])
                if old!=new:item['original']=deepcopy(new);changed=True
            for id,row in rows.items():
                if row['runId']!=scope:continue
                need(row['planId'] in plans and any(item['id']==row['planId'] for item in self.state['plans'].values()) and not row['preexisting'])
                if id not in self.state['rows']:
                    need(not row['retireId'] or self.read_only);self.state['rows'][id]=dict(original=deepcopy(row),retireId=row['retireId'] if self.read_only else '',issued=False);changed=True
            if changed:self.save()
        return packet

    def plan(self,scope,name):
        with self.held():
            need(not self.read_only and nonce(scope) and prefix(name))
            if self.state is None:
                packet=self.observe(scope)
                self.state=dict(snapshotCaptureOwnerVersion=1,binding=self.context,scope=scope,
                    native=dict(instance=packet['instance'],sourceInstance=packet['source']['instance']),plans={},rows={},artifacts={},
                    artifactRoot=self.artifact_root(),readOnly=False,retired=False)
                self.save()
            need(self.state['scope']==scope and not self.state['retired']);self.observe()
            if name not in self.state['plans']:
                need(not self.transport.scan(name)['files'])
                self.state['plans'][name]=dict(id=uuid.uuid4().hex,issued=False,sealId='',sealIssued=False,original=None);self.save()
            item=self.state['plans'][name]
            if item['original'] is None and not item['issued']:
                need(not self.transport.scan(name)['files']);item['issued']=True;self.save()
                self.source.request(scope,'plan',prefix=name,operation_id=item['id'])
            packet=self.observe();item=self.state['plans'][name];need(item['original'] is not None and not item['original']['sealed'])
            # Retrying a durable preflight can find later *owned* captures. A
            # second input is never inferred or sent by this file owner.
            self.inventories(packet)
            return deepcopy(item['original'])

    @staticmethod
    def root(plan,scan):
        if plan['rootPresent']:
            need(scan['root'] is not None and all(scan['root'][key]==plan['root'+key.capitalize()] for key in ('device','inode')))

    def inventories(self,packet):
        results={}
        for name,item in self.state['plans'].items():
            need(item['original'] is not None);scan=self.transport.scan(name);self.root(item['original'],scan)
            rows=[row for row in packet['source']['rows'] if row['planId']==item['id']]
            if rows:
                need(scan['root'] is not None and all(scan['root']['device']==row['rootDevice'] and scan['root']['inode']==row['rootInode'] for row in rows))
            known={Path(row['path']).name:row for row in rows};need(len(known)==len(rows))
            need(set(scan['files'])<=set(known))
            for basename,metadata in scan['files'].items():
                row=known[basename];need(row['opened'] and not row['retireId'] and not row['nativeRemoved']
                    and scan['root'] is not None and scan['root']['device']==row['rootDevice'] and scan['root']['inode']==row['rootInode'])
                need(all(metadata[key]==row[key] for key in ('device','inode','uid','links')))
                if row['closed']:need(all(metadata[key]==row[key] for key in ('bytes','sha256')))
            for basename,row in known.items():
                if row['opened'] and not row['nativeRemoved'] and not row['retireId']:need(basename in scan['files'])
            if item['original']['sealed']:need(not scan['files'])
            results[name]=scan
        return results

    def inventory(self):
        with self.held():
            need(self.state is not None);packet=self.observe();scans=self.inventories(packet)
            return dict(files=[dict(basename=name,**meta) for scan in scans.values() for name,meta in scan['files'].items()],
                rows=deepcopy([item['original'] for item in self.state['rows'].values()]),capturedEpochMs=packet['capturedEpochMs'])

    def host_path(self,row):
        result=self.transport.artifacts/row['name'];PrivateFeatureState(result)._parent();return result

    def artifact_root(self):
        info=self.transport.artifacts.lstat();need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o077)
        return dict(device=info.st_dev,inode=info.st_ino)

    def host_read(self,row,*,partial=False):
        path=self.host_path(row);need(row['phase'] in ('opened','saved') and row['file'] is not None)
        with os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)),'rb') as stream:
            before=os.fstat(stream.fileno());current=path.lstat()
            def signature(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid()
                and stat.S_IMODE(before.st_mode)==0o600 and before.st_size<=row['bytes']
                and (before.st_dev,before.st_ino)==(row['file']['device'],row['file']['inode']) and signature(before)==signature(current))
            content=stream.read(MAX_BYTES+1);need(signature(before)==signature(os.fstat(stream.fileno()))==signature(path.lstat()))
        need(len(content)==before.st_size)
        if not partial:need(len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256'])
        return content

    def publish(self,id,content):
        digest=hashlib.sha256(content).hexdigest();need(1<=len(content)<=MAX_BYTES)
        row=self.state['artifacts'].get(id)
        if row is None:
            row=dict(name='snapshot-owned-'+self.state['scope']+'-'+id+'.bin',bytes=len(content),sha256=digest,phase='planned',file=None,removeIntent=False)
            self.state['artifacts'][id]=row;self.save()
        need(row['bytes']==len(content) and row['sha256']==digest and not row['removeIntent'] and row['phase']!='removed')
        path=self.host_path(row)
        if row['phase']=='planned':
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            with os.fdopen(descriptor,'wb') as stream:
                original=os.fstat(stream.fileno());row.update(phase='opened',file=dict(device=original.st_dev,inode=original.st_ino));self.save()
                need(stream.write(content)==len(content));stream.flush();os.fsync(stream.fileno())
        elif row['phase']=='opened':
            original=self.host_read(row,partial=True);need(content.startswith(original))
            with os.fdopen(os.open(path,os.O_WRONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)),'wb') as stream:
                info=os.fstat(stream.fileno());need((info.st_dev,info.st_ino)==(row['file']['device'],row['file']['inode']))
                need(stream.seek(len(original))==len(original) and stream.write(content[len(original):])==len(content)-len(original));stream.flush();os.fsync(stream.fileno())
        need(self.host_read(row)==content);row['phase']='saved';self.save();return row['name']

    def acquire(self,path,captureId):
        with self.held():
            need(self.state is not None and native_path(path) and type(captureId) is str and not self.state['retired'])
            packet=self.observe();scans=self.inventories(packet)
            captures=[row for row in packet['source']['captures'] if row['captureId']==captureId and row['terminal']=='complete'];need(len(captures)==1)
            matches=[(id,item['original']) for id,item in self.state['rows'].items() if item['original']['path']==path and item['original']['captureId']==captureId]
            need(len(matches)==1);id,row=matches[0];need(row['opened'] and row['closed'] and not row['retireId'] and not row['nativeRemoved'] and row['bytes']>0)
            name=next(name for name,item in self.state['plans'].items() if item['id']==row['planId'])
            meta=scans[name]['files'][Path(path).name];content=self.transport._read(Path(path).name)
            need(self.transport._matches(meta,content))
            after=self.observe();need(next(item for item in after['source']['rows'] if item['id']==id)==row)
            need(self.inventories(after)[name]['files'][Path(path).name]==meta)
            artifact=self.publish(id,content);epoch=self.clock_ms();need(integer(epoch,after['capturedEpochMs']))
            return dict(path=path,captureId=captureId,bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),device=meta['device'],inode=meta['inode'],
                artifact=artifact,capturedEpochMs=epoch,nativeClosedEpochMs=row['closedEpochMs'],fileId=id,source='snapshot-capture-original')

    def files(self,name,*,allow_pending=False):
        with self.held():
            need(type(allow_pending) is bool and self.state is not None and name in self.state['plans']);packet=self.observe();scan=self.inventories(packet)[name]
            rows=[row for row in packet['source']['rows'] if row['planId']==self.state['plans'][name]['id'] and Path(row['path']).name in scan['files']]
            # The existing foundation polls for a complete output set. A
            # genuinely pending original descriptor/capture may yield no yet
            # qualified outputs, while its full original inventory remains in
            # this durable owner. This option is never used for preflight or
            # strict extended acquire, and errors/foreign originals stay red.
            if allow_pending:
                captures={row['captureId']:row for row in packet['source']['captures']}
                if any(not row['closed'] or captures[row['captureId']]['terminal']=='' for row in rows):return dict(files=[])
            return dict(files=[dict(basename=Path(row['path']).name,artifact=self.acquire(row['path'],row['captureId'])['artifact']) for row in rows])

    def binding(self):
        with self.held():
            need(self.state is not None);self.observe()
            return dict(snapshotCaptureBindingVersion=1,binding=deepcopy(self.context),scope=self.state['scope'],native=deepcopy(self.state['native']),
                plans={name:deepcopy(item['original']) for name,item in self.state['plans'].items()})

    def attach(self,binding):
        with self.held():
            need(self.read_only);exact(binding,{'snapshotCaptureBindingVersion','binding','scope','native','plans'})
            need(type(binding['snapshotCaptureBindingVersion']) is int and binding['snapshotCaptureBindingVersion']==1 and binding['binding']==self.context
                and nonce(binding['scope']) and type(binding['plans']) is dict and binding['plans'])
            if self.state is None:
                self.state=dict(snapshotCaptureOwnerVersion=1,binding=self.context,scope=binding['scope'],native=deepcopy(binding['native']),
                    plans={name:dict(id=row['id'],issued=False,sealId=row['sealId'],sealIssued=False,original=deepcopy(row)) for name,row in binding['plans'].items()},
                    rows={},artifacts={},artifactRoot=self.artifact_root(),readOnly=True,retired=False);self.save()
            need(self.state['scope']==binding['scope'] and self.state['native']==binding['native'])
            self.observe();return self.binding()

    def remove_host(self,row):
        path=self.host_path(row)
        if row['phase']=='planned':
            try:path.lstat()
            except FileNotFoundError:return
            need(False)
        if row['phase']=='removed':need(not path.exists() and not path.is_symlink());return
        try:self.host_read(row)
        except FileNotFoundError:need(row['removeIntent']);row['phase']='removed';self.save();return
        row['removeIntent']=True;self.save();path.unlink();need(not path.exists() and not path.is_symlink());row['phase']='removed';self.save()

    def retire(self):
        with self.held():
            need(self.state is not None);packet=self.observe();self.inventories(packet)
            need(all(row['terminal']!='' for row in packet['source']['captures']) and all(row['closed'] for row in packet['source']['rows']))
            # Resolve an interrupted *owned* publication from a fresh binary
            # acquisition before retiring its target original. Missing/mutated
            # saved files and unqualified planned collisions cannot be adopted.
            for id,row in list(self.state['artifacts'].items()):
                if row['phase']=='opened' and not row['removeIntent']:
                    original=self.state['rows'][id]['original'];self.acquire(original['path'],original['captureId'])
                elif row['phase']=='saved':
                    try:self.host_read(row)
                    except FileNotFoundError:need(row['removeIntent'])
                elif row['phase']=='planned':need(not self.host_path(row).exists() and not self.host_path(row).is_symlink())
            # Nested acquire refreshes self.state. Iterate its durable records.
            if not self.read_only:
                for id,item in self.state['rows'].items():
                    row=item['original']
                    if not item['retireId']:item['retireId']=uuid.uuid4().hex;self.save()
                    if not row['retireId'] and not item['issued']:
                        item['issued']=True;self.save();self.source.request(self.state['scope'],'retire',file_id=id,operation_id=item['retireId'])
                    self.observe();need(item['original']['retireId']==item['retireId'] and item['original']['absent'])
                for name,item in self.state['plans'].items():
                    if not item['sealId']:item['sealId']=uuid.uuid4().hex;self.save()
                    if not item['original']['sealed'] and not item['sealIssued']:
                        item['sealIssued']=True;self.save();self.source.request(self.state['scope'],'seal',file_id=item['id'],operation_id=item['sealId'])
                    self.observe();need(item['original']['sealed'] and item['original']['sealId']==item['sealId'])
            for row in self.state['artifacts'].values():self.remove_host(row)
            self.require_retired();self.state['retired']=True;self.save()

    def require_retired(self):
        with self.held():
            need(self.state is not None);packet=self.observe();scans=self.inventories(packet)
            need(all(row['terminal']!='' for row in packet['source']['captures']) and all(row['closed'] for row in packet['source']['rows'])
                and all(not scan['files'] for scan in scans.values()) and all(item['original']['sealed'] for item in self.state['plans'].values())
                and all(item['original']['retireId'] and item['original']['absent'] for item in self.state['rows'].values()))
            for row in self.state['artifacts'].values():
                need(row['phase'] in ('planned','removed'));path=self.host_path(row);need(not path.exists() and not path.is_symlink())
            # Unknown late names are obligations, never silently adopted or
            # deleted. Other scopes may share this private artifact directory.
            with os.scandir(self.transport.artifacts) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    need(not entry.name.startswith('snapshot-owned-'+self.state['scope']+'-'))
            return dict(retired=True,capturedEpochMs=packet['capturedEpochMs'],scope=self.state['scope'])
