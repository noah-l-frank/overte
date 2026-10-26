// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include <AccountManager.h>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QHttpMultiPart>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QTimer>
#include <sys/stat.h>
#include <cerrno>

namespace overte::e2e {
// This book owns only diagnostic values. QObject destruction, callback-stack
// departure and actual body-file descriptor observations remain distinct facts.
class IOSSnapshotUploadObservation {
public:
    static IOSSnapshotUploadObservation* get() noexcept {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
        try { if (!enabled()) {return nullptr;}static auto* value=new IOSSnapshotUploadObservation;return value; } catch (...) { return nullptr; }
#else
        return nullptr;
#endif
    }
    void incomplete() noexcept {fail();}
    QString begin(QObject* uploader,const QString& path,const overte::network::RequestTicket& scope) noexcept {
        QString result;protect([&] {
            if (!enabled()) {return;}QMutexLocker lock(&_mutex);
            if (!uploader || !scope.scoped() || !scope.featureActive() || _uploads.size()>=64) {fail();return;}
            result=uuid();const auto name=QFileInfo(path).fileName();
            const bool privateName=QFileInfo(path).isAbsolute() && QRegularExpression(
                "\\Aparity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,16}_[0-9]{1,10}\\.(?:png|jpg|jpeg|gif|webp)\\z").match(name).hasMatch();
            _uploads.insert(result,{{{"instance",result},{"bornEpochMs",epoch()},{"privateName",privateName},
                {"fileName",privateName?name:QString()},{"fileNameSha256",sha(name.toUtf8())}},scope,{}});
            resourceLocked(result,uploader,"uploader");append(result,"begin");
        });return result;
    }
    void resource(const QString& owner,QObject* object,const QString& kind) noexcept {
        protect([&] {if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);resourceLocked(owner,object,kind);});
    }
    void fileOpened(const QString& owner,QFile* file,bool opened) noexcept {
        protect([&] {if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);const auto id=_byObject.value(file);
            if (!_resources.contains(id) || _resources[id].owner!=owner || _resources[id].kind!="file" || _resources[id].openObserved) {fail();return;}
            auto& entry=_resources[id];entry.openObserved=true;entry.opened=opened;
            if (opened) {entry.fd=file->handle();struct stat value {};
                if (entry.fd<0 || ::fstat(entry.fd,&value)!=0 || !S_ISREG(value.st_mode)) {fail();}
                else {entry.first=statFact(value);}}
            append(owner,"file-opened",{{"resource",id},{"opened",opened}});
        });
    }
    std::shared_ptr<IOSRequestObservation> observer(const QString& owner,const QString& stage,
            const overte::network::RequestTicket& ticket) noexcept {
        std::shared_ptr<IOSRequestObservation> result;protect([&] {
            if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);
            if (!_uploads.contains(owner) || (stage!="upload" && stage!="story") || !ticket.scoped() || !ticket.featureActive()
                    || _requests.size()>=128) {fail();return;}
            const auto id=uuid();result=std::make_shared<IOSRequestObservation>();
            result->created=[this,id](QNetworkReply* reply,QHttpMultiPart* multipart) {created(id,reply,multipart);};
            _requests.insert(id,{owner,stage,ticket,result,{},epoch()});_uploads[owner].latest=ticket;
            _uploads[owner].requests.append(id);append(owner,"ticket-issued",{{"request",id}});
        });return result;
    }
    // These methods take actual production operands, never a requested result.
    QString callbackEnter(const QString& owner,const QString& method,QNetworkReply* reply,bool finished,
            const overte::network::RequestTicket& current,const std::shared_ptr<int>& stack) noexcept {
        QString result;protect([&] {if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);
            const auto resource=_byObject.value(reply);
            if (!_uploads.contains(owner) || !_resources.contains(resource) || _resources[resource].owner!=owner
                    || _resources[resource].kind!="reply" || !_resources[resource].alive || !stack || _callbacks.size()>=256) {fail();return;}
            QString request;for (auto it=_requests.cbegin();it!=_requests.cend();++it) {if (it->reply==resource) {if (!request.isEmpty()) {fail();return;}request=it.key();}}
            if (request.isEmpty()) {fail();return;}const auto& sent=_requests[request];
            result=uuid();_callbacks.insert(result,{stack,{{"instance",result},{"upload",owner},{"method",method},{"reply",resource},
                {"enteredEpochMs",epoch()},{"leftEpochMs",QVariant()},{"finishedAtEntry",finished},
                {"scopeGeneration",QString::number(current.featureGeneration())},{"scopeActiveAtEntry",current.featureActive()},
                {"request",request},{"requestGeneration",QString::number(sent.ticket.featureGeneration())},{"requestActiveAtEntry",sent.ticket.featureActive()}}});
            append(owner,"callback-enter",{{"callback",result}});
        });return result;
    }
    void callbackLeave(const QString& id) noexcept {
        protect([&] {if (id.isEmpty()) {return;}QMutexLocker lock(&_mutex);
            if (!_callbacks.contains(id) || _callbacks[id].original.value("leftEpochMs").isValid()) {fail();return;}
            auto& row=_callbacks[id].original;row["leftEpochMs"]=epoch();append(row.value("upload").toString(),"callback-left",{{"callback",id}});
        });
    }
    void response(const QString& owner,QNetworkReply* reply,const QByteArray& original) noexcept {
        protect([&] {if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);const auto id=_byObject.value(reply);
            if (!_resources.contains(id) || _resources[id].owner!=owner || _resources[id].kind!="reply") {fail();return;}
            if (original.size()>65536) {fail();return;}
            append(owner,"response-original",{{"reply",id},{"byteCount",int(original.size())},{"sha256",sha(original)}});
        });
    }
    void event(const QString& owner,const QString& kind,const overte::network::RequestTicket& current,bool finished,bool error=false) noexcept {
        protect([&] {if (owner.isEmpty()) {return;}QMutexLocker lock(&_mutex);
            if (!_uploads.contains(owner)) {fail();return;}_uploads[owner].latest=current;
            append(owner,kind,{{"scopeGeneration",QString::number(current.featureGeneration())},{"scopeActive",current.featureActive()},
                {"finished",finished},{"error",error}});
        });
    }
    QVariantMap read(const QString& nonce,const QString& run,const std::function<QVariantMap()>& activity) noexcept {
        QVariantMap result;protect([&] {result=_bracket.read("iosSnapshotUploadsVersion","native-main-snapshot-uploads",nonce,run,[&] {
            const auto active=activity();if (active.isEmpty()) {return QVariantMap{};}QMutexLocker lock(&_mutex);
            QVariantList uploads,resources,requests,callbacks;
            for (auto it=_uploads.cbegin();it!=_uploads.cend();++it) {auto row=it->original;row["requests"]=it->requests;
                row["scopeGeneration"]=QString::number(it->latest.featureGeneration());row["scopeActive"]=it->latest.featureActive();uploads.append(row);}
            for (auto it=_resources.cbegin();it!=_resources.cend();++it) {const auto& entry=it.value();auto row=entry.original;
                row["alive"]=entry.alive;row["openObserved"]=entry.openObserved;row["opened"]=entry.opened;
                row["descriptor"]=entry.fd;row["firstFile"]=entry.first;
                row["fdBefore"]=fdFact(entry);row["fdAfter"]=fdFact(entry);resources.append(row);}
            bool healthy=!_failed.load(std::memory_order_acquire);
            for (auto it=_requests.cbegin();it!=_requests.cend();++it) {const auto& entry=it.value();const bool complete=entry.observation && entry.observation->complete.load(std::memory_order_acquire);
                healthy=healthy&&complete;requests.append(QVariantMap{{"instance",it.key()},{"upload",entry.owner},{"stage",entry.stage},
                    {"issuedEpochMs",entry.issued},{"generation",QString::number(entry.ticket.featureGeneration())},{"active",entry.ticket.featureActive()},
                    {"diagnosticsComplete",complete},{"reply",entry.reply}});}
            for (const auto& entry:_callbacks) {auto row=entry.original;row["stackAlive"]=!entry.stack.expired();callbacks.append(row);}
            return QVariantMap{{"iosSnapshotUploadsSourceVersion",2},{"complete",healthy},{"uploads",uploads},{"resources",resources},{"requests",requests},{"callbacks",callbacks},
                {"events",_events},{"activity",active},{"transportFDObservationRequired",true}};
        });});return result;
    }
private:
    struct Upload {QVariantMap original;overte::network::RequestTicket latest;QStringList requests;};
    struct Resource {QString owner,kind;QVariantMap original;bool alive {true},openObserved {false},opened {false};int fd {-1};QVariantMap first;};
    struct Request {QString owner,stage;overte::network::RequestTicket ticket;std::shared_ptr<IOSRequestObservation> observation;QString reply;qint64 issued;};
    struct Callback {std::weak_ptr<int> stack;QVariantMap original;};
    template<typename Function> void protect(Function&& function) noexcept {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
        try {function();} catch (...) {fail();}
#else
        fail();
#endif
    }
    void fail() noexcept {_failed.store(true,std::memory_order_release);}
    static bool enabled() {return QCoreApplication::arguments().contains("--testScript");}
    static QString uuid() {return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');}
    static QString sha(const QByteArray& raw) {return QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex());}
    qint64 epoch() {const auto now=QDateTime::currentMSecsSinceEpoch();if (now<=0 || now<_epoch) {fail();}_epoch=now;return now;}
    static QVariantMap statFact(const struct stat& value) {
        return {{"device",QString::number(qulonglong(value.st_dev))},{"inode",QString::number(qulonglong(value.st_ino))},
            {"mode",QString::number(qulonglong(value.st_mode))},{"uid",QString::number(qulonglong(value.st_uid))},
            {"bytes",double(value.st_size)},{"links",double(value.st_nlink)},{"regular",bool(S_ISREG(value.st_mode))},
            {"mtimeSeconds",QString::number(qlonglong(value.st_mtimespec.tv_sec))},{"mtimeNanoseconds",double(value.st_mtimespec.tv_nsec)},
            {"ctimeSeconds",QString::number(qlonglong(value.st_ctimespec.tv_sec))},{"ctimeNanoseconds",double(value.st_ctimespec.tv_nsec)}};
    }
    static QVariantMap fdFact(const Resource& entry) {
        if (entry.kind!="file" || !entry.openObserved || !entry.opened || entry.fd<0 || entry.first.isEmpty()) {return {{"state","unobserved"},{"file",QVariantMap{}}};}
        struct stat value {};if (::fstat(entry.fd,&value)==0) {const auto fact=statFact(value);return {{"state",fact==entry.first?"present":"changed"},{"file",fact}};}
        return {{"state",errno==EBADF?"absent":"unknown"},{"file",QVariantMap{}}};
    }
    QString resourceLocked(const QString& owner,QObject* object,const QString& kind) {
        if (!_uploads.contains(owner) || !object || object->thread()!=QThread::currentThread() || _resources.size()>=256
                || (_byObject.contains(object) && _resources[_byObject.value(object)].alive)) {fail();return {};}
        const auto id=uuid();Resource entry;entry.owner=owner;entry.kind=kind;
        entry.original={{"instance",id},{"upload",owner},{"kind",kind},{"bornEpochMs",epoch()},{"destroyedEpochMs",QVariant()}};
        _resources.insert(id,entry);_byObject[object]=id;
        const auto connection=QObject::connect(object,&QObject::destroyed,[this,id] {protect([&] {QMutexLocker lock(&_mutex);
            if (!_resources.contains(id) || !_resources[id].alive) {fail();return;}
            auto& value=_resources[id];value.alive=false;value.original["destroyedEpochMs"]=epoch();append(value.owner,"resource-destroyed",{{"resource",id}});
        });});
        if (!connection) {fail();}append(owner,"resource-created",{{"resource",id}});return id;
    }
    // Called only by AccountManager's isolated observer on the real reply thread.
    void created(const QString& request,QNetworkReply* reply,QHttpMultiPart* multipart) {
        QMutexLocker lock(&_mutex);
        if (!_requests.contains(request) || !_requests[request].reply.isEmpty() || !reply) {fail();return;}
        auto& value=_requests[request];const auto id=resourceLocked(value.owner,reply,"reply");if (id.isEmpty()) {return;}value.reply=id;
        if (multipart) {const auto part=_byObject.value(multipart);if (!_resources.contains(part) || _resources[part].owner!=value.owner || _resources[part].kind!="multipart") {fail();}}
        const auto actual=reply->request();const auto path=actual.url().path();const bool endpoint=path=="/api/v1/snapshots" || path=="/api/v1/user_stories";
        const auto scheme=actual.url().scheme().toLower();const auto host=actual.url().host().toLower();
        append(value.owner,"reply-created",{{"request",request},{"reply",id},{"endpoint",endpoint?path:QString()},
            {"scheme",scheme},{"hostSha256",sha(host.toUtf8())},{"port",actual.url().port(scheme=="https"?443:80)},
            {"authorizationPresent",!actual.rawHeader("Authorization").isEmpty()},{"operation",int(reply->operation())}});
        for (auto* timer:reply->findChildren<QTimer*>(QString(),Qt::FindDirectChildrenOnly)) {resourceLocked(value.owner,timer,"reply-timer");}
        QObject::connect(reply,&QNetworkReply::finished,[this,request,reply] {protect([&] {QMutexLocker lock(&_mutex);
            if (!_requests.contains(request)) {fail();return;}const auto& value=_requests[request];
            const auto status=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute);
            append(value.owner,"reply-finished",{{"request",request},{"reply",value.reply},{"status",status},
                {"networkError",int(reply->error())},{"ticketActive",value.ticket.featureActive()}});
        });});
    }
    void append(const QString& owner,const QString& kind,const QVariantMap& detail={}) {
        if (_events.size()>=1024) {fail();return;}
        _events.append(QVariantMap{{"sequence",int(_events.size()+1)},{"upload",owner},{"kind",kind},{"capturedEpochMs",epoch()},{"detail",detail}});
    }
    QMutex _mutex;std::atomic<bool> _failed {false};qint64 _epoch {0};NativeReadBracket _bracket;
    QHash<QString,Upload> _uploads;QHash<QString,Resource> _resources;QHash<QString,Request> _requests;
    QHash<QString,Callback> _callbacks;QHash<QObject*,QString> _byObject;QVariantList _events;
};

class IOSSnapshotUploadCallback {
public:
    IOSSnapshotUploadCallback(const QString& owner,const QString& method,QNetworkReply* reply,bool finished,
            const overte::network::RequestTicket& current) noexcept : _book(IOSSnapshotUploadObservation::get()) {
#if defined(__cpp_exceptions) || defined(__EXCEPTIONS)
        try {if (_book && !owner.isEmpty()) {_stack=std::make_shared<int>(1);_id=_book->callbackEnter(owner,method,reply,finished,current,_stack);}}
        catch (...) {if (_book) {_book->incomplete();}}
#endif
    }
    ~IOSSnapshotUploadCallback() {if (_book) {_book->callbackLeave(_id);}}
    IOSSnapshotUploadCallback(const IOSSnapshotUploadCallback&)=delete;
    IOSSnapshotUploadCallback& operator=(const IOSSnapshotUploadCallback&)=delete;
private:
    IOSSnapshotUploadObservation* _book {nullptr};QString _id;std::shared_ptr<int> _stack;
};
} // namespace overte::e2e
#endif
