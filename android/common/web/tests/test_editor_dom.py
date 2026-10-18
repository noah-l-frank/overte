#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Execute the actual private editor in a real Chromium DOM; missing tools fail."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

WEB = Path(__file__).resolve().parents[1]
CASES = r'''
const outcomes = [], scratch = document.createElement('section'); document.body.append(scratch);
function check(value, message) { if (!value) throw Error(message); }
function equal(actual, expected) { check(actual === expected, JSON.stringify({actual, expected})); }
function setup(tag='input', text='abc', attributes={}) {
    const form=document.createElement('form'), el=document.createElement(tag), events=[];
    if(tag==='div') { el.contentEditable='true'; el.textContent=text; } else el.value=text;
    Object.assign(el,attributes);form.append(el);scratch.append(form);
    const state={form,el,events,submits:0,submitter:null};
    form.addEventListener('submit',e=>{e.preventDefault();++state.submits;state.submitter=e.submitter;});
    for(const type of ['keydown','beforeinput','input','compositionstart','compositionupdate','compositionend']) {
        el.addEventListener(type,e=>events.push({type:e.type,key:e.key,shift:e.shiftKey,inputType:e.inputType,cancelable:e.cancelable}));
    }
    el.focus();if(el.setSelectionRange)el.setSelectionRange(text.length,text.length);
    if(tag==='div') {const range=document.createRange();range.selectNodeContents(el);range.collapse(false);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}
    return state;
}
function test(name, body) {
    try { body();outcomes.push({name,passed:true}); }
    catch(error) { outcomes.push({name,passed:false,error:String(error.stack||error)}); }
    finally { window.__overteEditor.blur();scratch.replaceChildren(); }
}
const ime=(commit,preedit='')=>({action:'ime',commit,preedit,replaceStart:0,replaceLength:0,cursor:preedit.length});
test('single-line Enter submits with default button and no input mutation',()=>{
    const s=setup(),button=document.createElement('button');button.type='submit';s.form.append(button);
    window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,1);equal(s.submitter,button);equal(s.el.value,'abc');
    equal(s.events.filter(e=>e.type==='keydown').length,1);equal(s.events.filter(e=>e.type==='input').length,0);
});
test('Enter activates and respects default submit button click cancellation',()=>{
    const s=setup(),button=document.createElement('button');button.type='submit';s.form.append(button);let clicks=0;button.onclick=e=>{++clicks;e.preventDefault();};
    window.__overteEditor.edit({action:'enter',shift:false});equal(clicks,1);equal(s.submits,0);equal(s.el.value,'abc');
});
test('default submit button click and submit retain submitter overrides',()=>{
    const s=setup(),button=document.createElement('button');button.type='submit';button.formAction='https://example.invalid/override';button.formMethod='post';s.form.append(button);let clicks=0;button.onclick=()=>++clicks;
    window.__overteEditor.edit({action:'enter',shift:false});equal(clicks,1);equal(s.submits,1);equal(s.submitter,button);equal(s.submitter.formAction,'https://example.invalid/override');equal(s.submitter.formMethod,'post');
});
test('default submitter formnovalidate remains effective',()=>{
    const s=setup('input',''),button=document.createElement('button');s.el.required=true;button.type='submit';button.formNoValidate=true;s.form.append(button);
    window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,1);equal(s.submitter,button);
});
test('Enter keydown cancellation prevents submission',()=>{
    const s=setup();s.el.addEventListener('keydown',e=>e.preventDefault());window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);
});
test('Shift Enter reports modifier without implicit single-line submit',()=>{
    const s=setup();window.__overteEditor.edit({action:'enter',shift:true});equal(s.submits,0);check(s.events[0].shift,'shift metadata');
});
test('textarea Enter replaces selection with one newline without submit',()=>{
    const s=setup('textarea');s.el.setSelectionRange(1,2);window.__overteEditor.edit({action:'enter',shift:false});equal(s.el.value,'a\nc');equal(s.submits,0);
    equal(s.events.filter(e=>e.type==='beforeinput')[0].inputType,'insertLineBreak');equal(s.events.filter(e=>e.type==='input').length,1);
});
test('textarea Shift Enter retains newline',()=>{
    const s=setup('textarea');window.__overteEditor.edit({action:'enter',shift:true});equal(s.el.value,'abc\n');equal(s.submits,0);
});
test('textarea newline honors beforeinput cancellation',()=>{
    const s=setup('textarea');s.el.addEventListener('beforeinput',e=>e.preventDefault());window.__overteEditor.edit({action:'enter',shift:false});equal(s.el.value,'abc');equal(s.events.filter(e=>e.type==='input').length,0);
});
test('implicit form validation remains effective',()=>{
    const s=setup('input','');s.el.required=true;window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);
});
test('disabled default submitter prevents implicit submission',()=>{
    const s=setup(),button=document.createElement('button');button.type='submit';button.disabled=true;s.form.append(button);
    window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);
});
test('multiple blocking fields without submitter do not implicitly submit',()=>{
    const s=setup(),other=document.createElement('input');s.form.append(other);window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);
});
test('readonly controls reject text Enter and IME and publish inactive',()=>{
    const s=setup('input','locked',{readOnly:true});window.__overteEditor.publish();equal(window.lastEditor.active,false);
    for(const command of [{text:'bad'},{action:'backspace'},{action:'enter',shift:false},ime('bad')])window.__overteEditor.edit(command);
    equal(s.el.value,'locked');equal(s.submits,0);equal(s.events.length,0);
});
test('readonly textarea rejects newline',()=>{
    const s=setup('textarea','locked',{readOnly:true});window.__overteEditor.edit({action:'enter',shift:false});equal(s.el.value,'locked');
});
test('disabled fieldset blocks editing even when own disabled flag is false',()=>{
    const s=setup(),fieldset=document.createElement('fieldset');s.form.append(fieldset);fieldset.append(s.el);fieldset.disabled=true;
    window.__overteEditor.publish();equal(window.lastEditor.active,false);window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');
});
test('ordinary text honors keydown cancellation',()=>{
    const s=setup();s.el.addEventListener('keydown',e=>e.preventDefault());window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');equal(s.events.length,1);
});
test('ordinary text honors beforeinput cancellation',()=>{
    const s=setup();s.el.addEventListener('beforeinput',e=>e.preventDefault());window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');equal(s.events.filter(e=>e.type==='input').length,0);
});
test('readonly change during beforeinput cannot be overwritten',()=>{
    const s=setup();s.el.addEventListener('beforeinput',()=>s.el.readOnly=true);window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');equal(window.lastEditor.active,false);
});
test('focus replacement during keydown cannot edit either target',()=>{
    const s=setup(),other=document.createElement('input');other.value='other';s.form.append(other);s.el.addEventListener('keydown',()=>other.focus());window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');equal(other.value,'other');
});
test('application value replacement during beforeinput is retained',()=>{
    const s=setup();s.el.addEventListener('beforeinput',()=>s.el.value='application');window.__overteEditor.edit({text:'bad'});equal(s.el.value,'application');
});
test('application selection replacement during beforeinput is retained',()=>{
    const s=setup();s.el.addEventListener('beforeinput',()=>s.el.setSelectionRange(0,0));window.__overteEditor.edit({text:'bad'});equal(s.el.value,'abc');equal(s.el.selectionStart,0);
});
test('IME cancellation retains current value and emits no input',()=>{
    const s=setup();s.el.addEventListener('beforeinput',e=>e.preventDefault());window.__overteEditor.edit(ime('bad'));equal(s.el.value,'abc');equal(s.events.filter(e=>e.type==='input').length,0);
});
test('readonly change during compositionstart blocks IME mutation',()=>{
    const s=setup();s.el.addEventListener('compositionstart',()=>s.el.readOnly=true);window.__overteEditor.edit(ime('','bad'));equal(s.el.value,'abc');equal(window.lastEditor.active,false);
});
test('IME preedit commit and cancellation retain Unicode boundaries',()=>{
    const s=setup('textarea','a😀b');s.el.setSelectionRange(3,3);window.__overteEditor.edit(ime('','XY'));equal(s.el.value,'a😀XYb');window.__overteEditor.edit(ime('Z'));equal(s.el.value,'a😀Zb');
    window.__overteEditor.edit(ime('','W'));window.__overteEditor.edit(ime(''));equal(s.el.value,'a😀Zb');
});
test('Enter during IME preedit waits for commit before form submission',()=>{
    const s=setup();window.__overteEditor.edit(ime('','XY'));equal(s.el.value,'abcXY');window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);equal(s.el.value,'abcXY');window.__overteEditor.edit(ime('Z'));equal(s.el.value,'abcZ');window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,1);
});
test('backspace retains code points and deletion input type',()=>{
    const s=setup('input','a😀');window.__overteEditor.edit({action:'backspace'});equal(s.el.value,'a');equal(s.events.find(e=>e.type==='beforeinput').inputType,'deleteContentBackward');
});
test('rich text keeps existing nodes and emits one input event',()=>{
    const s=setup('div','');s.el.innerHTML='<b>abc</b>';const node=s.el.firstChild,range=document.createRange();range.selectNodeContents(s.el);range.collapse(false);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
    window.__overteEditor.edit({text:'z'});equal(s.el.textContent,'abcz');equal(s.el.firstChild,node);equal(s.events.filter(e=>e.type==='input').length,1);
});
test('password publication and bounded surrounding text remain private',()=>{
    const s=setup('input','secret',{type:'password'});window.__overteEditor.publish();equal(window.lastEditor.text,'');check(window.lastEditor.sensitive,'sensitive metadata');s.el.type='text';s.el.value='x'.repeat(20000);s.el.setSelectionRange(20000,20000);window.__overteEditor.publish();check(window.lastEditor.text.length<=16384,'bounded text');
});
document.getElementById('results').textContent=JSON.stringify({cases:outcomes,completed:true});
'''


def find_browser(explicit):
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError('The requested Chromium executable is missing: ' + str(path))
        return path
    for name in ('chromium', 'chromium-browser', 'google-chrome', 'chrome-headless-shell'):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    cached = sorted((Path.home() / '.cache/ms-playwright').glob(
        'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'))
    if cached:
        return cached[-1]
    raise RuntimeError('A real Chromium executable is required; use --browser or OVERTE_CHROMIUM_BINARY')


def run(browser, output):
    output.mkdir(parents=True, exist_ok=False)
    editor = WEB / 'resources/editor.js'
    page = output / 'editor.html'
    source = editor.read_text()
    page.write_text('<!doctype html><meta charset="utf-8"><pre id="results"></pre><script>'
                    'window.__overteEditorTransport={editor:function(state){window.lastEditor=state;}};'
                    '</script><script>' + source + '</script><script>' + CASES + '</script>')
    argv = [str(browser), '--headless', '--no-sandbox', '--disable-gpu',
            '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
            '--user-data-dir=' + str(output / 'profile'), '--dump-dom', page.as_uri()]
    version = subprocess.check_output([str(browser), '--version'], text=True, stderr=subprocess.STDOUT)
    try:
        completed = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except subprocess.TimeoutExpired as error:
        (output / 'timeout.json').write_text(json.dumps({'argv': argv, 'error': str(error)}) + '\n')
        raise RuntimeError('Chromium DOM test timed out; no PASS or skip is recorded') from error
    (output / 'dom.html').write_text(completed.stdout)
    (output / 'browser.log').write_text(completed.stderr)
    match = re.search(r'<pre id="results">(.*?)</pre>', completed.stdout, re.S)
    if completed.returncode or not match:
        raise RuntimeError('Chromium did not produce completed editor DOM results')
    results = json.loads(html.unescape(match.group(1)))
    (output / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    (output / 'inputs.json').write_text(json.dumps({
        'argv': argv, 'browser': str(browser), 'version': version.strip(),
        'browserSha256': hashlib.sha256(browser.read_bytes()).hexdigest(),
        'editor': str(editor), 'editorSha256': hashlib.sha256(editor.read_bytes()).hexdigest(),
        'testSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'boundary': 'Actual production editor.js and real Chromium DOM; Android WebView/JNI/app/device are separate.'
    }, indent=2) + '\n')
    failures = [case for case in results['cases'] if not case['passed']]
    if not results.get('completed') or len(results['cases']) != 28 or failures:
        raise AssertionError(json.dumps({'cases': len(results['cases']), 'failures': failures}, indent=2))
    print('PASS: 28 real Chromium editor DOM cases; no Android WebView/device claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', default=os.environ.get('OVERTE_CHROMIUM_BINARY'))
    parser.add_argument('--output', type=Path, help='Fresh output directory for exact browser/source/results')
    args = parser.parse_args()
    browser = find_browser(args.browser)
    if args.output:
        run(browser, args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='overte-editor-dom-') as temporary:
            run(browser, Path(temporary) / 'results')


if __name__ == '__main__':
    main()
