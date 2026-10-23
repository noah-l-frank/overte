"""Compile complete original tablet/offscreen methods with declared host services."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
from test_create_polyvox_controls_native import original

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def prepare(stage,environment,prefix):
    stage=Path(stage);surface=(ROOT/'libraries/qml/src/qml/OffscreenSurface.cpp').read_text()
    ui=(ROOT/'libraries/ui/src/ui/OffscreenQmlSurface.cpp').read_text()
    tablet=(ROOT/'libraries/ui/src/ui/TabletScriptingInterface.cpp').read_text()
    shared=(ROOT/'libraries/qml/src/qml/impl/SharedObject.cpp').read_text()
    signatures=('void OffscreenSurface::loadInternal(', 'void OffscreenSurface::finishQmlLoad(', 'QQmlContext* OffscreenSurface::contextForUrl(')
    blocks=[original(surface,signature) for signature in signatures]
    start=surface.index('QmlUrlValidator OffscreenSurface::validator =');end=surface.index('\n};',start)+3
    validator=surface[start:end]
    default=next(line for line in surface.splitlines() if line.startswith('const QmlContextCallback OffscreenSurface::DEFAULT_CONTEXT_CALLBACK ='))
    native='namespace hifi::qml {\nconst QString URL_SCHEME_QRC="qrc";\n'+default+'\n'+validator+'\n'+'\n'.join(blocks)+'\n}\n'
    native+='namespace hifi::qml {\n'+original(shared,'void SharedObject::addToDeletionList(').replace('SharedObject::','HostSharedObject::')+'\n}\n'
    native+='\n'+original(ui,'void OffscreenQmlSurface::loadFromQml(').replace('OffscreenQmlSurface::loadFromQml','HostSurfaceLoader::load')
    native+='\nconst char* TABLET_HOME_SOURCE_URL="hifi/tablet/TabletHome.qml";\n'
    methods=('void TabletProxy::gotoHomeScreen(', 'void TabletProxy::loadHomeScreen(', 'bool TabletProxy::onHomeScreen(', 'void TabletProxy::loadQMLSourceImpl(')
    native+='\n'.join(original(tablet,signature) for signature in methods)
    (stage/'AssetsTabletOriginals.inc').write_text(native)
    provenance={signature:hashlib.sha256(block.encode()).hexdigest() for signature,block in zip(signatures,blocks)}
    provenance.update({signature:hashlib.sha256(original(tablet,signature).encode()).hexdigest() for signature in methods})
    provenance['void OffscreenQmlSurface::loadFromQml(']=hashlib.sha256(original(ui,'void OffscreenQmlSurface::loadFromQml(').encode()).hexdigest()
    (stage/'tablet-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    for module in ('Hifi','stylesUit'):(stage/'imports'/module).mkdir(exist_ok=True)
    (stage/'imports/Hifi/qmldir').write_text('module Hifi\nSoundEffect 1.0 SoundEffect.qml\n')
    (stage/'imports/Hifi/SoundEffect.qml').write_text('import QtQuick 2.7\nQtObject {property real volume:0;property url source;function play(position) {}}\n')
    (stage/'imports/stylesUit/qmldir').write_text('module stylesUit\nHifiConstants 1.0 HifiConstants.qml\n')
    (stage/'imports/stylesUit/HifiConstants.qml').write_bytes((ROOT/'interface/resources/qml/stylesUit/HifiConstants.qml').read_bytes())
    (stage/'unrelated-tablet-content.qml').write_text('import QtQuick 2.7\nItem {signal canceled()}\n')
    output=stage/'tablet-host-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS',
        '-I'+str(ROOT),str(HERE/'assets-tablet-host.h'),'-o',str(output)],check=True,timeout=20,env=environment)
    return ['-DASSETS_PERSISTENT_TABLET_HOST',str(output)]
