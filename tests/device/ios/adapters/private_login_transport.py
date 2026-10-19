"""Private AFC bytes; the shared fixture sees only closed lease metadata."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import re
from adapters.private_login_input import FILE,VERSION
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError


class IOSPrivateLoginTransport:
    def __init__(self,observer):
        observer.guard();self.observer=observer;self.pid=observer.process['pid']
        self.root=observer.remote.rsplit('/',1)[0]+'/'
    def guard(self):self.observer.guard()
    def send(self,value):self.observer.send(value)
    def read(self):return self.observer.original(remote=self.root+FILE,limit=65536)
    @staticmethod
    def valid_name(name):
        need(type(name) is str and re.fullmatch(r'feature-login-input-[0-9a-f]{32}\.v'+str(VERSION)+r'\.json',name))
    def write(self,name,raw):
        try:
            self.valid_name(name);need(type(raw) is bytes and 0<len(raw)<=16384);self.guard()
            self.observer.client.execute(self.observer.session,'mobile: pushFile',
                {'remotePath':self.root+name,'payload':base64.b64encode(raw).decode('ascii')})
            self.guard()
        except Exception:raise NativeUIError('Private iOS app-file input transfer failed') from None
    def original(self,name):
        self.valid_name(name);self.guard()
        value=self.observer.original(remote=self.root+name,limit=16384).encode('utf-8')
        self.guard();return value

    def drain(self,name):
        return self.original(name)
