#!/usr/bin/env python3
"""Actual complete Pal/NameCard controls and pointer actions on Qt5 or Qt6.

Only native context services are substituted. The shared JS protocol is covered
separately by two production Pal engines and the real request serializer.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
major = os.environ.get('OVERTE_NATIVE_QT_MAJOR', '6')
assert major in ('5', '6')
env = os.environ | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software'}
kit = Path(os.environ.get('OVERTE_QT5_ROOT', str(Path.home() / '.local/overte-qt5/root')))
libraries = []
if major == '5' and (kit / 'usr/lib64/pkgconfig/Qt5QuickTest.pc').is_file():
    env.update({'PKG_CONFIG_PATH': str(kit / 'usr/lib64/pkgconfig'), 'PKG_CONFIG_SYSROOT_DIR': str(kit),
        'LD_LIBRARY_PATH': str(kit / 'usr/lib64'), 'QML2_IMPORT_PATH': str(kit / 'usr/lib64/qt5/qml'),
        'QT_PLUGIN_PATH': str(kit / 'usr/lib64/qt5/plugins')})
    tools = kit / 'usr/lib64/qt5/bin'
    libraries = ['-L' + str(kit / 'usr/lib64')]
else:
    tools = Path(subprocess.check_output(['pkg-config', '--variable=' + ('libexecdir' if major == '6' else 'host_bins'), 'Qt' + major + 'Core'], text=True, env=env).strip())
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', *['Qt' + major + v for v in ('QuickTest','Quick','Test')]], text=True, env=env))
with tempfile.TemporaryDirectory(prefix='overte-people-qml-') as temporary:
    stage = Path(temporary)
    env["XDG_CONFIG_HOME"] = str(stage / "settings")
    subprocess.run([str(tools / 'moc'), str(HERE / 'native-context.cpp'), '-o', str(stage / 'native-context.moc')], check=True, env=env)
    binary = stage / 'people-qml'
    subprocess.run(['c++', '-std=c++17', '-fPIC', str(HERE / 'native-context.cpp'), '-I' + str(stage), *libraries, '-o', str(binary), *flags], check=True, env=env, timeout=60)
    result = subprocess.run([str(binary), '-import', str(ROOT / 'interface/resources/qml'), '-import', str(ROOT / 'tests/device/qml/imports'), '-input', str(HERE / 'tst_people_connection.qml')], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, env=env, timeout=60)
    print(result.stdout, end='')
    result.check_returncode()
    if re.search(r'ReferenceError:|TypeError:|Binding loop|Cannot assign|Could not convert argument', result.stdout):
        raise RuntimeError('Production People QML emitted an execution error')
