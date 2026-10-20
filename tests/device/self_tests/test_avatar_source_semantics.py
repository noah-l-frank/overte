"""Execute original Avatar handlers with synthetic native boundaries in Node.

These checks establish source semantics only: no geometry, peer or device runs.
The actual unmodified handler bodies are evaluated, not a copied reducer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[3]
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const original=fs.readFileSync(process.argv[1],'utf8');
function section(start,end){
 const a=original.indexOf(start),b=original.indexOf(end,a+start.length);
 assert(a>=0&&b>a,'Original source handler boundary changed');return original.slice(a,b);
}
let joints=['Root','Spine','Hips','Head'],entities=[],applied=[],messages=[];
const signal={connect(){},disconnect(){}};
const scope={MyAvatar:{sessionUUID:'actual-synthetic-session',getJointNames:()=>joints,
 getFullAvatarURLFromPreferences:()=> 'http://owned.test/original.fst',
 useFullAvatarURL:url=>applied.push(url)},
 Entities:{addingWearable:signal,addEntity(properties,avatarEntity){
  entities.push({properties,avatarEntity});return 'original-synthetic-entity-id';}},
 sendToQml:value=>messages.push(value),currentAvatar:{},
 onAddingWearable(){},onSelectedEntity(){},updateAvatarWearables(){},print(){}};
vm.createContext(scope);
vm.runInContext(section('function validAvatarResourceUrl(', 'function updateAvatarWearables(')+
 section('function fromQml(', 'function isGrabbable('),scope);
'''


class AvatarSourceSemantics(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,str(ROOT/'scripts/system/avatarapp.js')],
            capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_wearable_creates_model_and_uses_actual_hips_index(self):
        self.run_case(r'''
for(const names of [['Root','Hips','Head'],['Head','Root','Spine','Hips'],['Root','Head']]){
 joints=names;const url='http://owned.test/ticket/gltf-bundle/main.gltf';
 scope.fromQml({method:'addWearable',url});
 const added=entities.at(-1);assert.equal(added.avatarEntity,true);
 assert.equal(added.properties.type,'Model');assert.equal(added.properties.modelURL,url);
 assert.equal(added.properties.parentID,'actual-synthetic-session');
 assert.equal(added.properties.parentJointIndex,names.indexOf('Hips'));
 assert.equal(added.properties.relayParentJoints,false);
}assert.equal(entities.length,3);
''')

    def test_original_applied_notification_does_not_mean_model_loaded(self):
        self.run_case(r'''
const url='http://owned.test/ticket/missing.fst';
scope.fromQml({method:'applyExternalAvatar',avatarURL:url});
assert.deepEqual(applied,[url]);assert.equal(entities.length,0);
assert.equal(messages.length,1);assert.equal(messages[0].method,'externalAvatarApplied');
assert.equal(messages[0].avatarURL,url);
assert(!messages.some(m=>m.method==='avatarError'));
// No native loader callback was supplied or executed by this boundary.
// This successful notification cannot establish loaded geometry or a popup.
''')

    def test_original_url_validation_is_not_an_entity_json_importer(self):
        self.run_case(r'''
scope.fromQml({method:'addWearable',url:'http://owned.test/wearable.json'});
assert.equal(entities.length,1);assert.equal(entities[0].properties.type,'Model');
assert.equal(entities[0].properties.modelURL,'http://owned.test/wearable.json');
for(const url of ['',null,'bad\nurl'])scope.fromQml({method:'addWearable',url});
assert.equal(entities.length,1);assert.equal(messages.length,3);
assert(messages.every(m=>m.method==='avatarError'));
''')


if __name__=='__main__':unittest.main()
