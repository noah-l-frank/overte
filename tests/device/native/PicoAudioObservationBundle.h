// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include "PicoRemoteAvatarStreamFile.h"
#include <QElapsedTimer>
#include <QDateTime>
#include <QJsonDocument>
#include <QMutex>
#include <QMutexLocker>
#include <QHash>
#include <QSet>
#include <QRegularExpression>
#include <exception>
#include <memory>

namespace overte::e2e {
struct PicoAudioBundleRequest {
    const QVariantMap command;
    const qint64 epoch{QDateTime::currentMSecsSinceEpoch()};
    QElapsedTimer elapsed;
    explicit PicoAudioBundleRequest(const QVariantMap& value):command(value) {elapsed.start();}
    bool fresh() const {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        return epoch>0 && now>=epoch && now-epoch<1500 && elapsed.isValid() && elapsed.elapsed()>=0 && elapsed.elapsed()<1500;
    }
    static bool valid(const QVariantMap& value) {
        const auto keys=value.keys();
        if(QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","action","commandId","runId","nativeNonce","settingsNonce"})return false;
        const auto schema=value.value("schemaVersion");
        if((schema.userType()!=QMetaType::Int && schema.userType()!=QMetaType::Double) || schema.toDouble()!=1)return false;
        for(const auto* key:{"action","commandId","runId","nativeNonce","settingsNonce"})if(value.value(key).userType()!=QMetaType::QString)return false;
        if(value.value("action").toString()!="feature-pico-audio-observation-bundle")return false;
        const auto nonce=QRegularExpression("\\A[0-9a-f]{32}\\z");
        for(const auto* key:{"commandId","runId","nativeNonce","settingsNonce"})if(!nonce.match(value.value(key).toString()).hasMatch())return false;
        return value.value("nativeNonce")!=value.value("settingsNonce") && value.value("nativeNonce")!=value.value("commandId")
            && value.value("settingsNonce")!=value.value("commandId");
    }
    static std::shared_ptr<const PicoAudioBundleRequest> original(const QVariantMap& value) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !valid(value))return {};
        struct Record {QByteArray bytes;std::shared_ptr<const PicoAudioBundleRequest> request;};
        static QMutex mutex;static QHash<QString,Record> records;
        const auto id=value.value("commandId").toString();const auto bytes=QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
        QMutexLocker lock(&mutex);
        if(records.contains(id))return records[id].bytes==bytes ? records[id].request : std::shared_ptr<const PicoAudioBundleRequest>();
        if(records.size()>=512)return {};
        const auto request=std::make_shared<const PicoAudioBundleRequest>(value);records.insert(id,{bytes,request});return request;
    }
};

// Explicit readonly source composition. A caller must prebook the additional
// fixed4MiB native carrier/work declaration in its SAME original Host family
// before its first command. This source does not mint an admission token.
class PicoAudioObservationBundle {
    struct UiOriginal {
        PicoStreamDescriptor root,file;
        PicoStreamDescriptor::CheckedCloseResult fileClose,rootClose;
        QByteArray raw;struct stat rootStamp{},fileStamp{};
        bool acquired{false},closed{false};
        bool directory(const QString& path) {
            struct stat held{},named{};
            return root.require() && !::fstat(root.fd(),&held) && !::lstat(QFile::encodeName(path).constData(),&named)
                && S_ISDIR(held.st_mode) && held.st_uid==::geteuid() && (held.st_mode&0777)==0700
                && held.st_dev==named.st_dev && held.st_ino==named.st_ino && held.st_uid==named.st_uid && held.st_mode==named.st_mode;
        }
        bool read(const QString& path) {
            if(!QDir::isAbsolutePath(path) || path.contains(QChar(0)) || QDir::cleanPath(path)!=path
                    || QFileInfo(path).canonicalFilePath()!=path
                    || !root.open(QFile::encodeName(path),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC)
                    || !directory(path) || ::fstat(root.fd(),&rootStamp)
                    || !file.openAt(root.fd(),"navigation-ui-observation.json",O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC)
                    || !file.require() || ::fstat(file.fd(),&fileStamp))return false;
            acquired=true;
            if(!S_ISREG(fileStamp.st_mode) || fileStamp.st_uid!=::geteuid() || (fileStamp.st_mode&0777)!=0600
                    || fileStamp.st_nlink!=1 || fileStamp.st_size<=0 || fileStamp.st_size>65536)return false;
            raw.resize(int(fileStamp.st_size)+1);const auto count=::pread(file.fd(),raw.data(),raw.size(),0);
            if(count>=0)raw.resize(int(count)); // Actual prefix stays strong even on a short read.
            struct stat after{},named{};
            if(count!=fileStamp.st_size || !file.require() || ::fstat(file.fd(),&after)
                    || ::fstatat(root.fd(),"navigation-ui-observation.json",&named,AT_SYMLINK_NOFOLLOW)
                    || !picoStreamStamp(fileStamp,after) || !picoStreamStamp(after,named) || !directory(path))return false;
            if(!file.closeChecked(fileClose) || !root.closeChecked(rootClose))return false;
            closed=true;return true;
        }
    };
    struct Attempt {
        std::shared_ptr<const PicoAudioBundleRequest> request;
        QVariantMap native,settings,result;
        QByteArray nativeRaw,settingsRaw;
        std::shared_ptr<UiOriginal> ui;
        bool nativeReady{false},settingsReady{false},terminal{false};
    };
public:
    static constexpr std::size_t NativeDeclaration=4*1024*1024;
    static constexpr int Limit=1048576;
    using Native=std::function<QVariantMap(const QString&)>;
    using Settings=std::function<QVariantMap(const QVariantMap&)>;
    void poison(std::exception_ptr failure={}) {
        if(!_failed) {_failed=true;_failure=failure;}
    }
    QVariantMap sample(const std::shared_ptr<const PicoAudioBundleRequest>& request,const QString& root,
            const Native& native,const Settings& settings) {
        if(_failed || !request || !request->fresh() || !native || !settings || QThread::currentThread()!=_thread)return {};
        const auto& command=request->command;const auto id=command.value("commandId").toString(),run=command.value("runId").toString();
        if(_current && _current->request==request && _current->terminal)return _current->result;
        if(!_current || _current->request!=request) {
            if((_current && !_current->terminal) || _seen.contains(id) || _seen.size()>=512 || (!_run.isEmpty() && _run!=run))return {};
            const auto nativeNonce=command.value("nativeNonce").toString(),settingsNonce=command.value("settingsNonce").toString();
            if(_sourceNonces.contains(nativeNonce) || _sourceNonces.contains(settingsNonce))return {};
            _seen.insert(id);_sourceNonces.insert(nativeNonce);_sourceNonces.insert(settingsNonce);_run=run;
            _current=std::make_shared<Attempt>();_current->request=request; // Strong before first source callback.
        }
        auto a=_current;
        if(!a->nativeReady) {
            a->native=native(command.value("nativeNonce").toString());
            if(!request->fresh()) {poison();return {};}
            if(a->native.value("requestId")!=command.value("nativeNonce")) {poison();return {};}
            if(a->native.value("pending").toBool())return {{"picoAudioObservationBundleVersion",1},{"commandId",id},{"status","pending"}};
            a->nativeRaw=QJsonDocument::fromVariant(a->native).toJson(QJsonDocument::Compact);
            if(a->nativeRaw.isEmpty() || a->nativeRaw.size()>262144) {poison();return {};}
            a->nativeReady=true;
        }
        if(!a->settingsReady) {
            const QVariantMap settingsCommand{{"schemaVersion",1},{"commandId",command.value("settingsNonce")},
                {"action","feature-audio-settings-observe"},{"runId",run}};
            a->settings=settings(settingsCommand);
            if(!request->fresh() || a->settings.value("commandId")!=command.value("settingsNonce")) {poison();return {};}
            a->settingsRaw=QJsonDocument::fromVariant(a->settings).toJson(QJsonDocument::Compact);
            if(a->settingsRaw.isEmpty() || a->settingsRaw.size()>262144) {poison();return {};}
            a->settingsReady=true;
        }
        a->ui=std::make_shared<UiOriginal>(); // Partial root/file owners survive every failure.
        if(!a->ui->read(root) || !a->ui->closed || !request->fresh()) {poison();return {};}
        const auto text=QString::fromUtf8(a->ui->raw);
        if(text.toUtf8()!=a->ui->raw) {poison();return {};}
        a->result={{"picoAudioObservationBundleVersion",1},{"commandId",id},{"runId",run},{"processId",QCoreApplication::applicationPid()},
            {"requestedEpochMs",request->epoch},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"status","ready"},{"nativeNonce",command.value("nativeNonce")},{"settingsNonce",command.value("settingsNonce")},
            {"nativeRaw",QString::fromUtf8(a->nativeRaw)},{"settingsRaw",QString::fromUtf8(a->settingsRaw)},
            {"pagesRaw",text},{"originalPageKnownClosed",true},{"nativeAdmissionJoined",false}};
        const auto encoded=QJsonDocument::fromVariant(a->result).toJson(QJsonDocument::Compact);
        if(encoded.size()>Limit || !request->fresh()) {poison();return {};}
        a->terminal=true;return a->result;
    }
private:
    QThread* const _thread{QThread::currentThread()};
    bool _failed{false};std::exception_ptr _failure;
    QString _run;QSet<QString> _seen,_sourceNonces;std::shared_ptr<Attempt> _current;
};
}
#endif
