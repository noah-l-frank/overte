// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QElapsedTimer>
#include "../../../interface/src/ui/SnapshotStorage.h"
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QMap>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QUuid>
#include <QVariantMap>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <dirent.h>

namespace overte::e2e {
// Passive original QFile creation/descriptor/close callbacks. No file input,
// open flag, write, deletion or desired result is changed by this instrument.
class PhoneSnapshotCaptureFiles {
public:
    static PhoneSnapshotCaptureFiles& get() { static PhoneSnapshotCaptureFiles owner;return owner; }
    static QString& currentCapture() { static thread_local QString id;return id; }
    struct Scope {
        explicit Scope(const QString& id) : previous(currentCapture()) { currentCapture()=id; }
        ~Scope() { currentCapture()=previous; }
        QString previous;
    };
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    void begin(const QString& id) {
        if(!enabled() || id.isEmpty())return;
        QMutexLocker lock(&_mutex);
        if(!validId(id) || _captures.size()>=64 || _captures.contains(id)) { _complete=false;return; }
        _captures.insert(id,QVariantMap{{"captureId",id},{"event",++_event},{"beganEpochMs",now()},{"terminal",""},{"terminalPath",""},{"terminalEpochMs",0}});
    }
    void terminal(const QString& id,const QString& phase,const QString& path) {
        if(!enabled() || !QStringList{"complete","error","cancelled"}.contains(phase))return;
        QMutexLocker lock(&_mutex);auto found=_captures.find(id);
        // Original rejected/busy requests never acquired capture/file ownership.
        if(found==_captures.end())return;
        if(!found->value("terminal").toString().isEmpty()) { _complete=false;return; }
        found->insert("terminal",phase);found->insert("terminalPath",path);found->insert("terminalEpochMs",now());
    }
    QString opening(const QString& path,const QString& root) {
        if(!enabled() || currentCapture().isEmpty())return {};
        QMutexLocker lock(&_mutex);
        const QFileInfo directory(root),file(path);const auto canonical=directory.canonicalFilePath();
        if(!_complete || !_captures.contains(currentCapture()) || _rows.size()>=64 || !directory.isDir() || directory.isSymLink()
                || canonical.isEmpty() || QDir::cleanPath(file.absolutePath())!=QDir::cleanPath(directory.absoluteFilePath())
                || file.fileName().isEmpty() || file.fileName().size()>255 || file.fileName()=="." || file.fileName()=="..") { _complete=false;return {}; }
        const auto actual=QDir(canonical).filePath(file.fileName());
        struct stat parent{},previous{};
        if(::lstat(QFile::encodeName(canonical).constData(),&parent)!=0 || !S_ISDIR(parent.st_mode) || parent.st_uid!=::getuid()) { _complete=false;return {}; }
        errno=0;const bool exists=::lstat(QFile::encodeName(actual).constData(),&previous)==0;
        if(!exists && errno!=ENOENT) { _complete=false;return {}; }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        Row row;row.capture=currentCapture();row.path=actual;row.preexisting=exists;row.rootDevice=parent.st_dev;row.rootInode=parent.st_ino;row.created=now();
        for(auto it=_plans.cbegin();it!=_plans.cend();++it) {
            const auto plan=it.value();
            if(file.fileName().startsWith(plan.value("prefix").toString()+"-")) {
                if(plan.value("sealed").toBool())_complete=false;
                if(!row.plan.isEmpty()) { _complete=false;return {}; }
                if(plan.value("rootPresent").toBool() && (plan.value("rootDevice").toULongLong()!=row.rootDevice || plan.value("rootInode").toULongLong()!=row.rootInode)) { _complete=false;return {}; }
                if(_captures.value(row.capture).value("event").toULongLong()>plan.value("event").toULongLong()) {
                    row.plan=it.key();row.run=plan.value("runId").toString();
                }
            }
        }
        if(!row.plan.isEmpty())for(const auto& older:_rows)if(older.plan==row.plan && (older.rootDevice!=row.rootDevice || older.rootInode!=row.rootInode)) { _complete=false;return {}; }
        _rows.insert(id,row);return id;
    }
    void opened(const QString& id,int descriptor) {
        if(id.isEmpty())return;QMutexLocker lock(&_mutex);auto found=_rows.find(id);
        if(found==_rows.end() || found->phase!="opening" || descriptor<0) { _complete=false;return; }
        struct stat actual{},path{};
        if(::fstat(descriptor,&actual)!=0 || ::lstat(QFile::encodeName(found->path).constData(),&path)!=0
                || !S_ISREG(actual.st_mode) || actual.st_uid!=::getuid() || actual.st_nlink!=1
                || actual.st_dev!=path.st_dev || actual.st_ino!=path.st_ino || !S_ISREG(path.st_mode)) { _complete=false;return; }
        found->descriptor=descriptor;found->device=actual.st_dev;found->inode=actual.st_ino;found->uid=actual.st_uid;
        found->links=actual.st_nlink;found->opened=true;found->phase="writing";
    }
    void openFailed(const QString& id) {
        if(id.isEmpty())return;QMutexLocker lock(&_mutex);auto found=_rows.find(id);
        if(found==_rows.end() || found->phase!="opening") { _complete=false;return; }
        found->closed=true;found->phase="open-failed";found->closedEpoch=now();
    }
    void beforeClose(const QString& id,int descriptor) {
        if(id.isEmpty())return;QMutexLocker lock(&_mutex);auto found=_rows.find(id);struct stat actual{};
        if(found==_rows.end() || found->phase!="writing" || descriptor!=found->descriptor || ::fstat(descriptor,&actual)!=0
                || actual.st_dev!=found->device || actual.st_ino!=found->inode || actual.st_uid!=found->uid
                || actual.st_nlink!=1 || !S_ISREG(actual.st_mode) || actual.st_size<0 || actual.st_size>256LL*1024*1024) { _complete=false;return; }
        found->bytes=actual.st_size;found->phase="closing";
    }
    void closed(const QString& id,bool objectStillOpen) {
        if(id.isEmpty())return;QMutexLocker lock(&_mutex);auto found=_rows.find(id);
        if(found==_rows.end() || found->phase!="closing") { _complete=false;return; }
        errno=0;bool closed=::fcntl(found->descriptor,F_GETFD)==-1 && errno==EBADF;
        if(!closed) {
            struct stat current{};
            closed=::fstat(found->descriptor,&current)==0 && (current.st_dev!=found->device || current.st_ino!=found->inode);
        }
        found->closed=!objectStillOpen && closed;found->phase=found->closed ? "closed" : "closing";
        if(found->closed) {
            struct stat actual{};
            if(::lstat(QFile::encodeName(found->path).constData(),&actual)!=0 || actual.st_dev!=found->device || actual.st_ino!=found->inode
                    || !S_ISREG(actual.st_mode) || actual.st_uid!=found->uid || actual.st_nlink!=1 || actual.st_size<0 || actual.st_size>256LL*1024*1024) { _complete=false;return; }
            found->bytes=actual.st_size;found->closedEpoch=now();
            if(!fingerprint(*found,found->sha256))_complete=false;
        }
    }
    void removed(const QString& id,bool actualReturn) {
        if(id.isEmpty())return;QMutexLocker lock(&_mutex);auto found=_rows.find(id);
        if(found==_rows.end() || !found->closed || found->removeAttempts>=4 || found->nativeRemoved && actualReturn) { _complete=false;return; }
        if(found->nativeRemoved) {
            struct stat current{};errno=0;
            if(::lstat(QFile::encodeName(found->path).constData(),&current)==0 || errno!=ENOENT) { _complete=false;return; }
        }
        ++found->removeAttempts;found->removeAttempted=true;found->nativeRemoved=found->nativeRemoved || actualReturn;
    }
    bool plan(const QString& run,const QString& prefix,const QString& id,const QString& root) {
        QMutexLocker lock(&_mutex);
        if(!enabled() || !_complete || !nonce(run) || !nonce(id)
                || !QRegularExpression("\\A(?:e2e-[0-9a-f]{32}(?:-[A-Za-z0-9_-]{1,11})?|parity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap))\\z").match(prefix).hasMatch() || prefix.size()>48)return false;
        auto prior=_plans.find(id);
        if(prior!=_plans.end())return prior->value("runId")==run && prior->value("prefix")==prefix;
        if(_plans.size()>=64 || _operations.contains(id))return false;
        for(const auto& existing:_plans) {
            const auto older=existing.value("prefix").toString();
            if(older==prefix || older.startsWith(prefix+"-") || prefix.startsWith(older+"-"))return false;
        }
        const QFileInfo directory(root);quint64 device=0,inode=0;struct stat actual{};
        if(root.isEmpty())return false;errno=0;
        const bool rootPresent=::lstat(QFile::encodeName(root).constData(),&actual)==0;
        if(!rootPresent && errno!=ENOENT)return false;
        if(rootPresent) {
            if(!S_ISDIR(actual.st_mode) || actual.st_uid!=::getuid() || !prefixAbsent(root,prefix,actual.st_dev,actual.st_ino))return false;
            device=actual.st_dev;inode=actual.st_ino;
        }
        _plans.insert(id,{{"id",id},{"runId",run},{"prefix",prefix},{"event",++_event},{"checkedEpochMs",now()},
            {"rootPresent",rootPresent},{"rootDevice",device},{"rootInode",inode},{"sealed",false},{"sealId",""},{"sealedEpochMs",0}});
        _planPaths.insert(id,root);return true;
    }
    bool retire(const QString& run,const QString& id,const QString& operation) {
        QMutexLocker lock(&_mutex);auto found=_rows.find(id);
        if(!enabled() || !_complete || !nonce(run) || !nonce(operation) || found==_rows.end() || found->run!=run || found->plan.isEmpty()
                || found->preexisting || !found->closed || !QStringList{"closed","open-failed"}.contains(found->phase))return false;
        for(const auto& capture:_captures)if(capture.value("terminal").toString().isEmpty())return false;
        for(const auto& row:_rows)if(!row.closed)return false;
        if(_plans.contains(operation) || _operations.contains(operation) && _operations.value(operation)!=id)return false;
        if(!found->retireId.isEmpty()) {
            if(found->retireId!=operation)return false;return inspect(*found);
        }
        if(found->nativeRemoved || !found->opened) {
            if(!absent(*found))return false;
            found->retireId=operation;_operations.insert(operation,id);return inspect(*found);
        }
        QString actual;if(!fingerprint(*found,actual) || actual!=found->sha256)return false;
        // Supported exclusion is this exclusive namespace and cooperating
        // original producer hooks. POSIX unlink is not inode-conditional against
        // arbitrary external writers; observed replacements remain owned/red.
        found->retireId=operation;_operations.insert(operation,id);found->deleteIssued=true;
        found->deleteResult=::unlink(QFile::encodeName(found->path).constData());
        return inspect(*found);
    }
    bool seal(const QString& run,const QString& id,const QString& operation) {
        QMutexLocker lock(&_mutex);auto found=_plans.find(id);
        if(!enabled() || !_complete || found==_plans.end() || found->value("runId")!=run || !nonce(operation)
                || _plans.contains(operation) || _operations.contains(operation) && _operations.value(operation)!="plan-"+id)return false;
        if(found->value("sealed").toBool())return found->value("sealId")==operation && namespaceAbsent(id);
        for(const auto& row:_rows)if(!row.closed || row.plan==id && (row.retireId.isEmpty() || !row.absentNow))return false;
        for(const auto& capture:_captures)if(capture.value("terminal").toString().isEmpty())return false;
        if(!namespaceAbsent(id))return false;
        found->insert("sealed",true);found->insert("sealId",operation);found->insert("sealedEpochMs",now());
        _operations.insert(operation,"plan-"+id);return true;
    }
    void removedPath(const QString& path,bool actualReturn) {
        if(!enabled())return;
        QString selected;
        { QMutexLocker lock(&_mutex);for(auto it=_rows.cbegin();it!=_rows.cend();++it)if(it->path==path) { if(!selected.isEmpty()) { _complete=false;return; }selected=it.key(); } }
        if(!selected.isEmpty())removed(selected,actualReturn);
    }
    QVariantMap snapshot() {
        if(!enabled())return {};
        QMutexLocker lock(&_mutex);QVariantList rows,captures,plans;
        for(auto it=_plans.cbegin();it!=_plans.cend();++it) {
            if(it->value("sealed").toBool() && !namespaceAbsent(it.key()))_complete=false;
            plans.append(it.value());
        }
        for(auto it=_rows.begin();it!=_rows.end();++it) {
            if(!it->retireId.isEmpty() && !inspect(it.value()))_complete=false;
            rows.append(it->view(it.key()));
        }
        for(const auto& capture:_captures)captures.append(capture);
        const auto epoch=now();
        return {{"phoneSnapshotCaptureFilesVersion",1},{"instance",_instance},{"complete",_complete},
            {"sequence",++_sequence},{"capturedEpochMs",epoch},{"rows",rows},{"captures",captures},{"plans",plans}};
    }
private:
    struct Row {
        QString capture,path,plan,run,sha256,retireId,phase{"opening"};int removeAttempts{0},deleteResult{-2};bool deleteIssued{false},absentNow{false};qint64 checked{0};bool preexisting{false},opened{false},closed{false},removeAttempted{false},nativeRemoved{false};
        int descriptor{-1};quint64 rootDevice{0},rootInode{0},device{0},inode{0},uid{0},links{0};qint64 bytes{0},created{0},closedEpoch{0};
        QVariantMap view(const QString& id) const {
            return {{"id",id},{"captureId",capture},{"path",path},{"planId",plan},{"runId",run},{"sha256",sha256},{"retireId",retireId},{"deleteIssued",deleteIssued},{"deleteResult",deleteResult},{"absent",absentNow},{"checkedEpochMs",checked},{"phase",phase},{"preexisting",preexisting},
                {"rootDevice",rootDevice},{"rootInode",rootInode},{"device",device},{"inode",inode},{"uid",uid},{"links",links},
                {"opened",opened},{"closed",closed},{"bytes",bytes},{"createdEpochMs",created},{"closedEpochMs",closedEpoch},
                {"removeAttempted",removeAttempted},{"removeAttempts",removeAttempts},{"nativeRemoved",nativeRemoved}};
        }
    };
    PhoneSnapshotCaptureFiles() : _instance(QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')) {}
    static bool nonce(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static bool fingerprint(const Row& row,QString& sha) {
        struct stat root{},before{},after{},path{};
        const auto parent=QFile::encodeName(QFileInfo(row.path).absolutePath()),name=QFile::encodeName(row.path);
        if(::lstat(parent.constData(),&root)!=0 || !S_ISDIR(root.st_mode) || root.st_dev!=row.rootDevice || root.st_ino!=row.rootInode)return false;
        const int fd=::open(name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)return false;
        bool valid=::fstat(fd,&before)==0 && S_ISREG(before.st_mode) && before.st_dev==row.device && before.st_ino==row.inode
            && before.st_uid==row.uid && before.st_nlink==1 && before.st_size==row.bytes;
        QCryptographicHash hash(QCryptographicHash::Sha256);QElapsedTimer timer;timer.start();qint64 total=0;char bytes[65536];
        while(valid) {
            const auto count=::read(fd,bytes,sizeof(bytes));
            if(count<0 && errno==EINTR && timer.elapsed()<15000)continue;
            if(count<0 || timer.elapsed()>=15000 || total+count>256LL*1024*1024) { valid=false;break; }
            if(count==0)break;total+=count;hash.addData(QByteArray(bytes,int(count)));
        }
        valid=valid && total==row.bytes && ::fstat(fd,&after)==0 && after.st_dev==before.st_dev && after.st_ino==before.st_ino && after.st_size==before.st_size
            && ::lstat(name.constData(),&path)==0 && path.st_dev==row.device && path.st_ino==row.inode && path.st_nlink==1 && S_ISREG(path.st_mode);
        const bool closed=::close(fd)==0;
        if(!valid || !closed)return false;sha=QString::fromLatin1(hash.result().toHex());return true;
    }
    static bool absent(const Row& row) {
        struct stat root{},path{};const auto parent=QFile::encodeName(QFileInfo(row.path).absolutePath());
        if(::lstat(parent.constData(),&root)!=0 || root.st_dev!=row.rootDevice || root.st_ino!=row.rootInode || !S_ISDIR(root.st_mode))return false;
        errno=0;return ::lstat(QFile::encodeName(row.path).constData(),&path)==-1 && errno==ENOENT;
    }
    bool inspect(Row& row) {
        const bool current=absent(row);if(!current && row.absentNow)return false;
        row.absentNow=current;row.checked=now();return current;
    }
    static bool prefixAbsent(const QString& root,const QString& prefix,quint64 device,quint64 inode) {
        const auto encoded=QFile::encodeName(root),start=prefix.toUtf8();DIR* directory=::opendir(encoded.constData());if(!directory)return false;
        struct stat opened{},current{};bool valid=::fstat(::dirfd(directory),&opened)==0 && opened.st_dev==device && opened.st_ino==inode && S_ISDIR(opened.st_mode);
        while(valid) {
            errno=0;const auto entry=::readdir(directory);
            if(!entry) { valid=errno==0;break; }
            const QByteArray name(entry->d_name);if(name!="." && name!=".." && name.startsWith(start)) { valid=false;break; }
        }
        const bool closed=::closedir(directory)==0;
        return valid && closed && ::lstat(encoded.constData(),&current)==0 && current.st_dev==device && current.st_ino==inode && S_ISDIR(current.st_mode);
    }
    bool namespaceAbsent(const QString& id) const {
        const auto plan=_plans.value(id);const auto root=_planPaths.value(id);
        if(root.isEmpty())return false;struct stat actual{};errno=0;
        if(::lstat(QFile::encodeName(root).constData(),&actual)!=0)return errno==ENOENT && !plan.value("rootPresent").toBool();
        if(!S_ISDIR(actual.st_mode) || actual.st_uid!=::getuid())return false;
        if(plan.value("rootPresent").toBool() && (actual.st_dev!=plan.value("rootDevice").toULongLong() || actual.st_ino!=plan.value("rootInode").toULongLong()))return false;
        for(const auto& row:_rows)if(row.plan==id && (actual.st_dev!=row.rootDevice || actual.st_ino!=row.rootInode))return false;
        return prefixAbsent(root,plan.value("prefix").toString(),actual.st_dev,actual.st_ino);
    }
    static bool validId(const QString& id) { return QRegularExpression("\\A[A-Za-z0-9_-]{1,64}\\z").match(id).hasMatch(); }
    qint64 now() { const auto value=QDateTime::currentMSecsSinceEpoch();if(value<=0 || value<_epoch)_complete=false;_epoch=value;return value; }
    QMutex _mutex;QString _instance;bool _complete{true};quint64 _sequence{0},_event{0};qint64 _epoch{0};
    QMap<QString,QString> _operations,_planPaths;QMap<QString,QVariantMap> _plans;QMap<QString,Row> _rows;QMap<QString,QVariantMap> _captures;
};
inline QVariantMap phoneSnapshotCaptureFileObservation(const QVariantMap& command,const QString& instance,quint64& sequence) {
    const auto json=QJsonObject::fromVariantMap(command);
    const auto id=json.value("commandId").toString(),run=json.value("runId").toString();
    const QRegularExpression nonce("\\A[0-9a-f]{32}\\z");
    const bool control=json.value("action")==QJsonValue("phone-snapshot-files-control");
    QStringList keys{"action","commandId","runId","schemaVersion"};if(control)keys.append({"operation","prefix","fileId","operationId"});keys.sort();
    if(!PhoneSnapshotCaptureFiles::enabled() || command.keys()!=keys
            || json.value("schemaVersion")!=QJsonValue(1) || (!control && json.value("action")!=QJsonValue("phone-snapshot-files-observe"))
            || !nonce.match(id).hasMatch() || !nonce.match(run).hasMatch() || !nonce.match(instance).hasMatch())return {};
    const auto requested=QDateTime::currentMSecsSinceEpoch();
    bool accepted=true;auto& owner=PhoneSnapshotCaptureFiles::get();
    if(control) {
        if(!json.value("operation").isString() || !json.value("prefix").isString() || !json.value("fileId").isString() || !json.value("operationId").isString())return {};
        const auto operation=json.value("operation").toString(),prefix=json.value("prefix").toString(),file=json.value("fileId").toString(),opId=json.value("operationId").toString();
        if(!nonce.match(opId).hasMatch())return {};
        if(operation=="plan" && file.isEmpty())accepted=owner.plan(run,prefix,opId,overte::snapshot::storageRoot());
        else if(operation=="retire" && prefix.isEmpty() && nonce.match(file).hasMatch())accepted=owner.retire(run,file,opId);
        else if(operation=="seal" && prefix.isEmpty() && nonce.match(file).hasMatch())accepted=owner.seal(run,file,opId);
        else return {};
    }
    const auto original=owner.snapshot();if(original.isEmpty())return {};
    return {{"schemaVersion",1},{"requestId",id},{"runId",run},{"instance",instance},{"sequence",++sequence},
        {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},
        {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"accepted",accepted},{"source",original}};
}
} // namespace overte::e2e
#endif
