"""Execute the production close handler for each tablet platform variant."""
from pathlib import Path
import os
import subprocess
import shlex
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
# The shared/Android layer retains its Android presenter member; the iOS
# product extends that API. Bind the fixture to the actual declared member.
HEADER = (ROOT / "libraries/ui/src/ui/TabletScriptingInterface.h").read_text()
SCREEN_SPACE_MEMBER = "_screenSpaceMode" if "bool _screenSpaceMode" in HEADER else "_androidScreenSpaceMode"


def platforms(method):
    result = ["ANDROID_APP_PHONE_INTERFACE"]
    if "defined(Q_OS_IOS)" in method:
        result.append("Q_OS_IOS")
    return result


class TabletClose(unittest.TestCase):
    def test_home_cleanup_keeps_closed_tablet_hidden(self):
        source = (ROOT / "libraries/ui/src/ui/TabletScriptingInterface.cpp").read_text()
        start = source.index("void TabletProxy::loadHomeScreen(bool forceOntoHomeScreen) {")
        end = source.index("\n}\n", start) + 2
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True))
        fixture = Path(__file__).with_name("tablet-home-visibility-test.cpp")
        qt_libexec = subprocess.check_output(
            ["pkg-config", "--variable=libexecdir", "Qt6Core"], text=True).strip()
        with tempfile.TemporaryDirectory(prefix="overte-tablet-home-") as directory:
            directory = Path(directory)
            (directory / "production.inc").write_text(source[start:end])
            subprocess.run([str(Path(qt_libexec) / "moc"), str(fixture),
                            "-o", str(directory / "tablet-home-visibility-test.moc")],
                           check=True, timeout=10)
            for platform in platforms(source[start:end]):
                with self.subTest(platform=platform):
                    binary = directory / platform
                    subprocess.run(["c++", "-std=c++17", "-fPIC", f"-D{platform}",
                                    f"-DOVERTE_TABLET_SCREEN_SPACE_MEMBER={SCREEN_SPACE_MEMBER}",
                                    "-I", str(directory), str(fixture), "-o", str(binary),
                                    *flags], check=True, timeout=30)
                    subprocess.run([str(binary)], check=True, timeout=5)

    def test_native_close_route(self):
        source = (ROOT / "libraries/ui/src/ui/TabletScriptingInterface.cpp").read_text()
        start = source.index("void TabletProxy::desktopWindowClosed() {")
        end = source.index("\n}\n", start) + 2
        method = source[start:end]
        # Service boundaries record which route the unchanged production
        # handler selects. Full WindowRoot behavior is covered by Qt Quick.
        fixture = """
class TabletProxy {
public:
    bool OVERTE_TABLET_SCREEN_SPACE_MEMBER = false;
    int homes = 0, closes = 0;
    void gotoHomeScreen() { ++homes; }
    void hideAndroidTablet() { ++closes; }
    void desktopWindowClosed();
};
""" + method + """
int main() {
    TabletProxy desktop;
    desktop.desktopWindowClosed();
    if (desktop.homes != 1 || desktop.closes != 0) return 1;
#if defined(ANDROID_APP_PHONE_INTERFACE) || defined(Q_OS_IOS)
    TabletProxy touch;
    touch.OVERTE_TABLET_SCREEN_SPACE_MEMBER = true;
    touch.desktopWindowClosed();
    if (touch.homes != 0 || touch.closes != 1) return 2;
#endif
}
"""
        with tempfile.TemporaryDirectory(prefix="overte-tablet-close-") as directory:
            cpp = Path(directory) / "close.cpp"
            cpp.write_text(fixture)
            for platform in ["DESKTOP_TEST", *platforms(method)]:
                with self.subTest(platform=platform):
                    binary = Path(directory) / platform
                    subprocess.run(["c++", "-std=c++17", f"-D{platform}",
                                    f"-DOVERTE_TABLET_SCREEN_SPACE_MEMBER={SCREEN_SPACE_MEMBER}", str(cpp),
                                    "-o", str(binary)], check=True, timeout=30)
                    subprocess.run([str(binary)], check=True, timeout=5)


class NativeFieldInputTests(unittest.TestCase):
    def test_actual_focused_field_keyboard_and_ime_events(self):
        major = os.environ.get("OVERTE_NATIVE_QT_MAJOR", "6")
        if major not in {"5", "6"}:
            raise ValueError("OVERTE_NATIVE_QT_MAJOR must be 5 or 6")
        environment = dict(os.environ)
        library_paths = []
        if major == "5" and environment.get("OVERTE_QT5_HOST_ROOT"):
            prefix = Path(environment["OVERTE_QT5_HOST_ROOT"]).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),
                PKG_CONFIG_LIBDIR=str(prefix / "usr/lib64/pkgconfig"),
                LD_LIBRARY_PATH=str(prefix / "usr/lib64"),
                QT_PLUGIN_PATH=str(prefix / "usr/lib64/qt5/plugins"),
                QML2_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"),
                QML_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"))
            # Fedora's Qt 5 pkg-config files omit the default /usr/lib64
            # search flag; the relocated SDK needs its actual library path.
            library_paths = ["-L" + str(prefix / "usr/lib64")]
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs",
            "Qt" + major + "Core", "Qt" + major + "Gui", "Qt" + major + "Qml",
            "Qt" + major + "Quick", "Qt" + major + "Test"], text=True, env=environment))
        here = Path(__file__).parent
        native = ROOT / "libraries/ui/src/ui"
        with tempfile.TemporaryDirectory(prefix="overte-native-field-input-") as temporary:
            binary = Path(temporary) / "test"
            source = (ROOT / "interface/resources/qml/hifi/tablet/TabletHome.qml").read_text()
            marker = source.index('objectName: "tabletPage."')
            start = source.rfind("MouseArea {", 0, marker)
            end, depth = start + len("MouseArea {"), 1
            while depth:
                depth += (source[end] == "{") - (source[end] == "}")
                end += 1
            # Keep the actual pointer/accessibility/key handlers intact; only
            # their surrounding presentation/model boundary is controlled.
            pager = Path(temporary) / "pager.qml"
            pager.write_text('''import QtQuick 2.12
import QtQuick.Controls 2.5
Item {
 id: root; width: 640; height: 260
 property bool directTouch: false
 readonly property int currentPage: swipeView.currentIndex
 QtObject { id: presentation; property int minimumTouchTarget: 60; property bool touchOptimized: root.directTouch }
 QtObject { id: pageIndicator; property int currentIndex: swipeView.currentIndex }
 SwipeView { id: swipeView; x: 10; y: 0; width: 200; height: 80; Item {} Item {} }
 Row { x: 10; y: 120
  Repeater { model: 2
   Item { width: 60; height: 60; property bool isHovered: false; ORIGINAL }
  }
 }
}'''.replace("ORIGINAL", source[start:end]))
            subprocess.run(["c++", "-std=c++17", "-fPIC", "-UNDEBUG", "-pthread",
                "-I" + str(native), str(native / "NativeFieldInput.cpp"),
                str(here / "native-field-input-test.cpp"), "-o", str(binary), *library_paths, *flags],
                check=True, timeout=60, env=environment)
            subprocess.run(["unshare", "--user", "--map-root-user", "--net", str(binary), str(pager)],
                check=True, timeout=30, env={**environment, "QT_QPA_PLATFORM": "offscreen",
                                            "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1"})


if __name__ == "__main__":
    unittest.main()
