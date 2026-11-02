"""Owned stdin host fixture; Native/replication/renderer/phase/time are models.

No SDK, device, network listener, service, compiler or normal product input.
The actual Create Parent in the other process supplies domain properties to
this independently faultable replica model, never public facts or verdicts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent)]
from test_create_model_resource_join import ResourceActor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.create_peer_source import PicoCreatePeerSource
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client


def native_domain_births(packet,births):
    """Explicit original Native v4 producer seam, not a compatibility reader."""
    source=packet['source'];source['createEntitySourceVersion']=4
    source['localCreations']=dict(createLocalCreationsVersion=1,armedAfterSequence=0,lastSequence=0,events=[])
    source['avatarRotation']=[0,0,0,1]
    for row in source['entities']:
        births.setdefault(row['id'],row['lastEditedEpochUs'])
        row.update(createdEpochUs=births[row['id']],lastEditedBy='22222222-2222-2222-2222-222222222222',voxels=None)
    return packet


def main():
    config=PrivateFeatureState(Path(sys.argv[2])).read();root=Path(sys.argv[2]).parent
    world_store=PrivateFeatureState(Path(config['worldPath']));b=ResourceActor(root)
    b.binding=config['binding'];b.loaded=True;b.submitted=-10;b.known=set();world=None;phase_sequence=0
    def update():
        nonlocal world
        world=world_store.read();b.ui.clock=max(b.now(),world['clock'])
        if not world.get('ignoreDelete',False) or world['rows']:
            b.rows=[] if world.get('ignoreEntity',False) else deepcopy(world['rows'])
        present={row['id'] for row in b.rows};b.absent=sorted(set(b.absent)|(b.known-present));b.known.update(present)
        b.ignore_renderer=world.get('ignoreRenderer',False);b.retain_models=world.get('retainModels',False)
        b.retain_resources=world.get('retainResources',False);b.replace_native_model=world.get('replaceModel',False)
    def original_reader(kind):
        native=b.reader('entities') if kind=='entities' else b.resource_reader();send=native.send;wire=['']
        def acquire(command):
            update();send(command);packet=json.loads(native.original())
            primary=json.loads(config['scope']['primaryEntities'])
            packet['processId']=456;packet['instance']=primary['instance'] if world.get('sameClient',False) else 'a'*32
            session=packet['source']['domainSession'];session.update(instance='b'*32,connectionBirth='c'*32)
            if kind=='entities':
                native_domain_births(packet,deepcopy(world['births']))
                for life in packet['source']['entityLifetimes']:life['instance']=uuid.uuid5(uuid.NAMESPACE_URL,'peer:'+life['id']).hex
                if world.get('differentCreation',False):
                    for row in packet['source']['entities']:row['createdEpochUs']+=1
                if world.get('wrongType',False):
                    for row in packet['source']['entities']:row['type']='Box'
                packet['source']['sessionId']=primary['source']['sessionId'] if world.get('sameClient',False) else '33333333-3333-3333-3333-333333333333'
                if world.get('foreignDomain',False):packet['source']['domainId']='44444444-4444-4444-4444-444444444444'
            if world.get('stale',False):packet['capturedEpochMs']-=2000
            wire[0]=json.dumps(packet,indent=2)+'\n'
        original=native.original
        # The producer invokes its original body before exposing the distinct
        # explicit client DTO. Keep its original read callback unmodified.
        def acquire_original(command):
            current=native.original;native.original=original
            try:acquire(command)
            finally:native.original=current
        native.send=acquire_original;native.original=lambda:wire[0];native.pid=456;return native
    class Phases(Client):
        def request(self,path,value=None,method=None,**options):
            nonlocal phase_sequence
            assert path=='/runs/'+config['scope']['runId']+'/phase' and value is None and method is None
            update();phase_sequence+=1;packet=deepcopy(world['phase'])
            if world.get('foreignPhase',False):packet['instance']='d'*32
            packet.update(requestId=options['phase_nonce'],sequence=10000+phase_sequence,capturedEpochMs=b.epoch());return packet
    update()
    client=Phases(config['scope']['fixtureUrl'].split('/runs/')[0],'owned-fixture-model-'+'a'*32)
    phases=PhaseFixtureReader(client,config['scope']['runId'],'create',epoch_ms=b.epoch,monotonic=b.now)
    source=PicoCreatePeerSource(root/'create-peer-originals.json',config['scope'],config['binding'],original_reader('entities'),
        original_reader('resources'),phases,ScriptSourceLock(root/'script-sources.lock'),guard=lambda:True,monotonic=b.now,sleep=b.ui.sleep)
    sender=None
    print(json.dumps(dict(ready=True)),flush=True)
    for line in sys.stdin:
        command=line.strip()
        try:
            if command=='read':result=source.read()
            elif command=='cleanup':result=source.cleanup()
            elif command=='publish':
                sender=source.sender(PrivateFeatureState(root/'return.json'),PrivateFeatureState(root/'consumption.json'));result=sender.publish()
            elif command=='consume':result=sender.consume()
            elif command=='stats':result=dict(entities=b.sequence['entities'],resources=b.resource_sequence,
                chunks=len(source.disk['chunks']),records=len(source.disk['records']),failed=source.failed,pending=source.disk['pending'])
            elif command=='tick':b.ui.sleep(.7);result=dict(explicitModelClock=b.now())
            elif command=='exit':break
            else:raise ValueError('Unsupported owned fixture command')
            print(json.dumps(dict(ok=True,result=result)),flush=True)
        except Exception as error:
            print(json.dumps(dict(ok=False,error=type(error).__name__)),flush=True)


if __name__=='__main__':main()
