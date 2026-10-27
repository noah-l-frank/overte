// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "AvatarV8Callers.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSet>
#include <QUrl>
#include <QUuid>
#include <QVariantMap>
#include <mutex>
#include <atomic>
#include <QUrlQuery>

namespace overte::e2e {

// Original social XHR events only. No request, callback or response is supplied
// by this observer. One library-owned ledger; snapshot never
// enters a ScriptEngine heap, calls a handler or waits for a script thread.
class AvatarSocialHttpObservation {
public:
    enum class Profile { AvatarSocial, SnapshotPreflight, SnapshotCombinedPreflight };
    explicit AvatarSocialHttpObservation(Profile profile=Profile::AvatarSocial) : _profile(profile) { _clock.start(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool installed(const QString& value,const QString& suffix) {
        const QUrl url(value);
        if (!url.isValid() || (url.scheme()!="file" && url.scheme()!="qrc") || !url.authority().isEmpty()
                || url.hasQuery() || url.hasFragment() || !url.path().endsWith(suffix)) { return false; }
        for (const auto& part:url.path().split('/')) { if (part=="." || part=="..") { return false; } }
        return url.scheme()=="qrc" || QDir::cleanPath(url.toLocalFile()).startsWith(
            QDir::cleanPath(QCoreApplication::applicationDirPath())+"/");
    }
    static bool endpoint(const QUrl& url) {
        if (!url.isValid() || url.scheme()!="https" || url.host().isEmpty() || !url.userInfo().isEmpty()
                || url.hasFragment() || url.toString().size()>4096) { return false; }
        const auto path=url.path(QUrl::FullyEncoded);
        if (path=="/api/v1/user/connection_request" || path=="/api/v1/users" || path=="/api/v1/users/connections") { return true; }
        if (!path.startsWith("/api/v1/user/connections/e2e-") || url.hasQuery()) { return false; }
        const auto username=path.mid(QString("/api/v1/user/connections/e2e-").size());
        if (username.size()!=32) { return false; }
        for (const auto c:username) { if (!((c>='0' && c<='9') || (c>='a' && c<='f'))) { return false; } }
        return true;
    }
    static bool snapshotPreflightEndpoint(const QUrl& url) {
        if (!url.isValid() || url.scheme()!="https" || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasFragment()
                || url.toString(QUrl::FullyEncoded).size()>4096 || url.path(QUrl::FullyEncoded)!="/api/v1/user_stories") { return false; }
        const auto query=QUrlQuery(url).queryItems(QUrl::FullyDecoded);QSet<QString> keys;
        for (const auto& item:query) { if (keys.contains(item.first)) { return false; }keys.insert(item.first); }
        if (keys!=QSet<QString>{"now","include_actions","domain_id","restriction"}) { return false; }
        const QUrlQuery parsed(url);const auto domain=parsed.queryItemValue("domain_id",QUrl::FullyDecoded);
        if (parsed.queryItemValue("include_actions",QUrl::FullyDecoded)!="concurrency" || parsed.queryItemValue("restriction",QUrl::FullyDecoded)!="open,hifi"
                || domain.size()!=36 || QUuid(domain).isNull() || QUuid(domain).toString(QUuid::WithoutBraces)!=domain) { return false; }
        const auto now=parsed.queryItemValue("now",QUrl::FullyDecoded);
        const auto date=QDateTime::fromString(now,Qt::ISODateWithMs);
        return date.isValid() && date.toUTC().toString(Qt::ISODateWithMs)==now;
    }
    static QVariantMap bytes(const QByteArray& raw) {
        return {{"bytes",raw.size()},{"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())},
            {"contentBase64",QString::fromLatin1(raw.toBase64())}};
    }
    QString create(const QVariantMap& details,const AvatarV8Callers& callers) {
        std::lock_guard<std::mutex> lock(_mutex);
        if (!enabled() || !_valid || _xhrs.size()>=128) { _valid=false;return {}; }
        const auto callerId=_callers.retain(callers);if (callerId.isEmpty()) { _valid=false;return {}; }
        auto original=details;original.insert("callerStackId",callerId);
        const auto id=nonce();_xhrs.insert(id);append(id,"created",original);return id;
    }
    void event(const QString& id,const QString& kind,const QVariantMap& details={}) {
        if (id.isEmpty()) { return; }
        std::lock_guard<std::mutex> lock(_mutex);
        if (!enabled() || !_valid || !_xhrs.contains(id)) { _valid=false;return; }
        append(id,kind,details);
    }
    void eventWithCallers(const QString& id,const QString& kind,const QVariantMap& details,const AvatarV8Callers& callers) {
        if (id.isEmpty()) { return; }std::lock_guard<std::mutex> lock(_mutex);
        if (!enabled() || !_valid || !_xhrs.contains(id)) { _valid=false;return; }
        const auto callerId=_callers.retain(callers);if (callerId.isEmpty()) { _valid=false;return; }
        auto original=details;original.insert("callerStackId",callerId);append(id,kind,original);
    }
    void invalid(const QString& id) {
        if (id.isEmpty()) { return; }
        std::lock_guard<std::mutex> lock(_mutex);_valid=false;
    }
    void unavailable() { std::lock_guard<std::mutex> lock(_mutex);_valid=false; }
    // A diagnostic failure cannot escape into the actual XHR/callback path.
    static void snapshotUnavailable(bool combined=false) noexcept { snapshotFailure(combined).store(true,std::memory_order_relaxed); }
    QVariantMap snapshot(const QVariantMap& command) {
        std::lock_guard<std::mutex> lock(_mutex);
        const auto value=QJsonObject::fromVariantMap(command);const auto keys=value.keys();
        const bool combined=_profile==Profile::SnapshotCombinedPreflight;
        const bool snapshot=_profile==Profile::SnapshotPreflight || combined;
        if (!enabled() || !_valid || (snapshot && snapshotFailure(combined).load(std::memory_order_relaxed))
                || (_profile!=Profile::AvatarSocial && !snapshot) || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || value.value("schemaVersion")!=QJsonValue(1) || value.value("action")!=QJsonValue(combined ? "feature-ios-snapshot-combined-preflight-http" : snapshot ? "feature-ios-snapshot-preflight-http" : "feature-ios-avatar-social-http")
                || !identifier(value.value("commandId").toString(),true) || !identifier(value.value("runId").toString())
                || _sequence>=1000000000) { return {}; }
        const auto before=clock();if (before.isEmpty()) { return {}; }
        const auto events=_events;const auto after=clock();if (after.isEmpty()) { return {}; }
        QVariantMap result {{combined ? "iosSnapshotCombinedPreflightHttpVersion" : snapshot ? "iosSnapshotPreflightHttpVersion" : "iosAvatarSocialHttpVersion",snapshot ? 1 : 2},{"requestId",command.value("commandId")},{"runId",command.value("runId")},
            {"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clockDomain",combined ? "native-process-snapshot-combined-preflight-http" : snapshot ? "native-process-snapshot-preflight-http" : "native-process-avatar-social-http"},
            {"clockBefore",before},{"clockAfter",after},{"events",events},{"callerStacks",_callers.snapshot()}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>262144) { _valid=false;return {}; }
        return result;
    }
private:
    static std::atomic_bool& snapshotFailure(bool combined=false) noexcept {
        if (combined) { static std::atomic_bool failed {false};return failed; }
        static std::atomic_bool failed {false};return failed;
    }
    static bool identifier(const QString& value,bool query=false) {
        if (query) { if (!value.startsWith("ios-")) { return false; }return identifier(value.mid(4)); }
        if (value.size()!=32) { return false; }
        for (const auto character:value) {
            if (!((character>='0' && character<='9') || (character>='a' && character<='f'))) { return false; }
        }
        return true;
    }
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    QVariantMap clock() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_epoch || elapsed<_elapsed) { _valid=false;return {}; }
        _epoch=epoch;_elapsed=elapsed;
        return {{"epochMs",static_cast<double>(epoch)},{"monotonicMs",static_cast<double>(elapsed)}};
    }
    void append(const QString& id,const QString& kind,const QVariantMap& details) {
        const auto now=clock();if (!_valid || now.isEmpty() || _events.size()>=1024) { _valid=false;return; }
        _events.append(QVariantMap {{"sequence",_events.size()+1},{"eventId",nonce()},{"xhrId",id},
            {"kind",kind},{"clock",now},{"details",details}});
    }
    std::mutex _mutex;
    const Profile _profile;
    QString _instance {nonce()};QElapsedTimer _clock;QVariantList _events;QSet<QString> _xhrs;
    AvatarV8CallerTable _callers;quint64 _sequence {0};qint64 _epoch {0},_elapsed {0};bool _valid {true};
};
inline AvatarSocialHttpObservation& avatarSocialHttp() { static AvatarSocialHttpObservation ledger;return ledger; }
inline AvatarSocialHttpObservation& snapshotPreflightHttp(bool combined=false) {
    if (combined) { static AvatarSocialHttpObservation ledger(AvatarSocialHttpObservation::Profile::SnapshotCombinedPreflight);return ledger; }
    static AvatarSocialHttpObservation ledger(AvatarSocialHttpObservation::Profile::SnapshotPreflight);return ledger;
}
} // namespace overte::e2e
#endif
