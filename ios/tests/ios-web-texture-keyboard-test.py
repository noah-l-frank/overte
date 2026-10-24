#!/usr/bin/env python3
"""Run actual iOS texture key/IME bodies and their scripts in real Chromium DOM.

Requires Qt6 Core/Gui development files, C++17, and an installed Chromium.
OVERTE_IOS_WEB_TEST_BROWSER selects a browser without downloading anything.
OVERTE_IOS_TEXTURE_KEYBOARD_ARTIFACTS optionally retains bounded proof files.
UIKit/WK, physical input, and full IME composition remain separate boundaries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def body(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def browser_path():
    explicit = os.environ.get("OVERTE_IOS_WEB_TEST_BROWSER")
    candidates = [Path(explicit)] if explicit else []
    if not explicit:
        candidates += [Path(found) for name in ("chromium", "chromium-browser", "google-chrome", "chrome-headless-shell")
                       if (found := shutil.which(name))]
        candidates += sorted((Path.home() / ".cache/ms-playwright").glob(
            "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"), reverse=True)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise SystemExit("Installed Chromium is required; set OVERTE_IOS_WEB_TEST_BROWSER. No browser is downloaded or test skipped.")


source = (ROOT / "ios/web/IOSWebView.mm").read_text()
methods = "\n".join(body(source, signature) for signature in (
    "QString encodedArguments(", "void IOSWebView::keyEvent(", "void IOSWebView::inputMethodEvent("))
driver = r'''
#include <QCoreApplication>
#include <QInputMethodEvent>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <iostream>
namespace overte::ios {
class IOSWebView {
public:
    struct Private { bool inputActive { true }, presentation { false }; } state, *_private { &state };
    bool activeWindow { true };
    QString evaluated;
    bool active() const { return activeWindow; } // Explicit current native window/owner boundary.
    void evaluate(const QString& code) { evaluated = code; } // Current document nonce boundary.
    void keyEvent(const QString&, int = 0, int = 0);
    void inputMethodEvent(QInputMethodEvent*);
};
''' + methods + r'''
}
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    overte::ios::IOSWebView item;
    QJsonObject cases;
    const auto key = [&](const char* name, int value, const QString& text = QString(), int modifiers = 0) {
        item.evaluated.clear(); item.keyEvent(text, value, modifiers); cases.insert(name, item.evaluated);
    };
    key("text", Qt::Key_Z, "Z"); key("left", Qt::Key_Left); key("right", Qt::Key_Right);
    key("home", Qt::Key_Home); key("end", Qt::Key_End);
    key("shift-left", Qt::Key_Left, "", Qt::ShiftModifier);
    key("shift-right", Qt::Key_Right, "", Qt::ShiftModifier);
    key("shift-home", Qt::Key_Home, "", Qt::ShiftModifier);
    key("shift-end", Qt::Key_End, "", Qt::ShiftModifier);
    key("return", Qt::Key_Return, "\r"); key("enter-empty", Qt::Key_Enter);
    key("backspace", Qt::Key_Backspace); key("delete", Qt::Key_Delete);
    key("empty-unknown", Qt::Key_F1); key("oversize", Qt::Key_Z, QString(8193, 'Z'));
    key("control", Qt::Key_Z, QString(QChar(0x1a)), Qt::ControlModifier);
    key("alt", Qt::Key_Z, "Z", Qt::AltModifier); key("meta", Qt::Key_Z, "Z", Qt::MetaModifier);
    QInputMethodEvent ime; ime.setCommitString("Z"); item.evaluated.clear(); item.inputMethodEvent(&ime);
    cases.insert("ime", item.evaluated);
    item.activeWindow = false; key("inactive", Qt::Key_Z, "Z"); item.activeWindow = true;
    item.state.inputActive = false; key("no-editor", Qt::Key_Z, "Z"); item.state.inputActive = true;
    item.state.presentation = true; key("native-sheet", Qt::Key_Z, "Z");
    std::cout << QJsonDocument(cases).toJson(QJsonDocument::Compact).toStdString();
}
'''

page_template = r'''<!doctype html><meta charset="utf-8"><body><pre id="results"></pre><script>
const scripts = NATIVE_SCRIPTS, results = [];
function run(name, script, options, expected) {
    const form = document.createElement('form'), element = document.createElement(options.tag || 'input');
    if (element.tagName === 'INPUT') element.type = options.type || 'text';
    element.value = options.value === undefined ? 'abc' : options.value;
    element.readOnly = !!options.readOnly;
    form.append(element); document.body.append(form); element.focus();
    try { element.setSelectionRange(options.start === undefined ? element.value.length : options.start,
        options.end === undefined ? (options.start === undefined ? element.value.length : options.start) : options.end,
        options.direction || 'forward'); } catch (_) {}
    element.disabled = !!options.disabled;
    if(options.disabledFieldset){const fieldset=document.createElement('fieldset');fieldset.disabled=true;form.append(fieldset);fieldset.append(element);}
    const events = []; let submits = 0, clicks = 0, submittedButton = false;
    if(options.submitButton){
        const button=document.createElement(options.imageButton?'input':'button');button.type=options.imageButton?'image':'submit';
        button.disabled=!!options.disabledButton;button.id='default-submit';
        button.addEventListener('click',event=>{++clicks;if(options.cancelClick)event.preventDefault();});
        if(options.externalButton){form.id='external-form';button.setAttribute('form',form.id);document.body.append(button);}else form.append(button);
    }
    form.addEventListener('submit', event => { event.preventDefault(); ++submits; submittedButton=!!event.submitter&&event.submitter.id==='default-submit'; });
    for (const type of ['keydown', 'beforeinput', 'input']) element.addEventListener(type, event => {
        events.push({type:event.type, key:event.key || null, inputType:event.inputType || null,
            cancelable:event.cancelable, shift:event.shiftKey || false});
        if (options.cancel === type) event.preventDefault();
    });
    let error = null; try { (0, eval)(scripts[script]); } catch (caught) { error = String(caught); }
    const actual = {value:element.value, start:element.selectionStart, end:element.selectionEnd,
        direction:element.selectionDirection, submits, clicks, submittedButton, inputEvents:events.filter(event => event.type === 'input').length};
    const failures = [];
    if (error) failures.push(error);
    for (const [field,value] of Object.entries(expected)) if (actual[field] !== value) failures.push(field + ': ' + JSON.stringify(actual[field]) + ' != ' + JSON.stringify(value));
    if (options.requireBeforeInput && !events.some(event => event.type === 'beforeinput' && event.cancelable)) failures.push('missing cancelable beforeinput');
    const named={left:'ArrowLeft',right:'ArrowRight',home:'Home',end:'End',return:'Enter','enter-empty':'Enter',backspace:'Backspace',delete:'Delete'};
    const expectedKey=named[script.replace('shift-','')];
    if(expectedKey && !events.some(event=>event.type==='keydown'&&event.key===expectedKey&&event.cancelable&&event.shift===script.startsWith('shift-'))) failures.push('missing cancelable named keydown');
    if(actual.inputEvents && events.map(event=>event.type).join(',')!=='keydown,beforeinput,input') failures.push('incorrect edit event ordering');
    results.push({name, script, actual, expected, events, failures});
    element.blur(); form.remove();document.querySelector('#default-submit')?.remove();
}
run('left collapses selection without deletion','left',{start:0,end:2},{value:'abc',start:0,end:0,inputEvents:0});
run('right collapses selection without deletion','right',{start:0,end:2},{value:'abc',start:2,end:2,inputEvents:0});
run('left moves caret','left',{start:2},{value:'abc',start:1,end:1,inputEvents:0});
run('right moves caret','right',{start:1},{value:'abc',start:2,end:2,inputEvents:0});
run('shift left retains anchor','shift-left',{start:1,end:3},{value:'abc',start:1,end:2,direction:'forward',inputEvents:0});
run('shift right retains reverse anchor','shift-right',{start:1,end:3,direction:'backward'},{value:'abc',start:2,end:3,direction:'backward',inputEvents:0});
run('home uses textarea line start','home',{tag:'textarea',value:'a\nbc',start:4},{value:'a\nbc',start:2,end:2,inputEvents:0});
run('end uses textarea line end','end',{tag:'textarea',value:'a\nbc',start:2},{value:'a\nbc',start:4,end:4,inputEvents:0});
run('home at first empty textarea line stays zero','home',{tag:'textarea',value:'\nabc',start:0},{value:'\nabc',start:0,end:0,inputEvents:0});
run('keydown cancels selection navigation','left',{start:0,end:2,cancel:'keydown'},{value:'abc',start:0,end:2,inputEvents:0});
run('shift home extends selection','shift-home',{tag:'textarea',value:'a\nbc',start:4},{value:'a\nbc',start:2,end:4,direction:'backward',inputEvents:0});
run('shift end extends selection','shift-end',{tag:'textarea',value:'a\nbc',start:2},{value:'a\nbc',start:2,end:4,direction:'forward',inputEvents:0});
run('single line Enter submits without text edit','return',{}, {value:'abc',submits:1,inputEvents:0});
run('Enter activates default submit button','return',{submitButton:true},{value:'abc',submits:1,clicks:1,submittedButton:true,inputEvents:0});
run('default button click cancellation blocks Enter submit','return',{submitButton:true,cancelClick:true},{value:'abc',submits:0,clicks:1,inputEvents:0});
run('disabled default submit button blocks Enter','return',{submitButton:true,disabledButton:true},{value:'abc',submits:0,clicks:0,inputEvents:0});
run('externally associated default button activates','return',{submitButton:true,externalButton:true},{value:'abc',submits:1,clicks:1,submittedButton:true,inputEvents:0});
run('image submit button activates','return',{submitButton:true,imageButton:true},{value:'abc',submits:1,clicks:1,submittedButton:true,inputEvents:0});
run('textarea Return inserts newline without submit','return',{tag:'textarea',value:'ab',start:1,requireBeforeInput:true},{value:'a\nb',submits:0,inputEvents:1});
run('textarea keypad Enter with empty text inserts newline','enter-empty',{tag:'textarea',value:'ab',start:1},{value:'a\nb',submits:0,inputEvents:1});
run('readonly text stays unchanged','text',{readOnly:true},{value:'abc',inputEvents:0,submits:0});
run('readonly IME stays unchanged','ime',{readOnly:true},{value:'abc',inputEvents:0,submits:0});
run('disabled text stays unchanged','text',{disabled:true},{value:'abc',inputEvents:0,submits:0});
run('fieldset disabled editor stays unchanged','text',{disabledFieldset:true},{value:'abc',inputEvents:0,submits:0});
run('disabled IME stays unchanged','ime',{disabled:true},{value:'abc',inputEvents:0,submits:0});
run('keydown cancels text','text',{cancel:'keydown'},{value:'abc',inputEvents:0});
run('keydown cancels submit','return',{cancel:'keydown'},{value:'abc',inputEvents:0,submits:0});
run('beforeinput cancels text','text',{cancel:'beforeinput',requireBeforeInput:true},{value:'abc',inputEvents:0});
run('beforeinput cancels backspace','backspace',{cancel:'beforeinput',requireBeforeInput:true},{value:'abc',inputEvents:0});
run('beforeinput cancels IME commit','ime',{cancel:'beforeinput',requireBeforeInput:true},{value:'abc',inputEvents:0});
run('beforeinput cancels textarea Enter','return',{tag:'textarea',cancel:'beforeinput',requireBeforeInput:true},{value:'abc',inputEvents:0,submits:0});
run('ordinary insertion replaces selection','text',{start:1,end:2,requireBeforeInput:true},{value:'aZc',start:2,end:2,inputEvents:1});
run('IME commit replaces selection','ime',{start:1,end:2},{value:'aZc',start:2,end:2,inputEvents:1});
run('backspace preserves surrogate boundary','backspace',{value:'A😀B',start:3},{value:'AB',start:1,end:1,inputEvents:1});
run('delete preserves surrogate boundary','delete',{value:'A😀B',start:1},{value:'AB',start:1,end:1,inputEvents:1});
run('empty unknown key never deletes selection','empty-unknown',{start:0,end:2},{value:'abc',inputEvents:0});
for(const cancel of ['keydown','beforeinput']){
    const el=document.createElement('div');el.contentEditable='true';el.textContent='abc';document.body.append(el);el.focus();
    let inputs=0;el.addEventListener(cancel,event=>event.preventDefault());el.addEventListener('input',()=>++inputs);
    (0,eval)(scripts.text);results.push({name:'contenteditable '+cancel+' cancellation',failures:el.textContent==='abc'&&inputs===0?[]:['contenteditable changed despite cancellation']});el.remove();
}
for (const kind of ['control','alt','meta','inactive','no-editor','native-sheet','oversize']) {
    const failures = scripts[kind] === '' ? [] : ['native gate generated an edit script'];
    results.push({name:'native gate '+kind, failures});
}
document.getElementById('results').textContent = JSON.stringify(results);
</script></body>'''

browser = browser_path()
flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core", "Qt6Gui"], text=True))
with tempfile.TemporaryDirectory(prefix="ios-texture-keyboard-") as temporary:
    stage = Path(temporary)
    cpp, binary = stage / "keys.cpp", stage / "keys"
    cpp.write_text(driver)
    compiler = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC", str(cpp), "-o", str(binary), *flags]
    subprocess.run(compiler, check=True, timeout=60)
    generated = subprocess.check_output([str(binary)], text=True, timeout=10)
    scripts = json.loads(generated)
    page = stage / "keyboard.html"
    page.write_text(page_template.replace("NATIVE_SCRIPTS", json.dumps(scripts).replace("<", "\\u003c")))
    browser_command = [str(browser), "--headless", "--no-sandbox", "--disable-gpu", "--disable-background-networking",
        "--no-first-run", "--no-default-browser-check", "--user-data-dir=" + str(stage / "profile"), "--dump-dom", page.as_uri()]
    result = subprocess.run(browser_command, capture_output=True, text=True, timeout=30)
    match = re.search(r'<pre id="results">(.*?)</pre>', result.stdout, re.S)
    if not match:
        raise SystemExit("Chromium returned no DOM results: " + result.stderr)
    results = json.loads(html.unescape(match.group(1)))
    failed = [row for row in results if row["failures"]]
    receipt = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "compiler": compiler,
        "browser_command": browser_command, "browser_path": str(browser),
        "browser_version": subprocess.check_output([str(browser), "--version"], text=True).strip(),
        "browser_sha256": hashlib.sha256(browser.read_bytes()).hexdigest(), "browser_exit": result.returncode, "fixture_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": len(results), "failed": len(failed), "results": results,
        "boundary": "Actual C++ key/IME bodies and generated scripts in real Chromium DOM. Native active-window/current nonce dispatch is substituted. No UIKit/WK, full IME composition, physical keyboard, app or device qualification."}
    artifacts = os.environ.get("OVERTE_IOS_TEXTURE_KEYBOARD_ARTIFACTS")
    if artifacts:
        retained = Path(artifacts)
        retained.mkdir(parents=True, exist_ok=True)
        for name, data in {"keys.cpp": driver, "scripts.json": generated, "keyboard.html": page.read_text(),
                           "browser-dom.html": result.stdout, "browser-stderr.log": result.stderr,
                           "receipt.json": json.dumps(receipt, indent=2) + "\n"}.items():
            (retained / name).write_text(data)
    print(json.dumps(receipt, indent=2))
    if result.returncode or failed:
        raise SystemExit("FAIL actual iOS texture keyboard: " + "; ".join(row["name"] for row in failed))
print("PASS actual iOS texture keyboard key/IME bodies and Chromium DOM; WK/device not performed")
