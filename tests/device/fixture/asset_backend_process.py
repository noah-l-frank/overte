"""Read-only kernel binding for one already-owned AssetServer assignment.

No process discovery, launch, signal, service or executable installation occurs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
from adapters import asset_backend_source as source
from adapters.chat_actor_files import node,stamp
from adapters.native_feature_observation import integer,need
from adapters.normal_ui import NativeUIError


class LinuxAssetsBackendProcess:
    def __init__(self,pid,directory,config_home,executable_sha256,owner_sha256,owned):
        need(sys.platform.startswith('linux') and integer(pid,1) and callable(owned));source.digest(executable_sha256);source.digest(owner_sha256)
        self.pid,self.path,self.config_home,self.owned=pid,Path(directory),Path(config_home),owned;self.fd=-1;self.owner_sha256=owner_sha256
        need(self.path.is_absolute() and self.path.resolve(strict=True)==self.path and self.config_home.is_absolute()
            and self.config_home.resolve(strict=True)==self.config_home)
        root=self.path.lstat();need(stat.S_ISDIR(root.st_mode) and stat.S_IMODE(root.st_mode)==0o700 and root.st_uid==os.geteuid())
        config=self.config_home.lstat();need(stat.S_ISDIR(config.st_mode) and stat.S_IMODE(config.st_mode)==0o700 and config.st_uid==os.geteuid());self.config_root=node(config)
        self.root=node(root);self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();source.work.identity(self.boot)
        self.start=self._start();self._configuration();self.fd=os.open(self._process_path('exe'),os.O_RDONLY|os.O_CLOEXEC)
        try:
            before=os.fstat(self.fd);need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=2**32);self.executable=stamp(before)
            digest=hashlib.sha256();remaining=before.st_size
            while remaining:
                data=os.read(self.fd,min(1024*1024,remaining));need(bool(data));remaining-=len(data);digest.update(data)
            need(os.read(self.fd,1)==b'' and stamp(os.fstat(self.fd))==self.executable and digest.hexdigest()==executable_sha256)
            self.sha256=executable_sha256;self.guard()
        except BaseException:self.close();raise

    @property
    def process_identity(self):return f'{self.pid}:{self.start}:{self.boot}'

    def _process_path(self,leaf=''):return Path('/proc')/str(self.pid)/leaf

    def _start(self):
        need(self.owned(self.pid) is True);root=self._process_path();need(root.stat().st_uid==os.geteuid())
        fields=(root/'stat').read_text().rsplit(')',1)[1].split()
        need(len(fields)>19 and fields[0] not in ('Z','X') and re.fullmatch('[1-9][0-9]{0,19}',fields[19]) is not None)
        return fields[19]

    def _configuration(self):
        root=self._process_path();args=(root/'cmdline').read_bytes().split(b'\0');need(args[-1]==b'' and args.count(b'-t')==1)
        role=args.index(b'-t');need(role+1<len(args) and args[role+1]==b'3'
            and not any(item.startswith(b'-t') and item!=b'-t' or item.startswith((b'--type',b'--testScript',b'--e2eChatActorDir')) for item in args))
        environment={}
        for entry in (root/'environ').read_bytes().split(b'\0'):
            if not entry:continue
            key,separator,value=entry.partition(b'=');need(bool(separator) and key not in environment);environment[key]=value
        token=environment.get(b'OVERTE_E2E_FIXTURE_PROCESS_OWNER',b'')
        need(re.fullmatch(b'[0-9a-f]{64}',token) is not None and hashlib.sha256(token).hexdigest()==self.owner_sha256
            and environment.get(b'XDG_CONFIG_HOME')==os.fsencode(self.config_home)
            and environment.get(b'OVERTE_E2E_ASSETS_SOURCE_ROOT')==os.fsencode(self.path))

    def guard(self):
        try:
            need(self.fd>=0 and self._start()==self.start and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot
                and self.path.resolve(strict=True)==self.path)
            root=self.path.lstat();need(node(root)==self.root and stat.S_ISDIR(root.st_mode) and stat.S_IMODE(root.st_mode)==0o700 and root.st_uid==os.geteuid())
            config=self.config_home.lstat();need(self.config_home.resolve(strict=True)==self.config_home and node(config)==self.config_root
                and stat.S_ISDIR(config.st_mode) and stat.S_IMODE(config.st_mode)==0o700 and config.st_uid==os.geteuid())
            self._configuration();need(stamp(os.fstat(self.fd))==self.executable and stamp(os.stat(self._process_path('exe')))==self.executable and self.owned(self.pid) is True)
            return True
        except (OSError,ValueError,IndexError):raise NativeUIError('Owned Assets backend process is unavailable') from None

    def close(self):
        """Release this host's executable descriptor only, never retire a server."""
        if self.fd>=0:os.close(self.fd);self.fd=-1
