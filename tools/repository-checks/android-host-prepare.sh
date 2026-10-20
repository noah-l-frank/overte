#!/usr/bin/env bash
# Trusted host tools only. Never execute candidate installers or prepare an APK.
set -euo pipefail
[[ $# == 1 ]] || { printf 'Expected an external Android host virtualenv path\n' >&2; exit 2; }
android_host_venv="$1"
# Pico's selected catalog compiles real Qt5 WebChannel/JNI and Qt6 QML
# contracts. Read the native PR base first; a push/manual branch is separate
# from refs/pull/.../merge and tags. No candidate installer is executed.
android_host_target="${GITHUB_BASE_REF:-}"
if [[ -z "$android_host_target" && "${GITHUB_REF_TYPE:-}" == branch ]]; then
    android_host_target="${GITHUB_REF_NAME:-}"
fi
if [[ -z "$android_host_target" && "${GITHUB_REF_TYPE:-branch}" == branch && "${GITHUB_REF:-}" == refs/heads/* ]]; then
    android_host_target="${GITHUB_REF#refs/heads/}"
fi
android_pico_qt_ready() {
    local qt5_tools qt5_headers qt6_tools qt6_lib qt6_qml module
    command -v pkg-config >/dev/null || return 1
    pkg-config --exists Qt5Core Qt5Quick Qt5WebChannel Qt5Network Qt6Widgets Qt6Qml Qt6Quick || return 1
    qt5_tools="$(pkg-config --variable=host_bins Qt5Core)" || return 1
    qt5_headers="$(pkg-config --variable=includedir Qt5WebChannel)" || return 1
    qt6_tools="$(pkg-config --variable=libexecdir Qt6Core)" || return 1
    qt6_lib="$(pkg-config --variable=libdir Qt6Core)" || return 1
    qt6_qml="$qt6_lib/qt6/qml"
    [[ -n "$qt5_tools" && -n "$qt5_headers" && -n "$qt6_tools" && -n "$qt6_lib" ]] || return 1
    [[ -x "$qt5_tools/moc" && -x "$qt5_tools/rcc" && -x "$qt6_tools/moc" ]] || return 1
    [[ -r "$qt5_headers/QtWebChannel/QWebChannel" ]] || return 1
    for module in QtQml/libqmlplugin.so QtQml/Models/libmodelsplugin.so \
        QtQml/WorkerScript/libworkerscriptplugin.so QtQuick/libqtquick2plugin.so; do
        [[ -r "$qt6_qml/$module" && -r "${qt6_qml}/${module%/*}/qmldir" ]] || return 1
    done
}
if [[ "$android_host_target" == android-vr-pico ]] && ! android_pico_qt_ready; then
    sudo -n /usr/bin/apt-get -o Acquire::Retries=4 update
    sudo -n /usr/bin/apt-get -o Acquire::Retries=4 install -y --no-install-recommends \
        qtbase5-dev qtbase5-dev-tools qtdeclarative5-dev libqt5webchannel5-dev \
        qt6-base-dev qt6-base-dev-tools qt6-declarative-dev qt6-declarative-dev-tools \
        qml6-module-qtqml qml6-module-qtqml-models qml6-module-qtqml-workerscript qml6-module-qtquick
    android_pico_qt_ready || { printf 'Selected Pico Qt host prerequisites remain unavailable\n' >&2; exit 1; }
fi
python3 -m venv "$android_host_venv"
"$android_host_venv/bin/python" -m pip install --disable-pip-version-check \
    --retries 4 --timeout 30 gcovr==8.4
android_quality_root="$android_host_venv/overte-static-quality"
mkdir -p "$android_quality_root/bin"
python3 -m venv "$android_quality_root/ruff-venv"
printf '%s\n' 'ruff==0.15.22 --hash=sha256:365523eb91d9224e1bcb03b022fbf0facb8f9e23792a2c53d9d4b3924bdbdebb' \
    > "$android_quality_root/requirements.txt"
"$android_quality_root/ruff-venv/bin/python" -m pip install --disable-pip-version-check \
    --require-hashes --only-binary=:all: --no-deps -r "$android_quality_root/requirements.txt"
android_quality_temporary="$(mktemp -d)"
trap 'rm -rf -- "$android_quality_temporary"' EXIT
curl --fail --silent --show-error --location --retry 4 --retry-all-errors \
    --connect-timeout 20 --max-time 300 \
    https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.xz \
    --output "$android_quality_temporary/shellcheck.tar.xz"
printf '%s  %s\n' 8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198 \
    "$android_quality_temporary/shellcheck.tar.xz" | sha256sum --check --status
tar -xJf "$android_quality_temporary/shellcheck.tar.xz" -C "$android_quality_temporary"
install -m 755 "$android_quality_temporary/shellcheck-v0.11.0/shellcheck" "$android_quality_root/bin/shellcheck"
