#!/usr/bin/env python3
"""Actual selected iOS world controls, pointer dispatch and real DOM scrolling.

Only the UIKit/WK endpoint is substituted; the original world surface, selected
wrapper and shared runJavaScript/openNative forwarding execute in place. The
captured production scroll commands then execute in installed Chromium. This
does not qualify WK video pixels, native presentation or physical-device input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
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
SOURCE_ROOT = Path(os.environ.get('OVERTE_IOS_WORLD_WEB_SOURCE_ROOT', ROOT)).resolve()
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
    'Qt6QuickTest', 'Qt6Quick', 'Qt6Test'], text=True))
flags = [part for flag in flags for part in (['-isystem', flag[2:]] if flag.startswith('-I') else [flag])]
tools = Path(subprocess.check_output(['pkg-config', '--variable=libexecdir', 'Qt6Core'], text=True).strip())
browser = os.environ.get('OVERTE_IOS_WEB_TEST_BROWSER')
if not browser:
    browser = next((shutil.which(name) for name in ('chromium', 'chromium-browser', 'google-chrome', 'chrome-headless-shell')
                    if shutil.which(name)), None)
if not browser:
    candidates = sorted((Path.home() / '.cache/ms-playwright').glob(
        'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'), reverse=True)
    browser = str(candidates[0]) if candidates else None
if not browser or not Path(browser).is_file():
    raise SystemExit('An installed Chromium is required; no download or skipped DOM check.')
with tempfile.TemporaryDirectory(prefix='ios-world-web-controls-') as temporary:
    stage = Path(temporary)
    cpp = Path(__file__).with_suffix('.cpp')
    subprocess.run([str(tools / 'moc'), str(cpp), '-o', str(stage / 'ios-world-web-controls-test.moc')],
        check=True, timeout=30)
    binary = stage / 'test'
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fPIC',
        '-I' + str(stage), '-I' + str(ROOT / 'libraries/ui/src'), str(cpp), '-o', str(binary), *flags],
        check=True, timeout=90)
    result = subprocess.run([str(binary), '-input', str(ROOT / 'ios/tests/qml/tst_ios_world_web_controls.qml')],
        text=True, capture_output=True, timeout=60, env=os.environ | {
            'OVERTE_WORLD_WEB_SOURCE_ROOT': str(SOURCE_ROOT),
            'OVERTE_WORLD_WEB_BOUNDARY': str(ROOT / 'ios/tests/qml/WorldWebNativeBoundary.qml'),
            'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'})
    print(result.stdout + result.stderr, end='')
    result.check_returncode()
    if re.search(r'ReferenceError:|TypeError:|Cannot assign|Binding loop', result.stdout + result.stderr):
        raise SystemExit('Actual selected world QML emitted an execution error.')
    match = re.findall(r'OVERTE_IOS_WORLD_SCROLL_SCRIPTS=(\[[^\n]+\])', result.stdout + result.stderr)
    assert len(match) == 1, 'The actual pointer-to-scroll trace must be unambiguous.'
    scripts = json.loads(match[0])
    page = stage / 'scroll.html'
    page.write_text('<!doctype html><style>html {scroll-behavior:auto} body{margin:0;height:10000px}</style>'
        '<pre id="result"></pre><script>const commands=' + json.dumps(scripts) + ';'
        'const before=scrollY;(0,eval)(commands[0]);const down=scrollY;(0,eval)(commands[1]);'
        'document.getElementById("result").textContent=JSON.stringify({before,down,up:scrollY});</script>')
    dom = subprocess.run([browser, '--headless', '--no-sandbox', '--disable-gpu', '--disable-background-networking',
        '--no-first-run', '--no-default-browser-check', '--user-data-dir=' + str(stage / 'profile'), '--dump-dom', page.as_uri()],
        text=True, capture_output=True, timeout=30)
    dom.check_returncode()
    match = re.search(r'<pre id="result">(.*?)</pre>', dom.stdout)
    assert match, dom.stderr
    observed = json.loads(html.unescape(match[1]))
    assert observed['before'] == 0 and observed['down'] > 0 and observed['up'] == 0, observed
    print('PASS actual selected iOS world pointer controls and unchanged shared/native API handoff; Chromium DOM:', observed)
    print('UIKit/WK presentation, media and physical input: NOT_PERFORMED')
