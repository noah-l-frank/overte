#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Execute Phone's real Gradle Sync task, XML deployment and Qt5 GIF decoder.

Uses host Qt plugins under Android ABI filenames; it does not compile an APK or
execute Android Qt. The production staging rule and deployment map are real.
Set OVERTE_CODEC_TEST_QT_ROOT and OVERTE_CODEC_TEST_GRADLE explicitly.
"""
import base64
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get('OVERTE_CODEC_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[3]))
qt = Path(os.environ['OVERTE_CODEC_TEST_QT_ROOT'])
gradle = os.environ['OVERTE_CODEC_TEST_GRADLE']
source = (ROOT / 'android/phone/apps/phoneInterface/build.gradle').read_text()
start = source.index("tasks.register('preparePhoneQtRuntime', Sync)")
end = source.index('\nandroid {', start)
task = source[start:end]
GIF = base64.b64decode('R0lGODlhAgACAIEAAP8AAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQACgAAACwAAAAAAgACAAAIBgABCAQQEAAh+QQBCgABACwAAAAAAgACAIEAAP8AAAAAAAAAAAAIBgABCAQQEAA7')
CPP = r'''
#include <QGuiApplication>
#include <QMovie>
#include <QImageReader>
#include <QDebug>
int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    QCoreApplication::setLibraryPaths({ QString::fromLocal8Bit(argv[1]) });
    QMovie movie(QString::fromLocal8Bit(argv[2]));
    if (!movie.isValid() || movie.frameCount() != 2 || !movie.jumpToFrame(0)
            || movie.currentImage().pixelColor(0,0) != QColor(Qt::red)
            || !movie.jumpToFrame(1) || movie.currentImage().pixelColor(0,0) != QColor(Qt::blue)) {
        qCritical() << "Staged Phone runtime cannot decode both GIF preview frames" << QImageReader::supportedImageFormats();
        return 1;
    }
    qInfo() << "Decoded both GIF preview frames with staged runtime codecs" << qVersion();
}
'''
with tempfile.TemporaryDirectory(prefix='phone-snapshot-codecs-') as temporary:
    stage = Path(temporary)
    cpp = stage/'decode.cpp'; cpp.write_text(CPP)
    binary = stage/'decode'
    subprocess.run(['c++','-std=c++17','-fPIC',f'-I{qt}/usr/include/qt5',
        f'-I{qt}/usr/include/qt5/QtCore',f'-I{qt}/usr/include/qt5/QtGui',str(cpp),
        f'-L{qt}/usr/lib64','-lQt5Gui','-lQt5Core',f'-Wl,-rpath,{qt}/usr/lib64',
        '-o',str(binary)],check=True,timeout=60)
    gif = stage/'preview.gif';gif.write_bytes(GIF)
    env = os.environ | {'LD_LIBRARY_PATH':str(qt/'usr/lib64'), 'QT_PLUGIN_PATH':'', 'QT_FORCE_STDERR_LOGGING':'1', 'QT_QPA_PLATFORM':'offscreen', 'QT_QPA_PLATFORM_PLUGIN_PATH':str(qt/'usr/lib64/qt5/plugins/platforms')}
    # Prove the host cannot borrow an installed GIF plugin as fallback.
    empty = stage/'empty';empty.mkdir()
    negative = subprocess.run([str(binary),str(empty),str(gif)],env=env,capture_output=True,text=True,timeout=20)
    assert negative.returncode == 1, negative.stdout + negative.stderr
    print('Negative control: an empty plugin deployment rejects the animated preview',flush=True)
    failures = []
    for abi, variant in [('arm64-v8a','main'),('x86_64','emulator')]:
        project = stage/abi; project.mkdir()
        plugins = project/'qt/plugins/imageformats';plugins.mkdir(parents=True)
        for name in ('gif','jpeg','svg'):
            shutil.copy2(qt/f'usr/lib64/qt5/plugins/imageformats/libq{name}.so',
                plugins/f'libplugins_imageformats_q{name}_{abi}.so')
        (project/'settings.gradle').write_text("rootProject.name = 'phone-codec-staging'\n")
        (project/'build.gradle').write_text("""
def qtPackageDir = file('qt')
def phoneQtRuntimeDir = layout.buildDirectory.dir('staged')
def phoneTargetAbi = '%s'
def qtAbiSuffix = phoneTargetAbi
def runtimeOverrides = file('unused')
def androidOpenSslDir = file('unused')
def usePhone16kQt = true
def usePhone16kDependencies = true
def isPhoneEmulatorBuild = %s
tasks.register('verifyPhone16kDependencies')
""" % (abi, str(variant=='emulator').lower()) + task)
        subprocess.run([gradle,'--offline','--no-daemon','--console=plain','-q',
            'preparePhoneQtRuntime'],cwd=project,check=True,timeout=90)
        deployed = project/'deployed'
        xml = ROOT/f'android/phone/apps/phoneInterface/src/{variant}/res/values/qt_dependencies.xml'
        for item in ET.parse(xml).findall(".//string-array[@name='bundled_in_lib']/item"):
            original, target = item.text.split(':',1)
            if '/imageformats/' not in target:
                continue
            payload = project/'build/staged'/abi/original
            assert payload.is_file(), f'{variant} deployment refers to unstaged {original}'
            destination = deployed/target
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(payload,destination)
        result = subprocess.run([str(binary),str(deployed/'plugins'),str(gif)],
            env=env,capture_output=True,text=True,timeout=20)
        print(abi, 'exit=' + str(result.returncode), result.stdout + result.stderr,flush=True)
        if result.returncode:
            failures.append(abi)
    assert not failures, 'GIF preview decoder absent from selected Phone runtime: ' + ', '.join(failures)
print('Phone production Sync + Qt deployment + animated GIF preview: PASS',flush=True)
