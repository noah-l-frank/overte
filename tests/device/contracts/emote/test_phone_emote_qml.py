#!/usr/bin/env python3
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
"""Explicit Qt5/Qt6 mouse/keyboard dispatch from unchanged PhoneEmote.qml into production JS.

Qt Quick controls/models/layout and JS handlers are real. Native animation cache
and avatar endpoints, frame counts and script timers are explicit JS seams. The
real bundled FBX bytes are checked, not decoded or rendered as an avatar here.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).parent
major = os.environ.get('OVERTE_EMOTE_QT_MAJOR', '5')
if major not in ('5', '6'):
    raise SystemExit('OVERTE_EMOTE_QT_MAJOR must explicitly select 5 or 6')
qt = 'Qt' + major
versions = subprocess.check_output(['pkg-config', '--modversion', qt + 'Core', qt + 'QuickTest'], text=True).split()
if len(versions) != 2 or len(set(versions)) != 1 or not versions[0].startswith(major + '.'):
    raise SystemExit('Matching requested Qt Core and QuickTest are required; no fallback or skip')
bins = Path(subprocess.check_output(['pkg-config', '--variable=' + ('host_bins' if major == '5' else 'bindir'), qt + 'Core'], text=True).strip())
runner = bins / 'qmltestrunner'
if not runner.is_file():
    raise SystemExit('The requested real Qt' + major + ' qmltestrunner is missing')
source = ROOT / 'scripts/system/+android_phoneInterface/PhoneEmote.qml'
with tempfile.TemporaryDirectory(prefix='overte-phone-emote-qt' + major + '-') as temporary:
    stage = Path(temporary)
    production = stage / 'production'
    production.mkdir()
    copied = production / source.name
    shutil.copy2(source, copied)
    assert copied.read_bytes() == source.read_bytes()
    shutil.copy2(HERE / 'tst_phone_emote.qml', stage)
    # Use the real compiled Phone selector with a native sound/enum boundary.
    # Production controls, touch metrics and all action handlers stay in-tree.
    moc = (bins if major == '5' else Path(subprocess.check_output(
        ['pkg-config', '--variable=libexecdir', qt + 'Core'], text=True).strip())) / 'moc'
    cpp = HERE / 'phone-native-context.cpp'
    subprocess.run([str(moc), str(cpp), '-o', str(stage / 'phone-native-context.moc')], check=True)
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', qt + 'QuickTest', qt + 'Quick', qt + 'Test'], text=True))
    libdir = subprocess.check_output(['pkg-config', '--variable=libdir', qt + 'Core'], text=True).strip()
    binary = stage / 'phone-emote'
    subprocess.run(['c++', '-std=c++17', '-fPIC', '-I' + str(stage), str(cpp),
                    '-o', str(binary), '-L' + libdir, *flags], check=True, timeout=60)
    result = subprocess.run([str(binary), '-import', str(ROOT / 'interface/resources/qml'),
                             '-input', str(stage / 'tst_phone_emote.qml')],
        env=os.environ | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
            # The real click trace is mandatory evidence, including on hosts
            # whose Qt logging configuration disables debug messages globally.
            'QT_LOGGING_RULES': os.environ.get('QT_LOGGING_RULES', '') + '\nqml.debug=true'},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    print(result.stdout, end='', flush=True)
    result.check_returncode()
    if re.search(r'TypeError:|ReferenceError:|Cannot assign|Binding loop', result.stdout):
        raise RuntimeError('Production QML emitted an execution error')
    if f'QtTest library {versions[0]}' not in result.stdout:
        raise RuntimeError('Executed Qt Quick Test runtime does not match the requested Qt development version')
    traces = re.findall(r'OVERTE_EMOTE_ACTIONS_JSON=(\[[^\n]+\])', result.stdout)
    if len(traces) != 1:
        raise RuntimeError('The real ten-button mouse dispatch trace is missing or ambiguous')
    actions = json.loads(traces[0])
    trace = stage / 'actual-clicks.json'
    trace.write_text(json.dumps(actions) + '\n')
    evidence = os.environ.get('OVERTE_EMOTE_QML_EVIDENCE')
    if evidence:
        Path(evidence).write_text(json.dumps({'source': str(source),
            'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'qt_version': versions[0], 'runner': str(binary),
            'runner_kind': 'Compiled Qt Quick Test with native Phone file selectors',
            'runner_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'native_boundary_source_sha256': hashlib.sha256(cpp.read_bytes()).hexdigest(),
            'actions': actions,
            'boundary': 'Unchanged production QML with real Qt' + major + ' mouse/keyboard and Controls; state feedback enters its actual fromScript handler at the script boundary. These exact mouse events next enter unchanged production JS; cache/avatar/timers are explicit seams.'}, indent=2) + '\n')
    subprocess.run(['node', '--test', str(ROOT / 'tests/javascript/test/phone-emote.production.test.js')],
        env=os.environ | {'OVERTE_EMOTE_QML_ACTIONS': str(trace)}, check=True, timeout=60)
