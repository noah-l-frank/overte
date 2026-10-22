"""Parent-owned Android CI dependency intent; never imports product child source."""
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

_recipe = Path(__file__).resolve().parents[3] / "android/common/conan/conanfile-pico.py"
_spec = importlib.util.spec_from_file_location("android_ci_common_recipe", _recipe)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class AndroidCiTarget(_module.PicoOverte):
    name = "OverteAndroidCiTarget"
    # Intentionally match the qualified producer recipe, not an obsolete lock.
    # Exact settings/options/package/edge provenance remains independently checked.
    qt_ref = "qt/5.15.18-2026.01.04@overte/stable#4fd1f62ee1914f2f3ec4fe298a07c283"
    openexr_ref = "openexr/3.2.12"
    default_options = dict(_module.PicoOverte.default_options)
    default_options.update({"qt*:qtwebengine": False, "qt*:with_mysql": False,
                            "qt*:with_odbc": False, "qt*:with_openal": False,
                            "qt*:with_pq": False})

    def build_requirements(self):
        self.tool_requires(self.qt_ref, run=True)
        self.tool_requires("glslang/1.4.350.0", run=True)
        self.tool_requires("scribe/2019.02@overte/stable", run=True)
        self.tool_requires("spirv-cross/1.4.350.0", run=True)
        self.tool_requires("spirv-tools/1.4.350.0", run=True)
