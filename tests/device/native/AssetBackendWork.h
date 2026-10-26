// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtGlobal>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_LINUX)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QPointer>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <QStringList>
#include <memory>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

namespace overte::e2e::asset_backend {
struct Configuration {
    QString root,ownerSha256;quint64 device{0},inode{0};bool valid{false};
    Configuration() {
        const auto owner=qEnvironmentVariable("OVERTE_E2E_FIXTURE_PROCESS_OWNER");
        root=qEnvironmentVariable("OVERTE_E2E_ASSETS_SOURCE_ROOT");
        if (!QCoreApplication::instance() || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(owner).hasMatch()
                || root.isEmpty() || !QDir::isAbsolutePath(root) || QFileInfo(root).canonicalFilePath()!=root) {return;}
        struct stat original{};const auto encoded=QFile::encodeName(root);
        if (::lstat(encoded.constData(),&original)!=0 || !S_ISDIR(original.st_mode) || original.st_uid!=::geteuid()
                || (original.st_mode&0777)!=0700) {return;}
        device=original.st_dev;inode=original.st_ino;
        ownerSha256=QString::fromLatin1(QCryptographicHash::hash(owner.toUtf8(),QCryptographicHash::Sha256).toHex());valid=true;
    }
    bool current() const {
        if (!valid) {return false;}struct stat actual{};const auto encoded=QFile::encodeName(root);
        return ::lstat(encoded.constData(),&actual)==0 && S_ISDIR(actual.st_mode) && actual.st_uid==::geteuid()
            && (actual.st_mode&0777)==0700 && static_cast<quint64>(actual.st_dev)==device && static_cast<quint64>(actual.st_ino)==inode
            && QFileInfo(root).canonicalFilePath()==root;
    }
};
inline const Configuration& configuration() {static const Configuration value;return value;}
inline QString nonce() {return QUuid::createUuid().toString(QUuid::WithoutBraces);}

// The registry holds weak references only. The lease token is the first member
// of each original task, so it expires after that task's original members have
// been destroyed. Bake tasks additionally retain their actual QObject and
// std::shared_ptr weak lifetimes; none is replaced by isBaking().
class Work {
public:
    static Work& shared() {static Work value;return value;}
    static bool enabled() {return configuration().valid;}
    QJsonObject clock() {std::lock_guard<std::mutex> guard(_mutex);return stamp();}
    void incomplete() {if (!enabled()) {return;}std::lock_guard<std::mutex> guard(_mutex);_complete=false;}
    void bindServer(QObject* server) {
        if (!enabled()) {return;}std::lock_guard<std::mutex> guard(_mutex);
        if (!server || server->thread()!=QThread::currentThread() || (_server && _server!=server)) {_complete=false;return;}_server=server;
    }
    QString queued(const QString& kind,const std::shared_ptr<void>& lease,QObject* object,const QJsonObject& fields) {
        if (!enabled()) {return {};}
        std::lock_guard<std::mutex> guard(_mutex);
        if (!lease || _rows.size()>=512 || (kind!="bake" && kind!="send" && kind!="upload")) {_complete=false;return {};}
        Row row;row.id=nonce();row.kind=kind;row.lease=lease;row.object=object;row.created=stamp();row.fields=fields;
        _rows.append(row);event(_rows.last(),"queued",{{"inputs",fields}});return row.id;
    }
    void owner(const QString& id,const std::weak_ptr<void>& original) {
        if (!enabled()) {return;}std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);
        if (!row || row->kind!="bake" || row->ownerKnown) {_complete=false;return;}
        row->owner=original;row->ownerKnown=true;event(*row,"owner-bound",{});
    }
    void field(const QString& id,const QString& name,const QString& value) {
        if (!enabled()) {return;}std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);
        if (!row || !row->fields.contains(name) || !row->fields.value(name).isString()
                || (!row->fields.value(name).toString().isEmpty() && row->fields.value(name).toString()!=value)) {_complete=false;return;}
        row->fields[name]=value;event(*row,"input-observed",{{"field",name},{"value",value}});
    }
    QString enter(const QString& id,const QString& kind,bool callback) {
        if (!enabled()) {return {};}
        std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);if (!row) {_complete=false;return {};}
        const auto body=nonce();auto& stack=callback ? row->callbacks : row->runs;stack.append(body);
        if (!callback && row->runEntered!=0) {_complete=false;}
        if (callback) {++row->callbackEntered;} else {++row->runEntered;}
        event(*row,callback ? "callback-enter" : "run-enter",{{"bodyId",body},{"callback",kind}});return body;
    }
    void leave(const QString& id,const QString& body,const QString& kind,bool callback) {
        if (!enabled()) {return;}std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);
        if (!row || body.isEmpty()) {_complete=false;return;}auto& stack=callback ? row->callbacks : row->runs;
        if (stack.isEmpty() || stack.last()!=body) {_complete=false;return;}stack.removeLast();
        if (callback) {++row->callbackReturned;} else {++row->runReturned;}
        event(*row,callback ? "callback-return" : "run-return",{{"bodyId",body},{"callback",kind}});
    }
    QJsonObject snapshot(QObject* server,const QJsonArray& pendingBakes,int transfers,int baking,int queuedRequests,bool queueing) {
        if (!enabled()) {return {};}
        std::lock_guard<std::mutex> guard(_mutex);bool available=configuration().current() && server && _server==server && server->thread()==QThread::currentThread();
        if (!available || transfers<0 || baking<0 || queuedRequests<0) {_complete=false;}
        for (const auto& value:pendingBakes) {
            const auto item=value.toObject();auto row=find(item.value("id").toString());
            if (!row || row->kind!="bake" || row->fields.value("hash")!=item.value("hash")) {_complete=false;}
        }
        QJsonArray jobs;
        for (auto& row:_rows) {
            const bool leaseAlive=!row.lease.expired();const bool ownerAlive=row.ownerKnown && !row.owner.expired();const bool objectAlive=!row.object.isNull();
            observeExpiry(row,"lease",leaseAlive,row.leaseExpired);
            if (row.ownerKnown) {observeExpiry(row,"owner",ownerAlive,row.ownerExpired);}
            if (row.kind=="bake") {observeExpiry(row,"object",objectAlive,row.objectExpired);if (!row.ownerKnown) {_complete=false;}}
            jobs.append(QJsonObject{{"id",row.id},{"kind",row.kind},{"inputs",row.fields},{"created",row.created},
                {"leaseAlive",leaseAlive},{"leaseExpired",nullable(row.leaseExpired)},
                {"ownerKnown",row.ownerKnown},{"ownerAlive",row.ownerKnown ? QJsonValue(ownerAlive) : QJsonValue(QJsonValue::Null)},
                {"ownerExpired",nullable(row.ownerExpired)},{"objectAlive",row.kind=="bake" ? QJsonValue(objectAlive) : QJsonValue(QJsonValue::Null)},
                {"objectExpired",nullable(row.objectExpired)},{"runEntered",static_cast<double>(row.runEntered)},
                {"runReturned",static_cast<double>(row.runReturned)},{"callbackEntered",static_cast<double>(row.callbackEntered)},
                {"callbackReturned",static_cast<double>(row.callbackReturned)},{"pendingRuns",row.runs.size()},
                {"pendingBodies",row.callbacks.size()},{"events",row.events}});
        }
        return {{"assetBackendWorkVersion",1},{"instance",_instance},{"sequence",static_cast<double>(++_sequence)},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"clock",stamp()},{"available",available},{"complete",_complete},
            {"jobs",jobs},{"pendingBakes",pendingBakes},{"transferActiveThreads",transfers},{"bakeActiveThreads",baking},
            {"queuedRequests",queuedRequests},{"queueingRequests",queueing}};
    }
private:
    struct Row {
        QString id,kind;std::weak_ptr<void> lease,owner;QPointer<QObject> object;bool ownerKnown{false};QJsonObject fields,created,leaseExpired,ownerExpired,objectExpired;
        quint64 runEntered{0},runReturned{0},callbackEntered{0},callbackReturned{0};QStringList runs,callbacks;QJsonArray events;
    };
    Work() {_clock.start();}
    QJsonObject stamp() const {return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"monotonicMs",static_cast<double>(_clock.elapsed())}};}
    static QJsonValue nullable(const QJsonObject& value) {return value.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(value);}
    Row* find(const QString& id) {for (auto& row:_rows) {if (row.id==id) {return &row;}}return nullptr;}
    void event(Row& row,const QString& kind,const QJsonObject& details) {
        if (row.events.size()>=128) {_complete=false;return;}
        row.events.append(QJsonObject{{"sequence",row.events.size()+1},{"eventId",nonce()},{"kind",kind},{"clock",stamp()},{"details",details}});
    }
    void observeExpiry(Row& row,const QString& kind,bool alive,QJsonObject& expired) {
        if (!alive && expired.isEmpty()) {expired=stamp();event(row,kind+"-expired-observed",{});}
        else if (alive && !expired.isEmpty()) {_complete=false;}
    }
    std::mutex _mutex;QPointer<QObject> _server;QVector<Row> _rows;QElapsedTimer _clock;bool _complete{true};quint64 _sequence{0};QString _instance{nonce()};
};

class TaskLease {
public:
    TaskLease(const QString& kind,QObject* object=nullptr,const QString& hash={},const QString& path={},const QString& sender={}) {
        if (!Work::enabled()) {return;}_token=std::make_shared<quint8>(0);
        _id=Work::shared().queued(kind,_token,object,{{"hash",hash},{"path",path},{"senderId",sender},{"messageId",QString()}});
    }
    const QString& id() const {return _id;}
    void field(const QString& name,const QString& value) {if (!_id.isEmpty()) {Work::shared().field(_id,name,value);}}
    TaskLease(const TaskLease&)=delete;TaskLease& operator=(const TaskLease&)=delete;
private:QString _id;std::shared_ptr<void> _token;
};
class Body {
public:
    Body(const QString& id,const QString& kind,bool callback) : _id(id),_kind(kind),_callback(callback) {
        if (!_id.isEmpty()) {_body=Work::shared().enter(_id,_kind,_callback);}
    }
    ~Body() {if (!_id.isEmpty()) {Work::shared().leave(_id,_body,_kind,_callback);}}
    Body(const Body&)=delete;Body& operator=(const Body&)=delete;
private:QString _id,_kind,_body;bool _callback;
};
}
#endif
