// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QMutex>
#include <QMutexLocker>
#include <memory>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QPointer>
#include <QHash>
#include <QThread>
#include <QVariantMap>
#include <QCryptographicHash>

namespace overte::e2e {
inline bool picoAssetsReadCommand(const QVariantMap& command,bool download=false,bool resolve=false) {
    const auto json=QJsonObject::fromVariantMap(command);
    QStringList keys{"schemaVersion","commandId","action","runId"};if (download) { keys.append("hash"); }if (resolve) { keys.append("path"); }keys.sort();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z"),hash("\\A[0-9a-f]{64}\\z");
    return !(download && resolve) && QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript") && command.keys()==keys
        && json.value("schemaVersion").isDouble() && json.value("schemaVersion").toDouble()==1
        && json.value("commandId").isString() && nonce.match(command.value("commandId").toString()).hasMatch()
        && command.value("commandId").toString()!=QString(32,'0')
        && json.value("runId").isString() && nonce.match(command.value("runId").toString()).hasMatch()
        && command.value("runId").toString()!=QString(32,'0')
        && command.value("action").toString()==(download ? "feature-pico-assets-download" : resolve ? "feature-pico-assets-resolve" : "feature-pico-assets-observe")
        && (!download || (json.value("hash").isString() && hash.match(command.value("hash").toString()).hasMatch()))
        && (!resolve || (json.value("path").isString() && QRegularExpression("\\A/(?:e2e-|renamed-)"+command.value("runId").toString()+
            "/(?:main\\.gltf|main\\.obj|stand\\.fbx|mesh/triangle\\.bin|textures/checker\\.png|materials/palette\\.mtl)\\z").match(command.value("path").toString()).hasMatch()));
}
inline bool picoAssetsPath(const QString& path) {
    if (!path.startsWith('/') || path.size()<2 || path.size()>1024 || path.endsWith('/') || path.contains('\\')) { return false; }
    for (auto character:path) { if (character.unicode()<32 || character.unicode()==127) { return false; } }
    for (const auto& part:path.mid(1).split('/')) { if (part.isEmpty() || part=="." || part=="..") { return false; } }
    return true;
}
// Takes the real GetAllMappingsRequest result, including hidden bake mappings.
// No desired paths, expected hashes or editor state enter this reducer.
template<class Mappings> QVariantMap picoAssetsMappingsOriginal(const Mappings& mappings,bool canWrite,const QString& domain,const QString& session,const QString& server) {
    if (mappings.size()>4096 || domain.isEmpty() || session.isEmpty() || server.isEmpty()) { return {}; }
    QVariantList rows;QString previous;
    const QRegularExpression digest("\\A[0-9a-f]{64}\\z");
    for (const auto& pair:mappings) {
        const auto& path=pair.first;const auto& value=pair.second;const auto status=int(value.status);
        if (!picoAssetsPath(path) || (!previous.isEmpty() && path<=previous) || !digest.match(value.hash).hasMatch()
                || status<0 || status>5 || value.bakingErrors.size()>4096) { return {}; }
        rows.append(QVariantMap{{"path",path},{"hash",value.hash},{"bakeStatus",status},{"bakeError",value.bakingErrors}});previous=path;
    }
    return {{"picoAssetsObservationVersion",1},{"domainId",domain},{"sessionId",session},{"assetServerId",server},{"canWrite",canWrite},
        {"complete",true},{"mappings",rows}};
}
inline QVariantMap picoAssetsDownloadOriginal(const QString& hash,const QByteArray& data,bool cached,const QString& domain,const QString& session,const QString& server) {
    if (domain.isEmpty() || session.isEmpty() || server.isEmpty() || data.isEmpty() || data.size()>1024*1024 || QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())!=hash) { return {}; }
    return {{"picoAssetsDownloadVersion",1},{"domainId",domain},{"sessionId",session},{"assetServerId",server},{"hash",hash},{"bytes",data.size()},{"base64",QString::fromLatin1(data.toBase64())},{"loadedFromCache",cached}};
}
inline QVariantMap picoAssetsResolveOriginal(const QString& path,const QString& hash,bool redirected,const QString& target,
        const QString& domain,const QString& session,const QString& server) {
    if (!picoAssetsPath(path) || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(hash).hasMatch()
            || (redirected ? !picoAssetsPath(target) : !target.isEmpty()) || domain.isEmpty() || session.isEmpty() || server.isEmpty()) { return {}; }
    return {{"picoAssetsResolveVersion",1},{"domainId",domain},{"sessionId",session},{"assetServerId",server},
        {"requestedPath",path},{"hash",hash},{"redirected",redirected},{"redirectedPath",target}};
}
// One bounded, original read request. Completion does not become observable
// until the actual QObject has been destroyed; a new command cannot replace an
// unconsumed read or a still-live request. Repeated polling does not retime it.
class PicoAssetsReadJob {
public:
    bool canBegin(const QVariantMap& command) const {
        QMutexLocker lock(&_mutex);return gui() && !_started && _delivered.size()<512
            && !_delivered.contains(command.value("commandId").toString());
    }
    bool same(const QVariantMap& command) const {QMutexLocker lock(&_mutex);return _started && _command==command;}
    QVariantMap context() const {QMutexLocker lock(&_mutex);return _context;}
    void reject() {if(!gui()) {return;} {QMutexLocker lock(&_mutex);_rejected=true;_source.clear();}abort();}
    bool begin(const QVariantMap& command,QObject* actual,QObject* cancellation,const QString& instance,quint64 sequence,const QVariantMap& context) {
        if(!gui() || !actual || !cancellation || cancellation->thread()!=QThread::currentThread() || instance.isEmpty() || !sequence) {return false;}
        QMutexLocker lock(&_mutex);
        if(_started || _delivered.size()>=512 || _delivered.contains(command.value("commandId").toString())) {return false;}
        _command=command;_context=context;_rejected=false;_request=actual;_weakRequest=actual;_cancellation=cancellation;
        _instance=instance;_sequence=sequence;_requested=QDateTime::currentMSecsSinceEpoch();
        _captured=_destroyedEpoch=0;_source.clear();_started=true;_finished=_destroyed=false;_finishedInstalled=_destroyedInstalled=false;return true;
    }
    // Called only by the actual request's DirectConnection on its owner thread.
    // No GUI QObject or dangling TSI pointer crosses this immutable-copy lane.
    void finish(QObject* actual,const QVariantMap& original,qint64 capturedEpochMs) {
        const bool originalThread=actual && actual->thread()==QThread::currentThread();
        QMutexLocker lock(&_mutex);
        if(!_started || _request!=actual) {return;}
        if(_finished || !originalThread) {_rejected=true;_source.clear();return;}
        _captured=capturedEpochMs;_source=_rejected ? QVariantMap() : original;_finished=true;
    }
    bool callback(const QString& lane,const QMetaObject::Connection& connection,const std::shared_ptr<void>& capture) {
        if(!gui() || !connection || !capture) {return false;}QMutexLocker lock(&_mutex);
        if(!_started) {return false;}
        if(lane=="finished" && !_finishedInstalled) {_finishedConnection=connection;_finishedCapture=capture;_finishedInstalled=true;return true;}
        if(lane=="destroyed" && !_destroyedInstalled) {_destroyedConnection=connection;_destroyedCapture=capture;_destroyedInstalled=true;return true;}
        _rejected=true;return false;
    }
    void abort() {
        if(!gui()) {return;}QPointer<QObject> original;
        {QMutexLocker lock(&_mutex);original=_cancellation;}
        if(original) {delete original.data();}
    }
    void destroyed(QObject* actual) {
        QMutexLocker lock(&_mutex);
        if(_started && _request==actual) {
            _destroyed=true;_destroyedEpoch=QDateTime::currentMSecsSinceEpoch();
            if(!_finished) {_finished=true;_source.clear();_captured=QDateTime::currentMSecsSinceEpoch();}
        }
    }
    QVariantMap poll(const QVariantMap& command) {
        if(!gui()) {return {};}QVariantMap result;bool completed=false;
        {
            QMutexLocker lock(&_mutex);
            if(!_started || _command!=command) {return {};}
            if(!_finished || !_destroyed || !_weakRequest.isNull() || !callbacksRetired()) {return {{"pending",true},{"requestId",command.value("commandId")}};}
            const bool valid=!_rejected && !_source.isEmpty() && _captured>=_requested && _captured-_requested<1500;
            if(valid) {result={{"schemaVersion",1},{"requestId",_command.value("commandId")},{"runId",_command.value("runId")},
                {"instance",_instance},{"sequence",static_cast<qulonglong>(_sequence)},{"processId",QCoreApplication::applicationPid()},
                {"requestedEpochMs",_requested},{"capturedEpochMs",_captured},{"source",_source},{"activeRequests",0},{"retainedResults",0}};}
            recordRetirement();completed=true;
        }
        if(completed) {abort();}return result;
    }
    QVariantMap retire(const QVariantMap& command) {
        if(!gui()) {return {};}
        {QMutexLocker lock(&_mutex);if(_started && _command!=command) {return {};}
            if(!_started && (!_delivered.contains(command.value("commandId").toString())
                    || _delivered.value(command.value("commandId").toString()).value("command").toMap()!=command)) {return {};}}
        abort();
        QMutexLocker lock(&_mutex);
        const bool retired=!_started || (_request && _finished && _destroyed && _weakRequest.isNull() && callbacksRetired() && _cancellation.isNull());
        if(retired && _started) {recordRetirement();}
        const auto old=_delivered.value(command.value("commandId").toString());
        return {{"picoAssetsReadRetirementVersion",1},{"originalRequestId",command.value("commandId")},{"runId",command.value("runId")},
            {"retired",retired},{"requestAlive",_started && !_weakRequest.isNull()},
            {"finishedConnected",_started && bool(_finishedConnection)},{"destroyedConnected",_started && bool(_destroyedConnection)},
            {"finishedCaptureAlive",_started && !_finishedCapture.expired()},{"destroyedCaptureAlive",_started && !_destroyedCapture.expired()},
            {"cancellationAlive",_started && !_cancellation.isNull()},
            {"originalRequestedEpochMs",retired ? old.value("requestedEpochMs") : QVariant(_requested)},
            {"originalCapturedEpochMs",retired ? old.value("capturedEpochMs") : QVariant(_captured)},
            {"originalDestroyedEpochMs",retired ? old.value("destroyedEpochMs") : QVariant(_destroyedEpoch)},
            {"retiredEpochMs",retired ? old.value("retiredEpochMs") : QVariant()}};
    }
private:
    void recordRetirement() {
        _delivered.insert(_command.value("commandId").toString(),QVariantMap{{"command",_command},{"requestedEpochMs",_requested},
            {"capturedEpochMs",_captured},{"destroyedEpochMs",_destroyedEpoch},{"retiredEpochMs",QDateTime::currentMSecsSinceEpoch()}});
        _command.clear();_source.clear();_context.clear();_request=nullptr;_started=false;
        _finishedConnection={};_destroyedConnection={};
    }
    bool callbacksRetired() const {return _finishedInstalled && _destroyedInstalled && !_finishedConnection && !_destroyedConnection
        && _finishedCapture.expired() && _destroyedCapture.expired();}
    QMetaObject::Connection _finishedConnection,_destroyedConnection;
    std::weak_ptr<void> _finishedCapture,_destroyedCapture;bool _finishedInstalled{false},_destroyedInstalled{false};
    static bool gui() {return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript");}
    mutable QMutex _mutex;QVariantMap _command,_source,_context;QObject* _request{nullptr};QPointer<QObject> _weakRequest,_cancellation;
    QString _instance;QHash<QString,QVariantMap> _delivered;quint64 _sequence{0};qint64 _requested{0},_captured{0},_destroyedEpoch{0};
    bool _rejected{false},_started{false},_finished{false},_destroyed{false};
};
} // namespace overte::e2e
#endif
