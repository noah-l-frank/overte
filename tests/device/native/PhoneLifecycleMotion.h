// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QJsonObject>
#include <QUuid>
#include <QVariantMap>
#include <cmath>

namespace overte::e2e {
// Samples only from the original application update after real input mapping.
// No command, input ACK or caller-selected drive/position can write this source.
class PhoneLifecycleMotion {
public:
    static PhoneLifecycleMotion& get() { static PhoneLifecycleMotion value;return value; }
    void sample(const QVariantMap& keyboard,const QVariantList& feet,const QVariantList& drive,const QVariantList& raw,bool grounded) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript"))return;
        QMutexLocker lock(&_mutex);const auto epoch=QDateTime::currentMSecsSinceEpoch();
        const auto json=QJsonObject::fromVariantMap(keyboard);const auto pressed=json.value("upPressed").toDouble(-1),channel=json.value("upChannel").toDouble(-1);
        if(!_valid || keyboard.keys()!=QStringList{"keyboardPluginActive","upChannel","upPressed"}
                || keyboard.value("keyboardPluginActive").userType()!=QMetaType::Bool || !vector(feet,1e6) || !vector(drive,1e3) || !vector(raw,1e3)
                || !json.value("upPressed").isDouble() || !std::isfinite(pressed) || pressed<0 || pressed>1
                || !json.value("upChannel").isDouble() || !std::isfinite(channel) || channel<0 || channel>65535 || std::floor(channel)!=channel
                || epoch<=0 || epoch<_epoch) { _valid=false;return; }
        _epoch=epoch;_source={{"phoneLifecycleMotionVersion",1},{"instance",_instance},{"sequence",++_sequence},{"capturedEpochMs",epoch},
            {"keyboardPluginActive",keyboard.value("keyboardPluginActive")},{"upChannel",keyboard.value("upChannel")},{"upPressed",keyboard.value("upPressed")},
            {"feetPosition",feet},{"effectiveDrive",drive},{"rawDrive",raw},{"grounded",grounded}};
    }
    QVariantMap snapshot() const { QMutexLocker lock(&_mutex);return _valid ? _source : QVariantMap(); }
private:
    static bool vector(const QVariantList& value,double bound) {
        if(value.size()!=3)return false;
        for(const auto& item:value) { bool ok=false;const auto number=item.toDouble(&ok);if(!ok || !QJsonValue::fromVariant(item).isDouble() || !std::isfinite(number) || std::abs(number)>bound)return false; }
        return true;
    }
    mutable QMutex _mutex;QVariantMap _source;QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
};
} // namespace overte::e2e
#endif
