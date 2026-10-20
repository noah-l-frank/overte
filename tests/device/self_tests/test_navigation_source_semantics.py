"""Original Places JavaScript/QML functions; Qt and network boundaries synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
SETUP=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const qml=fs.readFileSync(process.argv[1],'utf8'),script=fs.readFileSync(process.argv[2],'utf8');
function section(source,start,end){let a=source.indexOf(start),b=source.indexOf(end,a+start.length);
assert(a>=0&&b>a,'Original source boundary changed');return source.slice(a,b);}
let rows=[];const ctx={records:[{id:'owned',name:'e2e-owned',address:'http://controlled.invalid/scene.json?location=/2,0,4',maturity:'everyone'}],
 search:{text:''},maturityFilter:['everyone'],qsTr:s=>s,placesModel:{clear:()=>rows=[],append:r=>rows.push(r)}};
vm.createContext(ctx);vm.runInContext(section(qml,'    function rebuildPlaces(', '    function toggleMaturity('),ctx);
'''


class NavigationSourceSemantics(unittest.TestCase):
    def run_case(self,body):
        result=subprocess.run(['node','-e',SETUP+body,str(ROOT/'scripts/system/places/PicoPlaces.qml'),
            str(ROOT/'scripts/system/places/places.js')],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_original_empty_and_owned_queries_and_maturity_filter_have_actual_results(self):
        self.run_case(r'''
ctx.rebuildPlaces();assert.equal(rows.length,1);assert.equal(rows[0].placeId,'owned');
ctx.search.text='hidden-owned';ctx.rebuildPlaces();assert.equal(rows.length,0);
ctx.search.text=' E2E-OWNED ';ctx.rebuildPlaces();assert.equal(rows.length,1);
ctx.maturityFilter=[];ctx.rebuildPlaces();assert.equal(rows.length,0);
''')

    def test_original_rebuild_clears_old_model_and_does_not_modify_input_query(self):
        self.run_case(r'''
ctx.search.text='e2e-owned';ctx.rebuildPlaces();ctx.records=[];ctx.rebuildPlaces();assert.equal(rows.length,0);
assert.equal(ctx.search.text,'e2e-owned');ctx.search={text:''};ctx.records=[{id:'new',address:'owned-new'}];
ctx.rebuildPlaces();assert.equal(rows[0].placeId,'new');assert.equal(ctx.search.text,'');
''')

    def test_original_directory_processor_requires_actual_matching_protocol_and_retains_record_identity(self):
        self.run_case(r'''
const row={id:'owned',name:'e2e-owned',description:'',thumbnail:'',maturity:'everyone',address:'http://controlled.invalid/scene.json?location=/2,0,4',
 visibility:'open',tags:[],managers:[],domain:{id:'domain',name:'controlled',protocol_version:'actual-signature',num_users:0,capacity:8}};
const p={Window:{protocolSignature:()=> 'actual-signature'},placesData:{data:{places:[row]}},portalList:[],placesOfTheCurrentDomain:[],
 nbrPlaceProtocolKnown:0,nbrPlacesNoProtocolMatch:0,location:{domainID:'other'},getSeededRandomForString:()=>.5,
 getListFromArray:a=>a.join(','),zeroPad:n=>String(n),aplphabetize:n=>n};
vm.createContext(p);vm.runInContext(section(script,'    function processData(', '    function getPositionFromPath('),p);
p.processData({order:0,url:'http://controlled.invalid',region:'owned'});assert.equal(p.portalList.length,1);
assert.equal(p.portalList[0].id,'owned');assert.equal(p.portalList[0].address,row.address);
p.portalList=[];row.domain.protocol_version='foreign';p.processData({});assert.equal(p.portalList.length,0);
row.domain={};p.processData({});assert.equal(p.portalList.length,0);
''')


if __name__=='__main__':unittest.main()
