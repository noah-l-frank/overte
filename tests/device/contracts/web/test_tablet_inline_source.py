# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile the actual native tablet source with real Qt/QML/Quick lifetimes."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


def complete_block(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class TabletInlineSource(unittest.TestCase):
    def test_actual_native_source_and_page_lifetimes(self):
        major = os.environ.get("OVERTE_INLINE_QT_MAJOR", "6")
        environment = os.environ | {"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"}
        libraries = []
        if major == "5":
            prefix = Path(os.environ.get("OVERTE_QT5_ROOT", str(Path.home() / ".local/overte-qt5/root")))
            if (prefix / "usr/lib64/pkgconfig/Qt5Core.pc").is_file():
                environment.update(PKG_CONFIG_PATH=str(prefix / "usr/lib64/pkgconfig"),
                    PKG_CONFIG_SYSROOT_DIR=str(prefix), LD_LIBRARY_PATH=str(prefix / "usr/lib64"),
                    QT_PLUGIN_PATH=str(prefix / "usr/lib64/qt5/plugins"),
                    QML2_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"))
                libraries = ["-L" + str(prefix / "usr/lib64")]
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs",
            *["Qt" + major + name for name in ("Core", "Gui", "Qml", "Quick")]], env=environment, text=True))
        variable = "host_bins" if major == "5" else "libexecdir"
        moc = Path(subprocess.check_output(["pkg-config", "--variable=" + variable, "Qt" + major + "Core"],
                                          env=environment, text=True).strip()) / "moc"
        if not moc.is_file() and environment.get("PKG_CONFIG_SYSROOT_DIR"):
            moc = Path(environment["PKG_CONFIG_SYSROOT_DIR"]) / str(moc).lstrip("/")
        ui = ROOT / "libraries/ui/src/ui"
        with tempfile.TemporaryDirectory(prefix="overte-tablet-inline-") as temporary:
            stage = Path(temporary)
            tablet = (ui / "TabletScriptingInterface.cpp").read_text()
            (stage / "production-tablet-native-loader.inc").write_text(complete_block(
                tablet, "void TabletProxy::loadHTMLSourceOnTopImpl("))
            # Copy complete production callers and aliases. Only unrelated
            # application services/window decoration and the OS browser are
            # bounded substitutes; no tablet navigation method is extracted.
            qmlroot = ROOT / "interface/resources/qml"
            for name in ("hifi/tablet/TabletRoot.qml", "hifi/tablet/WindowRoot.qml",
                         "hifi/tablet/TabletWebView.qml", "hifi/tablet/BlocksWebView.qml",
                         "hifi/tablet/TabletPageLoader.qml", "hifi/tablet/TabletPageStatus.qml",
                         "controls/EmbeddedWebView.qml", "controls/NativeFlickableWebViewCore.qml",
                         "controls/FlickableWebViewCore.qml", "controls/TabletWebView.qml",
                         "controls/TabletWebScreen.qml", "controls/TabletWebButton.qml",
                         "controls/WebView.qml", "Web3DSurface.qml"):
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(qmlroot / name, target)
            modules = {
                "controlsUit": ("Keyboard", "Key", "TouchUiMetrics", "TouchUiProfileBase", "TouchUiProfile"),
                "stylesUit": ("HifiConstants", "RalewaySemiBold"),
                "styles": ("HifiConstants",),
            }
            for module, names in modules.items():
                directory = stage / module
                directory.mkdir(exist_ok=True)
                for name in names:
                    shutil.copy2(qmlroot / module / (name + ".qml"), directory)
                (directory / "qmldir").write_text("module " + module + "\n" + "".join(
                    name + " 1.0 " + name + ".qml\n" for name in names))
            fixtures = {
                "controls/EmbeddedWebBackend.qml": '''import QtQuick 2.7
                    import TestNative 1.0
                    NativeEndpoint {
                        objectName: "native-endpoint"
                        property string userAgent: ""
                        property bool useBackground: true
                        property string eventBridgeJavaScript: ""
                        property string surface: "tablet"
                        readonly property string currentUrl: url
                        readonly property bool loading: false
                        readonly property bool canGoBack: false
                        readonly property bool canGoForward: false
                        readonly property string error: ""
                        readonly property string warning: ""
                        readonly property bool bridgeAvailable: false
                        signal webEventReceived(var message)
                        signal nativeClosed()
                        function emitScriptEvent(message) { return false; }
                        function runJavaScript(source, callback) { return false; }
                        function openNative() { return false; }
                        function goBack() { return false; }
                        function goForward() { return false; }
                        function reload() { return false; }
                        function reloadAndBypassCache() { return false; }
                        function stop() {}
                        function unfocus() {}
                    }''',
                "controlsUit/TouchUiProfile.qml": '''import QtQuick 2.7
                    TouchUiProfileBase { systemImeAvailable: true }''',
                "Hifi/SoundEffect.qml": '''import QtQuick 2.7
                    QtObject { property real volume: 0; property url source
                               function play(position) {} }''',
                "TabletScriptingInterface/TabletSurfaceGeometry.qml": '''import QtQuick 2.7
                    QtObject { property var profile; property bool valid: true
                        property real x: 0; property real y: 0
                        property real width: 480; property real height: 706 }''',
                "hifi/tablet/TabletNavigation.qml": '''import QtQuick 2.7
                    Item { property bool shown: false; property real contentScale: 1
                        property bool backVisible: true; signal backRequested()
                        signal homeRequested(); signal closeRequested() }''',
                "windows/ScrollingWindow.qml": '''import QtQuick 2.7
                    Item {
                        default property alias contentData: content.data
                        property bool shown: false
                        property bool resizable: false
                        property bool closable: true
                        property bool pinnable: false
                        property bool alwaysOnTop: false
                        property bool contentFlickableInteractive: false
                        property Item footer
                        property alias frame: decoration
                        property alias pane: content
                        function setShown(value) { shown = value; }
                        Item { id: decoration }
                        Item { id: content; anchors.fill: parent
                            property real scrollHeight: 706
                            property real contentWidth: 480 }
                    }''',
                "dialogs/TabletQueryDialog.qml": "import QtQuick 2.7\nItem {}",
                "dialogs/TabletMessageBox.qml": "import QtQuick 2.7\nItem {}",
                "hifi/tablet/TabletHome.qml": "import QtQuick 2.7\nItem {}",
            }
            for name, text in fixtures.items():
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text)
            for module, names in {"Hifi": ("SoundEffect",),
                                  "TabletScriptingInterface": ("TabletSurfaceGeometry",)}.items():
                (stage / module / "qmldir").write_text("module " + module + "\n" + "".join(
                    name + " 1.0 " + name + ".qml\n" for name in names))
            fixture_moc = stage / "tablet-inline-source-test.moc"
            subprocess.run([str(moc), str(Path(__file__).with_name("tablet-inline-source-test.cpp")),
                            "-o", str(fixture_moc)], env=environment, check=True, timeout=30)
            generated = stage / "moc.cpp"
            subprocess.run([str(moc), str(ui / "NativeInlineHtmlSource.h"), "-o", str(generated)],
                           env=environment, check=True, timeout=30)
            binary = stage / "tablet-source"
            subprocess.run(["c++", "-std=c++17", "-fPIC", "-UNDEBUG", "-Wall", "-Wextra", "-Werror",
                "-I" + str(ROOT / "libraries/shared/src"), "-I" + str(ui), "-I" + str(stage),
                str(ui / "NativeInlineHtmlSource.cpp"), str(generated),
                str(Path(__file__).with_name("tablet-inline-source-test.cpp")), "-o", str(binary),
                *libraries, *flags], env=environment, check=True, timeout=60)
            subprocess.run([str(binary), str(stage)], env=environment, check=True, timeout=20)


if __name__ == "__main__":
    unittest.main()
