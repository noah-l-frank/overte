"""Actual Installed frontdoor over existing declared Avatar native producers.

No capability, flow, historical verifier or returned product fact is patched.
Target mode is declared before the first fingerprint/Installed original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.installed_adapter import create_physical_adapter
from ios.adapters import feature_configuration
from ios.self_tests.avatar_terminal_domain import TerminalDomain


class CanonicalTerminalDomain(TerminalDomain):
    def declare_native_target(self,role,native):
        need(role in ('primary','actor'))
        native.target.update(artifactMode='personal-team-preinstalled',_artifactMode='personal-team-preinstalled')


class AvatarCanonicalFrontdoor:
    domain_type=CanonicalTerminalDomain
    AUDIT_NATIVE_QUERIES=False
    def __init__(self,case):
        self.stack=ExitStack();case.addCleanup(self.stack.close)
        self.domain=self.domain_type(case);domain=self.domain;self.original=domain.runtime.adapter
        self.directory=tempfile.TemporaryDirectory(prefix='avatar-frontdoor-');case.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);self.root.chmod(0o700)
        self.artifacts=self.root/'candidate';self.artifacts.mkdir(mode=0o700)
        candidate=self.artifacts/'declared-model.ipa';candidate.write_bytes(b'Declared native model, not an installable IPA');candidate.chmod(0o600)
        self.config_store=PrivateFeatureState(self.root/'feature-configuration.json')
        self.reader_store=PrivateFeatureState(self.root/'fixture-reader.json')
        self.reader_store.write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=domain.client.url,adapterToken=domain.adapter),None)
        self.stack.enter_context(patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(self.config_store.path)))
        self.operations=[]
        self.bundle_audit_lock=threading.Lock();self.bundle_audit_sent={};self.bundle_audit_last={}
        # These are original declared OS/Bundle PRODUCER boundaries. New raw
        # responses use actual queries and existing producer clock/nonce; no
        # retained observation, binding or target fingerprint is rewritten.
        for role,native in domain.natives.items():
            gate=domain.installed[role];old_execute=native.execute;old_post=native.post
            def execute(session,operation,values,*,role=role,native=native,gate=gate,old=old_execute):
                need(session==native.state['sessionId']);self.operations.append((role,operation,deepcopy(values)))
                if operation=='mobile: overteProcessSourceInfo':
                    need(values==dict(bundleId=native.target['appId']));return deepcopy(gate.source)
                if operation=='mobile: terminateApp':
                    need(values==dict(bundleId=native.target['appId']));native.lifecycle_input('app.stop');gate.process=None;return None
                if operation=='mobile: pullFile' and values.get('remotePath','').endswith('/ios-installed-bundle-observation.json'):
                    wanted='@'+native.target['appId']+':documents/'+native.target['testBuild']['resultsDirectory']+'/ios-installed-bundle-observation.json'
                    need(values==dict(remotePath=wanted));raw=gate.native.original()
                    if self.AUDIT_NATIVE_QUERIES:self.audit_bundle('original',role,json.loads(raw) if raw else None)
                    return base64.b64encode(raw.encode()).decode()
                return old(session,operation,values)
            def post(request,timeout,*,role=role,native=native,gate=gate,old=old_post):
                def produce():
                    command=json.loads(request.data)
                    if command.get('action')!='ios-bundle-observe':return old(request,timeout)
                    native.commands.append(deepcopy(command));native.echo=json.dumps(command).encode();gate.native.send(command)
                    self.audit_bundle('sent',role,command);return native
                channels=getattr(native,'avatar_channels',None)
                return produce() if channels is None else channels.http_reply(produce)
            native.execute=execute;native.post=post
        outer=self
        class Base:
            def __init__(_self,platform):_self.platform=platform;_self.adapter_id='avatar-host-declared-native'
            @staticmethod
            def advertised_capabilities(_target):return ['app.launch','app.foreground','app.process']
            def target(_self,selector):return deepcopy(domain.natives[selector].target)
            def state_path(_self,selector):return outer.original.state_path(selector)
            def read_session(_self,selector):return outer.original.read_session(selector)
            def save_session(_self,selector,value):return outer.original.save_session(selector,value)
            def ensure_session(_self,selector):
                value=_self.read_session(selector);need(value is not None)
                return domain.natives[selector],value['sessionId'],value
            def invoke(_self,*_args):raise AssertionError('No generic operation fallback is selected')
            def cleanup(_self,*_args):raise AssertionError('Typed Avatar end must precede generic cleanup fallback')
            def script_store(_self,selector):return outer.original.script_store(selector)
            def script_files_store(_self,selector):return outer.original.script_files_store(selector)
            def script_restart_store(_self,selector):return outer.original.script_restart_store(selector)
            def script_restart_inputs_store(_self,selector):return outer.original.script_restart_inputs_store(selector)

        gate=domain.installed['primary']
        summary=dict(physicalHandoffVersion=1,bundleIdentity=deepcopy(gate.native.bundle),
            artifactIdentity={key:gate.scope[key] for key in ('sourceRevision','artifactSha256')})
        self.adapter=create_physical_adapter(SimpleNamespace(artifact_root=str(self.artifacts)),Base,lambda _args:deepcopy(summary))
        # Actual _target/_scope/_binding/candidate verification stay literal.
        domain.runtime.adapter=self.adapter
    def audit_bundle(self,kind,role,value):
        """Bounded metadata per distinct nonce/status; never credentials/locals.

        Each original read is still performed. Repeated unchanged foreign
        nonces do not create a diagnostic row per 100-ms poll. This journal is
        a host transport diagnostic and supplies no product/source verdict.
        """
        if not self.AUDIT_NATIVE_QUERIES:return
        need(kind in ('sent','original') and role in ('primary','actor')
            and (value is None or type(value) is dict))
        thread=threading.get_ident();key=(role,thread)
        command=None if value is None else value.get('commandId')
        with self.bundle_audit_lock:
            if kind=='sent':self.bundle_audit_sent[key]=command
            status=None if value is None else value.get('status')
            identity=(kind,role,thread,command,status,self.bundle_audit_sent.get(key))
            if self.bundle_audit_last.get((kind,role,thread))==identity:return
            self.bundle_audit_last[(kind,role,thread)]=identity
            row=dict(event=kind,role=role,thread=thread,commandId=command,
                sentByThisThread=self.bundle_audit_sent.get(key),status=status,
                sequence=None if value is None else value.get('sequence'))
            need(all(item is None or type(item) in (str,int) for item in row.values()))
            path=self.root/'native-bundle-query-diagnostics.jsonl'
            descriptor=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
            with os.fdopen(descriptor,'a') as stream:
                stream.write(json.dumps(row,sort_keys=True)+'\n');stream.flush();os.fsync(stream.fileno())

    def configuration(self,version):
        primary=self.domain.owners['primary']
        value=dict(iosFeatureAdapterVersion=version,areas=['avatar-people'],fixtureConfig=str(self.reader_store.path))
        if version>=2:value['graphics']=None
        if version>=3:value['create']=None
        if version>=4:value['emotes']=None
        if version>=5:value.update(worldNavigation=None,worldWeb=None,tabletWeb=None,
            avatarPeople=dict(artifactRoot=str(primary.root),imagePolicy=deepcopy(primary.policy),actorTarget='actor'))
        if version>=6:value['emoteCoordinatorVersion']=None
        if version>=7:value['worldWebCoordinatorVersion']=None
        if version>=8:value['emoteTargets']=None
        return value
    def set_configuration(self,value):self.config_store.write(value,self.config_store.read())
    def snapshot_effects(self):
        return dict(os=deepcopy(self.operations),native={role:deepcopy(n.commands) for role,n in self.domain.natives.items()},
            input={role:list(n.input_log) for role,n in self.domain.natives.items()},
            lifecycle={role:list(n.lifecycle_inputs) for role,n in self.domain.natives.items()})
