#!/usr/bin/env python3
"""Device-free contracts for the Pico semantic Tablet-E2E adapter."""

from __future__ import annotations

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]
DEVICE_ROOT = ROOT / "tests/device"
if str(DEVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVICE_ROOT))

from contracts import load_tablet_product_policy  # noqa: E402


APP = ROOT / "android/vr/pico/apps/picoInterface"
BRIDGE = (APP / "e2e/PicoE2eTabletBridge.cpp").read_text(encoding="utf-8")
ADAPTER = (DEVICE_ROOT / "adapters/android/adapter.py").read_text(encoding="utf-8")
POLICY = ROOT / "android/vr/pico/device-tests/pico4-tablet-policy.json"


class PicoTabletE2EAdapterTest(unittest.TestCase):
    def test_original_candidate_binding_and_normal_navigation_flow(self):
        subprocess.run([sys.executable, str(Path(__file__).parent / "device/test_native_execution_binding.py")],
                       check=True, timeout=90)

    def test_actual_navigation_resolver_and_native_qt_input(self):
        self.run_native_ui('navigation')

    def test_actual_snapshot_review_and_native_qt_input(self):
        self.run_native_ui('snapshot')

    def run_native_ui(self, fixture):
        major = os.environ.get("OVERTE_NATIVE_QT_MAJOR", "6")
        if major not in {"5", "6"}:
            raise ValueError("OVERTE_NATIVE_QT_MAJOR must be 5 or 6")
        environment, library_paths = dict(os.environ), []
        if major == "5" and environment.get("OVERTE_QT5_HOST_ROOT"):
            prefix = Path(environment["OVERTE_QT5_HOST_ROOT"]).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),
                PKG_CONFIG_LIBDIR=str(prefix / "usr/lib64/pkgconfig"),
                LD_LIBRARY_PATH=str(prefix / "usr/lib64"),
                QT_PLUGIN_PATH=str(prefix / "usr/lib64/qt5/plugins"),
                QML2_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"),
                QML_IMPORT_PATH=str(prefix / "usr/lib64/qt5/qml"))
            library_paths = ["-L" + str(prefix / "usr/lib64")]
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs",
            *["Qt" + major + module for module in ("Core", "Gui", "Qml", "Quick", "Test")]],
            text=True, env=environment))
        with tempfile.TemporaryDirectory(prefix="overte-pico-navigation-ui-") as directory:
            binary = Path(directory) / "test"
            def original(source, signature):
                start = source.index(signature)
                end = source.index("{", start) + 1
                depth = 1
                while depth:
                    depth += (source[end] == "{") - (source[end] == "}")
                    end += 1
                return source[start:end]
            button = (ROOT / "interface/resources/qml/hifi/tablet/TabletButton.qml").read_text()
            handlers = original(button, "function activate() {") + "\n" + original(button, "    MouseArea {")
            (Path(directory) / "NativeGotoButton.qml").write_text('''import QtQuick 2.12
Item {
 id: tabletButton
 property string text: "GOTO"
 property var tabletRoot: null
 property bool inDebugMode: false
 property bool isActive: false
 property bool isEntered: false
 property bool hoverEnabled: true
 property bool prioritizeTap: false
 property int buttonIndex: 0
 property var gridView: grid
 QtObject { id: grid; property int currentIndex: 0 }
 signal clicked()
 ORIGINAL_HANDLERS
}'''.replace("ORIGINAL_HANDLERS", handlers))
            if fixture == 'snapshot':
                stage = Path(directory)
                production = stage / 'production'
                shutil.copytree(ROOT / 'scripts/system/snapshot', production)
                page = production / 'NativeSnapshotReview.qml'
                page.chmod(0o644)
                page.write_text('import TestSnapshot 1.0\n' + page.read_text())
                shutil.copytree(ROOT / 'interface/resources/qml/controls', stage / 'controls')
                boundary = stage / 'TestSnapshot'; boundary.mkdir()
                (boundary / 'qmldir').write_text('module TestSnapshot\nsingleton Snapshot 1.0 Snapshot.qml\n')
                (boundary / 'Snapshot.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject {'
                    ' property string format: "png"; function getAvailableSnapshotFormats(){return ["png","jpg","webp"]}'
                    ' function getSnapshotFormat(){return format} function setSnapshotFormat(value){format=value}'
                    ' function snapshotFileUrl(path){return ""} }\n')
                (stage / 'ReviewHost.qml').write_text('import QtQuick 2.7\nimport "production"\n'
                    'Item {width:480; height:706; NativeSnapshotReview {anchors.fill:parent} }\n')
            pointer_flags = ["-I" + directory]
            if major == "5":
                surface = (ROOT / "libraries/ui/src/ui/OffscreenQmlSurface.cpp").read_text()
                header = (ROOT / "libraries/ui/src/ui/OffscreenQmlSurface.h").read_text()
                pointer = (ROOT / "libraries/script-engine/src/PointerEvent.cpp").read_text()
                first = header.index("    struct TouchState {")
                last = header.index("std::map<uint32_t, TouchState> _activeTouchPoints;", first)
                state = header[first:last + len("std::map<uint32_t, TouchState> _activeTouchPoints;")]
                context = '''
class OffscreenQmlSurface : public QObject {
public:
    OffscreenQmlSurface(QQuickItem* root, QQuickWindow* window) : root(root), window(window) {}
    QQuickItem* getRootItem() { return root; }
    QQuickWindow* getWindow() { return window; }
    bool isPaused() const { return false; }
    void hoverBeginEvent(const PointerEvent&, QTouchDevice&);
    void hoverEndEvent(const PointerEvent&, QTouchDevice&);
    bool handlePointerEvent(const PointerEvent&, QTouchDevice&, bool release = false);
    QQuickItem* root;
    QQuickWindow* window;
    STATE
};
'''.replace("STATE", state)
                functions = [original(pointer, signature) for signature in (
                    "PointerEvent::PointerEvent(EventType type, uint32_t id) :",
                    "PointerEvent::PointerEvent(EventType type, uint32_t id, const glm::vec2& pos2D, Button button,")]
                functions += [context]
                functions += [original(surface, signature) for signature in (
                    "void OffscreenQmlSurface::hoverBeginEvent(", "void OffscreenQmlSurface::hoverEndEvent(",
                    "bool OffscreenQmlSurface::handlePointerEvent(")]
                functions += [original(BRIDGE, signature) for signature in (
                    "bool effectiveVisible(", "QTouchDevice& bridgeTouchDevice(", "bool sendPointerClick(")]
                (Path(directory) / "actual-pointer-route.inc").write_text("\n".join(functions))
                pointer_flags += ["-DOVERTE_TEST_PICO_SURFACE_POINTER=1",
                                  "-I" + str(ROOT / "libraries/script-engine/src")]
                if environment.get("OVERTE_TEST_GLM_INCLUDE"):
                    glm = Path(environment["OVERTE_TEST_GLM_INCLUDE"]).resolve(strict=True)
                    self.assertTrue((glm / "glm/glm.hpp").is_file())
                    pointer_flags += ["-isystem", str(glm)]
            subprocess.run(["c++", "-std=c++17", "-UNDEBUG", "-fPIC", "-pthread",
                *pointer_flags,
                "-I" + str(ROOT / "libraries/ui/src"), "-I" + str(APP / "e2e"),
                str(APP / "e2e/PicoE2eNavigationUi.cpp"),
                str(ROOT / "libraries/ui/src/ui/NativeFieldInput.cpp"),
                str(Path(__file__).parent / f"device/native/{fixture}-ui-test.cpp"),
                "-o", str(binary), *library_paths, *flags], check=True, timeout=60, env=environment)
            subprocess.run(["unshare", "--user", "--map-root-user", "--net", str(binary), directory],
                check=True, timeout=30, env={**environment, "QT_QPA_PLATFORM": "offscreen",
                    "QT_QUICK_BACKEND": "software", "QT_FORCE_STDERR_LOGGING": "1"})

    def test_product_policy_requires_the_real_vr_surface(self):
        policy = load_tablet_product_policy(POLICY)
        self.assertEqual("pico4.vr", policy["profileId"])
        home = policy["expectations"]["settings.home"]["requiredControlIds"]
        self.assertTrue({
            "settings.audio", "settings.controllers", "settings.general",
            "settings.graphics", "settings.security",
        }.issubset(home))
        self.assertIn(
            "settings.hmd-preferences",
            policy["expectations"]["settings.general"]["requiredControlIds"],
        )
        self.assertIn(
            "settings.vr-render-resolution",
            policy["expectations"]["settings.graphics"]["requiredControlIds"],
        )

    def test_bridge_observes_qml_and_uses_the_vr_surface_pointer_path(self):
        self.assertIn("getTabletRoot()", BRIDGE)
        self.assertIn('property("semanticScreenId")', BRIDGE)
        self.assertIn("bool semanticScreenFound { false };", BRIDGE)
        self.assertIn("else if (!semanticScreenFound)", BRIDGE)
        self.assertIn("visibleControlIds", BRIDGE)
        self.assertIn('property("semanticId")', BRIDGE)
        self.assertIn("item->mapToScene(local)", BRIDGE)
        self.assertIn("getTabletSurface()", BRIDGE)
        self.assertIn("surface->hoverBeginEvent", BRIDGE)
        self.assertIn("surface->handlePointerEvent(press", BRIDGE)
        self.assertIn("surface->handlePointerEvent(release", BRIDGE)
        self.assertIn("surface->hoverEndEvent", BRIDGE)
        self.assertIn("PointerEvent::Press", BRIDGE)
        self.assertIn("PointerEvent::Release", BRIDGE)
        self.assertNotIn("pico4-tablet-policy.json", BRIDGE)
        self.assertNotIn("gotoHomeScreen", BRIDGE)
        self.assertNotIn("loadQMLSource", BRIDGE)

    def test_bridge_is_debug_only_and_app_private(self):
        cmake = (APP / "CMakeLists.txt").read_text(encoding="utf-8")
        setup = (ROOT / "interface/src/Application_Setup.cpp").read_text(encoding="utf-8")
        self.assertIn("if(OVERTE_PICO_E2E_OPENXR_INPUT)", cmake)
        self.assertIn("PicoE2eTabletBridge.cpp", cmake)
        self.assertIn("OVERTE_E2E_OPENXR_INPUT_V1", setup)
        self.assertIn("installTabletBridge(this)", setup)
        self.assertIn("/data/user/0/org.overte.pico/files/overte-e2e", BRIDGE)
        self.assertIn("QFileInfo(PROBE_PATH).canonicalFilePath()", BRIDGE)
        self.assertIn("activeProbe == expectedProbe", BRIDGE)

    def test_adapter_exposes_semantics_only_for_qualified_pico(self):
        capability_block = ADAPTER.split(
            'if self.kind == "pico" and os.environ.get("OVERTE_PICO_OPENXR_INPUT") == "1":',
            1,
        )[1].split("return sorted(values)", 1)[0]
        self.assertIn('"tablet.snapshot"', capability_block)
        self.assertIn('"tablet.activate"', capability_block)
        self.assertIn("validate_tablet_ui_snapshot", ADAPTER)
        self.assertIn("PICO_TABLET_OBSERVATION", ADAPTER)
        self.assertIn("PICO_TABLET_COMMAND", ADAPTER)
        self.assertNotIn("OVERTE_E2E_TABLET_POLICY", ADAPTER)

    def test_visible_navigation_controls_have_single_semantic_names(self):
        home = (ROOT / "interface/resources/qml/hifi/tablet/TabletHome.qml").read_text(
            encoding="utf-8")
        header = (ROOT / "scripts/system/settings/qml/HeaderElement.qml").read_text(
            encoding="utf-8")
        general = (ROOT / "interface/resources/qml/hifi/tablet/TabletGeneralPreferences.qml").read_text(
            encoding="utf-8")
        settings_script = (ROOT / "scripts/system/settings/settings.js").read_text(
            encoding="utf-8")
        self.assertEqual(1, home.count('property string semanticId: "nav.close"'))
        self.assertEqual(1, home.count('objectName: "OverteTabletClose"'))
        self.assertEqual(1, home.count('if ("id" in Accessible)'))
        self.assertEqual(1, home.count("Accessible.id = Qt.binding(function() { return objectName })"))
        self.assertIn('objectName: "nav.home"', header)
        self.assertIn('objectName: "nav.back"', general)
        self.assertIn('event.type === "returnToSettings"', settings_script)


if __name__ == "__main__":
    unittest.main()
