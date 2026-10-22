"""Reuse original private PNG/JSON engines for Create; no feature-state producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_feature_observation import need
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_graphics_images import PhoneGraphicsImages


class CreateOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'create','create-input','create-retirement'})


class CreateImages(PhoneGraphicsImages):
    KIND='create'

    def resume(self,value,raw):
        """Finish only exact owned PNG prefixes from original native memory."""
        self.record(value);self.content(value,raw);value=deepcopy(value);path=self._path(value)
        need(value['phase'] in ('planned','opened','saved'))
        if value['phase']=='saved':need(self.read(value)==raw);return value
        need(self.guard() is not False)
        if value['phase']=='planned':
            need(self.absent(value));descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        else:descriptor=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'r+b') as stream:
            if value['phase']=='planned':
                info=os.fstat(stream.fileno());value.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino));need(self.intent(deepcopy(value)) is not False)
            self._file(path,stream.fileno(),value);before=os.fstat(stream.fileno());prefix=stream.read(self.LIMIT+1)
            self._file(path,stream.fileno(),value);after=os.fstat(stream.fileno())
            need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                and len(prefix)==after.st_size<=len(raw) and raw.startswith(prefix) and self.guard() is not False)
            need(stream.write(raw[len(prefix):])==len(raw)-len(prefix));stream.flush();os.fsync(stream.fileno());self._file(path,stream.fileno(),value)
        need(self.read(value)==raw);value['phase']='saved';need(self.intent(deepcopy(value)) is not False);return value
