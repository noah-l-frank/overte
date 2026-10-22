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
#include <QThread>
#include <mutex>
#include <QVariantMap>
#include <functional>
#include <cmath>
#include "ChatPeerPosition.h"
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#endif

namespace overte::e2e {
// Dedicated owned Assignment Client IPC. Observation accepts only native
// read/inspect/retire queries. A distinct opt-in private fixture input channel
// never supplies observations or requested delivery/position results.
class ChatActorFiles {
public:
    ChatActorFiles(const QString& directory,const QString& scriptSha,const QString& instance,
            std::function<QVariantMap()> avatarPosition={}) : _path(directory),_avatarPosition(std::move(avatarPosition)) {
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
                || ::fstatat(_root,"feature-chat-observation.json",&existing,AT_SYMLINK_NOFOLLOW)==0 || errno!=ENOENT
                || ::fstatat(_root,"chat-peer-input-receipt.v1.json",&existing,AT_SYMLINK_NOFOLLOW)==0 || errno!=ENOENT) { closeAll();return; }
        QString configuredRevision;
#if defined(OVERTE_E2E_CONFIGURED_SOURCE_REVISION)
        configuredRevision=QString::fromLatin1(OVERTE_E2E_CONFIGURED_SOURCE_REVISION);
#endif
        const bool knownRevision=QRegularExpression("\\A[0-9a-f]{40}\\z").match(configuredRevision).hasMatch();
        if (!knownRevision) { configuredRevision.clear(); }
        const QJsonObject build{{"cleanConfiguredSource",knownRevision},{"compiledSourceRevision",configuredRevision}};
        QJsonObject source{{"actorVersion",2},{"instance",instance},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"configuredEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"scriptSha256",scriptSha},{"build",build}};
        const auto bytes=QJsonDocument(source).toJson(QJsonDocument::Compact)+'\n';
        _source=::openat(_root,"chat-actor-source.v1.json",O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        if (!writeAll(_source,bytes) || ::fsync(_source)!=0 || !node(_source,false,&_sourceNode)
                || !same(_sourceNode,"chat-actor-source.v1.json")) { closeAll();return; }
        _available=true;
#else
        Q_UNUSED(scriptSha) Q_UNUSED(instance)
#endif
    }
    ~ChatActorFiles() { std::lock_guard<std::recursive_mutex> lock(_mutex);closeAll(); }
    bool available() const {
        std::lock_guard<std::recursive_mutex> lock(_mutex);return QThread::currentThread()==_ownerThread && _available;
    }
    // A separate opt-in fixture INPUT path. Consumption is never a position,
    // delivery or restoration observation. The original peer script performs
    // ordinary Avatar/ Messages operations after this call returns.
    QVariantMap takeInput(bool scriptPoll=true) {
        std::lock_guard<std::recursive_mutex> lock(_mutex);
        if (QThread::currentThread()!=_ownerThread) { return {}; }
#if defined(Q_OS_UNIX)
        if (!_available || !root() || !same(_sourceNode,"chat-actor-source.v1.json")) { return {}; }
        if (scriptPoll) { if (_scriptPolls>=9007199254740991LL) { closeAll();return {}; }++_scriptPolls; }
        const auto raw=readCommand("chat-peer-input.v1.json");
        QJsonParseError error;const auto document=QJsonDocument::fromJson(raw,&error);
        const auto value=document.object();const auto operation=value.value("operation").toString();
        QSet<QString> required{"schemaVersion","commandId","runId","operation"};
        if (operation=="hold") { required.insert("position"); }
        else if (operation=="send") { required.insert("channel");required.insert("textKey"); }
        else if (operation!="restore" && operation!="release" && operation!="inspect") { return {}; }
        if (!scriptPoll && operation!="inspect") { return {}; }
        const auto keys=value.keys();const auto id=value.value("commandId").toString();const auto run=value.value("runId").toString();
        if (error.error!=QJsonParseError::NoError || !document.isObject() || raw!=document.toJson(QJsonDocument::Compact)+'\n'
                || QSet<QString>(keys.begin(),keys.end())!=required || value.value("schemaVersion")!=QJsonValue(1)
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || (!_inputRun.isEmpty() && _inputRun!=run) || _inputs.contains(id) || _inputs.size()>=4096
                || (_inputReleased && operation!="inspect")) { return {}; }
        if (operation=="hold") {
            const auto position=value.value("position").toObject();const auto coordinates=position.keys();
            if (QSet<QString>(coordinates.begin(),coordinates.end())!=QSet<QString>{"x","y","z"}) { return {}; }
            for (const auto key:{"x","y","z"}) {
                const auto coordinate=position.value(key);
                if (!coordinate.isDouble() || !std::isfinite(coordinate.toDouble()) || std::abs(coordinate.toDouble())>100000) { return {}; }
            }
        } else if (operation=="send" && ((value.value("channel")!="local" && value.value("channel")!="domain")
                || (value.value("textKey")!="reply" && value.value("textKey")!="hidden"))) { return {}; }
        const auto originalAvatar=_avatarPosition?_avatarPosition():QVariantMap();
        const auto session=originalAvatar.value("sessionId");const auto position=originalAvatar.value("position").toMap();
        if (originalAvatar.size()!=2 || session.userType()!=QMetaType::QUuid || session.toUuid().isNull()
                || !ChatPeerPosition::position(position)) { return {}; }
        // Admit once before publishing consumption or returning to script.
        _inputs.insert(id);_inputRun=run;
        if (operation=="release") { _inputReleased=true; }
        const QVariantMap receipt{{"peerInputVersion",3},{"commandId",id},{"runId",run},{"operation",operation},
            {"instance",_inputInstance},{"sequence",_inputs.size()},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"avatarSha256",ChatPeerPosition::identity(run,session.toUuid())},{"avatarPosition",position},
            {"scriptPolls",_scriptPolls},{"releaseConsumed",_inputReleased}};
        if (!writeResult(receipt,"chat-peer-input-receipt.v1.json",_inputResult,_inputResultNode,_commandNode)) { closeAll();return {}; }
        return value.toVariantMap();
#else
        return {};
#endif
    }
    void tick(const std::function<QVariantMap(const QVariantMap&)>& observe) {
        std::lock_guard<std::recursive_mutex> lock(_mutex);
        if (QThread::currentThread()!=_ownerThread) { return; }
#if defined(Q_OS_UNIX)
        if (!_available || !observe) { return; }
        if (!root() || !same(_sourceNode,"chat-actor-source.v1.json")) { closeAll();return; }
        // Passive inspect remains available after the original script stops
        // polling its input route. Timer reads never advance that actual poll
        // counter and can never consume a mutating command.
        takeInput(false);if (!_available) { return; }
        if (_inputResult>=0 && !same(_inputResultNode,"chat-peer-input-receipt.v1.json")) {
            struct stat current{};
            if (_inputReleased && ::fstatat(_root,"chat-peer-input-receipt.v1.json",&current,AT_SYMLINK_NOFOLLOW)!=0 && errno==ENOENT) {
                ::close(_inputResult);_inputResult=-1;
            } else { closeAll();return; }
        }
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
                || request.value("schemaVersion")!=QJsonValue(1) || request.value("action")!=QJsonValue("feature-chat-observe")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request.value("commandId").toString()).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(request.value("runId").toString()).hasMatch()
                || (request.value("operation")!=QJsonValue("inspect") && request.value("operation")!=QJsonValue("observe") && request.value("operation")!=QJsonValue("retire"))) { return; }
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
    mutable std::recursive_mutex _mutex;
    QThread* const _ownerThread{QThread::currentThread()};
    QString _path,_lastCommand;
    QString _inputRun,_inputInstance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QSet<QString> _inputs;
    qint64 _scriptPolls{0};
    std::function<QVariantMap()> _avatarPosition;
    bool _inputReleased{false};
    bool _available{false},_lastRetired{false};
#if defined(Q_OS_UNIX)
    int _root{-1},_source{-1},_result{-1},_inputResult{-1};
    struct stat _rootNode{},_sourceNode{},_resultNode{},_commandNode{},_inputResultNode{};
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
    QByteArray readCommand(const char* name="chat-actor-command.v1.json") {
        const int fd=::openat(_root,name,O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
        struct stat before{};
        if (!node(fd,false,&before) || before.st_size<1 || before.st_size>2048 || !same(before,name)) {
            if (fd>=0) { ::close(fd); }return {};
        }
        QByteArray bytes(static_cast<int>(before.st_size),'\0');int done{0};
        while (done<bytes.size()) {
            const auto size=::read(fd,bytes.data()+done,bytes.size()-done);
            if (size<0 && errno==EINTR) { continue; }if (size<=0) { break; }done+=static_cast<int>(size);
        }
        struct stat after{};const bool valid=node(fd,false,&after) && after.st_dev==before.st_dev && after.st_ino==before.st_ino
            && after.st_size==before.st_size && mtime(after)==mtime(before) && ctime(after)==ctime(before)
            && done==bytes.size() && same(before,name);
        ::close(fd);if (valid) { _commandNode=before; }return valid?bytes:QByteArray();
    }
    // Called only under the original owner's mutex, after timer-driven FD
    // retirement. No input command, poll, observer or resource is created here.
    bool inputLifetime(const QVariantMap& frame,QJsonObject& result) const {
        const auto pathState=[&](const char* name,QJsonObject& state) {
            struct stat current{};
            if (::fstatat(_root,name,&current,AT_SYMLINK_NOFOLLOW)!=0) {
                if (errno!=ENOENT) { return false; }
                state={{"present",false},{"node",QJsonObject()}};return true;
            }
            if (!S_ISREG(current.st_mode) || current.st_uid!=::geteuid()
                    || (current.st_mode&0777)!=0600 || current.st_nlink!=1) { return false; }
            state={{"present",true},{"node",identity(current)}};return true;
        };
        QJsonObject command,receipt,handle;
        if (!root() || !pathState("chat-peer-input.v1.json",command)
                || !pathState("chat-peer-input-receipt.v1.json",receipt)) { return false; }
        if (_inputResult>=0) {
            struct stat current{};
            if (!node(_inputResult,false,&current) || current.st_dev!=_inputResultNode.st_dev
                    || current.st_ino!=_inputResultNode.st_ino || !same(_inputResultNode,"chat-peer-input-receipt.v1.json")) { return false; }
            handle={{"open",true},{"node",identity(current)}};
        } else { handle={{"open",false},{"node",QJsonObject()}}; }
        result={{"inputLifetimeVersion",1},{"commandId",frame.value("commandId").toString()},
            {"runId",frame.value("runId").toString()},{"instance",_inputInstance},{"ownerRunId",_inputRun},
            {"sequence",_inputs.size()},{"scriptPolls",static_cast<double>(_scriptPolls)},{"releaseConsumed",_inputReleased},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"command",command},{"receipt",receipt},{"receiptHandle",handle}};
        return root();
    }
    bool writeResult(const QVariantMap& originalFrame) {
        QJsonObject lifetime;
        if (!inputLifetime(originalFrame,lifetime)) { return false; }
        return writeResult(originalFrame,"feature-chat-observation.json",_result,_resultNode,_commandNode,lifetime);
    }
    bool writeResult(const QVariantMap& originalFrame,const char* name,int& result,struct stat& resultNode,const struct stat& commandNode,const QJsonObject& lifetime={}) {
        if (!root() || (result>=0 && !same(resultNode,name))) { return false; }
        const auto temporary=(".chat-result-"+QUuid::createUuid().toString(QUuid::WithoutBraces)).toLatin1();
        const int fd=::openat(_root,temporary.constData(),O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        struct stat original{};
        bool okay=node(fd,false,&original);
        QJsonObject envelope{{"actorFileVersion",1},{"commandNode",identity(commandNode)},
            {"resultNode",identity(original)},{"native",QJsonObject::fromVariantMap(originalFrame)}};
        if (!lifetime.isEmpty()) { envelope.insert("inputLifetime",lifetime); }
        const auto bytes=QJsonDocument(envelope).toJson(QJsonDocument::Compact)+'\n';
        okay=okay && bytes.size()<=131072 && writeAll(fd,bytes) && ::fsync(fd)==0 && node(fd,false,&original) && root();
        if (okay) {
            if (result<0) { // Exclusive first publication; never adopt another writer's result.
                okay=::linkat(_root,temporary.constData(),_root,name,0)==0;
            } else {
                okay=same(resultNode,name) && ::renameat(_root,temporary.constData(),_root,name)==0;
            }
        }
        ::unlinkat(_root,temporary.constData(),0);
        if (okay) { okay=node(fd,false,&original) && same(original,name); }
        if (!okay) { if (fd>=0) { ::close(fd); }return false; }
        if (result>=0) { ::close(result); }
        result=fd;resultNode=original;return true;
    }
#endif
    void closeAll() {
#if defined(Q_OS_UNIX)
        for (auto fd:{&_inputResult,&_result,&_source,&_root}) { if (*fd>=0) { ::close(*fd);*fd=-1; } }
#endif
        _available=false;
    }
};
} // namespace overte::e2e
#endif
