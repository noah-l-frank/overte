"""Run the native close-frame calculation against the real shared QML footer.

UIKit rectangle operations are mapped to Qt rectangles on the host. This checks
both shipping selection/geometry and the actual E2E input core against the real
shared QML footer, not UIKit event delivery or device acceptance.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "ios/ui/IOSTouchUiMetrics.mm").read_text()
# Select the actual shipping branch before extracting its frame expression.
# Cutting the unpreprocessed first activation block can strand an E2E #if.
# Includes alone are omitted for preprocessing; all extracted native logic is
# kept, and the E2E core is compiled/exercised separately below on the same QML.
source = subprocess.run(['c++', '-E', '-P', '-x', 'c++', '-', '-DQ_OS_IOS=1'],
    input=re.sub(r'^\s*#(?:include|import)\s+.*$', '', source, flags=re.MULTILINE),
    capture_output=True, text=True, check=True, timeout=10).stdout


def function(signature):
    start = source.index(signature)
    cursor = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


functions = [function(signature) for signature in (
    "bool visibleTabletItem(", "CGRect tabletItemFrame(",
    "QList<QQuickItem*> tabletVisualItems(")]
if "QQuickItem* tabletCloseControl(" in source:
    functions.append(function("QQuickItem* tabletCloseControl("))
start = source.index('hint = @"Return to the world controls";') + len(
    'hint = @"Return to the world controls";')
end = source.index("activationHandler = ^BOOL", start)
frame_calculation = source[start:end].replace("safeBounds.size.width", "safeBounds.width()")
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "Qt6Core", "Qt6Gui", "Qt6Qml", "Qt6Quick", "Qt6Test"], text=True))
with tempfile.TemporaryDirectory(prefix="overte-close-hit-target-") as scratch:
    scratch = Path(scratch)
    (scratch / "production.inc").write_text("\n".join(functions) + """
CGRect nativeCloseFrame(QQuickItem* root, CGRect safeBounds) {
    struct Tablet { QQuickItem* root; QQuickItem* getIOSTabletRoot() { return root; } } instance {root};
    auto* tablet = &instance;
    CGRect controlFrame;
""" + frame_calculation + "\nreturn controlFrame;\n}\n")
    fixture = scratch / "footer.qml"
    fixture.write_text('''import QtQuick 2.12
import "''' + (ROOT / "interface/resources/qml/hifi/tablet").as_uri() + '''" as TabletUi
Item {
    width: 768; height: 900
    property int homes: 0
    property int closes: 0
    property real footerScale: 1
    property real bottomInset: 0
    TabletUi.TabletNavigation {
        objectName: "footer"
        anchors.bottom: parent.bottom
        anchors.bottomMargin: parent.bottomInset
        width: parent.width
        contentScale: parent.footerScale
        onHomeRequested: parent.homes++
        onCloseRequested: parent.closes++
    }
}''')
    binary = scratch / "test"
    subprocess.run(["c++", "-std=c++17", "-fPIC", "-I", str(scratch),
                    '-I' + str(ROOT / 'ios/ui'), '-I' + str(ROOT / 'libraries/ui/src'),
                    str(ROOT / 'ios/ui/IOSNormalUiInput.cpp'),
                    str(ROOT / 'libraries/ui/src/ui/NativeFieldInput.cpp'),
                    str(Path(__file__).with_suffix(".cpp")), "-o", str(binary),
                    *flags], check=True, timeout=60)
    subprocess.run([str(binary), str(ROOT), str(fixture)], check=True, timeout=30,
                   env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"})
