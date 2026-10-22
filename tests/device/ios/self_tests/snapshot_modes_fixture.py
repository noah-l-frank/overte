"""Real private multi-output files and owners; native/Script/SDK clocks modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
from io import BytesIO
import json
from PIL import Image
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import snapshot_capture_controls as controls,snapshot_chunks
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.self_tests.test_ios_snapshot_completion import SnapshotCompletionTests,BASE,RUN
from ios.self_tests.test_ios_snapshot_captures import Native


def image_bytes(kind,*,frames=2):
    image=Image.new('RGB',(32,16),'navy');image.paste('orange',(8,4,24,12));stream=BytesIO()
    if kind=='gif':
        other=Image.new('RGB',image.size,'green');other.paste('purple',(4,2,28,14))
        image.save(stream,format='GIF',save_all=True,append_images=[other] if frames==2 else [],duration=500,loop=0)
    else:image.save(stream,format={'png':'PNG','jpg':'JPEG'}[kind])
    return stream.getvalue()


class ModesFixture(SnapshotCompletionTests):
    def setUp(self):
        super().setUp();self.mode='still';self.format='png';self.output_paths=[]
        observed=self.input_native.observed
        def observation():
            value=observed();value['controls'][0]['snapshotMode']=('still','animated','panorama','cubemap').index(self.mode);return value
        self.input_native.observed=observation
        self.f.h.post=self.post_files

    def post_files(self,request,timeout):
        native=self.ctx.files;q=native.fixture.set_client_command(json.loads(request.data));native.commands.append(q);native.echo=json.dumps(q).encode()
        rows=[];content={}
        for path in self.output_paths:
            stat=path.lstat();raw=path.read_bytes()
            revision=hashlib.sha256(str((stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)).encode()).hexdigest()
            rows.append(dict(name=path.name,size=len(raw),revision=revision,sha256=hashlib.sha256(raw).hexdigest()));content[path.name]=raw
        native.value=dict(schemaVersion=q['schemaVersion'],commandId=q['commandId'],operation=q['operation'],prefix=q['prefix'],processId=42,
            sampleEpochMs=self.now,ok=True)
        if q['operation']=='list':native.value['files']=sorted(rows,key=lambda v:v['name'])
        else:
            row=next(v for v in rows if v['name']==q['name']);assert row['revision']==q['revision']
            raw=content[row['name']];offset=q['offset'];part=raw[offset:offset+snapshot_chunks.CHUNK_BYTES]
            native.value['file']=dict(name=row['name'],revision=row['revision'],size=len(raw),offset=offset,eof=offset+len(part)==len(raw),data=base64.b64encode(part).decode())
        return native

    def manifest(self,index):
        owner=SnapshotManifest(PrivateFeatureState(self.ctx.root/('ios-snapshot-primary-manifest-'+format(index,'04d')+'.json')),
            self.ctx.lock,self.ctx.binding,RUN,'primary',index,self.ctx.feature,self.clock(),lambda:True)
        owner.reserve('still-'+self.format if self.mode=='still' else self.mode);owner.send(self.now);owner.recover();return owner

    def work(self):
        before,after=super().work()
        for packet in (before,after):
            for worker in packet['source']['workers']:
                worker['state']['mode']=self.mode;worker['latest']['state']['mode']=self.mode
                for event in worker['events']:event['state']['mode']=self.mode
        return before,after

    def prepared_set(self,mode='still',kind='png',*,gif_frames=2,extra=False):
        self.mode,self.format=mode,kind;label='still-'+kind if mode=='still' else mode
        self.f.h.prefix='parity-'+RUN[:16]+'-'+label;self.input_native.name=self.f.h.prefix
        first=self.manifest(1);native=Native();native.tick=lambda:self.now
        native.clock=lambda:dict(epochMs=self.now,monotonicMs=self.now-BASE+1000)
        self.now=BASE-40;before_native=native.read();before_work,after_work=self.work();self.now=BASE+10
        inputs=SnapshotInputOwner(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-inputs.json'),self.ctx.lock,
            self.ctx.binding,RUN,'primary',self.input_native.input(),lambda:True)
        inputs.reserve('snapshot.capture',controls.project(inputs.native.capture()));inputs.send()
        self.now=BASE+1000;capture,identifier=native.begin(self.request)
        kinds=[kind,'gif'] if mode=='animated' else [kind]
        if extra:kinds.append('jpg' if kind!='jpg' else 'png')
        self.now=BASE+1050
        for extension in kinds:
            path=self.ctx.root/(self.f.h.prefix+'-'+self.request+'.'+extension)
            path.write_bytes(image_bytes(extension,frames=gif_frames));path.chmod(0o600);self.output_paths.append(path)
        if mode!='still':native.event(identifier,'status',phase='processing',hasPath=mode=='animated',hasError=False)
        self.now=BASE+1100;native.finish(capture,identifier);del capture
        self.now=BASE+1122;after_native=native.read();self.now=BASE+1130;start=self.manifest(2)
        groups=[];index=0
        for path in self.output_paths:
            chunks=[]
            for offset in range(0,path.stat().st_size,snapshot_chunks.CHUNK_BYTES):
                index+=1;owner=self.f.h.owner(index);owner.reserve_original(start,path.name,offset);owner.send(self.now);owner.recover();chunks.append(owner)
            groups.append(chunks)
        finish=self.manifest(3);self.f.callbacks.clear();work=self.f.jobs.read();artifacts=[]
        for index,chunks in enumerate(groups,1):
            artifact=SnapshotArtifact(PrivateFeatureState(self.ctx.root/('ios-snapshot-primary-artifact-'+format(index,'04d')+'.json')),
                self.ctx.lock,self.ctx.binding,RUN,'primary',index,lambda:True)
            artifact.capture(start,finish,chunks,work);artifacts.append(artifact)
        return inputs,1,before_work,after_work,before_native,after_native,first,artifacts,'qrc:/scripts/'
