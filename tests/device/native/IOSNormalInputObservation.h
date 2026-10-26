// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>

namespace overte::e2e {

// Passive original command reception and return. It changes no UI control,
// dispatches no event and deliberately excludes all login/private input.
class IOSNormalInputObservation {
public:
    enum class Profile { Avatar, Snapshot, Lifecycle, LifecycleNavigation };
    static IOSNormalInputObservation& shared(Profile profile=Profile::Avatar) {
        if (profile==Profile::Snapshot) {static IOSNormalInputObservation snapshot(Profile::Snapshot);return snapshot;}
        if (profile==Profile::Lifecycle) {static IOSNormalInputObservation lifecycle(Profile::Lifecycle);return lifecycle;}
        if (profile==Profile::LifecycleNavigation) {static IOSNormalInputObservation navigation(Profile::LifecycleNavigation);return navigation;}
        static IOSNormalInputObservation value(Profile::Avatar);return value;
    }

    QString received(Profile profile,const QJsonObject& outer,const QString& control,const QJsonObject& root) {
        QMutexLocker locker(&_mutex);
        if (profile!=_profile) { return {}; }
        const auto input=outer.value("input").toObject();
        if (profile==Profile::Snapshot) {
            if (root.isEmpty() || !QRegularExpression("\\Asnapshot\\.(name|mode|format|capture|cancel|export-cancel|upload-cancel|(?:save|share|upload)\\.[0-7])\\z").match(control).hasMatch()) {return {};}
            // This passive source must not retain foreign/private text even
            // when the ordinary input handler would subsequently reject it.
            const auto operation=input.value("operation").toString();
            if (operation=="replace") {
                if (control!="snapshot.name" || !input.value("text").isString()) {return {};}
                const auto text=input.value("text").toString();
                if (!text.isEmpty() && !QRegularExpression("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\\z").match(text).hasMatch()) {return {};}
            } else if (operation!="activate") {return {};}
        } else if (profile==Profile::Lifecycle) {
            if (root.isEmpty() || (control!="lifecycle.create.text" && control!="lifecycle.scripts.filter"
                    && control!="chat.input" && control!="tablet.back")) {return {};}
            const auto operation=input.value("operation").toString();const auto keys=input.keys();
            QSet<QString> expected{"schemaVersion","commandId","instance","sequence","observedElapsedMs","fieldToken","operation"};
            if (operation=="replace") {
                expected.insert("text");
                const auto prefix=control=="lifecycle.create.text" ? QStringLiteral("Overte ä Ω 東京 ")
                    : control=="chat.input" ? QStringLiteral("reply-") : QStringLiteral("retry-");
                const auto text=input.value("text").toString();
                if (control=="tablet.back" || !input.value("text").isString() || text.size()>128
                        || (!text.isEmpty() && !QRegularExpression("\\A"+QRegularExpression::escape(prefix)+"[a-f0-9]{32}\\z").match(text).hasMatch())) {return {};}
            } else if (operation!="activate") {return {};}
            if (QSet<QString>(keys.begin(),keys.end())!=expected || input.value("schemaVersion")!=QJsonValue(1)) {return {};}
        } else if (profile==Profile::LifecycleNavigation) {
            const auto keys=input.keys();
            const QSet<QString> expected{"schemaVersion","commandId","instance","sequence","observedElapsedMs","fieldToken","operation"};
            if (root.isEmpty() || input.value("operation")!=QJsonValue("activate") || input.value("schemaVersion")!=QJsonValue(1)
                    || QSet<QString>(keys.begin(),keys.end())!=expected
                    || (!QStringList{"hud.tablet","tablet.home","tablet.close","create.entry","chat.entry","scripts.entry",
                        "scripts.menu","scripts.menu-edit","scripts.menu-running"}.contains(control)
                        && !QRegularExpression("\\Atablet\\.page\\.([1-9]|[12][0-9]|3[0-2])\\z").match(control).hasMatch())) {return {};}
        } else {
            if (!control.startsWith("avatar.") && !control.startsWith("people.")
                && control!="tablet.home" && !control.startsWith("tablet.page.")) { return {}; }
            if ((control=="tablet.home" || control.startsWith("tablet.page.")) && root.isEmpty()) { return {}; }
        }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
        QJsonObject details{{"outerCommandId",outer.value("commandId")},{"command",input},
            {"controlId",control},{"root",root.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(root)}};
        if (!append(id,"received",details)) { return {}; }
        return id;
    }

    void returned(const QString& id,const QJsonObject& originalReceipt) {
        if (id.isEmpty()) { return; }QMutexLocker locker(&_mutex);
        append(id,"returned",originalReceipt);
    }

    QJsonObject observation(Profile profile,const QString& request,const QString& run) {
        QMutexLocker locker(&_mutex);const auto before=clock();
        if (profile!=_profile) { return {}; }
        QJsonObject source{{"complete",_complete},{"events",_events}};
        return QJsonObject{{"iosNormalInputsVersion",1},{"profile",profile==Profile::Snapshot ? "snapshot" : profile==Profile::Lifecycle ? "lifecycle" : profile==Profile::LifecycleNavigation ? "lifecycle-navigation" : "avatar"},{"requestId",request},{"runId",run},{"instance",_instance},
            {"sequence",static_cast<double>(++_sequence)},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"clockDomain","native-process-normal-inputs"},{"clockBefore",before},{"clockAfter",clock()},{"source",source}};
    }

private:
    explicit IOSNormalInputObservation(Profile profile) : _profile(profile),_instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) { _clock.start(); }
    QJsonObject clock() const {
        return QJsonObject{{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"monotonicMs",static_cast<double>(_clock.elapsed())}};
    }
    bool append(const QString& id,const QString& kind,const QJsonObject& details) {
        if (!_complete) { return false; }
        QJsonObject row{{"sequence",static_cast<double>(_events.size()+1)},{"eventId",QUuid::createUuid().toString(QUuid::WithoutBraces)},
            {"inputId",id},{"kind",kind},{"clock",clock()},{"details",details}};
        const auto bytes=QJsonDocument(row).toJson(QJsonDocument::Compact).size();
        if (_events.size()>=512 || _bytes+bytes>524288) { _complete=false;return false; }
        _bytes+=bytes;_events.append(row);return true;
    }
    QMutex _mutex;
    const Profile _profile;
    QElapsedTimer _clock;
    QString _instance;
    QJsonArray _events;
    int _bytes {0};
    quint64 _sequence {0};
    bool _complete {true};
};
} // namespace overte::e2e
#endif
