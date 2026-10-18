#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the selected production World Loader's authored URL classifier."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
root = Path(__file__).resolve().parents[4]
runner = shutil.which(os.environ.get('OVERTE_QML_TEST_RUNNER', 'qmltestrunner'))
if not runner:
    raise SystemExit('Qt Quick Test is required')
with tempfile.TemporaryDirectory(prefix='overte-world-inline-dispatch-') as temporary:
    stage = Path(temporary)
    shutil.copy2(root / 'interface/resources/qml/+android_interface/Web3DSurface.qml', stage)
    # Loader destination observation boundary: dispatch runs unchanged production QML.
    (stage / 'Web3DSurfaceAndroid.qml').write_text('import QtQuick 2.7\nItem { property string url; property string scriptUrl; property bool useBackground; property string userAgent }\n')
    (stage / 'ActualDocument.qml').write_text('import QtQuick 2.7\nItem { property bool actualDocument: true }\n')
    (stage / 'tst_world_dispatch.qml').write_text('''import QtQuick 2.7
import QtTest 1.2
TestCase {
    name: "WorldSourceDispatch"
    Component { id: factory; Web3DSurface {} }
    function test_inline_data() {
        var values = ["data:text/html,<p>literal.qml", "DATA:text/html,<p>literal.qml#fragment", "data:text/html;charset=UTF-8,<p>.qml?x"];
        for (var i=0;i<values.length;++i) {
            var item = createTemporaryObject(factory, this, {url: values[i]});
            verify(item !== null); verify(item.webViewLoaded); verify(item.item !== null);
            compare(item.item.url, values[i]);
        }
    }
    function test_authored_qml() {
        var item = createTemporaryObject(factory, this, {url: Qt.resolvedUrl("ActualDocument.qml")});
        verify(item !== null); compare(item.webViewLoaded, false);
        verify(item.item.actualDocument);
    }
}
''')
    subprocess.run([runner, '-input', str(stage)], check=True, timeout=60,
                   env=os.environ | {'QT_QPA_PLATFORM':'offscreen', 'QT_QUICK_BACKEND':'software'})
