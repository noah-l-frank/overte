"""Original Parent-owned flow/cursor and separate actual Actor host.

Native/widget/Parent admission producers are model seams. The single actual
fixture coordinator stays in the Parent; only normal raw fixture requests and
responses cross the owned stdin transport. No live owner crosses processes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests.test_chat_remote_actor_return import WORKER as RETURN_WORKER

ACTOR_WORKER=RETURN_WORKER.split('h=fixture.PicoChatCursorActorTests();h.setUp();actor=h.actor')[0]+'''
import json,uuid,os
from copy import deepcopy
from types import SimpleNamespace
from adapters.chat_actor_files import ChatActorFiles
from adapters.chat_journey.compiled_samples import CompiledChatSamples,CompiledChatCacheAbsence
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.observation_cursor import ChatObservationCursor
from adapters.chat_journey.observation_publisher import ChatObservationPublisher
from adapters.chat_journey.script_source import ChatScriptSource
from adapters.chat_journey.cursor_source_seal import ChatCursorSourceSeal
from adapters.chat_journey.source_chunks import digest
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.native_fd_owner import OriginalDescriptor
from adapters.pico4.chat_composition import PicoChatWitness
from adapters.pico4.chat_cursor_actor import PicoChatCursorActor
from adapters.host_process_identity import host_identity
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_actor_process import LinuxChatActorProcess
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from self_tests import test_chat_observation_publisher as sources
from self_tests.test_chat_script_source import CompiledBoundary
from self_tests.chat_cursor_fixture import cleanup
h=sources.ChatObservationPublisherTests();h.setUp();native=h.native
native.epoch=config['epoch'];native.host=config['host'];h.cursor.read(0)
stores={key:PrivateFeatureState(path) for key,path in config['stores'].items()}
locks=tuple(ScriptSourceLock(path) for path in config['locks'])
client=Client(config['fixtureUrl'].split('/runs/')[0],'a'*48)
def request(path,value=None,**kwargs):
    print(json.dumps(dict(kind='fixture',path=path,body=value,phaseNonce=kwargs.get('phase_nonce'))),flush=True)
    return json.loads(sys.stdin.readline())
client.request=request
source=PhaseFixtureReader(client,config['runId'],'chat',epoch_ms=lambda:native.epoch,monotonic=lambda:native.host)
boundary=CompiledBoundary();send=boundary.roots.send;full=boundary.full
def roots(request):boundary.roots.epoch=native.epoch;send(request);boundary.roots.value['processId']=123
boundary.roots.send=roots
def script(value):full(value);value.update(processId=123,capturedEpochMs=native.epoch,requestedEpochMs=native.epoch)
boundary.script.mutate=script;root_reader,script_reader=boundary.readers()
for reader in (root_reader,script_reader):
    reader.pid=123;reader.clock_ms=lambda:native.epoch;reader.monotonic=lambda:native.host;reader.sleep=h.flow.sleep
with locks[0].held():code=ChatScriptSource(config['runId'],'actor',config['binding'],root_reader,script_reader,stores['code'],locks[0],monotonic=lambda:native.host)
def samples(stage):
    original=h.flow.h;kind=CompiledChatSamples if stage=='active' else CompiledChatCacheAbsence
    readers=(original.h.primary.reader(),original.h.peer.reader(),original.h.view.reader(vr=True),original.h.native.reader())
    readers[1].pid=456
    for reader in readers:reader.clock_ms=lambda:native.epoch;reader.monotonic=lambda:native.host;reader.sleep=h.flow.sleep
    return kind(config['runId'],'actor',config['binding'],config['peerBinding'],*readers,
        stores[stage+'-samples'],*locks,vr=True,script_source=code,monotonic=lambda:native.host)
def observation(stage,role=None):
    return ChatObservationOwner(source,role or samples(stage),stores['flow'],stores[stage+'-observation'],stage=stage,
        cleanup_store=stores['cleanup'] if stage=='cleanup' else None,monotonic=lambda:native.host)
a=PicoChatCursorActor.__new__(PicoChatCursorActor);a.target='original-model-target';a.source=source
a.store,a.stop_store=stores['actor'],stores['stop'];a.return_store,a.consumption_store=stores['return'],stores['consumption']
a.previous=None;a.previous_sha=digest(None);a.root_stamp=None;a.return_sender=None;a.return_started=a.parent_consumed=False
a.failed=a.started=a.closed=False;a.seal=None;a.seal_receipt=None;a.stop_value=a.stop_stamp=a.stop_raw=None
a.scope=dict(picoChatCursorActorVersion=3,instance=uuid.uuid4().hex,runId=config['runId'],fixtureUrl=config['fixtureUrl'],
    binding=config['binding'],peerBinding=config['peerBinding'],hostProcessIdentity=host_identity());a.scope_sha=digest(a.scope)
original=a.original=PicoChatWitness.__new__(PicoChatWitness);original.binding=config['binding'];original.lock=locks[0]
original.native=SimpleNamespace(guard=lambda:True);peer=original.peer=OwnedChatPeer.__new__(OwnedChatPeer)
peer.lock=locks[1];peer.binding=config['peerBinding'];peer.guard=lambda:True;peer.retirement_files=None
peer.reader=lambda:samples('cleanup').peer
peer.files=ChatActorFiles.__new__(ChatActorFiles);peer.files.fd_owner=OriginalDescriptor(stores['actor'].path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);peer.files.fd=peer.files.fd_owner.fd
peer.process=LinuxChatActorProcess.__new__(LinuxChatActorProcess);peer.process.fd_owner=OriginalDescriptor('/proc/self/exe',os.O_RDONLY|os.O_CLOEXEC);peer.process.fd=peer.process.fd_owner.fd
a.pairs=tuple((owner,dict(label=label,node=list(owner.node),fd=owner.fd,anchor=owner.anchor)) for label,owner in
    (('peer-directory',peer.files.fd_owner),('peer-executable',peer.process.fd_owner)));a.pairs_sha=digest([row for _owner,row in a.pairs])
original.publisher=SimpleNamespace(samples=samples('active'))
a.adapter=SimpleNamespace(_chat_composition_store=lambda _target:PrivateFeatureState(config['parent']),
    _scripts=lambda _target:SimpleNamespace(binding=config['binding']),
    _chat_observation=lambda _target,_source,role,**kw:observation(kw['stage'],role),
    _chat_cache_absence=lambda *_args,**_kw:samples('cleanup'),
    _chat_cursor_source_seal=lambda _target,publisher,**_kw:ChatCursorSourceSeal(publisher,stores['seal']))
initial=observation('initial');cursor=ChatObservationCursor(initial,stores['cursor']);a.publisher=ChatObservationPublisher(cursor,stores['publisher'])
a.save('publishing',pairs=[deepcopy(row) for _owner,row in a.pairs],returnedPublication=None);a.publish()
PrivateFeatureState(config['metadata']).write(dict(expected={key:a.scope[key] for key in
    ('runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance')}),None)
print(json.dumps(dict(kind='ready')),flush=True)
for line in sys.stdin:
    command=json.loads(line);action=command['action']
    if action=='exit':break
    if action=='publish':value=a.publish()
    elif action=='tick':h.flow.sleep(command['seconds']);value=True
    elif action=='advance':
        h.flow.next(1);h.cursor.select(h.observation(h.h.samples('actor',h.flow.w.witness_store),'active'));h.cursor.read(1);value=a.publish()
    elif action=='cleanup':cleanup(h.h,h.cursor);value=a.publish()
    elif action=='late':native.epoch+=2000;value=True
    elif action=='stop':a.stop_once();a.publish_return();value=True
    elif action=='consume':a.consume_return();value=True
    else:raise ValueError('Closed fixture command')
    print(json.dumps(dict(kind='reply',value=value)),flush=True)
'''


class RemoteActorFixture:
    def start_actor(self,parent,stores,locks,admission):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.host_root=Path(temporary.name);self.host_root.chmod(0o700);(self.host_root/'tmp').mkdir(mode=0o700)
        self.entry=self.host_root/'original-actor.py';self.entry.write_text(ACTOR_WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.metadata=PrivateFeatureState(self.host_root/'metadata.json');config=PrivateFeatureState(self.host_root/'config.json')
        config.write(dict(metadata=str(self.metadata.path),stores={key:str(store.path) for key,store in stores.items()},
            locks=[str(lock.path) for lock in locks],parent=str(admission.path),epoch=parent.native.epoch,host=parent.native.host,
            runId=parent.initial.source.run,fixtureUrl=parent.initial.source.fixture_url,
            binding=parent.cursor.scope['binding'],peerBinding=parent.cursor.scope['peerBinding']),None)
        self.journal=parent.flow.w.journal;self.run=parent.initial.source.run;self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(config.path)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(self.host_root/'tmp'),
                'OVT_CHAT_CLEANUP_ACTOR':self.token});self.addCleanup(self.finish_actor);self.response('ready')
        fields=Path(f'/proc/{self.worker.pid}/stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            try:
                with Path(f'/proc/{pid}/environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and raw.split(b'\0').count(('OVT_CHAT_CLEANUP_ACTOR='+self.token).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,config.path,hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),
            hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned);self.addCleanup(self.process.close)
        self.expected=self.metadata.read()['expected'];self.assertEqual(identity,self.expected['hostProcessIdentity'])

    def response(self,kind):
        while True:
            self.assertTrue(select.select([self.worker.stdout],[],[],20)[0]);raw=self.worker.stdout.readline()
            if not raw:
                self.worker.wait(timeout=5);self.fail(self.worker.stderr.read().decode())
            value=json.loads(raw)
            if value['kind']!='fixture':self.assertEqual(kind,value['kind']);return value.get('value')
            path=value['path']
            if path.endswith('/phase'):result=self.journal.phase(self.run,value['phaseNonce'])
            elif path.endswith('/samples'):self.journal.publish(self.run,value['body']);result={'accepted':True}
            else:self.assertEqual('/runs/'+self.run,path);result=self.journal.snapshot(self.run)
            self.worker.stdin.write((json.dumps(result)+'\n').encode());self.worker.stdin.flush()

    def command(self,action,**fields):
        self.worker.stdin.write((json.dumps(dict(action=action,**fields))+'\n').encode());self.worker.stdin.flush()
        return self.response('reply')

    def finish_actor(self):
        if not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=20)
        for stream in (self.worker.stdout,self.worker.stderr):stream.close()
