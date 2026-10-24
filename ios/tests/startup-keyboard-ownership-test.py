#!/usr/bin/env python3
"""Execute actual initialization callbacks with real Qt timers/focus queries.

The OffscreenUi getter is original; its broader application services and public
UIKit/WK editor/presentation inspection are explicit unopened native seams.
No Apple SDK, native responder behavior or physical keyboard pass is inferred.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--source-ref', help='Read original callbacks from an immutable local Git revision.')
args = parser.parse_args()
relative = 'interface/src/Application_UI.cpp'
source = subprocess.check_output(['git', '-C', str(ROOT), 'show', args.source_ref + ':' + relative], text=True) \
    if args.source_ref else (ROOT / relative).read_text()
start = source.index('    dismissIOSKeyboard();\n    // Qt can briefly')
end = source.index('    qInfo().noquote() << "OVERTE_IOS_UI_POLICY', start)
callbacks = source[start:end]
header = (ROOT / 'libraries/ui/src/ui/OffscreenQmlSurface.h').read_text()
getter = next(line for line in header.splitlines() if 'bool isFocusText() const' in line)
# Native safety source guards complement the executed Qt policy. They do not
# represent a compiled UIKit/WebKit implementation or native responder test.
native = (ROOT / 'ios/ui/IOSTouchUiMetrics.mm').read_text()
if not args.source_ref:
    helper = native[native.index('void dismissIOSStartupKeyboard()'):native.index('void suppressIOSKeyboardAssistant()')]
    for needed in ('!NSThread.isMainThread', 'presentedViewController', 'findFirstResponder(window)',
                   'UITextField.class', 'UITextView.class', 'WKWebView.class', 'dismissActiveWindowEditing();'):
        assert needed in helper, needed
    assert 'dispatch_async' not in helper, 'Never queue a destructive action after a focus snapshot.'
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Quick'], text=True))
flags = [part for flag in flags for part in (['-isystem', flag[2:]] if flag.startswith('-I') else [flag])]
with tempfile.TemporaryDirectory(prefix='ios-startup-keyboard-') as temporary:
    stage = Path(temporary)
    (stage / 'production-startup-cleanup.inc').write_text(callbacks)
    (stage / 'production-offscreen-focus-getter.inc').write_text(getter)
    binary = stage / 'test'
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fPIC',
        '-I' + str(stage), str(Path(__file__).with_suffix('.cpp')), '-o', str(binary), *flags],
        check=True, timeout=60)
    subprocess.run([str(binary)], check=True, timeout=30, env=os.environ | {
        'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'})
print('PASS production startup callbacks, unscaled250ms/1000ms Qt timers, cached/live editable focus, idle cleanup and owner lifetimes')
print('UIKit/WK responder and native presentation inspection: SOURCE_GUARDED_NOT_EXECUTED')
