#!/usr/bin/env python3
"""Link real touch-metrics metadata and desktop destruction with both Qt majors.

Only the UIKit constructor is substituted. The real header, MOC output and
portable destructor implementation are compiled and executed without devices.
"""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
header = ROOT / 'interface/src/IOSTouchUiMetrics.h'
shim = ROOT / 'interface/src/IOSTouchUiMetrics.cpp'
program = r'''
#include <QCoreApplication>
#include <cassert>
#include <IOSTouchUiMetrics.h>
// Native UIKit observer setup is outside this desktop link regression.
IOSTouchUiMetrics::IOSTouchUiMetrics(QObject* parent) : QObject(parent) {}
int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    int destroyed = 0;
    {
        QObject owner;
        auto* metrics = new IOSTouchUiMetrics(&owner);
        QObject::connect(metrics, &QObject::destroyed, [&] { ++destroyed; });
        assert(metrics->metaObject()->indexOfProperty("keyboardVisible") >= 0);
        assert(!metrics->property("keyboardVisible").toBool());
        assert(metrics->property("density").toDouble() == 1.0);
        delete metrics;
        assert(destroyed == 1);
        metrics = new IOSTouchUiMetrics(&owner);
        QObject::connect(metrics, &QObject::destroyed, [&] { ++destroyed; });
    }
    assert(destroyed == 2);
}
'''
with tempfile.TemporaryDirectory(prefix='touch-metrics-link-') as temporary:
    directory = Path(temporary)
    source = directory / 'main.cpp'
    source.write_text(program)
    for major in (5, 6):
        package = f'Qt{major}Core'
        flags = shlex.split(subprocess.check_output(
            ['pkg-config', '--cflags', '--libs', package], text=True))
        variable = 'host_bins' if major == 5 else 'libexecdir'
        location = subprocess.check_output(
            ['pkg-config', '--variable=' + variable, package], text=True).strip()
        candidates = [Path(location) / 'moc'] if location else []
        candidates += [Path(f'/usr/lib/qt{major}/libexec/moc'),
                       Path(f'/usr/lib64/qt{major}/libexec/moc'),
                       Path(f'/usr/lib/qt{major}/bin/moc')]
        moc = next(path for path in candidates if path.is_file())
        generated = directory / f'moc-qt{major}.cpp'
        subprocess.run([str(moc), str(header), '-o', str(generated)], check=True, timeout=30)
        binary = directory / f'test-qt{major}'
        sources = [str(source), str(generated), *([str(shim)] if shim.is_file() else [])]
        subprocess.run(['c++', '-std=c++17', '-fPIC', '-I', str(header.parent),
                        *sources, '-o', str(binary), *flags], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
        print(f'PASS Qt{major}: actual touch-metrics MOC and desktop destructor link; '
              'explicit and parent-owned destruction execute exactly once', flush=True)
