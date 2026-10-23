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
    el.focus();if(el.setSelectionRange && el.type!=='number')el.setSelectionRange(text.length,text.length);
    if(tag==='div') {const range=document.createRange();range.selectNodeContents(el);range.collapse(false);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);}
    return state;
}
function test(name, body) {
    try { body();outcomes.push({name,passed:true}); }
    catch(error) { outcomes.push({name,passed:false,error:String(error.stack||error)}); }
    finally { window.__overteEditor.blur();scratch.replaceChildren(); }
}
const ime=(commit,preedit='')=>({action:'ime',commit,preedit,replaceStart:0,replaceLength:0,cursor:preedit.length});
test('empty IME update preserves the selected text and emits no text input',()=>{
    const s=setup('textarea');s.el.setSelectionRange(1,2);
    window.__overteEditor.edit(ime(''));
    equal(s.el.value,'abc');equal(s.el.selectionStart,1);equal(s.el.selectionEnd,2);
    equal(s.events.length,0);equal(window.lastEditor.text,'abc');
});
test('selection-only IME update changes selection without deleting text or emitting input',()=>{
    const s=setup('textarea');s.el.setSelectionRange(1,2);
    window.__overteEditor.edit({...ime(''),selection:{start:0,length:1}});
    equal(s.el.value,'abc');equal(s.el.selectionStart,0);equal(s.el.selectionEnd,1);
    equal(s.events.length,0);equal(window.lastEditor.text,'abc');equal(window.lastEditor.cursor,1);equal(window.lastEditor.anchor,0);
});
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
test('IME preedit is visible while Qt surrounding text remains committed-only',()=>{
    const s=setup('textarea','ab');s.el.setSelectionRange(1,1);window.__overteEditor.publish();const originalCaret=window.lastEditor.caret;
    window.__overteEditor.edit({...ime('','XY'),cursor:1});equal(s.el.value,'aXYb');
    equal(window.lastEditor.text,'ab');equal(window.lastEditor.length,2);equal(window.lastEditor.cursor,1);equal(window.lastEditor.anchor,1);equal(window.lastEditor.absoluteCursor,1);
    check(window.lastEditor.caret.x>originalCaret.x,'visual caret still includes the real preedit cursor');
});
test('Qt surrounding metadata retains commit but excludes the next preedit',()=>{
    const s=setup('textarea','ab');s.el.setSelectionRange(1,1);window.__overteEditor.edit(ime('Z','XY'));
    equal(s.el.value,'aZXYb');equal(window.lastEditor.text,'aZb');equal(window.lastEditor.cursor,2);
    window.__overteEditor.edit(ime(''));equal(s.el.value,'aZb');equal(window.lastEditor.text,'aZb');equal(window.lastEditor.cursor,2);
});
test('password composition publishes only committed mask length',()=>{
    const s=setup('input','ab',{type:'password'});s.el.setSelectionRange(1,1);window.__overteEditor.edit(ime('','XY'));
    equal(s.el.value,'aXYb');equal(window.lastEditor.text,'');equal(window.lastEditor.length,2);equal(window.lastEditor.cursor,1);
    check(!JSON.stringify(window.lastEditor).includes('XY'),'password preedit contents must remain private');
});
test('rich text native publication waits for the complete composition edit',()=>{
    const s=setup('div','ab'),range=document.createRange();range.setStart(s.el.firstChild,1);range.collapse(true);window.getSelection().removeAllRanges();window.getSelection().addRange(range);
    const original=window.__overteEditorTransport.editor,states=[];window.__overteEditorTransport.editor=state=>{states.push(state);original(state);};
    try {window.__overteEditor.edit(ime('','XY'));equal(s.el.textContent,'aXYb');check(states.length>0,'final native state missing');
        for(const state of states) {equal(state.text,'ab');equal(state.cursor,1);equal(state.anchor,1);}
    } finally {window.__overteEditorTransport.editor=original;}
});
test('application input replacement cannot be stripped as the old native preedit',()=>{
    const s=setup('input','ab');s.el.setSelectionRange(1,1);s.el.oninput=()=>{s.el.value='application';};
    window.__overteEditor.edit(ime('','XY'));equal(s.el.value,'application');equal(window.lastEditor.text,'application');equal(window.lastEditor.cursor,11);
    s.el.oninput=null;window.__overteEditor.edit(ime('!'));equal(s.el.value,'application!');equal(window.lastEditor.text,'application!');
});
test('Unicode composition keeps native UTF16 offsets outside the preedit',()=>{
    const s=setup('textarea','a😀b');s.el.setSelectionRange(3,3);window.__overteEditor.edit({...ime('','漢👩‍💻'),cursor:1});
    equal(s.el.value,'a😀漢👩‍💻b');equal(window.lastEditor.text,'a😀b');equal(window.lastEditor.cursor,3);equal(window.lastEditor.absoluteCursor,3);
});
test('long surrounding window excludes preedit before slicing around the committed cursor',()=>{
    const text='a'.repeat(20000),s=setup('textarea',text);s.el.setSelectionRange(19999,19999);window.__overteEditor.edit(ime('','XYZ'));
    equal(s.el.value,text.slice(0,19999)+'XYZa');equal(window.lastEditor.absoluteCursor,19999);equal(window.lastEditor.cursor,8192);
    equal(window.lastEditor.text,text.slice(19999-8192));check(!window.lastEditor.text.includes('XYZ'),'preedit entered Qt surrounding window');
});
test('Enter during IME preedit waits for commit before form submission',()=>{
    const s=setup();window.__overteEditor.edit(ime('','XY'));equal(s.el.value,'abcXY');window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,0);equal(s.el.value,'abcXY');window.__overteEditor.edit(ime('Z'));equal(s.el.value,'abcZ');window.__overteEditor.edit({action:'enter',shift:false});equal(s.submits,1);
});
test('backspace retains code points and deletion input type',()=>{
    const s=setup('input','a😀');window.__overteEditor.edit({action:'backspace'});equal(s.el.value,'a');equal(s.events.find(e=>e.type==='beforeinput').inputType,'deleteContentBackward');
});
test('rich text keeps existing nodes and emits one input event',()=>{
    const s=setup('div','');s.el.innerHTML='<b>abc</b>';const node=s.el.firstChild,range=document.createRange();range.selectNodeContents(s.el);range.collapse(false);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
    window.__overteEditor.edit({text:'z'});equal(s.el.textContent,'abcz');equal(s.el.firstChild,node);equal(s.events.filter(e=>e.type==='input').length,1);equal(window.lastEditor.kind,'contenteditable');
});
test('password publication and bounded surrounding text remain private',()=>{
    const s=setup('input','secret',{type:'password'});window.__overteEditor.publish();equal(window.lastEditor.text,'');check(window.lastEditor.sensitive,'sensitive metadata');s.el.type='text';s.el.value='x'.repeat(20000);s.el.setSelectionRange(20000,20000);window.__overteEditor.publish();check(window.lastEditor.text.length<=16384,'bounded text');
});
test('numeric key edits retain the intermediate decimal and native caret',()=>{
    const s=setup('input','',{type:'number'});
    for(const text of ['1','2','.'])window.__overteEditor.edit({text});
    equal(s.el.value,'12');window.__overteEditor.edit({text:'5'});equal(s.el.value,'12.5');
    equal(s.events.filter(e=>e.type==='input').length,4);
});
test('numeric negative decimal and deletion retain browser editing state',()=>{
    const s=setup('input','',{type:'number'});
    for(const text of ['-','1','.','5'])window.__overteEditor.edit({text});
    equal(s.el.value,'-1.5');window.__overteEditor.edit({action:'backspace'});equal(s.el.value,'-1');
    window.__overteEditor.edit({text:'5'});equal(s.el.value,'-1.5');
});
test('numeric IME commits retain the decimal without unsupported selection APIs',()=>{
    const s=setup('input','',{type:'number'});
    for(const text of ['1','2','.','5'])window.__overteEditor.edit(ime(text));
    equal(s.el.value,'12.5');equal(window.lastEditor.text,'12.5');
});
test('numeric decimal draft preserves native cursor metadata',()=>{
    const s=setup('input','',{type:'number'});
    for(const text of ['1','2','.'])window.__overteEditor.edit({text});
    equal(window.lastEditor.text,'12.');equal(window.lastEditor.cursor,3);
    window.__overteEditor.edit(ime('5'));equal(s.el.value,'12.5');
});
test('numeric incomplete exponent preserves native cursor metadata',()=>{
    const s=setup('input','',{type:'number'});
    for(const text of ['1','e'])window.__overteEditor.edit({text});
    equal(s.el.value,'');equal(window.lastEditor.text,'1e');equal(window.lastEditor.cursor,2);
    window.__overteEditor.edit(ime('2'));equal(Number(s.el.value),100);
});
test('native edit tickets acknowledge completed edits and reject duplicate or older commands',()=>{
    const s=setup('input','');window.__overteEditor.publish();const owner=window.lastEditor.editor;check(owner && window.lastEditor.sequence===0,'fresh editor owner missing');
    window.__overteEditor.edit({editor:owner,sequence:10,text:'a'});equal(s.el.value,'a');equal(window.lastEditor.sequence,10);
    for(const sequence of [10,9,NaN,Infinity,1.5])window.__overteEditor.edit({editor:owner,sequence,text:'bad'});
    equal(s.el.value,'a');equal(window.lastEditor.sequence,10);
    window.__overteEditor.edit({editor:owner,sequence:11,text:'b'});equal(s.el.value,'ab');equal(window.lastEditor.sequence,11);
});
test('native queued input never crosses DOM focus ownership or a blur-refocus cycle',()=>{
    const s=setup('input','first');window.__overteEditor.publish();const old=window.lastEditor.editor;
    const other=document.createElement('input');other.value='second';s.form.append(other);other.focus();window.__overteEditor.publish();const current=window.lastEditor.editor;check(current!==old,'owner did not change');
    window.__overteEditor.edit({editor:old,sequence:1,text:'bad'});equal(other.value,'second');
    window.__overteEditor.edit({editor:current,sequence:2,text:'!'});equal(other.value,'second!');
    other.blur();other.focus();window.__overteEditor.publish();check(window.lastEditor.editor!==current,'refocus reused revoked owner');
    window.__overteEditor.edit({editor:current,sequence:3,text:'bad'});equal(other.value,'second!');equal(s.el.value,'first');
});
test('canceled and application-formatted edits acknowledge actual page state',()=>{
    const s=setup('input','ab');s.el.setSelectionRange(1,1);window.__overteEditor.publish();const owner=window.lastEditor.editor;
    const cancel=e=>e.preventDefault();s.el.addEventListener('beforeinput',cancel);
    window.__overteEditor.edit({editor:owner,sequence:4,text:'bad'});equal(s.el.value,'ab');equal(window.lastEditor.sequence,4);equal(window.lastEditor.text,'ab');
    s.el.removeEventListener('beforeinput',cancel);s.el.oninput=()=>s.el.value='PAGE';
    window.__overteEditor.edit({editor:owner,sequence:5,text:'x'});equal(s.el.value,'PAGE');equal(window.lastEditor.sequence,5);equal(window.lastEditor.text,'PAGE');
});
test('a canceled native edit leaves the next queued edit applicable to actual page state',()=>{
    const s=setup('input','');window.__overteEditor.publish();const owner=window.lastEditor.editor;s.el.onbeforeinput=e=>{if(e.data==='a')e.preventDefault();};
    window.__overteEditor.edit({editor:owner,sequence:1,text:'a'});equal(s.el.value,'');equal(window.lastEditor.sequence,1);
    window.__overteEditor.edit({editor:owner,sequence:2,text:'b'});equal(s.el.value,'b');equal(window.lastEditor.sequence,2);equal(window.lastEditor.cursor,1);
});
test('bounded surrounding text never splits UTF16 at either edge of its window',()=>{
    const text='a'.repeat(11807)+'😀'+'b'.repeat(8191),s=setup('textarea',text);window.__overteEditor.publish();
    equal(window.lastEditor.absoluteCursor,text.length);equal(window.lastEditor.cursor,8193);check(window.lastEditor.text.startsWith('😀'),'window begins with a broken surrogate');
    s.el.value='a'.repeat(16383)+'😀rest';s.el.setSelectionRange(0,0);window.__overteEditor.publish();
    equal(window.lastEditor.text,'a'.repeat(16383));equal(window.lastEditor.length,16383);
});
test('same focused editor pointer release republishes metadata only for that editor',()=>{
    const s=setup('input','abc');window.__overteEditor.publish();equal(window.lastEditor.requestKeyboard===true,false);window.lastEditor=null;
    s.el.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));
    check(window.lastEditor,'Repeated editor touch must republish');equal(window.lastEditor.text,'abc');equal(window.lastEditor.cursor,3);
    equal(window.lastEditor.requestKeyboard,true);
    window.__overteEditor.edit({text:'z'});equal(s.el.value,'abcz');equal(window.lastEditor.requestKeyboard===true,false);
    window.lastEditor=null;s.form.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));equal(window.lastEditor,null);
});
test('native caret geometry identifies a thin actual insertion point',()=>{
    const s=setup('input','abcdef');s.el.style.cssText='font:20px monospace;width:240px;padding:8px;border:2px solid';
    s.el.setSelectionRange(1,1);window.__overteEditor.publish();const first=window.lastEditor.caret;
    check(first && first.width>0 && first.width<=2 && first.height>10,'actual caret geometry missing');
    const bounds=s.el.getBoundingClientRect();check(first.x>=bounds.left && first.x<bounds.right,'caret outside editor');
    s.el.setSelectionRange(5,5);window.__overteEditor.publish();
    check(window.lastEditor.caret.x>first.x+30,'caret must follow actual selection');equal(s.el.value,'abcdef');
});
test('native point moves input selection without text input or click side effects',()=>{
    const s=setup('input','abcdef');s.el.style.cssText='font:20px monospace;width:240px;padding:8px;border:2px solid';
    let clicks=0;s.el.onclick=()=>++clicks;
    const bounds=s.el.getBoundingClientRect(),style=getComputedStyle(s.el),context=document.createElement('canvas').getContext('2d');
    context.font=style.fontSize+' '+style.fontFamily;
    const point={x:bounds.left+parseFloat(style.borderLeftWidth)+parseFloat(style.paddingLeft)+context.measureText('a').width,y:bounds.top+bounds.height/2};
    s.el.setSelectionRange(6,6);window.__overteEditor.publish();
    window.__overteEditor.edit({action:'point',x:point.x,y:point.y});
    equal(s.el.selectionStart,1);equal(s.el.selectionEnd,1);equal(s.el.value,'abcdef');equal(clicks,0);equal(s.events.length,0);
});
test('native point preserves multiline wrapping and real second-line position',()=>{
    const s=setup('textarea','first line\nsecond line');s.el.style.cssText='font:20px/24px monospace;width:240px;height:100px;padding:8px;border:2px solid';
    const bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    const point={x:bounds.left+10+context.measureText('se').width,y:bounds.top+10+36};
    s.el.setSelectionRange(0,0);window.__overteEditor.publish();
    window.__overteEditor.edit({action:'point',x:point.x,y:point.y});
    equal(s.el.selectionStart,13);equal(s.el.value,'first line\nsecond line');equal(s.events.length,0);
});
test('password point geometry never publishes password contents',()=>{
    const s=setup('input','dummy-secret',{type:'password'});s.el.style.cssText='font:20px monospace;width:240px;padding:8px';
    s.el.setSelectionRange(2,2);window.__overteEditor.publish();const point=window.lastEditor.caret;check(point,'caret missing');
    check(!JSON.stringify(window.lastEditor).includes('dummy-secret'),'password crossed editor boundary');
    s.el.setSelectionRange(12,12);window.__overteEditor.publish();
    window.__overteEditor.edit({action:'point',x:point.x,y:point.y+point.height/2});
    equal(s.el.selectionStart,2);equal(s.el.value,'dummy-secret');check(!JSON.stringify(window.lastEditor).includes('dummy-secret'),'password leaked after point');
});
test('native point rejects positions outside current editor and nonfinite coordinates',()=>{
    const s=setup('input','abcdef');const bounds=s.el.getBoundingClientRect();
    for(const point of [{x:bounds.right+20,y:bounds.top},{x:NaN,y:bounds.top},{x:bounds.left,y:Infinity}]) {
        window.__overteEditor.edit({action:'point',x:point.x,y:point.y});equal(s.el.value,'abcdef');equal(s.el.selectionStart,6);
    }
    equal(s.events.length,0);
});
test('native point in rich text preserves original nodes and selection owner',()=>{
    const s=setup('div','');s.el.innerHTML='<b>first</b><i>second</i>';s.el.style.cssText='font:20px monospace;width:240px;padding:8px';
    const bold=s.el.firstChild,italic=s.el.lastChild,range=document.createRange();range.setStart(italic.firstChild,2);range.collapse(true);
    const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);window.__overteEditor.publish();
    const point=window.lastEditor.caret;check(point,'caret missing');
    range.setStart(bold.firstChild,0);range.collapse(true);selection.removeAllRanges();selection.addRange(range);
    window.__overteEditor.edit({action:'point',x:point.x,y:point.y+point.height/2});
    equal(window.lastEditor.cursor,7);equal(s.el.firstChild,bold);equal(s.el.lastChild,italic);equal(s.el.textContent,'firstsecond');equal(s.events.length,0);
});
test('native point uses browser shaping for right-to-left text',()=>{
    const s=setup('input','אבגדה');s.el.dir='rtl';s.el.style.cssText='font:20px monospace;width:240px;padding:8px;border:2px solid';
    const bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    window.__overteEditor.edit({action:'point',x:bounds.right-10-context.measureText('אב').width,y:bounds.top+bounds.height/2});
    equal(s.el.selectionStart,2);equal(s.el.selectionEnd,2);equal(s.el.value,'אבגדה');equal(s.events.length,0);
});
test('native point honors a scrolled textarea viewport without changing its scroll',()=>{
    const text=Array.from({length:20},(_,i)=>'line'+i).join('\n'),s=setup('textarea',text);
    s.el.style.cssText='font:20px/24px monospace;width:240px;height:80px;padding:8px;border:2px solid';
    s.el.scrollTop=120;const scroll=s.el.scrollTop,bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    window.__overteEditor.edit({action:'point',x:bounds.left+10+context.measureText('li').width,y:bounds.top+10+12});
    equal(s.el.selectionStart,text.indexOf('line5')+2);equal(s.el.value,text);equal(s.el.scrollTop,scroll);equal(s.events.length,0);
});
function scrollEditor(tag='textarea', attributes={}) {
    const s=setup(tag,'',attributes);
    s.el.style.cssText='font:20px/24px monospace;width:240px;height:80px;padding:8px;border:2px solid';
    return s;
}
function caretVisible(s) {
    window.__overteEditor.publish();const caret=window.lastEditor.caret,bounds=s.el.getBoundingClientRect();
    check(caret,'caret geometry missing');
    const left=bounds.left+s.el.clientLeft,top=bounds.top+s.el.clientTop;
    check(caret.x>=left-1 && caret.x+caret.width<=left+s.el.clientWidth+1,'caret outside inner horizontal viewport');
    check(caret.y>=top-1 && caret.y+caret.height<=top+s.el.clientHeight+1,'caret outside inner vertical viewport');
}
test('IME multiline edits reveal the actual final line and selection back to first line',()=>{
    const s=scrollEditor(),text=Array.from({length:20},(_,i)=>'line'+i).join('\n');
    window.__overteEditor.edit(ime(text));equal(s.el.value,text);equal(s.el.selectionStart,text.length);
    check(s.el.scrollTop>300,'actual textarea must scroll after native edit');caretVisible(s);
    window.__overteEditor.edit({action:'selection',start:0,length:0});
    equal(s.el.selectionStart,0);check(s.el.scrollTop<24,'first line must be visible after moving cursor');caretVisible(s);
    equal(s.events.filter(e=>e.type==='input').length,1);
});
test('individual newline edits reveal the empty last line without changing prior text',()=>{
    const s=scrollEditor();let text='';
    for(let i=0;i<12;++i) {window.__overteEditor.edit({text:'x'});window.__overteEditor.edit({action:'enter',shift:false});text+='x\n';}
    equal(s.el.value,text);equal(s.el.selectionStart,text.length);check(s.el.scrollTop>150,'newline must scroll actual textarea');caretVisible(s);
    equal(s.events.filter(e=>e.type==='input').length,24);equal(s.submits,0);
});
test('preedit and replacement reveal wrapping text and keep composition selection intact',()=>{
    const s=scrollEditor(),text='word '.repeat(120);
    window.__overteEditor.edit(ime('',text));equal(s.el.value,text);check(s.el.scrollTop>100,'preedit wrapping must scroll');caretVisible(s);
    window.__overteEditor.edit(ime('committed'));equal(s.el.value,'committed');equal(s.el.selectionStart,9);caretVisible(s);
    equal(s.events.filter(e=>e.type==='compositionstart').length,1);equal(s.events.filter(e=>e.type==='compositionend').length,1);
});
test('horizontal input edits and Home reveal the active cursor',()=>{
    const s=scrollEditor('input'),text='0123456789'.repeat(20);
    window.__overteEditor.edit(ime(text));equal(s.el.value,text);check(s.el.scrollLeft>100,'actual input must scroll');caretVisible(s);
    window.__overteEditor.edit({action:'home'});equal(s.el.selectionStart,0);check(s.el.scrollLeft<24,'Home must show first character');caretVisible(s);
});
test('right-to-left input scrolling follows the actual active endpoint',()=>{
    const s=scrollEditor('input',{dir:'rtl'}),text='אבגדה '.repeat(80);
    window.__overteEditor.edit(ime(text));equal(s.el.value,text);check(s.el.scrollLeft<0,'RTL input must scroll toward its text end');caretVisible(s);
    window.__overteEditor.edit({action:'home'});equal(s.el.selectionStart,0);caretVisible(s);
});
test('unwrapped multiline textarea scrolls both axes to its actual end',()=>{
    const s=scrollEditor('textarea',{wrap:'off'}),text=Array.from({length:12},()=> 'long text '.repeat(40)).join('\n');
    window.__overteEditor.edit(ime(text));equal(s.el.value,text);equal(s.el.selectionStart,text.length);
    check(s.el.scrollTop>100,'last unwrapped line must scroll vertically');check(s.el.scrollLeft>100,'unwrapped text must scroll horizontally');caretVisible(s);
});
test('backward selection reveals its active endpoint and preserves direction',()=>{
    const s=scrollEditor(),text=Array.from({length:20},(_,i)=>'line'+i).join('\n');window.__overteEditor.edit(ime(text));
    window.__overteEditor.edit({action:'selection',start:text.length,length:-text.length});
    equal(s.el.selectionStart,0);equal(s.el.selectionEnd,text.length);equal(s.el.selectionDirection,'backward');caretVisible(s);
    equal(s.el.value,text);equal(s.events.filter(e=>e.type==='input').length,1);
});
test('publication and canceled edits preserve manual scroll and never move focus',()=>{
    const s=scrollEditor(),text=Array.from({length:20},(_,i)=>'line'+i).join('\n');s.el.value=text;s.el.setSelectionRange(text.length,text.length);s.el.scrollTop=0;
    window.__overteEditor.publish();equal(s.el.scrollTop,0);
    s.el.addEventListener('beforeinput',e=>e.preventDefault());window.__overteEditor.edit(ime('blocked'));equal(s.el.scrollTop,0);equal(s.el.value,text);
    const other=document.createElement('input');s.form.append(other);s.el.addEventListener('keydown',()=>other.focus());
    window.__overteEditor.edit({text:'blocked'});equal(document.activeElement,other);equal(s.el.scrollTop,0);equal(other.value,'');
});
test('native point respects the browser emoji boundary',()=>{
    const s=setup('input','A😀B');s.el.style.cssText='font:20px monospace;width:240px;padding:8px;border:2px solid';
    const bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    window.__overteEditor.edit({action:'point',x:bounds.left+10+context.measureText('A😀').width,y:bounds.top+bounds.height/2});
    equal(s.el.selectionStart,3);equal(s.el.selectionEnd,3);equal(s.el.value,'A😀B');equal(s.events.length,0);
});
test('native left and right selection handles preserve their opposite endpoint',()=>{
    const s=setup('input','abcdef');s.el.style.cssText='font:20px monospace;width:240px;padding:8px;border:2px solid';
    const bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    const x=index=>bounds.left+10+context.measureText(s.el.value.slice(0,index)).width,y=bounds.top+bounds.height/2;
    s.el.setSelectionRange(1,5);window.__overteEditor.edit({action:'point',handle:2,x:x(2),y});
    equal(s.el.selectionStart,2);equal(s.el.selectionEnd,5);
    window.__overteEditor.edit({action:'point',handle:3,x:x(4),y});
    equal(s.el.selectionStart,2);equal(s.el.selectionEnd,4);equal(s.el.value,'abcdef');equal(s.events.length,0);
});
test('native selection handles retain a complete grapheme when crossing',()=>{
    const s=setup('input','A👩‍💻B');s.el.style.cssText='font:20px monospace;width:300px;padding:8px;border:2px solid';
    const bounds=s.el.getBoundingClientRect(),context=document.createElement('canvas').getContext('2d');context.font='20px monospace';
    const x=index=>bounds.left+10+context.measureText(s.el.value.slice(0,index)).width,y=bounds.top+bounds.height/2;
    s.el.setSelectionRange(1,6);window.__overteEditor.edit({action:'point',handle:2,x:x(7),y});
    equal(s.el.selectionStart,1);equal(s.el.selectionEnd,6);
    window.__overteEditor.edit({action:'point',handle:3,x:x(0),y});
    equal(s.el.selectionStart,1);equal(s.el.selectionEnd,6);equal(s.el.value,'A👩‍💻B');equal(s.events.length,0);
});
test('native selection point rejects unknown handles and stale collapsed selection grips',()=>{
    const s=setup('input','abcdef');const bounds=s.el.getBoundingClientRect();
    for(const handle of [0,4,2,3])window.__overteEditor.edit({action:'point',handle,x:bounds.left+2,y:bounds.top+bounds.height/2});
    equal(s.el.selectionStart,6);equal(s.el.selectionEnd,6);equal(s.el.value,'abcdef');equal(s.events.length,0);
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
    if not results.get('completed') or len(results['cases']) != 68 or failures:
        raise AssertionError(json.dumps({'cases': len(results['cases']), 'failures': failures}, indent=2))
    print('PASS: 68 real Chromium editor DOM cases; no Android WebView/device claim')


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
