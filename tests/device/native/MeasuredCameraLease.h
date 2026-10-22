// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QObject>
#include <QPointer>
#include <QVariantMap>
#include <QUuid>
#include <functional>
#include <cmath>

namespace overte::e2e {
// A subordinate lease of the existing navigation fixture, never avatar input
// or render evidence. Holds only a view captured from the original camera.
class MeasuredCameraLease {
public:
    struct Source {
        QObject* object {nullptr};
        std::function<QVariantMap()> read;
        std::function<void(const QVariantMap&,bool)> apply;
    };
    static bool canPrepare(const Source& camera) {
        if (!camera.object || !camera.read || !camera.apply) { return false; }
        const auto actual=camera.read();return valid(actual) && (actual.value("mode")=="selfie" || actual.value("mode")=="look at");
    }
    bool prepare(const Source& camera) {
        if (_phase!="empty" || !canPrepare(camera)) { return false; }
        _original=camera.read();
        _object=camera.object;_instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        // The containing fixture is destroyed before this camera in normal
        // Application teardown. The weak identity remains authoritative.
        _phase="preparing";_applying=true;camera.apply(_original,true);_applying=false;
        _held=camera.read();
        if (!valid(_held) || _held.value("mode")!="independent" || !sameView(_original,_held)) { _phase="lost";return false; }
        _phase="held";return true;
    }
    // Called by the original Camera::modeUpdated signal. Even changing away
    // and back between observations invalidates authority to restore it.
    void modeChanged() { if (!_applying && _phase=="held") { ++_foreignModeChanges;_phase="lost"; } }
    bool owns(const Source& camera) {
        if (_phase!="held") { return false; }
        if (!_object || camera.object!=_object || !camera.read || !valid(camera.read())
                || camera.read().value("mode")!="independent" || !sameView(camera.read(),_held)) { _phase="lost";return false; }
        return true;
    }
    bool release(const Source& camera) {
        if (_phase=="restored") { return _object && camera.object==_object && camera.read && valid(camera.read())
            && camera.read().value("mode")==_original.value("mode") && sameView(camera.read(),_original); }
        if (!owns(camera) || !camera.apply) { return false; }
        _phase="restoring";_applying=true;camera.apply(_original,false);_applying=false;
        const auto actual=camera.read();
        if (!_object || camera.object!=_object || !valid(actual) || actual.value("mode")!=_original.value("mode") || !sameView(actual,_original)) {
            _phase="lost";return false;
        }
        _phase="restored";return true;
    }
    QVariantMap observe(const Source& camera) {
        if (_phase=="empty") { return {}; }
        if (_phase=="held") { owns(camera); }
        const bool original=_object && camera.object==_object;
        const auto current=original && camera.read ? camera.read() : QVariantMap();
        return {{"measuredCameraLeaseVersion",1},{"instance",_instance},{"phase",_phase},
            {"originalObject",original},{"originalView",_original},{"heldView",_held},{"currentView",current},
            {"foreignModeChanges",_foreignModeChanges}};
    }
    bool restored() const { return _phase=="restored"; }
private:
    static bool valid(const QVariantMap& value) {
        if (value.keys()!=QStringList{"mode","position","projection","rotation"} || value.value("mode").userType()!=QMetaType::QString) { return false; }
        for (const auto& pair:std::initializer_list<std::pair<QString,int>>{{"position",3},{"rotation",4},{"projection",16}}) {
            const auto list=value.value(pair.first).toList();if (list.size()!=pair.second) { return false; }
            for (const auto& item:list) { bool okay=false;const auto number=item.toDouble(&okay);if (!okay || !std::isfinite(number) || std::abs(number)>1e12) { return false; } }
        }
        return true;
    }
    static bool sameView(const QVariantMap& a,const QVariantMap& b) {
        for (const auto& key:QStringList{"position","rotation","projection"}) {
            const auto left=a.value(key).toList(),right=b.value(key).toList();if (left.size()!=right.size()) { return false; }
            for (int index=0;index<left.size();++index) { if (std::abs(left[index].toDouble()-right[index].toDouble())>1e-6) { return false; } }
        }
        return true;
    }
    QPointer<QObject> _object;
    QString _instance,_phase {"empty"};
    QVariantMap _original,_held;
    int _foreignModeChanges {0};bool _applying {false};
};
}
#endif
