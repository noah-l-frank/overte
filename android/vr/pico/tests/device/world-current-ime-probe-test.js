// Actual proposed probe branch under a cold declared Test API, not Native/Qt.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(path.join(__dirname,'../../../../../tests/device/probe/overte_e2e_probe.js'),'utf8');
const start=source.indexOf('        if (command && command.action === "pico-world-web" && command.operation === "commit-current-text") {');
const end=source.indexOf('        if (command && command.action === "pico-world-web"\n                && (command.operation === "measure-current-ray"',start);
assert(start>=0&&end>start);const branch=source.slice(start,end);
function command(){return {schemaVersion:1,commandId:'1'.repeat(32),action:'pico-world-web',runId:'2'.repeat(32),
    fixtureUrl:'https://primary.invalid/feature-fixture/v1/runs/'+'2'.repeat(32)+'/',operation:'commit-current-text',
    ownerToken:'3'.repeat(32),documentNonce:'4'.repeat(32),focusNonce:'5'.repeat(32),control:'text',text:'Grüße 東京 🧪'};}
function run(c,mode='normal') {
    let calls=0,saves=[];const original={picoWorldCurrentImeVersion:1,commandId:c.commandId,source:{dispatch:{issued:true,acceptedQt:false}}};
    const Test={saveObject:(value,file)=>saves.push({value,file})};
    if(mode!=='missing')Test.featurePicoWorldCurrentIme=value=>{calls++;assert.strictEqual(value,c);
        if(mode==='lost')throw Error('declared lost API return');
        if(mode==='wrong')return {commandId:'0'.repeat(32)};return original;};
    const context=vm.createContext({Test});const apply=vm.runInContext('(function(command){'+branch+';return false;})',context);
    const handled=apply(c);return {calls,saves,original,handled};
}
let cases=0;
{
    const c=command(),r=run(c);assert.strictEqual(r.calls,1);assert(r.handled);
    assert.strictEqual(r.saves[0].value,r.original);assert.strictEqual(r.saves[0].file,'feature-world-current-ime.json');
    assert.strictEqual(c.text,'Grüße 東京 🧪');assert.strictEqual(r.saves[0].value.source.dispatch.acceptedQt,false);cases++;
}
{
    const fields=['commandId','runId','ownerToken','documentNonce','focusNonce','fixtureUrl','control','text'];
    for(const field of fields)for(const value of ([['converted'],true,{},new String('converted')])) {
        const c=command();c[field]=value;assert.strictEqual(run(c).calls,0);
    }cases++;
}
{
    for(const value of [true,'1',[],NaN,2]){const c=command();c.schemaVersion=value;assert.strictEqual(run(c).calls,0);}
    for(const mutate of [c=>c.extra=true,c=>delete c.focusNonce,c=>c.focusNonce=c.documentNonce,c=>c.commandId='BAD',c=>c.control='bridge']) {
        const c=command();mutate(c);assert.strictEqual(run(c).calls,0);
    }cases++;
}
{
    for(const value of ['\ud800','\udfff','\u0000','\ue000','x'.repeat(513)]){const c=command();c.text=value;assert.strictEqual(run(c).calls,0);}
    const c=command();c.text='\ud83e\uddea';assert.strictEqual(run(c).calls,1);cases++;
}
{
    for(const mode of ['lost','wrong','missing']) {
        const r=run(command(),mode);assert.strictEqual(r.calls,mode==='missing'?0:1);assert.strictEqual(r.saves.length,1);
        assert.strictEqual(Object.keys(r.saves[0].value).length,0);
    }cases++;
}
console.log(JSON.stringify({green:true,cases,actualProbeBranch:true,declaredTestApi:true,nativeQtCalls:0,sourceReady:false}));
