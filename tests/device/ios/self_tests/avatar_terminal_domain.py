"""Original native/SDK producers for the paired held-terminal host case.

Full Login/Pal/People/HTTP, private files, typed decoders and pixel originals
stay real host code. SDK lifecycle, DVT absence and GPU are explicit models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.retired_process import IOSRetiredProcess
from ios.adapters import retired_process
from ios.self_tests.avatar_strong_domain import StrongDomain
from ios.self_tests.test_ios_retired_process import Boundary as NodeOS


class TerminalDomain(StrongDomain):
    def __init__(self,test):
        super().__init__(test);outer=self;self.sdk_exists={role:True for role in self.natives};self.sdk_requests=[];self.os={}
        for role,native in self.natives.items():
            class SharedOS(NodeOS):
                @property
                def clock(_self):return outer.clock[0]
                @clock.setter
                def clock(_self,value):outer.clock[0]=value
            now=self.clock[0];os=SharedOS();self.clock[0]=now;os.pid=native.pid;os.anchor['pid']=native.pid
            os.anchor['bundlePids']=[native.pid,native.pid];os.anchor['clockBefore']['epochMs']=os.node_epoch()-5000
            os.anchor['clockAfter']['epochMs']=os.node_epoch()-4990;self.os[role]=os
            execute=native.execute
            def native_call(session,operation,values,old=execute,os=os,n=native):
                if operation=='mobile: overteRetiredProcessInfo':
                    test.assertFalse(n.running);return os.send(values)
                return old(session,operation,values)
            native.execute=native_call
            call=native.call
            def sdk(method,path,body=None,old=call,role=role,n=native):
                if path=='/session/'+n.state['sessionId']:
                    outer.sdk_requests.append((role,method))
                    if method=='DELETE':outer.sdk_exists[role]=False;return {}
                    if not outer.sdk_exists[role]:raise WebDriverRequestError(404,'invalid-session')
                return old(method,path,body)
            native.call=sdk
        class ModeledRetiredProcess(IOSRetiredProcess):
            def __init__(self,*args,**kwargs):
                # The actual runtime imports this constructor, including its
                # explicit base-class call sites. No reader or saved original
                # has its clock replaced after construction.
                kwargs.setdefault('epoch_ms',outer.host)
                kwargs.setdefault('monotonic',lambda:outer.clock[0])
                super().__init__(*args,**kwargs)
        boundary=patch.object(retired_process,'IOSRetiredProcess',ModeledRetiredProcess)
        boundary.start();test.addCleanup(boundary.stop)
        adapter=self.runtime.adapter
        def stop(selector,operation,values):
            test.assertEqual(('app.stop',{}),(operation,values));native=self.natives[selector];gate=self.installed[selector]
            binding=gate.make();binding.begin_retirement();result=native.lifecycle_input(operation);gate.process=None
            binding.finish_retirement();return result
        adapter.invoke=stop;adapter.reset_launch_state=lambda *_args:None
