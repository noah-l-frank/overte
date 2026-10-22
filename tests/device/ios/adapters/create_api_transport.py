"""Final Create transport guards on the original native/W3C channels."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_ui import NativeUI,NativeUIError
from ios.adapters.normal_input import NativeInput
from ios.adapters.create_api_clock import check


class CreateNativeInput(NativeInput):
    @classmethod
    def from_original(cls,original):
        if not isinstance(original,NativeInput):raise NativeUIError('Create requires the original native input channel')
        if isinstance(original,cls):return original
        value=object.__new__(cls);value.__dict__=original.__dict__;return value
    def _request(self,operation,native=None,*,before_send=None):
        def final_guard():
            check()
            if before_send is not None and before_send() is False:return False
            check()
        return super()._request(operation,native,before_send=final_guard)


class CreateNativeUI(NativeUI):
    @classmethod
    def from_original(cls,original):
        if not isinstance(original,NativeUI):raise NativeUIError('Create requires the original W3C input channel')
        if isinstance(original,cls):return original
        value=object.__new__(cls);value.__dict__=original.__dict__;return value
    def _request(self,method,path,body=None):
        check();value=super()._request(method,path,body);check();return value
