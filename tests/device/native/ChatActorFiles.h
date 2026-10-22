// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QUuid>
#include <initializer_list>
#include <cstdio>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QVariantMap>
#include <functional>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#endif

namespace overte::e2e {
// Dedicated owned Assignment Client IPC. This source accepts only native
// receive queries and closed dedicated-peer stimuli; never desired results.
class ChatActorFiles {
public:
    ChatActorFiles(const QString& directory,const QString& scriptSha,const QString& instance) : _path(directory) {
#if defined(Q_OS_UNIX)
        if (!QCoreApplication::arguments().contains("--testScript")
                || !QRegularExpression("\\A[0-9a-f]{64}\\z").match(scriptSha).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(instance).hasMatch()
                || !QFileInfo(directory).isAbsolute() || QDir::cleanPath(directory)!=directory
                || QFileInfo(directory).canonicalFilePath()!=directory) { return; }
        _root=::open(QFile::encodeName(_path).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if (!node(_root,true,&_rootNode) || !root()) { closeAll();return; }
        // A new actor must not adopt a previous process's files. The query may
        // be staged by the owner, but native output names must be absent.
        struct stat existing{};
        if (::fstatat(_root,"chat-actor-source.v1.json",&existing,AT_SYMLINK_NOFOLLOW)==0 || errno!=ENOENT
                || ::fstatat(_root,"feature-chat-observation.json",&existing,AT_SYMLINK_NOFOLLOW)==0 || errno!=ENOENT) { closeAll();return; }
        QJsonObject source{{"actorVersion",1},{"instance",instance},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"configuredEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"scriptSha256",scriptSha}};
        const auto bytes=QJsonDocument(source).toJson(QJsonDocument::Compact)+'\n';
        _source=::openat(_root,"chat-actor-source.v1.json",O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        if (!writeAll(_source,bytes) || ::fsync(_source)!=0 || !node(_source,false,&_sourceNode)
                || !same(_sourceNode,"chat-actor-source.v1.json")) { closeAll();return; }
        _available=true;
#else
        Q_UNUSED(scriptSha) Q_UNUSED(instance)
#endif
    }
    ~ChatActorFiles() { closeAll(); }
    bool available() const { return _available; }
    void tick(const std::function<QVariantMap(const QVariantMap&)>& observe) {
#if defined(Q_OS_UNIX)
        if (!_available || !observe) { return; }
        if (!root() || !same(_sourceNode,"chat-actor-source.v1.json")) { closeAll();return; }
        // After a real retired/empty reply, its owner may remove that original
        // output. Close the actual unlinked FD even when no next query exists.
        if (_result>=0 && !same(_resultNode,"feature-chat-observation.json")) {
            struct stat current{};
            if (_lastRetired && ::fstatat(_root,"feature-chat-observation.json",&current,AT_SYMLINK_NOFOLLOW)!=0 && errno==ENOENT) {
                ::close(_result);_result=-1;
            } else { closeAll();return; }
        }
        const auto raw=readCommand();
        if (raw.isEmpty()) { return; }
        QJsonParseError error;
        const auto document=QJsonDocument::fromJson(raw,&error);const auto request=document.object();
        const auto keys=request.keys();
        if (error.error!=QJsonParseError::NoError || !document.isObject() || raw!=document.toJson(QJsonDocument::Compact)+'\n'
                || QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","operation","runId"}
                || request.value("schemaVersion")!=QJsonValue(1) || (request.value("action")!=QJsonValue("feature-chat-observe") && request.value("action")!=QJsonValue("feature-chat-peer"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request.value("commandId").toString()).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request.value("runId").toString()).hasMatch()
                || (request.value("action")==QJsonValue("feature-chat-observe")
                    ? !QSet<QString>{"inspect","observe","retire"}.contains(request.value("operation").toString())
                    : !QSet<QString>{"inspect","lease","send-domain-reply","send-domain-hidden","send-local-reply","send-local-distant","restore"}.contains(request.value("operation").toString()))) { return; }
        const auto id=request.value("commandId").toString();
        if (id==_lastCommand) { return; }
        _lastCommand=id; // Never replay an uncertain cache-creation/retire query.
        const auto original=observe(request.toVariantMap());
        if (original.isEmpty() || original.value("commandId").toString()!=id || !root()) { return; }
        if (!writeResult(original)) { closeAll();return; }
        const auto source=original.value("source").toMap();
        _lastRetired=source.value("retired").userType()==QMetaType::Bool && source.value("retired").toBool()
            && !source.value("scopePresent").toBool() && source.value("events").toList().isEmpty();
#else
        Q_UNUSED(observe)
#endif
    }
private:
    QString _path,_lastCommand;
    bool _available{false},_lastRetired{false};
#if defined(Q_OS_UNIX)
    int _root{-1},_source{-1},_result{-1};
    struct stat _rootNode{},_sourceNode{},_resultNode{},_commandNode{};
    static bool node(int fd,bool directory,struct stat* result=nullptr) {
        struct stat value{};
        if (fd<0 || ::fstat(fd,&value)!=0 || value.st_uid!=::geteuid()
                || (value.st_mode&0777)!=(directory?0700:0600)
                || (directory?!S_ISDIR(value.st_mode):!S_ISREG(value.st_mode)||value.st_nlink!=1)) { return false; }
        if (result) { *result=value; } return true;
    }
    bool root() const {
        struct stat current{};
        return node(_root,true) && ::lstat(QFile::encodeName(_path).constData(),&current)==0
            && S_ISDIR(current.st_mode) && current.st_uid==::geteuid() && (current.st_mode&0777)==0700
            && current.st_dev==_rootNode.st_dev && current.st_ino==_rootNode.st_ino
            && QFileInfo(_path).canonicalFilePath()==_path;
    }
    bool same(const struct stat& original,const char* name) const {
        struct stat current{};
        return root() && ::fstatat(_root,name,&current,AT_SYMLINK_NOFOLLOW)==0 && S_ISREG(current.st_mode)
            && current.st_uid==::geteuid() && (current.st_mode&0777)==0600 && current.st_nlink==1
            && current.st_dev==original.st_dev && current.st_ino==original.st_ino && current.st_size==original.st_size
            && mtime(current)==mtime(original) && ctime(current)==ctime(original);
    }
    static qint64 mtime(const struct stat& value) {
#if defined(Q_OS_DARWIN)
        return static_cast<qint64>(value.st_mtimespec.tv_sec)*1000000000LL+value.st_mtimespec.tv_nsec;
#else
        return static_cast<qint64>(value.st_mtim.tv_sec)*1000000000LL+value.st_mtim.tv_nsec;
#endif
    }
    static qint64 ctime(const struct stat& value) {
#if defined(Q_OS_DARWIN)
        return static_cast<qint64>(value.st_ctimespec.tv_sec)*1000000000LL+value.st_ctimespec.tv_nsec;
#else
        return static_cast<qint64>(value.st_ctim.tv_sec)*1000000000LL+value.st_ctim.tv_nsec;
#endif
    }
    static QJsonObject identity(const struct stat& value) {
        // Device/inode identities must not lose precision through JSON doubles.
        return {{"device",QString::number(static_cast<qulonglong>(value.st_dev))},
            {"inode",QString::number(static_cast<qulonglong>(value.st_ino))}};
    }
    static bool writeAll(int fd,const QByteArray& bytes) {
        if (fd<0) { return false; }
        int done{0};
        while (done<bytes.size()) {
            const auto size=::write(fd,bytes.constData()+done,bytes.size()-done);
            if (size<0 && errno==EINTR) { continue; }
            if (size<=0) { return false; }done+=static_cast<int>(size);
        }
        return true;
    }
    QByteArray readCommand() {
        const int fd=::openat(_root,"chat-actor-command.v1.json",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        struct stat before{};
        if (!node(fd,false,&before) || before.st_size<1 || before.st_size>2048 || !same(before,"chat-actor-command.v1.json")) {
            if (fd>=0) { ::close(fd); }return {};
        }
        QByteArray bytes(static_cast<int>(before.st_size),'\0');int done{0};
        while (done<bytes.size()) {
            const auto size=::read(fd,bytes.data()+done,bytes.size()-done);
            if (size<0 && errno==EINTR) { continue; }if (size<=0) { break; }done+=static_cast<int>(size);
        }
        struct stat after{};const bool valid=node(fd,false,&after) && after.st_dev==before.st_dev && after.st_ino==before.st_ino
            && after.st_size==before.st_size && mtime(after)==mtime(before) && ctime(after)==ctime(before)
            && done==bytes.size() && same(before,"chat-actor-command.v1.json");
        ::close(fd);if (valid) { _commandNode=before; }return valid?bytes:QByteArray();
    }
    bool writeResult(const QVariantMap& originalFrame) {
        if (!root() || (_result>=0 && !same(_resultNode,"feature-chat-observation.json"))) { return false; }
        const auto temporary=(".chat-result-"+QUuid::createUuid().toString(QUuid::WithoutBraces)).toLatin1();
        const int fd=::openat(_root,temporary.constData(),O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        struct stat original{};
        bool okay=node(fd,false,&original);
        const QJsonObject envelope{{"actorFileVersion",1},{"commandNode",identity(_commandNode)},
            {"resultNode",identity(original)},{"native",QJsonObject::fromVariantMap(originalFrame)}};
        const auto bytes=QJsonDocument(envelope).toJson(QJsonDocument::Compact)+'\n';
        okay=okay && bytes.size()<=131072 && writeAll(fd,bytes) && ::fsync(fd)==0 && node(fd,false,&original) && root();
        if (okay) {
            if (_result<0) { // Exclusive first publication; never adopt another writer's result.
                okay=::linkat(_root,temporary.constData(),_root,"feature-chat-observation.json",0)==0;
            } else {
                okay=same(_resultNode,"feature-chat-observation.json")
                    && ::renameat(_root,temporary.constData(),_root,"feature-chat-observation.json")==0;
            }
        }
        ::unlinkat(_root,temporary.constData(),0);
        if (okay) { okay=node(fd,false,&original) && same(original,"feature-chat-observation.json"); }
        if (!okay) { if (fd>=0) { ::close(fd); }return false; }
        if (_result>=0) { ::close(_result); }
        _result=fd;_resultNode=original;return true;
    }
#endif
    void closeAll() {
#if defined(Q_OS_UNIX)
        for (auto fd:{&_result,&_source,&_root}) { if (*fd>=0) { ::close(*fd);*fd=-1; } }
#endif
        _available=false;
    }
};
} // namespace overte::e2e
#endif
