"""Durable private copy of the actual native Create export, never a generator.

The complete owner must prove paired product/native/file quiet before retiring
this host artifact. A lost copy/removal remains owned; it is not overwritten or
reported as a newly captured product file after reconstruction.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import os
import re
import secrets
import stat

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.create_export import exported

VERSION=1


class CreateExportArtifact:
    def __init__(self,store,lock,root,binding,run,guard):
        from pathlib import Path
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard))
        self.store,self.lock,self.root,self.binding,self.run,self.guard=store,lock,Path(root),deepcopy(context(binding)),identifier(run),guard
        need(lock.path==store.path.with_name('script-feature-sources.lock') and self.root.is_absolute() and self.root.resolve(strict=True)==self.root)
        PrivateFeatureState(self.root/'create-export-root-check')._parent();lock.assert_held();self.previous=store.read()
        self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self):
        return dict(iosCreateExportArtifactVersion=VERSION,binding=self.binding,runId=self.run,root=str(self.root),payload=pack([self.state]))
    def decode(self,value):
        exact(value,{'iosCreateExportArtifactVersion','binding','runId','root','payload'})
        need(type(value['iosCreateExportArtifactVersion']) is int and value['iosCreateExportArtifactVersion']==VERSION and same(value['binding'],self.binding)
            and value['runId']==self.run and value['root']==str(self.root));rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','name','originals','measurement','file'})
        need(state['phase'] in ('planned','opened','copied','removing','removed') and type(state['name']) is str
            and re.fullmatch('create-export-'+self.run+r'-[a-f0-9]{32}\.json',state['name']))
        originals=state['originals'];exact(originals,{'baseline','current','model','ownedId','afterNative'})
        need(originals['model']['runId']==self.run and originals['model']['processId']==int(self.binding['processIdentity']))
        need(same(state['measurement'],exported(originals['baseline'],originals['current'],originals['model'],originals['ownedId'],after_native=originals['afterNative'])))
        if state['file'] is not None:
            exact(state['file'],{'device','inode'});need(integer(state['file']['device'],0) and integer(state['file']['inode'],1))
        if state['phase'] in ('opened','copied','removing'):need(state['file'] is not None)
        return state
    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def identity(self,descriptor):
        need(self.state['file'] is not None);PrivateFeatureState(self.root/self.state['name'])._parent()
        before,current=os.fstat(descriptor),(self.root/self.state['name']).lstat()
        for row in (before,current):
            need(stat.S_ISREG(row.st_mode) and row.st_nlink==1 and row.st_uid==os.geteuid() and stat.S_IMODE(row.st_mode)==0o600
                and 0<=row.st_size<=65536 and row.st_dev==self.state['file']['device'] and row.st_ino==self.state['file']['inode'])
        return before
    def capture(self,baseline,current,model,owned_id,*,after_native):
        self.bound();need(self.state is None)
        measured=exported(baseline,current,model,owned_id,after_native=after_native)
        self.state=dict(phase='planned',name='create-export-'+self.run+'-'+secrets.token_hex(16)+'.json',
            originals=dict(baseline=deepcopy(baseline),current=deepcopy(current),model=deepcopy(model),ownedId=owned_id,afterNative=after_native),
            measurement=measured,file=None);self.save()
        descriptor=os.open(self.root/self.state['name'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as stream:
            info=os.fstat(stream.fileno());self.state.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino));self.save();self.identity(stream.fileno())
            raw=base64.b64decode(measured['base64'],validate=True);need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self.identity(stream.fileno())
        self.state['phase']='copied';self.save();need(self.read()==raw);return deepcopy(self.state)
    def read(self,*,partial=False):
        self.bound();need(self.state is not None and self.state['file'] is not None and self.state['phase']!='removed')
        descriptor=os.open(self.root/self.state['name'],os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            before=self.identity(stream.fileno());raw=stream.read(65537);after=self.identity(stream.fileno())
            need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        original=base64.b64decode(self.state['measurement']['base64'],validate=True)
        need(original.startswith(raw) if partial else raw==original)
        if not partial:need(len(raw)==self.state['measurement']['bytes'] and hashlib.sha256(raw).hexdigest()==self.state['measurement']['sha256'])
        return raw
    def remove(self):
        """Enclosing complete owner must first prove paired actual quiet."""
        self.bound();need(self.state is not None)
        if self.state['phase'] in ('removing','removed'):return self.recover_removal()
        if self.state['phase']=='planned':
            try:(self.root/self.state['name']).lstat()
            except FileNotFoundError:
                self.state['phase']='removed';self.save();return {'performed':True}
            raise NativeUIError('Host export creation has no recorded inode; ownership remains unresolved')
        need(self.state['phase'] in ('opened','copied'));partial=self.state['phase']=='opened';self.read(partial=partial)
        self.state['phase']='removing';self.save()
        # Journal IO is another scheduling boundary. Re-admit the actual inode
        # and bytes immediately before this one owned unlink.
        self.read(partial=partial);(self.root/self.state['name']).unlink()
        return self.recover_removal()
    def recover_removal(self):
        self.bound();need(self.state['phase'] in ('removing','removed'))
        try:(self.root/self.state['name']).lstat()
        except FileNotFoundError:pass
        else:raise NativeUIError('Original host export removal is unresolved; no unlink is repeated')
        self.state['phase']='removed';self.save();return {'performed':True}
