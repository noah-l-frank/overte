"""Pico-owned CI dependency intent extending the Android parent's CI contract."""
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

_recipe = Path(__file__).resolve().parents[4] / "android/common/native-ci/target.conanfile.py"
_spec = importlib.util.spec_from_file_location("pico_ci_parent_recipe", _recipe)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


class PicoCiTarget(_module.AndroidCiTarget):
    name = "OvertePicoCiTarget"
