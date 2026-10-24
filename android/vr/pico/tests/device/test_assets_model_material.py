"""Same normal Assets flow through real original material/texture CPU owners.

No Model/renderer/Actor readiness is supplied. Original geometry-cache and
parentless glTF-request retention remain explicit live negative evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import stat
from pathlib import Path
import shutil
import unittest
import test_assets_geometry_resource as resource_module
import test_assets_cancel_effects as effects_module
from test_create_polyvox_controls_native import compile_original_native
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW
from adapters.normal_feature_state import PrivateFeatureState
from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.native_fd_owner import OriginalDescriptor


class AssetsModelMaterialTests(resource_module.AssetsGeometryResourceTests):
    prepare_name='assets-model-material-prepare.py'
    model_cache=True
    model_baker=True

    @classmethod
    def compile_native(cls,command):
        try:compile_original_native(cls.parser_stage,command,cls.environment)
        finally:
            destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
            if destination:
                # Retain the actual fresh build stage even when compilation
                # refuses before the first normal Assets acquisition.
                shutil.copytree(cls.parser_stage,Path(destination)/'model-material-build-originals')

    def prepare_native_environment(self):
        profile=self.path/'original-material-profile';profile.mkdir(mode=0o700)
        for variable,leaf in (('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache')):
            path=profile/leaf;path.mkdir(mode=0o700);self.environment[variable]=str(path)

    def native_provenance_names(self):
        return (*super().native_provenance_names(),'model-material-original-provenance.json','create-texture-original-provenance.json',
            'original-create-build-inputs.json','original-create-build-result.json')

    def source_scope(self):
        return dict(binding=deepcopy(self.binding),parserArtifactSha256=hashlib.sha256(self.parser.read_bytes()).hexdigest(),
            kind='original-assets-model-material-provenance')

    def source_originals(self):
        result={}
        for name in self.native_provenance_names():
            raw=(self.parser_stage/name).read_bytes()
            result[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),raw=raw.decode('utf-8'))
        return result

    def source_root(self):
        return PrivateFeatureState(self.parser_store.path.with_name(self._testMethodName+'-source-provenance.json'))

    def native_source_provenance(self):
        scope=self.source_scope();original=dict(modelMaterialSourceProvenanceVersion=1,scope=scope,files=self.source_originals())
        ref,parts=source_bundles.prepare(original,0,[]);root=self.source_root();root._parent()
        owner=OriginalDescriptor(root.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        info=os.fstat(owner.fd)
        parent=dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,uid=info.st_uid,links=info.st_nlink)
        def parent_guard():
            root._parent();owner.require(owner.fd);current=root.path.parent.lstat()
            self.assertEqual(parent,dict(device=current.st_dev,inode=current.st_ino,mode=current.st_mode,uid=current.st_uid,links=current.st_nlink))
        try:
            parent_guard();history=ChatSourceChunks(root,scope);manifest=[]
            state=dict(modelMaterialSourceProvenanceVersion=1,scopeSha256=digest(scope),phase='reading',chunks=manifest,bundle=ref)
            root.write(state,None)
            for part in parts:
                parent_guard();manifest=history.append(part,manifest);updated=dict(state,chunks=manifest)
                root.write(updated,state);state=updated;parent_guard()
            sealed=dict(state,phase='sealed');root.write(sealed,state);parent_guard()
            reader=ClosedOriginalFile(root.path,0o600,parent_guard);raw,stamp=reader.read();self.assertTrue(reader.close())
            reference=dict(modelMaterialSourceProvenanceVersion=1,scope=scope,parent=parent,
                root=dict(name=root.path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),stamp=stamp),
                chunks=[list(value) for value in history.identities])
            self.read_source_provenance(reference);parent_guard()
            return reference
        finally:self.assertTrue(owner.close())

    def read_source_provenance(self,reference):
        # Every call constructs a cold reader; a descriptor/path/hash or warm
        # decoded object never replaces rereading all admitted original bytes.
        self.assertEqual({'modelMaterialSourceProvenanceVersion','scope','parent','root','chunks'},set(reference))
        self.assertIs(type(reference['modelMaterialSourceProvenanceVersion']),int)
        self.assertEqual(1,reference['modelMaterialSourceProvenanceVersion'])
        scope=self.source_scope();self.assertEqual(canonical(scope),canonical(reference['scope']))
        root=self.source_root();root._parent();self.assertEqual(root.path.name,reference['root']['name'])
        owner=OriginalDescriptor(root.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        def parent_guard():
            root._parent();owner.require(owner.fd);held=os.fstat(owner.fd);current=root.path.parent.lstat()
            for info in (held,current):
                self.assertTrue(stat.S_ISDIR(info.st_mode))
                self.assertEqual(reference['parent'],dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,uid=info.st_uid,links=info.st_nlink))
        try:
            parent_guard();reader=ClosedOriginalFile(root.path,0o600,parent_guard);raw,stamp=reader.read()
            self.assertEqual(reference['root']['stamp'],stamp);self.assertEqual(reference['root']['bytes'],len(raw))
            self.assertEqual(reference['root']['sha256'],hashlib.sha256(raw).hexdigest());self.assertTrue(reader.close())
            state=json.loads(raw);self.assertEqual({'modelMaterialSourceProvenanceVersion','scopeSha256','phase','chunks','bundle'},set(state))
            self.assertEqual(1,state['modelMaterialSourceProvenanceVersion']);self.assertEqual('sealed',state['phase'])
            self.assertEqual(digest(scope),state['scopeSha256'])
            history=ChatSourceChunks(root,scope);history.load(state['chunks'])
            self.assertEqual(reference['chunks'],[list(value) for value in history.identities])
            original,logical=source_bundles.original(history,state['chunks'],[state['bundle']],0)
            expected=dict(modelMaterialSourceProvenanceVersion=1,scope=scope,files=self.source_originals())
            self.assertEqual(canonical(expected),canonical(original))
            parent_guard();after,after_stamp=reader.read()
            self.assertEqual(raw,after);self.assertEqual(stamp,after_stamp);self.assertTrue(reader.close());history.verify()
            stored=sum(history.store(index).path.stat().st_size for index in range(len(state['chunks'])))
            self.provenance_usage=dict(files=len(state['chunks'])+1,bytes=len(logical)+len(raw)+stored)
            self.assertLessEqual(self.provenance_usage['files'],MAX_FRAMES);self.assertLessEqual(self.provenance_usage['bytes'],MAX_RAW)
            return original
        finally:self.assertTrue(owner.close())

    def export_effect_journals(self,directory,prefix):
        home=self.home_store.read() if hasattr(self,'home_store') else None
        if not home or home['phase'] not in ('home-retained','home-resources-retired'):
            # Refused/incomplete journeys retain their ordinary full negatives.
            return effects_module.AssetsCancelEffectsTests.export_effect_journals(self,directory,prefix)
        original=PrivateFeatureState(directory/(prefix+'-home.json'))
        if not hasattr(self,'journal_export_refs'):
            original.write(home,None);original._parent()
            owner=OriginalDescriptor(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            info=os.fstat(owner.fd)
            parent=dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,uid=info.st_uid,links=info.st_nlink)
            def guard():
                original._parent();owner.require(owner.fd);current=directory.lstat()
                self.assertEqual(parent,dict(device=current.st_dev,inode=current.st_ino,mode=current.st_mode,uid=current.st_uid,links=current.st_nlink))
            try:
                guard();reader=ClosedOriginalFile(original.path,0o600,guard);raw,stamp=reader.read();self.assertTrue(reader.close())
                self.assertEqual(canonical(home),canonical(json.loads(raw)));children=unpack(home['children']);refs={}
                for role,index in (('cancel',0),('files',1)):
                    child=children[index];live=(self.store if role=='cancel' else self.file_store).read()
                    self.assertEqual(canonical(live),canonical(child))
                    identity=({key:child[key] for key in ('browserId','modelId')} if role=='cancel' else {'ownerToken':child['ownerToken']})
                    reference=dict(assetsModelMaterialJournalReferenceVersion=1,kind='historical-home-child-original',
                        binding=deepcopy(self.binding),runId=self.run,role=role,index=index,parent=parent,
                        home=dict(name=original.path.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),stamp=stamp),
                        child=dict(bytes=len(canonical(child)),sha256=digest(child),identity=identity))
                    PrivateFeatureState(directory/(prefix+'-'+role+'.json')).write(reference,None);refs[role]=reference
                self.journal_export_refs=refs;guard()
            finally:self.assertTrue(owner.close())
        self.assertEqual(canonical(home),canonical(original.read()))
        for role in ('cancel','files'):
            reference=PrivateFeatureState(directory/(prefix+'-'+role+'.json')).read()
            self.assertEqual(canonical(self.journal_export_refs[role]),canonical(reference))
            child=self.read_effect_journal_reference(directory,prefix,role,reference)
            self.assertEqual(canonical((self.store if role=='cancel' else self.file_store).read()),canonical(child))

    def read_effect_journal_reference(self,directory,prefix,role,reference):
        # These aliases resolve retained historical originals. They never
        # acquire a current product sample or replace any Home/Quiet query.
        self.assertEqual({'assetsModelMaterialJournalReferenceVersion','kind','binding','runId','role','index','parent','home','child'},set(reference))
        self.assertIs(type(reference['assetsModelMaterialJournalReferenceVersion']),int)
        self.assertEqual(1,reference['assetsModelMaterialJournalReferenceVersion'])
        self.assertEqual('historical-home-child-original',reference['kind']);self.assertEqual(role,reference['role'])
        self.assertEqual(canonical(self.binding),canonical(reference['binding']));self.assertEqual(self.run,reference['runId'])
        index={'cancel':0,'files':1}[role];self.assertIs(type(reference['index']),int);self.assertEqual(index,reference['index'])
        original=PrivateFeatureState(directory/(prefix+'-home.json'));original._parent()
        self.assertEqual(original.path.name,reference['home']['name'])
        owner=OriginalDescriptor(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        def guard():
            original._parent();owner.require(owner.fd)
            for info in (os.fstat(owner.fd),directory.lstat()):
                self.assertTrue(stat.S_ISDIR(info.st_mode))
                self.assertEqual(reference['parent'],dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,uid=info.st_uid,links=info.st_nlink))
        try:
            guard();reader=ClosedOriginalFile(original.path,0o600,guard);raw,stamp=reader.read()
            self.assertEqual(reference['home']['stamp'],stamp);self.assertEqual(reference['home']['bytes'],len(raw))
            self.assertEqual(reference['home']['sha256'],hashlib.sha256(raw).hexdigest());home=json.loads(raw)
            self.assertEqual(canonical(self.binding),canonical(home['binding']));self.assertEqual(self.run,home['runId'])
            self.assertIn(home['phase'],('home-retained','home-resources-retired'))
            children=unpack(home['children']);self.assertEqual(2,len(children));child=children[index]
            self.assertEqual(reference['child']['bytes'],len(canonical(child)));self.assertEqual(reference['child']['sha256'],digest(child))
            self.assertEqual(canonical(self.binding),canonical(child['binding']));self.assertEqual(self.run,child['runId'])
            self.assertEqual('cancel-observed-files-retired' if role=='cancel' else 'retired',child['phase'])
            identity=({key:child[key] for key in ('browserId','modelId')} if role=='cancel' else {'ownerToken':child['ownerToken']})
            self.assertEqual(canonical(identity),canonical(reference['child']['identity']))
            after,after_stamp=reader.read();self.assertEqual(raw,after);self.assertEqual(stamp,after_stamp)
            self.assertTrue(reader.close());guard();return child
        finally:self.assertTrue(owner.close())

    def effect_journal_export_usage(self,cancel,files,home):
        # Remove copies only at the actual export producer: two references are
        # physically written and fully re-read before claiming their inventory.
        directory=self.parser_store.path.parent;prefix=self._testMethodName
        self.export_effect_journals(directory,prefix)
        for role,expected in (('cancel',cancel),('files',files)):
            reference=PrivateFeatureState(directory/(prefix+'-'+role+'.json')).read()
            self.assertEqual(canonical(expected),canonical(self.read_effect_journal_reference(directory,prefix,role,reference)))
        return 2,sum((directory/(prefix+'-'+role+'.json')).stat().st_size for role in ('cancel','files'))

    def validate_native_source_provenance(self,value):self.read_source_provenance(value)

    def validate_native_result(self,native,pending):
        self.assertEqual(2,native['modelMaterialHostEvidenceVersion'])
        self.assertTrue(native['protocolValid'] and native['workerRetired'] and native['sameOriginal'])
        self.assertEqual(pending['inputSha256'],native['sourcePacketSha256'])
        self.assertFalse(native['rendererReadinessQualified'] or native['wholeResourceRetired'])
        self.assertEqual(self.indexed,native['materialProcessingQualified'])
        self.assertEqual(self.indexed,native['bakerProcessingQualified'])
        self.assertEqual(0,native['pending']);self.assertEqual(0,native['processing'])
        self.assertEqual(self.resource_original['resources'][0]['sha256'],native['loadedOriginalSha256'])
        self.assertEqual(['constructed','loaded-signal','geometry-callback','external-reference-released','after-release'],
            [row['phase'] for row in native['ownerOriginals']])
        requests=native['requestBirths'];finishes=native['requestFinishes']
        self.assertEqual(3 if self.indexed else 2,len(requests));self.assertEqual(len(requests),len(finishes))
        self.assertTrue(all(not row['threads']['hasQObjectParent'] for row in requests))
        expected={row['url']:row for row in self.resource_original['resources']}
        births={row['url']:row for row in requests}
        self.assertEqual(len(requests),len(births))
        for row in finishes:
            self.assertEqual(births[row['url']]['instance'],row['instance']);self.assertNotEqual('0',row['instance'])
            self.assertTrue(row['receipt']['success'] and row['receipt']['onRequestThread'])
            self.assertEqual(expected[row['url']]['sha256'],row['receipt']['sha256'])
            self.assertEqual(expected[row['url']]['bytes'],row['receipt']['bytes'])
        self.assertEqual([False,True,False] if self.indexed else [False,True],native['transportPresenceBeforeProcessExit'])
        if self.indexed:
            owner=native['ownerOriginals'][-1]
            self.assertTrue(owner['alive'] and owner['resourceLoaded'] and owner['hfmPresent'])
            self.assertFalse(owner['resourceFailed']);self.assertEqual(1,native['cacheOriginals'][-1]['numCached'])
            self.assertGreater(native['cacheOriginals'][-1]['unusedLimit'],0)
            self.assertTrue(native['bakerInputAlive']);self.assertFalse(native['bakerGraphAlive'])
            self.assertGreaterEqual(native['bakerBuffersRemaining'],4)
            # Preserve the existing Baker selector's original indexed-fixture
            # checks while observing its new, honestly retained HFM/cache owner.
            rows=native['bakerOriginals']
            self.assertEqual(['constructed','run-enter','run-exit','destructor-enter'],[row['phase'] for row in rows])
            self.assertEqual(1,len({row['graphId'] for row in rows}));self.assertNotEqual('0',rows[0]['graphId'])
            self.assertEqual(1,len({row['id'] for row in rows}));self.assertEqual(1,len({row['thread'] for row in rows}))
            self.assertTrue(all(row['graphAlive'] and row['inputAlive'] for row in rows))
            self.assertEqual(0,rows[0]['bufferCount']);self.assertGreater(rows[2]['bufferCount'],0)
            before=native['parsedHandoff'];processed=native['bakerHandoff']
            for key in ('id','url','joints','materials','textures'):self.assertEqual(before[key],processed[key])
            self.assertEqual(0,processed['errors']);self.assertEqual(1,len(processed['meshes']))
            mesh=processed['meshes'][0];self.assertTrue(mesh['graphicsMeshExists'] and mesh['skinningDataValid'])
            self.assertEqual([[-.5,0,0],[.5,0,0],[0,1,0]],mesh['bufferVertices'])
            self.assertEqual([0,1,2],sorted(mesh['bufferIndices']));self.assertEqual(1,mesh['bufferParts'])
            self.assertEqual(3,len(mesh['normals']));self.assertEqual(3,len(mesh['tangents']))
            materials=native['materialOriginals'];self.assertEqual(2,len(materials))
            self.assertEqual('published',materials[0]['phase']);self.assertEqual('released',materials[1]['phase'])
            self.assertEqual(materials[0]['material'],materials[1]['material']);self.assertFalse(materials[1]['alive'])
            textures=native['textureOriginals'];self.assertEqual(['decoded','released'],[row['phase'] for row in textures])
            self.assertTrue(textures[0]['alive'] and textures[0]['loaded']);self.assertFalse(textures[0]['failed'])
            self.assertGreater(textures[0]['storedBytes'],0);self.assertGreater(textures[0]['width'],0);self.assertGreater(textures[0]['height'],0)
            self.assertEqual(self.resource_original['resources'][2]['url'],textures[0]['url'])
            self.assertEqual(textures[0]['instance'],textures[1]['instance']);self.assertFalse(textures[1]['alive'])
            pixels=native['pixelOriginals'];self.assertEqual(2,len(pixels))
            self.assertTrue(pixels[0]['alive']);self.assertFalse(pixels[1]['alive'])
            self.assertEqual(pixels[0]['instance'],pixels[1]['instance']);self.assertNotEqual('0',pixels[0]['instance'])
        else:
            self.assertFalse(native['ownerOriginals'][-1]['alive'])
            for name in ('materialOriginals','textureOriginals','pixelOriginals','bakerOriginals'):self.assertEqual([],native[name])

    def exercise_cancel_home(self,baseline):
        counts,raw=super().exercise_cancel_home(baseline)
        if self.parser_original['bakerHandoff']:counts+=1
        for name in ('materialOriginals','textureOriginals','pixelOriginals','requestBirths','requestFinishes'):
            counts+=len(self.parser_original[name])
        # The persisted composite repeats the actual input and native originals
        # alongside the expanded original-source/tool/build provenance. Count
        # this additional physical envelope instead of ignoring its new bytes.
        self.read_source_provenance(self.parser_disk['originalCppSources'])
        counts+=1+self.provenance_usage['files'];raw+=len(canonical(self.parser_disk))+self.provenance_usage['bytes']
        return counts,raw

    def test_original_geometry_nonindexed_parser_refusal_and_original_owner_retirement(self):
        self.exercise(True);self.assertFalse(self.parser_original['materialProcessingQualified'])
        self.assertIn('No indices accessor',self.parser_disk['stderr'])

    def test_indexed_geometry_original_download_worker_cpu_handoff_and_original_owner_retirement(self):
        self.exercise(True);self.assertTrue(self.parser_original['materialProcessingQualified'])
        self.assertFalse(self.parser_original['wholeResourceRetired'])


if __name__=='__main__':unittest.main()
