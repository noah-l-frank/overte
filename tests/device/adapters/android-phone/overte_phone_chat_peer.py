"""Attach to the existing explicitly owned fixture AC and MessagesMixer control.

No child launch, process discovery, primary state forwarding or delivery verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,Request,build_opener
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.chat_actor_files import ChatActorFiles,SOURCE,COMMAND,RESULT,stamp,node
from adapters.native_chat_observation import NativeChatObservation
from adapters.native_chat_peer import NativeChatPeer
from fixture.chat_actor_process import LinuxChatActorProcess
from fixture.owned_processes import OWNER_VARIABLE

VERSION=1


def configuration(value):
    exact(value,{'chatPeerFixtureVersion','actorConfiguration','domainReady','actorArtifact'})
    need(type(value['chatPeerFixtureVersion']) is int and value['chatPeerFixtureVersion']==VERSION)
    for key in ('actorConfiguration','domainReady'):
        path=Path(value[key]);need(path.is_absolute() and path.resolve(strict=True)==path);PrivateFeatureState(path)._parent()
    artifact=value['actorArtifact'];exact(artifact,{'sourceRevision','artifactSha256'})
    need(type(artifact['sourceRevision']) is str and re.fullmatch('[0-9a-f]{40}',artifact['sourceRevision'])
         and type(artifact['artifactSha256']) is str and re.fullmatch('[0-9a-f]{64}',artifact['artifactSha256']))
    return deepcopy(value)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):return None


class PhoneChatPeer:
    def __init__(self,config,path,primary_binding,run,*,read_only=False,attach_files=True,script_sha256,clock_ms,monotonic,sleep):
        self.config=configuration(config);self.path=Path(path);self.run=run;self.read_only=read_only
        self.primary=context(primary_binding);self.process=None;self.files=None
        data=PrivateFeatureState(Path(config['actorConfiguration'])).read()
        exact(data,{'actorFilesVersion','directory','expectedScriptSha256','expectedExecutableSha256','ownerToken','configHome'})
        need(type(data['actorFilesVersion']) is int and data['actorFilesVersion']==1
            and data['expectedExecutableSha256']==config['actorArtifact']['artifactSha256']
            and data['expectedScriptSha256']==script_sha256
            and config['actorArtifact']['sourceRevision']==primary_binding['sourceRevision']
            and type(data['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',data['ownerToken'])
            and type(data['configHome']) is str and Path(data['configHome']).is_absolute())
        root=Path(data['directory']);PrivateFeatureState(root/'boundary.json')._parent()
        # This original source PID is only a hint into an already owned process;
        # its executable/start/environment and actual retained FDs qualify it.
        native=PrivateFeatureState(root/SOURCE).read();need(type(native) is dict and integer(native.get('processId'),1))
        def owned(pid):
            try:
                actual=Path('/proc')/str(pid);need(actual.stat().st_uid==os.geteuid())
                environment=(actual/'environ').read_bytes().split(b'\0')
                return (f'{OWNER_VARIABLE}={data["ownerToken"]}'.encode() in environment
                        and f'XDG_CONFIG_HOME={data["configHome"]}'.encode() in environment)
            except OSError:return False
        try:
            self.process=LinuxChatActorProcess(native['processId'],root,data['expectedExecutableSha256'],owned)
            fingerprint=hashlib.sha256(('chat-peer:'+self.process.process_identity+':'+data['expectedExecutableSha256']).encode()).hexdigest()
            self.binding=dict(**config['actorArtifact'],processIdentity=self.process.process_identity,sessionId=native['instance'],
                              generation=1,targetFingerprint=fingerprint)
            need(self.binding['targetFingerprint']!=primary_binding['targetFingerprint'] and self.binding['processIdentity']!=primary_binding['processIdentity'])
            self.directory=root
            self.source_stamp=stamp((root/SOURCE).stat());self.source_sha=hashlib.sha256((root/SOURCE).read_bytes()).hexdigest()
            need(self.process.released(node((root/SOURCE).stat())) is False)
            if attach_files:
                self.files=ChatActorFiles(root,PrivateFeatureState(self.path.with_name('phone-chat-peer-files.json')),self.binding,
                    data['expectedScriptSha256'],self.process.guard,self.process.released,clock_ms=clock_ms,monotonic=monotonic,sleep=sleep)
                def send(command):
                    if read_only:need(command['operation']=='inspect' and command['action'] in ('feature-chat-peer','feature-chat-observe'))
                    self.files.send(command)
                common=dict(monotonic=monotonic,sleep=sleep)
                self.receive=NativeChatObservation(send,self.files.read,clock_ms,self.process.guard,self.process.pid,**common)
                self.control=NativeChatPeer(send,self.files.read,clock_ms,self.process.guard,self.process.pid,**common)
            self.ready=PrivateFeatureState(Path(config['domainReady'])).read()
            need(type(self.ready) is dict and type(self.ready.get('controlToken')) is str and len(self.ready['controlToken'])>=32)
            parsed=urlsplit(self.ready.get('messagesMixerControlUrl',''))
            need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port is not None
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path=='/v1/messages-mixer-state')
        except BaseException:self.detach();raise

    def detach(self):
        if self.files is not None:self.files.detach()
        if self.process is not None:self.process.close()

    def mixer(self,action=None):
        need(action in (None,'offline','online') and (not self.read_only or action is None));self.process.guard()
        body=None if action is None else json.dumps(dict(schemaVersion=1,action=action),separators=(',',':')).encode()
        request=Request(self.ready['messagesMixerControlUrl'],body,headers={'X-Overte-E2E-Token':self.ready['controlToken'],
            'Content-Type':'application/json'},method='GET' if body is None else 'POST')
        with build_opener(NoRedirect()).open(request,timeout=2) as response:
            need(response.status==200);raw=response.read(4097);need(len(raw)<=4096)
        value=decode(raw.decode());exact(value,{'mixerProcessVersion','running','generation','pending'})
        need(type(value['mixerProcessVersion']) is int and value['mixerProcessVersion']==1 and type(value['running']) is bool
             and integer(value['generation'],1) and type(value['pending']) is bool and not value['pending'])
        self.process.guard();return value
