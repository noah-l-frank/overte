"""Selected standalone Photos artifact bytes; the product reader stays strict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import plistlib
import stat
import zipfile
from adapters.native_feature_observation import need
from ios.adapters.bundle_identity import name,root_digest,compare,MAX_NODES,MAX_BYTES,MAX_FILE,MAX_PLIST,EMPTY
from execution_identity import file_digest


def ascii_name(value):
    need(name(value)==value and value.isascii());return value


def artifact(path,sha256):
    """Read a stable final archive, preserving signatures and provisioning bytes.

    This structurally checks selected bytes. It does not verify an Apple code
    signature or qualify packaging, signing, installation or hardware.
    """
    import re
    need(type(sha256) is str and re.fullmatch('[0-9a-f]{64}',sha256));path=Path(path)
    need(path.is_absolute() and path.resolve()==path and file_digest(path)==sha256)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(descriptor,'rb') as stream:
        before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_nlink==1)
        digest=hashlib.sha256()
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
        need(digest.hexdigest()==sha256);stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            infos=archive.infolist();need(0<len(infos)<=MAX_NODES)
            roots=set();seen=set()
            for info in infos:
                original=info.filename[:-1] if info.is_dir() else info.filename;ascii_name(original)
                need(original not in seen and info.flag_bits&1==0);seen.add(original)
                if original.startswith('Payload/'):
                    parts=original.split('/');need(len(parts)>=2 and parts[1].endswith('.app'))
                    roots.add('/'.join(parts[:2])+'/')
            need(len(roots)==1);root=next(iter(roots));need(root!='Payload/Overte.app/')
            entries={};info_bytes=None;expanded=0
            for member in infos:
                raw=member.filename[:-1] if member.is_dir() else member.filename
                if raw in ('Payload',root[:-1]):need(member.is_dir() and member.file_size==0);continue
                if not raw.startswith(root):continue
                relative=ascii_name(raw[len(root):]);mode=stat.S_IFMT(member.external_attr>>16)
                need(mode in ({0,stat.S_IFDIR} if member.is_dir() else {0,stat.S_IFREG}))
                parts=relative.split('/')
                for index in range(1,len(parts)):
                    parent='/'.join(parts[:index]);need(parent not in entries or entries[parent]==('D',0,EMPTY));entries[parent]=('D',0,EMPTY)
                if member.is_dir():
                    need(member.file_size==0 and (relative not in entries or entries[relative]==('D',0,EMPTY)))
                    entries[relative]=('D',0,EMPTY);continue
                need(relative not in entries and 0<=member.file_size<=MAX_FILE);expanded+=member.file_size;need(expanded<=MAX_BYTES)
                count=0;digest=hashlib.sha256();chunks=[]
                with archive.open(member) as original:
                    for block in iter(lambda:original.read(1024*1024),b''):
                        count+=len(block);need(count<=member.file_size);digest.update(block)
                        if relative=='Info.plist':need(count<=MAX_PLIST);chunks.append(block)
                need(count==member.file_size);entries[relative]=('F',count,digest.digest())
                if relative=='Info.plist':info_bytes=b''.join(chunks)
            need(info_bytes is not None);info=plistlib.loads(info_bytes);need(type(info) is dict)
            need(type(info.get('OVTSnapshotCompanionContractVersion')) is int and info['OVTSnapshotCompanionContractVersion']==1
                and info.get('OVTSnapshotCompanionRole')=='photos' and info.get('UIFileSharingEnabled') is True
                and info.get('CFBundlePackageType')=='APPL')
            executable=ascii_name(info.get('CFBundleExecutable'));need('/' not in executable and executable in entries and entries[executable][0]=='F')
            identity=dict(bundleContractVersion=1,bundleId=info.get('CFBundleIdentifier'),executableSha256=entries[executable][2].hex(),**root_digest(entries));compare(identity,identity)
            result=dict(snapshotCompanionArtifactVersion=1,role='photos',artifactSha256=sha256,appRoot=root,bundle=identity)
        after=os.fstat(stream.fileno());need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
    need(file_digest(path)==sha256);return result
