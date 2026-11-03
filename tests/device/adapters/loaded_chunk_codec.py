"""Bounds from the already loaded original chunk codec; no source authority.

The existing prepare/pack functions, default zlib parameters, native dependency
and original code files stay pinned. No library is activated or replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ast
import base64
import ctypes
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import sys
import threading
import zlib

from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from adapters.chat_journey import source_bundles
from adapters.script_journey import history
from adapters.script_journey.history import canonical,MAX_RAW

UNRESOLVED=[]
FIELDS=('st_dev','st_ino','st_mode','st_uid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')


class _DlInfo(ctypes.Structure):
    _fields_=[('filename',ctypes.c_char_p),('base',ctypes.c_void_p),('symbol',ctypes.c_char_p),('address',ctypes.c_void_p)]


class OriginalChunkCodec:
    def __init__(self):
        self.files=[];self.failed=False;self.closed=False;self.host=host_identity();self.thread=threading.get_ident()
        self.functions=self.original_functions=(zlib.compress,zlib.decompressobj,base64.b64encode,base64.b64decode,
            history.pack,history.unpack,history.canonical,source_bundles.prepare,source_bundles.decode_parts)
        self.codes=self.original_codes=tuple(getattr(fn,'__code__',None) for fn in self.functions)
        self.modules=self.original_modules=(zlib,history,source_bundles,base64)
        try:
            need(os.name=='posix' and hasattr(os,'RTLD_NOLOAD'))
            extension=Path(zlib.__file__).resolve(strict=True)
            # NOLOAD forbids activating another compressor implementation.
            self.library=ctypes.CDLL(str(extension),mode=os.RTLD_NOW|os.RTLD_NOLOAD)
            self.original_library=self.library
            self.bound=self.original_bound=self.library.compressBound;self.bound.argtypes=[ctypes.c_ulong];self.bound.restype=ctypes.c_ulong
            self.ffi_argtypes=self.bound.argtypes;self.ffi_pointer=ctypes.cast(self.bound,ctypes.c_void_p).value
            self.ffi_flags=self.bound._flags_
            self.ffi=self.original_ffi=(self.ffi_argtypes,ctypes.c_ulong,self.ffi_flags,self.ffi_pointer)
            need(getattr(self.bound,'errcheck',None) is None)
            version=self.library.zlibVersion;version.restype=ctypes.c_char_p
            self.runtime=self.original_runtime=version().decode('ascii');need(self.runtime==zlib.ZLIB_RUNTIME_VERSION)
            process=ctypes.CDLL(None);dladdr=process.dladdr
            dladdr.argtypes=[ctypes.c_void_p,ctypes.POINTER(_DlInfo)];dladdr.restype=ctypes.c_int
            location=_DlInfo();need(dladdr(ctypes.cast(self.bound,ctypes.c_void_p),ctypes.byref(location))!=0 and location.filename)
            native=Path(os.fsdecode(location.filename)).resolve(strict=True)
            for fn in (history.pack,source_bundles.prepare):
                need(fn.__globals__['zlib'] is zlib)
                calls=[node for node in ast.walk(ast.parse(inspect.getsource(fn))) if isinstance(node,ast.Call)
                    and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name)
                    and node.func.value.id=='zlib' and node.func.attr=='compress']
                need(len(calls)==1 and len(calls[0].args)==1 and len(calls[0].keywords)==1
                    and calls[0].keywords[0].arg=='level' and isinstance(calls[0].keywords[0].value,ast.Constant)
                    and type(calls[0].keywords[0].value.value) is int and calls[0].keywords[0].value.value==9)
            for path in dict.fromkeys((extension,native,Path(history.__file__).resolve(strict=True),Path(source_bundles.__file__).resolve(strict=True),Path(__file__).resolve(strict=True))):
                owner=object.__new__(OriginalDescriptor);self.files.append([path,owner,None,None])
                OriginalDescriptor.__init__(owner,path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
                self._file(self.files[-1])
            self.pinned_files=self.original_pinned_files=tuple(tuple(row) for row in self.files)
            self.original_files=self.files
            self.profile=self.original_profile=(self.runtime,tuple((str(path),physical,digest) for path,owner,physical,digest in self.files))
            self._public=dict(loadedChunkCodecVersion=1,zlibRuntime=self.runtime,compressionLevel=9,
                compressionOptions='default-wbits-memlevel-strategy',
                files=[dict(path=str(path),physical=list(physical),sha256=digest) for path,owner,physical,digest in self.files])
            self.public_bytes=self.original_public_bytes=canonical(self._public)
            need(len(self.public_bytes)<=32768)
            self.guard()
        except BaseException:self.poison();raise

    def _file(self,row):
        path,owner,physical,digest=row;owner.require(owner.fd);before=os.fstat(owner.fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid in (0,os.geteuid())
            and stat.S_IMODE(before.st_mode)&0o022==0 and before.st_nlink>=1 and 0<before.st_size<=8*1024*1024)
        digest_state=hashlib.sha256();offset=0
        while offset<before.st_size:
            owner.require(owner.fd);raw=os.pread(owner.fd,min(65536,before.st_size-offset),offset);owner.require(owner.fd)
            need(raw and len(raw)<=before.st_size-offset);digest_state.update(raw);offset+=len(raw)
        owner.require(owner.fd);stamp=tuple(getattr(before,key) for key in FIELDS)
        need(offset==before.st_size and stamp==tuple(getattr(os.fstat(owner.fd),key) for key in FIELDS)
            ==tuple(getattr(path.lstat(),key) for key in FIELDS))
        current=digest_state.hexdigest()
        if physical is None:row[2:]=[stamp,current]
        else:need(stamp==physical and current==digest)

    def guard(self):
        try:return self._guard()
        except BaseException:self.poison();raise

    def _guard(self):
        need(self.failed is False and self.closed is False and host_identity()==self.host and threading.get_ident()==self.thread
            and self.functions is self.original_functions and type(self.functions) is tuple and len(self.functions)==9
            and all(original is current for original,current in zip(self.functions,(zlib.compress,zlib.decompressobj,
                base64.b64encode,base64.b64decode,history.pack,history.unpack,history.canonical,source_bundles.prepare,source_bundles.decode_parts)))
            and self.profile is self.original_profile and self.runtime is self.original_runtime
            and type(self.runtime) is str and type(zlib.ZLIB_RUNTIME_VERSION) is str and zlib.ZLIB_RUNTIME_VERSION==self.runtime
            and self.library is self.original_library and self.bound is self.original_bound
            and self.modules is self.original_modules and type(self.modules) is tuple and len(self.modules)==4
            and all(original is current for original,current in zip(self.modules,(zlib,history,source_bundles,base64)))
            and sys.modules.get('zlib') is zlib and history.zlib is zlib and source_bundles.zlib is zlib
            and self.codes is self.original_codes and type(self.codes) is tuple and len(self.codes)==len(self.functions)
            and all(getattr(fn,'__code__',None) is original for fn,original in zip(self.functions,self.codes)))
        need(self.ffi is self.original_ffi and type(self.ffi) is tuple and len(self.ffi)==4
            and self.ffi_argtypes is self.ffi[0] and self.ffi[1] is ctypes.c_ulong
            and self.ffi_flags is self.ffi[2] and type(self.ffi_flags) is int
            and self.ffi_pointer is self.ffi[3] and type(self.ffi_pointer) is int
            and self.bound.argtypes is self.ffi_argtypes and type(self.ffi_argtypes) is list and len(self.ffi_argtypes)==1
            and self.ffi_argtypes[0] is ctypes.c_ulong and self.bound.restype is ctypes.c_ulong
            and type(self.bound._flags_) is int and self.bound._flags_==self.ffi_flags
            and getattr(self.bound,'errcheck',None) is None and ctypes.cast(self.bound,ctypes.c_void_p).value==self.ffi_pointer)
        need(self.files is self.original_files and type(self.files) is list
            and self.pinned_files is self.original_pinned_files and type(self.pinned_files) is tuple and len(self.files)==len(self.pinned_files)
            and all(type(row) is list and len(row)==4 and type(pinned) is tuple and len(pinned)==4
                and type(row[1]) is OriginalDescriptor and all(current is original for current,original in zip(row,pinned))
                for row,pinned in zip(self.files,self.pinned_files))
            and self.profile==(self.runtime,tuple((str(path),physical,digest) for path,owner,physical,digest in self.pinned_files))
            and self.public_bytes is self.original_public_bytes)
        source_bundles.plain(self._public);need(canonical(self._public)==self.public_bytes)
        for row in self.files:self._file(row)
        return True

    def compress_bound(self,size):
        need(type(size) is int and 0<=size<=MAX_RAW)
        self.guard();result=self.bound(size);self.guard()
        # This is a runtime refusal, not an assumed portable DEFLATE bound.
        need(type(result) is int and 0<=result<=2*size+1024);return result

    def public_profile(self):
        self.guard();result=json.loads(self.public_bytes);source_bundles.plain(result)
        need(canonical(result)==self.public_bytes);self.guard();return result

    def metadata_bytes(self):
        # Resource-only accounting remains available after business/codec loss.
        need(self.public_bytes is self.original_public_bytes and type(self.public_bytes) is bytes)
        return 3*len(self.public_bytes)+2*65536

    def poison(self):
        self.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def close_host(self):
        # A caller-mutable business flag cannot certify actual FD retirement.
        # Check only the original typed holders; never invoke a foreign close.
        if self.closed is not False:
            valid=(self.closed is True and self.failed is False
                and host_identity()==self.host and threading.get_ident()==self.thread
                and self.files is self.original_files and type(self.files) is list
                and self.pinned_files is self.original_pinned_files and type(self.pinned_files) is tuple
                and len(self.files)==len(self.pinned_files) and len(self.files)>0
                and all(type(row) is list and len(row)==4 and type(pinned) is tuple and len(pinned)==4
                    and all(current is original for current,original in zip(row,pinned))
                    and type(row[1]) is OriginalDescriptor and row[1].closed is True and row[1].lost is False
                    and type(row[1].fd) is int and row[1].fd==-1
                    and type(row[1].anchor) is int and row[1].anchor==-1
                    for row,pinned in zip(self.files,self.pinned_files)))
            if not valid:self.poison()
            return valid
        if self.failed is not False:return False
        try:
            self.guard()
            for path,owner,physical,digest in self.files:
                if not owner.close():self.poison();return False
            self.closed=True;return True
        except BaseException:self.poison();raise
