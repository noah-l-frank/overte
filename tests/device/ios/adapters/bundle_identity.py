"""Original installed-bundle byte association; not an archive identity echo.

The native source measures its actual main bundle. This reader independently
hashes the selected final signed IPA's app contents and compares the two. It
does not infer installed identity from version strings or Info.plist claims.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import plistlib
import re
import stat
import struct
import unicodedata
import zipfile
from execution_identity import file_digest

VERSION=1
CONTRACT='overte-ios-installed-bundle-v1'
APP='Payload/Overte.app/'
MAX_NODES=20000
MAX_BYTES=2*1024**3
MAX_FILE=1024**3
MAX_PLIST=4*1024**2
EMPTY=hashlib.sha256(b'').digest()


def need(condition):
    if not condition:raise ValueError('OVT_IOS_BUNDLE_IDENTITY_REJECTED')


def name(value):
    need(type(value) is str and value and len(value.encode('utf-8'))<=1024
         and not value.startswith('/') and '\\' not in value
         and all(32<=ord(c)!=127 for c in value))
    result=unicodedata.normalize('NFC',value)
    need(len(result.split('/'))<=64 and all(part not in ('','.','..') and len(part.encode('utf-8'))<=255 for part in result.split('/')))
    return result


def root_digest(entries):
    """Canonical original file/directory records, independent of ZIP packing."""
    need(type(entries) is dict and 0<len(entries)<=MAX_NODES)
    digest=hashlib.sha256(CONTRACT.encode('ascii')+b'\0');folded=set()
    files=total=0
    for path in sorted(entries,key=lambda v:v.encode('utf-8')):
        need(name(path)==path and path.casefold() not in folded);folded.add(path.casefold())
        kind,size,sha=entries[path]
        need(kind in ('F','D') and type(size) is int and 0<=size<=MAX_FILE
             and type(sha) is bytes and len(sha)==32 and (kind!='D' or size==0 and sha==EMPTY))
        parent=path.rpartition('/')[0]
        if parent:need(parent in entries and entries[parent]==('D',0,EMPTY))
        raw=path.encode('utf-8');digest.update(kind.encode('ascii')+struct.pack('>I',len(raw))+raw+struct.pack('>Q',size)+sha)
        if kind=='F':files+=1;total+=size;need(total<=MAX_BYTES)
    return dict(bundleSha256=digest.hexdigest(),nodeCount=len(entries),fileCount=files,totalBytes=total)


def artifact_bundle(path,expected_sha256):
    """Read a stable original IPA without extracting or executing any member.

    All installed app bytes participate, including signatures and Info.plist.
    Re-signing, thinning or resource replacement needs a separately qualified
    final artifact. Such a mismatch is never normalized into success here.
    """
    need(type(expected_sha256) is str and re.fullmatch('[0-9a-f]{64}',expected_sha256))
    path=Path(path);need(file_digest(path)==expected_sha256)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        with os.fdopen(fd,'rb') as stream:
            fd=-1;before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode))
            actual=hashlib.sha256()
            for block in iter(lambda:stream.read(1024**2),b''):actual.update(block)
            need(actual.hexdigest()==expected_sha256);stream.seek(0)
            with zipfile.ZipFile(stream) as archive:
                infos=archive.infolist();need(0<len(infos)<=MAX_NODES)
                seen=set();entries={};info_bytes=None
                def parents(path):
                    parts=path.split('/')
                    for n in range(1,len(parts)):
                        parent='/'.join(parts[:n]);need(parent not in entries or entries[parent]==('D',0,EMPTY))
                        need(parent in entries or len(entries)<MAX_NODES)
                        entries[parent]=('D',0,EMPTY)
                expanded=0
                for member in infos:
                    raw=member.filename[:-1] if member.is_dir() else member.filename
                    normalized=name(raw)
                    need(normalized not in seen and member.flag_bits&1==0);seen.add(normalized)
                    if normalized in ('Payload','Payload/Overte.app'):
                        need(member.is_dir() and member.file_size==0 and stat.S_IFMT(member.external_attr>>16) in {0,stat.S_IFDIR})
                        continue
                    # No second app may compete for the selected Payload root.
                    if normalized.startswith('Payload/'):
                        need(normalized=='Payload/Overte.app' or normalized.startswith(APP))
                    if not normalized.startswith(APP):continue
                    relative=normalized[len(APP):];need(relative)
                    mode=stat.S_IFMT(member.external_attr>>16)
                    need(mode in ({0,stat.S_IFDIR} if member.is_dir() else {0,stat.S_IFREG}))
                    parents(relative)
                    if member.is_dir():
                        need(member.file_size==0)
                        need(relative not in entries or entries[relative]==('D',0,EMPTY))
                        need(relative in entries or len(entries)<MAX_NODES)
                        entries[relative]=('D',0,EMPTY);continue
                    need(type(member.file_size) is int and 0<=member.file_size<=MAX_FILE and relative not in entries)
                    expanded+=member.file_size;need(expanded<=MAX_BYTES and len(entries)<MAX_NODES)
                    digest=hashlib.sha256();count=0;chunks=[]
                    with archive.open(member) as original:
                        while True:
                            block=original.read(1024**2)
                            if not block:break
                            count+=len(block);need(count<=member.file_size);digest.update(block)
                            if relative=='Info.plist':need(count<=MAX_PLIST);chunks.append(block)
                    need(count==member.file_size);entries[relative]=('F',count,digest.digest())
                    if relative=='Info.plist':info_bytes=b''.join(chunks)
                need(info_bytes is not None)
                info=plistlib.loads(info_bytes);need(type(info) is dict)
                bundle=info.get('CFBundleIdentifier');exe=info.get('CFBundleExecutable')
                need(type(bundle) is str and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',bundle)
                     and type(exe) is str and name(exe)==exe and '/' not in exe and exe in entries and entries[exe][0]=='F'
                     and type(info.get('OverteE2ETestBuildContractVersion')) is int
                     and info['OverteE2ETestBuildContractVersion']==1 and info.get('UIFileSharingEnabled') is True)
                output=dict(bundleContractVersion=VERSION,bundleId=bundle,executableSha256=entries[exe][2].hex(),**root_digest(entries))
            after=os.fstat(stream.fileno())
            need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                 (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        need(file_digest(path)==expected_sha256)
        return output
    except (OSError,ValueError,TypeError,KeyError,zipfile.BadZipFile,plistlib.InvalidFileException):
        raise ValueError('OVT_IOS_BUNDLE_IDENTITY_REJECTED') from None
    finally:
        if fd>=0:os.close(fd)


def compare(original,artifact):
    need(type(original) is dict and type(artifact) is dict and set(original)==set(artifact)=={
        'bundleContractVersion','bundleId','executableSha256','bundleSha256','nodeCount','fileCount','totalBytes'})
    for value in (original,artifact):
        need(type(value['bundleContractVersion']) is int and value['bundleContractVersion']==VERSION
             and type(value['bundleId']) is str and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',value['bundleId'])
             and all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]) for k in ('bundleSha256','executableSha256'))
             and all(type(value[k]) is int and 1<=value[k]<=MAX_NODES for k in ('fileCount','nodeCount'))
             and value['fileCount']<=value['nodeCount'] and type(value['totalBytes']) is int and 0<value['totalBytes']<=MAX_BYTES)
    need(original==artifact)
    return original
