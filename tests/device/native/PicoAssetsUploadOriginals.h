// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QCryptographicHash>
#include <QMap>
#include <QSet>
#include <QMutex>
#include <QPointer>
#include <QThread>
#include <QJsonDocument>
#include <QJsonObject>
#include <memory>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QUuid>
#include <QVariantMap>
#include <algorithm>

namespace overte::e2e {
class PicoAssetsUploadOriginals {
public:
    static QString digest(const QString& value) { return QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(),QCryptographicHash::Sha256).toHex()); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    // Every original entry is recorded, including rejected/busy/malformed calls.
    // Keep only original argument digests; arbitrary user filenames stay private.
    void entry(const QString& kind,const QVariantMap& arguments) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) {return;}
        QMutexLocker locker(&_mutex);
        if (QThread::currentThread()!=QCoreApplication::instance()->thread()) {_overflow=true;return;}
        if (_calls.size()>=512 || (kind!="bundle" && kind!="single" && kind!="cancel")) {_overflow=true;return;}
        const auto raw=QJsonDocument(QJsonObject::fromVariantMap(arguments)).toJson(QJsonDocument::Compact);
        if(raw.size()>262144) {_overflow=true;return;}
        _calls.append(QVariantMap{{"kind",kind},{"epochMs",QDateTime::currentMSecsSinceEpoch()},
            {"argumentsSha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}});
    }
    QString run(const QString& id) const {QMutexLocker locker(&_mutex);return _bundles.value(id).value("runId").toString();}
    bool callback(const QString& instance,const QString& lane,const QMetaObject::Connection& connection,const std::shared_ptr<void>& capture) {
        if(!enabled() || !connection || !capture) {return false;}QMutexLocker locker(&_mutex);
        auto found=_lives.find(instance);if(found==_lives.end()) {_overflow=true;return false;}auto& life=found.value();
        if(lane=="finished" && !life.finishedInstalled) {life.finished=connection;life.finishedCapture=capture;life.finishedInstalled=true;return true;}
        if(lane=="destroyed" && !life.destroyedInstalled) {life.destroyed=connection;life.destroyedCapture=capture;life.destroyedInstalled=true;return true;}
        _overflow=true;return false;
    }
    bool begin(const QString& id,const QStringList& files,const QStringList& relative,const QString& destination,const QString& primary,const QVariantMap& connection) {
        if (!enabled()) { return false; }
        const auto match=QRegularExpression("\\A/e2e-([0-9a-f]{32})/\\z").match(destination);
        if (!match.hasMatch() || files.size()!=relative.size() || files.isEmpty() || files.size()>7 || !relative.contains(primary)) { return false; }
        const auto run=match.captured(1);QString directory;QVariantList originals;
        for (int i=0;i<files.size();++i) {
            const auto path=files[i],name=relative[i];
            if (name.isEmpty() || name.startsWith('/') || name.contains('\\') || name.split('/').contains("..") || name.split('/').contains(".")
                    || QDir::cleanPath(path)!=path || !path.endsWith('/'+name)) { return false; }
            const auto current=path.left(path.size()-name.size()-1);
            if (directory.isEmpty()) { directory=current; }
            if (current!=directory || !QRegularExpression("\\A/(?:[^/]+/)*feature-assets-"+run+"(?:-stage[1-6])?/(?:gltf-bundle|obj-bundle|fbx-bundle)\\z").match(current).hasMatch()) { return false; }
            originals.append(QVariantMap{{"relativePath",name},{"filenameSha256",digest(path)}});
        }
        QMutexLocker locker(&_mutex);
        if (_retired.contains(run)) { if (_late.size()<64) { _late.insert(run); }else { _overflow=true; }return false; }
        if (_bundles.size()>=64 || _bundles.contains(id)) { fault(run);return false; }
        _bundles.insert(id,QVariantMap{{"id",id},{"runId",run},{"directorySha256",digest(directory)},{"destination",destination},
            {"primary",primary},{"files",originals},{"connection",connection},{"createdEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"active",true},{"finishedEpochMs",QVariant()},{"errorSha256",QVariant()},{"requests",QVariantList{}}});return true;
    }
    QString issue(const QString& id,const QString& kind,const QVariantMap& connection,QObject* actual) {
        if(!enabled() || !actual) {return {};}
        QMutexLocker locker(&_mutex);auto found=_bundles.find(id);if (found==_bundles.end()) { return {}; }
        auto& bundle=found.value();auto requests=bundle.value("requests").toList();
        if (!bundle.value("active").toBool() || requests.size()>=14 || bundle.value("connection").toMap()!=connection || (kind!="upload" && kind!="mapping")) {
            fault(bundle.value("runId").toString());return {};
        }
        const auto instance=nonce();_lives.insert(instance,Life{actual});requests.append(QVariantMap{{"instance",instance},{"kind",kind},{"issuedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"completedEpochMs",QVariant()},{"destroyedEpochMs",QVariant()},{"original",QVariant()}});bundle["requests"]=requests;return instance;
    }
    void finished(const QString& id,const QString& instance,const QVariantMap& original) { update(id,instance,"finished",original); }
    void destroyed(const QString& id,const QString& instance) { update(id,instance,"destroyed",{}); }
    void end(const QString& id,const QString& error) {
        QMutexLocker locker(&_mutex);auto found=_bundles.find(id);if (found==_bundles.end()) { return; }
        auto& value=found.value();if (!value.value("active").toBool()) { fault(value.value("runId").toString());return; }
        value["active"]=false;value["finishedEpochMs"]=QDateTime::currentMSecsSinceEpoch();value["errorSha256"]=digest(error);
    }
    QVariantMap observe(const QString& run) const { if(!enabled()) {return {};}QMutexLocker locker(&_mutex);return snapshot(run); }
    QVariantMap release(const QString& run,const QString& instance,const QStringList& ids) {
        if(!enabled()) {return {};}QMutexLocker locker(&_mutex);if (_overflow || instance!=_instance || _invalid.contains(run) || _late.contains(run)) { return {}; }
        if (_retired.contains(run)) { return _retired.value(run)==ids ? snapshot(run) : QVariantMap(); }
        if (_retired.size()>=64) { return {}; }
        QStringList actual;
        for (auto it=_bundles.cbegin();it!=_bundles.cend();++it) {
            const auto& bundle=it.value();if (bundle.value("runId")!=run) { continue; }
            actual.append(it.key());if (bundle.value("active").toBool() || bundle.value("finishedEpochMs").isNull()) { return {}; }
            for (const auto& raw:bundle.value("requests").toList()) {
                const auto request=raw.toMap();if (!retired(_lives.value(request.value("instance").toString())) || request.value("completedEpochMs").isNull() || request.value("destroyedEpochMs").isNull() || request.value("original").toMap().isEmpty()) { return {}; }
            }
        }
        actual.sort();if (actual!=ids) { return {}; }
        for (const auto& id:actual) {for(const auto& raw:_bundles.value(id).value("requests").toList()) {_lives.remove(raw.toMap().value("instance").toString());}_bundles.remove(id); }_retired.insert(run,ids);return snapshot(run);
    }
private:
    struct Life {QPointer<QObject> weak;QMetaObject::Connection finished,destroyed;std::weak_ptr<void> finishedCapture,destroyedCapture;bool finishedInstalled{false},destroyedInstalled{false};};
    static bool enabled() {return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread() && QCoreApplication::arguments().contains("--testScript");}
    static bool retired(const Life& life) {return life.weak.isNull() && life.finishedInstalled && life.destroyedInstalled && !life.finished && !life.destroyed && life.finishedCapture.expired() && life.destroyedCapture.expired();}
    static QVariantMap lifetime(const Life& life) {return {{"requestAlive",!life.weak.isNull()},
        {"finishedConnected",bool(life.finished)},{"destroyedConnected",bool(life.destroyed)},
        {"finishedCaptureAlive",!life.finishedCapture.expired()},{"destroyedCaptureAlive",!life.destroyedCapture.expired()},
        {"callbacksInstalled",life.finishedInstalled && life.destroyedInstalled},{"resourcesRetired",retired(life)}};}
    void fault(const QString& run) { if (_invalid.size()<64) { _invalid.insert(run); }else { _overflow=true; } }
    void update(const QString& id,const QString& instance,const QString& operation,const QVariantMap& original) {
        QMutexLocker locker(&_mutex);auto found=_bundles.find(id);if (found==_bundles.end()) { return; }
        auto& bundle=found.value();auto requests=bundle.value("requests").toList();bool matched=false;
        for (auto& raw:requests) { auto value=raw.toMap();if (value.value("instance")!=instance) { continue; }
            matched=true;const auto field=operation=="finished" ? "completedEpochMs" : "destroyedEpochMs";
            if (!value.value(field).isNull() || (operation=="finished" && (!value.value("destroyedEpochMs").isNull() || original.isEmpty()))) { fault(bundle.value("runId").toString());return; }
            if (operation=="destroyed" && value.value("completedEpochMs").isNull()) { fault(bundle.value("runId").toString()); }
            value[field]=QDateTime::currentMSecsSinceEpoch();if (operation=="finished") { value["original"]=original; }raw=value;
        }
        if (!matched) { fault(bundle.value("runId").toString());return; }bundle["requests"]=requests;
    }
    QVariantMap snapshot(const QString& run) const {
        QVariantList rows;int live=0,active=0;
        for (const auto& original:_bundles) { if (original.value("runId")!=run) { continue; }auto bundle=original;active+=bundle.value("active").toBool();
            auto requests=bundle.value("requests").toList();for (auto& raw:requests) {auto value=raw.toMap();const auto life=_lives.value(value.value("instance").toString());
                live+=!retired(life);value.insert("lifetime",lifetime(life));raw=value;}bundle["requests"]=requests;rows.append(bundle);
        }
        return {{"picoAssetsUploadsVersion",1},{"totalCalls",_calls.size()},{"calls",_calls},{"instance",_instance},{"runId",run},{"valid",!_overflow && !_invalid.contains(run) && !_late.contains(run)},
            {"retired",_retired.contains(run)},{"activeBundles",active},{"liveRequests",live},{"retainedBundles",rows.size()},{"bundles",rows}};
    }
    QHash<QString,Life> _lives;QVariantList _calls;
    const QString _instance=nonce();mutable QMutex _mutex;QMap<QString,QVariantMap> _bundles;
    bool _overflow{false};QMap<QString,QStringList> _retired;QSet<QString> _invalid,_late;
};
} // namespace overte::e2e
#endif
