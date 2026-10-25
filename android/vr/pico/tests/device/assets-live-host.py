"""Owned pipe into actual Qt Assets UI/native sources; SDK/network remain seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ast
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
from types import SimpleNamespace
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.assets_ui import PicoAssetsIO
from adapters.pico4 import binding as original_binding
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.pico4.assets_uploads import PicoAssetsUploads
from adapters.pico4.assets_files import NativeAssetsFiles

# Execute the exact production factories, including the original two-argument
# final callback bridge; only their runtime/installation endpoints are supplied
# by this declared host. No copied or parallel input implementation.
_binding_path=Path(original_binding.__file__)
_binding_tree=ast.parse(_binding_path.read_text())
_method_names={'_bind_create_transport','_assets_controls'}
_methods=[node for node in ast.walk(_binding_tree) if isinstance(node,ast.FunctionDef) and node.name in _method_names]
assert len(_methods)==len(_method_names)
_factory_tree=ast.Module(body=[ast.ClassDef(name='OriginalAssetsControlsFactory',bases=[],keywords=[],body=_methods,decorator_list=[])],type_ignores=[])
ast.fix_missing_locations(_factory_tree)
_factory_scope=dict(vars(original_binding))
exec(compile(_factory_tree,str(_binding_path),'exec'),_factory_scope)
OriginalAssetsControlsFactory=_factory_scope['OriginalAssetsControlsFactory']

class AssetsLiveHost:
    def __init__(self,binary,environment,args,directory):
        self.directory=Path(directory);self.log=(self.directory/'native.log').open('w');os.chmod(self.directory/'native.log',0o600)
        self.process=subprocess.Popen(['unshare','--user','--map-root-user','--net',str(binary),*args,'--testScript','--serve'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=environment,stderr=self.log)
        self.raw='';self.status='';self.inputs=[];self.operations=[];self.lose=False;self.fail_send=False;self.last_guard=None
        self.identity=str(self.process.pid)+':explicit-host-process';self.before_guard=None
        self.adb=self;self.target='owned-host-endpoint'
        self.installation_identity=dict(schemaVersion=1,sourceRevision='f8cd43a02da492fc326f3f86ccebcfd223d3bacf',artifactSha256=hashlib.sha256(Path(binary).read_bytes()).hexdigest(),installedCandidateVerified=True)
        # The installation endpoint is explicitly this host binary, never an Android qualification.
        try:
            self.reconnect_inputs()
        except Exception:
            self.close();raise
    def reconnect_inputs(self):
        # Cold adapter input objects, same exact native process and persisted
        # navigation context. Never clear/replace a bound transport callback.
        self.native=NativeNavigationIO(self,self.target,self.identity,lambda operation:(_ for _ in ()).throw(AssertionError('No host controller effect')))
        self.navigation=PicoNavigation(self.native,self.directory/'navigation.json',self.installation_identity,self.identity,'https://127.0.0.1/owned/scene.json')
        self.io=PicoAssetsIO(PicoScriptIO(self.navigation));self.factory=OriginalAssetsControlsFactory()
        self.factory._script_runtime=lambda target:(SimpleNamespace(io=self.io.original,monotonic=time.monotonic,sleep=time.sleep),None,None)
    def request(self,command):
        assert self.process.poll() is None
        self.process.stdin.write(json.dumps(command,separators=(',',':'))+'\n');self.process.stdin.flush()
        assert select.select([self.process.stdout],[],[],8)[0],'Original native pipe timed out'
        raw=self.process.stdout.readline();assert raw,'Original native process exited';return raw
    def guard(self):assert self.process.poll() is None
    def require_same_process(self,target,identity,reason):self.guard();assert identity==self.identity
    def require_pico_session_identity(self,target):self.guard();return self.identity
    def foreground_package(self,target):return 'org.overte.pico'
    def _installation(self,target):self.guard()
    def probe_retry_policy(self):return 1,0
    def epoch_milliseconds(self,target=None):return int(time.time()*1000)
    def read_debug_app_file(self,target,package,path,**options):
        assert target==self.target and package=='org.overte.pico'
        if path.endswith('navigation-ui-observation.json'):return self.request(dict(action='host-observe-original-ui'))
        assert path.endswith('navigation-ui-status.json');return self.status
    def write_debug_app_file(self,target,package,path,raw):
        assert path.endswith('navigation-ui-command.json');command=json.loads(raw);self.inputs.append(command)
        if self.fail_send:raise RuntimeError('Declared undelivered original input boundary')
        result=self.request(dict(action='host-original-ui-input',original=command));self.status='' if self.lose else result
    def source_send(self,command):
        self.operations.append(command);self.raw=self.request(command)
    def files(self,stage=1):return NativeAssetsFiles(self.source_send,lambda:self.raw,self.epoch_milliseconds,self.guard,self.process.pid,stage=stage)
    def mappings(self,*,intent=None):return PicoAssetsSource(self.source_send,lambda:self.raw,self.epoch_milliseconds,self.guard,self.process.pid,intent=intent)
    def uploads(self,*,intent=None):return PicoAssetsUploads(self.source_send,lambda:self.raw,self.epoch_milliseconds,self.guard,self.process.pid,intent=intent)
    def controls(self,intent,*,before_send=None,audit=None):
        return self.factory._assets_controls(self.target,intent,before_send=before_send,audit=audit)
    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=3)
        self.process.stdout.close();self.log.close()
        assert self.process.returncode==0
