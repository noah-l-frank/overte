"""Actual Pico observer/input, original Assets QML and real file helper.

Asset Server/entity and keyboard-device endpoints are declared host seams.
This compiles selected original bodies, not Interface or an actual oven/server.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
from test_create_polyvox_controls_native import pointer_source,original
from test_assets_read_native import prepare_source



def navigation_source(stage,filename='actual-assets-navigation.inc'):
    """Complete original Pico observer+writer, shared by normal feature hosts."""
    native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
    bodies='\n'.join(original(native,signature) for signature in ('QString token()', 'bool visible(', 'bool enabled(',
        'QString controlId(', 'bool integer(', 'bool exactKeys('))
    bodies+='\nNavigationUi::NavigationUi() : _bridgeId(token()), _generation(token()) { _clock.start(); }\n'
    bodies+='\n'+original(native,'QJsonObject NavigationUi::observe(')+'\n'+original(native,'QJsonObject NavigationUi::apply(')
    (stage/filename).write_text('namespace overte::pico::e2e {\n'+bodies+'\n}\n')


def compile_ui(stage,*,original_uploads=False,sanitize=False,persistent_tablet=False,original_server=False,original_model=False,original_entity=False,original_resources=False,request_lifetimes=False,original_resource_manager=False,original_resource_data=False):
    environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
        QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
        *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test','Widgets'))],text=True,env=environment))
    stage=Path(stage);prepare_source(stage,environment,prefix);pointer_source(stage);imports=stage/'imports/controlsUit';imports.mkdir(parents=True)
    (imports/'qmldir').write_text('module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\nKeyboard 1.0 Keyboard.qml\n')
    (imports/'TouchUiMetrics.qml').write_text('import QtQml 2.7\nQtObject {property bool systemImeAvailable:false}\n')
    (imports/'Keyboard.qml').write_text('import QtQuick 2.7\nItem {property bool raised:false;property bool numeric:false;property bool password:false;property real keyboardWidth:640;property real raisedHeight:200}\n')
    (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
        'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
        'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
    navigation_source(stage)
    files=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    (stage/'AssetsFilesMethod.inc').write_text(original(files,'QVariantMap TestScriptingInterface::featurePicoAssetsFiles('))
    (stage/'AssetsUploadsMethod.inc').write_text(original(files,'QVariantMap TestScriptingInterface::featurePicoAssetsUploadsObservation('))
    mappings=(ROOT/'interface/src/scripting/AssetMappingsScriptingInterface.cpp').read_text()
    bundle=original(mappings,'struct AssetMappingsScriptingInterface::BundleUpload {')+';\n'+original(mappings,'static QVariantMap assetsOriginalConnection(')+'\n'
    bundle+='\n'.join(original(mappings,signature) for signature in ('QString AssetMappingsScriptingInterface::uploadBundle(',
        'bool AssetMappingsScriptingInterface::cancelUploadBundle(', 'void AssetMappingsScriptingInterface::finishBundle('))
    header=(ROOT/'interface/src/scripting/AssetMappingsScriptingInterface.h').read_text()
    bundle+='\n'+original(header,'QVariantMap featurePicoBundleOriginals(').replace('QVariantMap featurePicoBundleOriginals(',
        'QVariantMap AssetMappingsScriptingInterface::featurePicoBundleOriginals(').replace(') const {',') {')
    upload_arguments=['-fsanitize=address','-fno-omit-frame-pointer','-g1'] if sanitize else []
    if original_server:
        from test_assets_server_state import prepare_server_originals
        prepare_server_originals(stage);upload_arguments+=['-DASSETS_ORIGINAL_SERVER_QUERY']
    if original_model:
        assert original_server
        spec=importlib.util.spec_from_file_location('assets_mapping_prepare',HERE/'assets-mapping-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,environment,prefix)
    if original_entity:
        assert original_server and original_model and persistent_tablet
        spec=importlib.util.spec_from_file_location('assets_entity_prepare',HERE/'assets-entity-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,environment,prefix)
        from adapters.assets_input import documents
        fixture=stage/'original-entity-input';fixture.mkdir()
        for name,data in documents().items():
            if not name.startswith('gltf-bundle/'):continue
            target=fixture/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        environment['OVERTE_ASSETS_ENTITY_FIXTURE']=str(fixture)
    if original_resources:
        assert original_entity
        spec=importlib.util.spec_from_file_location('assets_resource_prepare',HERE/'assets-resource-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,environment,prefix)
    if request_lifetimes:
        assert original_resources
        upload_arguments+=['-DASSETS_OBSERVE_REQUEST_LIFETIMES']
    if original_resource_manager:
        assert request_lifetimes
        spec=importlib.util.spec_from_file_location('assets_resource_manager_prepare',HERE/'assets-resource-manager-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,resource_data=original_resource_data)
    if original_resource_data:
        assert original_resource_manager
        spec=importlib.util.spec_from_file_location('assets_resource_data_prepare',HERE/'assets-resource-data-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,environment,prefix)
    if persistent_tablet:
        spec=importlib.util.spec_from_file_location('assets_tablet_prepare',HERE/'assets-tablet-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        upload_arguments+=prepare.prepare(stage,environment,prefix)
    if original_uploads:
        bundle+='\n'+original(mappings,'void AssetMappingsScriptingInterface::advanceBundle(')
        network=ROOT/'libraries/networking/src'
        for name in ('AssetUpload.h','AssetUpload.cpp'):(stage/name).write_bytes((network/name).read_bytes())
        factories=(network/'AssetClient.cpp').read_text()
        (stage/'AssetsUploadOriginalFactories.inc').write_text('\n'.join(original(factories,signature) for signature in
            ('AssetUpload* AssetClient::createUpload(const QString&','SetMappingRequest* AssetClient::createSetMappingRequest(')))
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            str(stage/'AssetUpload.h'),'-o',str(stage/'AssetUpload-moc.cpp')],check=True,timeout=15,env=environment)
        upload_arguments+=['-DASSETS_ORIGINAL_BUNDLE_UPLOADS',str(stage/'AssetUpload.cpp'),str(stage/'AssetUpload-moc.cpp')]
    (stage/'AssetsBundleOriginals.inc').write_text(bundle)
    moc_definitions=['-DASSETS_ORIGINAL_MAPPING_MODEL','-I'+str(stage)] if original_model else []
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),*moc_definitions,str(HERE/'assets-upload-mappings-host.h'),'-o',str(stage/'upload-moc.cpp')],check=True,timeout=15,env=environment)
    bundle=stage/('feature-assets-'+'a'*32)/'gltf-bundle';(bundle/'mesh').mkdir(parents=True);(bundle/'textures').mkdir()
    for name,data in (('main.gltf',b'actual main bytes'),('mesh/triangle.bin',b'actual mesh bytes'),('textures/checker.png',b'actual texture bytes')):(bundle/name).write_bytes(data)
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),str(ROOT/'libraries/ui/src/FileDialogHelper.h'),'-o',str(stage/'helper-moc.cpp')],check=True,timeout=20,env=environment)
    binary=stage/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-fmax-errors=3','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(stage),'-I'+str(HERE),'-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),
        '-I'+str(ROOT/'libraries/script-engine/src'),'-I'+str(ROOT/'tests/device/native'),'-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
        str(HERE/'assets-controls-native.cpp'),str(ROOT/'libraries/ui/src/FileDialogHelper.cpp'),
        str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),str(stage/'helper-moc.cpp'),str(stage/'upload-moc.cpp'),str(stage/'MappingRequest.cpp'),str(stage/'AssetRequest.cpp'),str(stage/'MappingRequest-moc.cpp'),str(stage/'AssetRequest-moc.cpp'),*upload_arguments,'-o',str(binary),
        '-L'+str(prefix/'usr/lib64'),*flags],check=True,timeout=90,env=environment)
    args=[str(stage/'imports'),str(ROOT/'interface/resources/qml/hifi/dialogs/TabletAssetServer.qml'),str(bundle),str(stage/'originals.json'),str(ROOT)]
    if persistent_tablet:args.append('--persistent-tablet')
    environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_LOGGING_RULES='*.warning=true',QT_FORCE_STDERR_LOGGING='1')
    return binary,environment,args


class AssetsNativeUITests(unittest.TestCase):
    def test_actual_pico_asset_browser_bundle_upload_and_unavailable_selection(self):
        with tempfile.TemporaryDirectory(prefix='pico-assets-native-ui-') as directory:
            stage=Path(directory);binary,environment,args=compile_ui(stage)
            for gate in ([],['--testScript']):
                subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*args,*gate],check=True,timeout=30,env=environment)
            from adapters.pico4.navigation import validate_snapshot
            from adapters.pico4.assets_ui import project
            originals=json.loads((stage/'originals.json').read_text());self.assertGreater(len(originals),50)
            for value in originals:
                validate_snapshot(value,value['processId'],value['updatedEpochMs']);project(value)


if __name__=='__main__':unittest.main()
