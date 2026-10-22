// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "AudioSettingsQueue.h"
#include <QCoreApplication>
#include <QDateTime>
#include <QHash>
#include <QMap>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <cmath>

namespace overte::e2e {
inline bool audioSettingsCommand(const QVariantMap& command) {
    const auto keys=command.keys();
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
        && (command.value("schemaVersion").userType()==QMetaType::Int || command.value("schemaVersion").userType()==QMetaType::Double)
        && command.value("schemaVersion").toDouble()==1
        && command.value("action").userType()==QMetaType::QString && command.value("action").toString()=="feature-audio-settings-observe"
        && command.value("commandId").userType()==QMetaType::QString && command.value("runId").userType()==QMetaType::QString
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(command.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(command.value("runId").toString()).hasMatch();
}

inline QStringList audioSettingsBooleans() {
    return {"muted","mutedDesktop","mutedHMD","pushToTalkDesktop","pushToTalkHMD","noiseReduction",
        "noiseReductionAutomatic","warnWhenMuted","acousticEchoCancellation"};
}
inline QStringList audioSettingsNumbers() {
    return {"noiseReductionThreshold","inputVolume","localInjectorGain",
        "systemInjectorGain","pushingToTalkOutputGainDesktop"};
}
inline QVariantMap audioSettingsProperties(QObject* original) {
    if (!original || original->thread()!=QThread::currentThread()) { return {}; }
    QVariantMap result;
    for (const auto& name:audioSettingsBooleans()) {
        const auto value=original->property(name.toUtf8().constData());
        if (value.userType()!=QMetaType::Bool) { return {}; } result.insert(name,value);
    }
    for (const auto& name:audioSettingsNumbers()) {
        const auto value=original->property(name.toUtf8().constData());
        if ((value.userType()!=QMetaType::Float && value.userType()!=QMetaType::Double)
                || !std::isfinite(value.toDouble()) || std::abs(value.toDouble())>1000000) { return {}; }
        result.insert(name,value);
    }
    const auto context=original->property("context");
    if (context.userType()!=QMetaType::QString || (context.toString()!="VR" && context.toString()!="Desktop")) { return {}; }
    result.insert("context",context);return result;
}

// An original role is never rebound after destruction/replacement. These weak
// IDs identify actual objects; no first-read time is called a creation time.
class AudioSettingsObservation {
public:
    bool admit(const QVariantMap& command) {
        if (!enabled() || !_valid || !audioSettingsCommand(command) || _requests.size()>=4096
                || _requests.contains(command.value("commandId").toString())
                || (!_run.isEmpty() && _run!=command.value("runId").toString())) { return false; }
        _run=command.value("runId").toString();_requests.insert(command.value("commandId").toString());return true;
    }
    QVariantMap snapshot(const QVariantMap& command,const QMap<QString,QPointer<QObject>>& roles,const QVariantMap& source) {
        if (!enabled() || !_valid || !audioSettingsCommand(command) || command.value("runId")!=_run
                || !_requests.contains(command.value("commandId").toString()) || _published.contains(command.value("commandId").toString())
                || _sequence>=9007199254740991ULL || roles.keys()!=QStringList{"client","devices","input","nodes","script"}) { return {}; }
        QSet<QObject*> distinct;QVariantMap ids;
        for (auto role=roles.begin();role!=roles.end();++role) {
            if (!role.value() || distinct.contains(role.value().data())) { _valid=false;return {}; } distinct.insert(role.value().data());
            if (_objects.contains(role.key())) {
                if (!_objects.value(role.key()) || _objects.value(role.key())!=role.value()) { _valid=false;return {}; }
            } else { _objects.insert(role.key(),role.value());_ids.insert(role.key(),nonce()); }
            ids.insert(role.key()+"Id",_ids.value(role.key()));
        }
        auto result=source;
        for (auto entry=ids.begin();entry!=ids.end();++entry) { result.insert(entry.key(),entry.value()); }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<=0 || now<_epoch || source.isEmpty()) { _valid=false;return {}; } _epoch=now;
        _published.insert(command.value("commandId").toString());
        return {{"audioSettingsVersion",2},{"commandId",command.value("commandId")},{"runId",_run},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",now},{"source",result}};
    }
private:
    bool enabled() const { return QCoreApplication::instance() && QThread::currentThread()==_thread
        && QCoreApplication::arguments().contains("--testScript"); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    QMap<QString,QPointer<QObject>> _objects;QMap<QString,QString> _ids;QSet<QString> _requests,_published;
    QString _instance{nonce()},_run;quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
    QThread* _thread{QThread::currentThread()};
};
} // namespace overte::e2e
#endif
