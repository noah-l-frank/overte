// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NormalLoginControls.h"
#include <AccountManager.h>
#include <DependencyManager.h>
#include <MetaverseAPI.h>
#include <NetworkingConstants.h>
#include <SettingHandle.h>
#include <QProcessEnvironment>
#include <QSet>
#include <QUuid>

namespace overte::e2e {
// Passive original endpoint/account/settings and original login-field source.
// Reads do not log out, update auth, create UI, reload settings or write them.
class NavigationEnvironmentObservation {
public:
    void observe(const QJsonObject& frame,QQuickItem* server,QQuickItem* page) {
        if (!enabled()) { return; }
        _frame=frame;_server=server;_page=page;
    }
    QVariantMap snapshot(const QVariantMap& request) {
        const auto object=QJsonObject::fromVariantMap(request);const auto keys=object.keys();
        if (!enabled() || !_valid || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!=QJsonValue("feature-navigation-environment")
                || !object.value("commandId").isString() || !identifier(object.value("commandId").toString())
                || !object.value("runId").isString() || !identifier(object.value("runId").toString())
                || _requests.size()>=4096 || _requests.contains(object.value("commandId").toString())) { return {}; }
        const auto now=QDateTime::currentMSecsSinceEpoch();
        const auto frameEpoch=static_cast<qint64>(_frame.value("updatedEpochMs").toDouble());
        if (now<=0 || now<_epoch) { _valid=false;return {}; }
        if (!frameEpoch || now<frameEpoch || now-frameEpoch>1500 || !_frame.value("ready").toBool()) { return {}; }
        const auto account=DependencyManager::get<AccountManager>();
        if (!account || account->thread()!=QThread::currentThread()) { return {}; }
        const auto originalAccount=account->featureAccountObservation();
        if (originalAccount.isEmpty()) { return {}; }
        Settings settings;
        const auto selected=settings.value("private/selectedMetaverseURL",NetworkingConstants::METAVERSE_SERVER_URL_STABLE);
        const auto selectedUrl=selected.toUrl();const auto effective=MetaverseAPI::getCurrentMetaverseServerURL();
        if (!selectedUrl.isValid() || selectedUrl.isRelative() || !effective.isValid() || effective.isRelative()) { return {}; }
        QJsonObject other;
        for (const auto& key:{"placesAppPinnedMetaverse","placesAppMetaverseToFetch","placesAppMaturityFilter"}) {
            other[key]=QJsonObject{{"present",settings.contains(key)},{"value",QJsonValue::fromVariant(settings.value(key))}};
        }
        QVariant draft,passwordEmpty;
        if (_page) {
            auto password=uniqueLoginItem(_page,{"passwordField"});
            if (!password || password->property("text").userType()!=QMetaType::QString) { return {}; }
            passwordEmpty=password->property("text").toString().isEmpty();
        }
        if (_server) {
            if (!loginGuiItem(_server) || genericLoginControlId(_server)!="login.server"
                    || !_page || genericLoginRoot(_server)!=_page || _server->property("text").userType()!=QMetaType::QString) { return {}; }
            const auto text=_server->property("text").toString();
            if (text.size()>4096) { return {}; }draft=loginEndpointDigest(text);
        }
        // Account observation has its own later clock. Capture the enclosing
        // packet after all original reads, never before its nested source.
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        if (captured<now || captured<originalAccount.value("observation").toMap().value("capturedEpochMs").toLongLong()) {
            _valid=false;return {};
        }
        if (captured-frameEpoch>1500) { return {}; }
        _epoch=captured;_requests.insert(object.value("commandId").toString());
        return {{"navigationEnvironmentVersion",1},{"commandId",request.value("commandId")},{"runId",request.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",captured},
            {"selectedSettingPresent",settings.contains("private/selectedMetaverseURL")},
            {"selectedServer",selectedUrl.toString(QUrl::FullyEncoded)},{"effectiveServer",effective.toString(QUrl::FullyEncoded)},
            {"environmentOverride",QProcessEnvironment::systemEnvironment().contains("HIFI_METAVERSE_URL")},
            {"otherSettingsSha256",QString::fromLatin1(QCryptographicHash::hash(QJsonDocument(other).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex())},
            {"account",originalAccount},{"ui",QVariantMap{{"bridgeId",_frame.value("bridgeId").toString()},
                {"generation",_frame.value("generation").toString()},{"sequence",_frame.value("lastCommandSequence").toVariant()},
                {"elapsedMs",_frame.value("elapsedMs").toVariant()},{"observedEpochMs",frameEpoch},
                {"loginPageAlive",!_page.isNull()},{"passwordEmpty",passwordEmpty},{"serverDraftSha256",draft},
                {"serverFocused",_server ? QVariant(_server->hasActiveFocus()) : QVariant()}}}};
    }
private:
    static bool enabled() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript"); }
    static bool identifier(const QString& text) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(text).hasMatch(); }
    QJsonObject _frame;QPointer<QQuickItem> _server,_page;QSet<QString> _requests;
    QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    qint64 _epoch{0};quint64 _sequence{0};bool _valid{true};
};
inline NavigationEnvironmentObservation& navigationEnvironmentObservation() { static NavigationEnvironmentObservation source;return source; }
}
#endif
