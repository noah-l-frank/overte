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


def artifact(path,sha256):return _artifact(path,sha256,'photos')


def share_artifact(path,sha256):return _artifact(path,sha256,'share-archive')


def _artifact(path,sha256,role):
    """Read a stable final archive, preserving signatures and provisioning bytes.

    This structurally checks selected bytes. It does not verify an Apple code
    signature or qualify packaging, signing, installation or hardware.
    """
    import re
    need(role in ('photos','share-archive') and type(sha256) is str and re.fullmatch('[0-9a-f]{64}',sha256));path=Path(path)
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
            entries={};info_bytes=None;extension_plists={};expanded=0
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
                        if relative=='Info.plist' or role=='share-archive' and re.fullmatch(r'PlugIns/[^/]+\.appex/Info\.plist',relative):
                            need(count<=MAX_PLIST);chunks.append(block)
                need(count==member.file_size);entries[relative]=('F',count,digest.digest())
                if relative=='Info.plist':info_bytes=b''.join(chunks)
                elif role=='share-archive' and chunks:extension_plists[relative]=b''.join(chunks)
            need(info_bytes is not None);info=plistlib.loads(info_bytes);need(type(info) is dict)
            need(type(info.get('OVTSnapshotCompanionContractVersion')) is int and info['OVTSnapshotCompanionContractVersion']==1
                and info.get('OVTSnapshotCompanionRole')==role and info.get('UIFileSharingEnabled') is True
                and info.get('CFBundlePackageType')=='APPL')
            executable=ascii_name(info.get('CFBundleExecutable'));need('/' not in executable and executable in entries and entries[executable][0]=='F')
            identity=dict(bundleContractVersion=1,bundleId=info.get('CFBundleIdentifier'),executableSha256=entries[executable][2].hex(),**root_digest(entries));compare(identity,identity)
            if role=='photos':result=dict(snapshotCompanionArtifactVersion=1,role='photos',artifactSha256=sha256,appRoot=root,bundle=identity)
            else:
                need(len(extension_plists)==1);extension_path,extension_raw=next(iter(extension_plists.items()));extension=plistlib.loads(extension_raw)
                need(type(extension) is dict and extension.get('CFBundlePackageType')=='XPC!'
                    and extension.get('CFBundleIdentifier')==identity['bundleId']+'.receiver'
                    and type(extension.get('NSExtension')) is dict and extension['NSExtension'].get('NSExtensionPointIdentifier')=='com.apple.share-services')
                group=info.get('OVTSnapshotShareGroup');need(type(group) is str and re.fullmatch(r'group\.[A-Za-z0-9.-]+',group)
                    and extension.get('OVTSnapshotShareGroup')==group)
                prefix=extension_path.rsplit('/',1)[0]+'/';extension_entries={name[len(prefix):]:row for name,row in entries.items() if name.startswith(prefix)}
                leaf=ascii_name(extension.get('CFBundleExecutable'));need('/' not in leaf and leaf in extension_entries and extension_entries[leaf][0]=='F'
                    and all(not name.endswith('.appex') or name==prefix[:-1] for name,row in entries.items() if row[0]=='D')
                    and not any(name.startswith('PlugIns/') and name.endswith('.appex') and name!=prefix[:-1] for name,row in entries.items()))
                extension_identity=dict(bundleContractVersion=1,bundleId=extension['CFBundleIdentifier'],executableSha256=extension_entries[leaf][2].hex(),**root_digest(extension_entries))
                compare(extension_identity,extension_identity)
                result=dict(snapshotShareCompanionArtifactVersion=1,role='share-archive',artifactSha256=sha256,appRoot=root,bundle=identity,
                    extension=dict(relativeRoot=prefix[:-1],appGroup=group,bundle=extension_identity))
        after=os.fstat(stream.fileno());need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
    need(file_digest(path)==sha256);return result
