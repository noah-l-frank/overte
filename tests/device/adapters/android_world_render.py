"""Closed Android app-private world-render receipt IO for Phone/Pico bindings."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import shlex
from adapters.normal_feature_state import need


class AndroidWorldRenderReceipts:
    def __init__(self,adb,target,package,guard):
        need(callable(guard) and re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+',package))
        self.adb,self.target,self.package,self.guard=adb,target,package,guard

    @staticmethod
    def path(name):
        need(type(name) is str and re.fullmatch(r'world-render-storage-[0-9a-f]{32}\.json',name))
        return 'files/overte-e2e/'+name

    def read(self,name):
        need(self.guard() is not False)
        raw=self.adb.read_debug_app_file(self.target,self.package,self.path(name),attempts=1)
        need(self.guard() is not False)
        return raw

    def _call(self,name,operation):
        path=self.path(name);need(self.guard() is not False)
        # The runner owns this bound private probe root. Never recurse, follow a
        # link, or widen deletion beyond one previously journaled nonce filename.
        root='if [ -L files ] || [ -L files/overte-e2e ] || [ ! -d files/overte-e2e ]; then exit 1; fi; '
        if operation=='remove':
            script=root+'if [ -L "$1" ] || { [ -e "$1" ] && [ ! -f "$1" ]; }; then exit 1; fi; rm -f -- "$1"'
        else:
            script=root+'if [ ! -e "$1" ] && [ ! -L "$1" ]; then printf "absent\\n"; else printf "present\\n"; fi'
        remote=' '.join(shlex.quote(v) for v in ('run-as',self.package,'sh','-c',script,'overte-world-render-receipt',path))
        result=self.adb.execute(['shell',remote],target=self.target,timeout=5)
        need(self.guard() is not False)
        return result

    def remove(self,name):self._call(name,'remove')
    def absent(self,name):return self._call(name,'inspect')=='absent\n'
