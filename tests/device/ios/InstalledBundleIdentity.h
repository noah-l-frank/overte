// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <CoreFoundation/CoreFoundation.h>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QFile>
#include <QFileInfo>
#include <QJsonObject>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <algorithm>
#include <chrono>
#include <functional>
#include <memory>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#if defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach/vm_prot.h>
#include <limits>
#include <cstring>
#if __has_feature(ptrauth_calls)
#include <ptrauth.h>
#endif
#endif

namespace overte::e2e {
// Original CF main-bundle bytes only. No requested path, digest, expected
// manifest or host archive identity enters this source. Native code uncompiled.
class InstalledBundleIdentity {
    using Clock=std::chrono::steady_clock;
    static constexpr quint64 MAX_BYTES=2ULL*1024*1024*1024,MAX_FILE=1024ULL*1024*1024;
    static constexpr int MAX_NODES=20000;
    struct Node { QByteArray raw,path,sha;struct stat original{};bool directory{false}; };
    struct State {
        QMutex mutex;bool ready{false},failed{false};int root{-1};QString path,executable,bundle;
        struct stat original{};QList<Node> nodes;QVariantMap result;qint64 prepared{0},startedEpoch{0};
        ~State() { if (root>=0) { ::close(root); } }
    };
    class FD {
    public:
        explicit FD(int value):value(value) {} ~FD() { if (value>=0) { ::close(value); } }
        int value;
    };
public:
    QVariantMap observe(const QVariantMap& input) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
        const auto object=QJsonObject::fromVariantMap(input);const auto keys=object.keys();const auto id=object.value("commandId").toString();
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!=QJsonValue("ios-bundle-observe")
                || !QRegularExpression("\\Aios-[0-9a-f]{32}\\z").match(id).hasMatch()) { return {}; }
        const auto started=Clock::now();const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_epoch || _sequence>=9007199254740991ULL) { _failed=true; }
        _epoch=epoch;
        QString root,executable,bundle;
        if (!originalBundle(root,executable,bundle)) { _failed=true; }
        if (!_state && !_failed) {
            _state=std::make_shared<State>();_state->path=root;_state->executable=executable;_state->bundle=bundle;_state->startedEpoch=epoch;
            const auto state=_state;
            auto worker=QThread::create([state] {
                const auto began=Clock::now();bool okay=collect(*state,began);
                QMutexLocker lock(&state->mutex);
                state->prepared=okay?QDateTime::currentMSecsSinceEpoch():0;
                state->failed=!okay || state->prepared<state->startedEpoch;state->ready=!state->failed;
            });
            QObject::connect(worker,&QThread::finished,worker,&QObject::deleteLater);worker->start();
        }
        QVariantMap result;QString status="unavailable";qint64 prepared{0};
        if (_state && !_failed) {
            QMutexLocker lock(&_state->mutex);
            if (_state->path!=root || _state->executable!=executable || _state->bundle!=bundle || _state->failed) { _failed=true; }
            else if (!_state->ready) { status="pending"; }
            else if (valid(*_state,started,1500)) { status="ready";result=_state->result;prepared=_state->prepared; }
            else { _failed=true; }
        }
        const auto captured=QDateTime::currentMSecsSinceEpoch();
        if (captured<epoch || captured<prepared || elapsed(started)>1500) { _failed=true; }
        _epoch=std::max(_epoch,captured);
        if (_failed) { status="unavailable";result.clear();prepared=0; }
        return {{"bundleObservationVersion",1},{"commandId",id},{"instance",_instance},
            {"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",captured},{"status",status},{"preparedEpochMs",prepared},{"bundle",result}};
    }
#if defined(OVERTE_IOS_E2E_TEST_BUILD)
    // A passive extension of this SAME already prepared byte-manifest owner.
    // No requested path/hash, new bundle walker, device query or product owner.
    QVariantMap observeQtEntryImage(const void *actualEntry) {
        if (!qApp || QThread::currentThread()!=qApp->thread() || !actualEntry || !_state || _failed
                || !QCoreApplication::arguments().contains("--testScript") || _imageSequence>=1000000000ULL) return {};
        const auto started=Clock::now();const auto before=QDateTime::currentMSecsSinceEpoch();
        const void *entry=actualEntry;
#if __has_feature(ptrauth_calls)
        entry=ptrauth_strip(entry,ptrauth_key_function_pointer);
#endif
        Dl_info info{};
        // The current reviewed iOS runtime is static. Its actual API entry must
        // be in the non-unloadable main executable. Dynamic image lifetimes
        // need a separate dyld add/remove observer, never a dlopen retention.
        const auto *header=_dyld_get_image_header(0);
        if (!header || header->magic!=MH_MAGIC_64 || !::dladdr(entry,&info) || info.dli_fbase!=header
                || !info.dli_fname || reinterpret_cast<const mach_header_64 *>(header)->cputype!=CPU_TYPE_ARM64) return {};
        QString root,executable,bundle;
        if (!originalBundle(root,executable,bundle)) return {};
        QMutexLocker lock(&_state->mutex);
        if (!_state->ready || _state->failed || _state->path!=root || _state->executable!=executable || _state->bundle!=bundle
                || !valid(*_state,started,1500)
                || QFileInfo(QString::fromUtf8(info.dli_fname)).canonicalFilePath()!=root+"/"+executable) return {};
        const Node *node=nullptr;
        for (const auto &value:_state->nodes) if (!value.directory && value.path==executable.toUtf8()) { node=&value;break; }
        if (!node || node->sha.size()!=32) return {};
        FD fd(::openat(_state->root,node->raw.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK));struct stat first{},last{};
        if (fd.value<0 || ::fstat(fd.value,&first)!=0 || !same(first,node->original)) return {};
        auto read=[&](void *data,size_t size,off_t offset) {
            auto *bytes=static_cast<char *>(data);size_t count=0;
            while (count<size) {
                const auto amount=::pread(fd.value,bytes+count,size-count,offset+off_t(count));
                if (amount<0 && errno==EINTR) continue;
                if (amount<=0 || elapsed(started)>1500) return false;count+=size_t(amount);
            }
            return true;
        };
        mach_header_64 disk{};
        if (!read(&disk,sizeof(disk),0) || disk.magic!=MH_MAGIC_64 || disk.cputype!=CPU_TYPE_ARM64
                || disk.filetype!=MH_EXECUTE || disk.ncmds>4096 || disk.sizeofcmds>4*1024*1024
                || quint64(sizeof(disk))+disk.sizeofcmds>quint64(first.st_size)) return {};
        QByteArray commands(qsizetype(disk.sizeofcmds),'\0');
        if (!read(commands.data(),size_t(commands.size()),sizeof(disk))) return {};
        // dyld's main header cannot be unloaded. Match its original commands
        // to the same actual descriptor, not a separately hashed pathname.
        if (::memcmp(header,&disk,sizeof(disk)) || ::memcmp(reinterpret_cast<const char *>(header)+sizeof(disk),commands.constData(),size_t(commands.size()))) return {};
        QByteArray uuid;quint64 offset=0,fileOffset=0;bool found=false;int uuids=0;
        const auto address=reinterpret_cast<uintptr_t>(entry);const auto slide=_dyld_get_image_vmaddr_slide(0);
        for (quint32 index=0;index<disk.ncmds;++index) {
            if (offset+sizeof(load_command)>quint64(commands.size())) return {};
            load_command command{};::memcpy(&command,commands.constData()+offset,sizeof(command));
            if (command.cmdsize<sizeof(command) || command.cmdsize%8 || offset+command.cmdsize>quint64(commands.size())) return {};
            if (command.cmd==LC_UUID) {
                if (command.cmdsize!=sizeof(uuid_command) || ++uuids!=1) return {};
                uuid=QByteArray(commands.constData()+offset+8,16).toHex();
            }
            if (command.cmd==LC_SEGMENT_64) {
                segment_command_64 segment{};
                if (command.cmdsize<sizeof(segment)) return {};
                ::memcpy(&segment,commands.constData()+offset,sizeof(segment));
                if (segment.fileoff>quint64(first.st_size) || segment.filesize>quint64(first.st_size)-segment.fileoff) return {};
                if (segment.nsects>4096 || quint64(sizeof(segment))+quint64(segment.nsects)*sizeof(section_64)>command.cmdsize
                        || segment.filesize>segment.vmsize) return {};
                quint64 start=0;
                if (slide>=0) {
                    if (segment.vmaddr>std::numeric_limits<quint64>::max()-quint64(slide)) return {};
                    start=segment.vmaddr+quint64(slide);
                } else {
                    const auto amount=quint64(-(slide+1))+1;
                    if (segment.vmaddr<amount) return {};start=segment.vmaddr-amount;
                }
                if ((segment.initprot&VM_PROT_EXECUTE) && address>=start && quint64(address)-start<segment.filesize) {
                    if (found) return {};fileOffset=segment.fileoff+(quint64(address)-start);found=true;
                }
            }
            offset+=command.cmdsize;
        }
        if (!found || uuids!=1 || offset!=quint64(commands.size()) || ::fstat(fd.value,&last)!=0 || !same(first,last)
                || !valid(*_state,started,1500) || elapsed(started)>1500) return {};
        QByteArray original(reinterpret_cast<const char *>(&disk),sizeof(disk));original+=commands;
        const auto after=QDateTime::currentMSecsSinceEpoch();if (after<before) return {};
        return {{"iosQtEntryImageVersion",1},{"source","native-main-image-entry-fd"},{"instance",_instance},
            {"sequence",qulonglong(++_imageSequence)},{"processId",QCoreApplication::applicationPid()},
            {"beforeEpochMs",before},{"afterEpochMs",after},{"bundlePreparedEpochMs",_state->prepared},
            {"bundle",_state->result},{"relativePath",executable},{"fileBytes",QString::number(qulonglong(first.st_size))},
            {"fileSha256",QString::fromLatin1(node->sha.toHex())},{"imageUuid",QString::fromLatin1(uuid)},
            {"headerSha256",QString::fromLatin1(QCryptographicHash::hash(original,QCryptographicHash::Sha256).toHex())},
            {"symbolFileOffset",QString::number(fileOffset)},
            {"fileDevice",QString::number(qulonglong(first.st_dev))},{"fileInode",QString::number(qulonglong(first.st_ino))}};
    }
#endif
private:
    static qint64 elapsed(Clock::time_point began) { return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-began).count(); }
    static QString string(CFStringRef value) {
        if (!value || CFGetTypeID(value)!=CFStringGetTypeID()) { return {}; }
        const auto size=CFStringGetMaximumSizeForEncoding(CFStringGetLength(value),kCFStringEncodingUTF8)+1;
        if (size<=0 || size>16384) { return {}; }QByteArray bytes(static_cast<int>(size),'\0');
        return CFStringGetCString(value,bytes.data(),size,kCFStringEncodingUTF8)?QString::fromUtf8(bytes.constData()):QString();
    }
    static QString location(CFURLRef value) {
        if (!value) { return {}; }auto text=CFURLCopyFileSystemPath(value,kCFURLPOSIXPathStyle);
        const auto result=string(text);if (text) { CFRelease(text); }return result;
    }
    static bool originalBundle(QString& root,QString& executable,QString& bundle) {
        auto actual=CFBundleGetMainBundle();if (!actual) { return false; }
        auto url=CFBundleCopyBundleURL(actual);auto exe=CFBundleCopyExecutableURL(actual);
        root=QFileInfo(location(url)).canonicalFilePath();const auto path=QFileInfo(location(exe)).canonicalFilePath();
        if (url) { CFRelease(url); }if (exe) { CFRelease(exe); }
        bundle=string(CFBundleGetIdentifier(actual));executable=QFileInfo(path).fileName();
        return !root.isEmpty() && root.endsWith("/Overte.app") && !path.isEmpty() && !executable.isEmpty()
            && path==root+"/"+executable && path==QFileInfo(QCoreApplication::applicationFilePath()).canonicalFilePath()
            && QRegularExpression("\\A[A-Za-z0-9_-]+(?:\\.[A-Za-z0-9_-]+)+\\z").match(bundle).hasMatch();
    }
    static bool same(const struct stat& a,const struct stat& b) {
        return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_mode==b.st_mode && a.st_nlink==b.st_nlink
            && a.st_size==b.st_size && a.st_mtimespec.tv_sec==b.st_mtimespec.tv_sec && a.st_mtimespec.tv_nsec==b.st_mtimespec.tv_nsec
            && a.st_ctimespec.tv_sec==b.st_ctimespec.tv_sec && a.st_ctimespec.tv_nsec==b.st_ctimespec.tv_nsec;
    }
    static bool safe(const QByteArray& bytes,QString& normalized) {
        const auto original=QString::fromUtf8(bytes);
        if (original.isEmpty() || original.toUtf8()!=bytes || bytes.size()>1024 || bytes.startsWith('/') || bytes.contains('\\')) { return false; }
        normalized=original.normalized(QString::NormalizationForm_C);
        if (normalized.split('/').size()>64) { return false; }
        for (auto character:normalized) { if (character.unicode()<32 || character.unicode()==127) { return false; } }
        for (const auto& part:normalized.split('/')) { if (part.isEmpty() || part=="." || part==".." || part.toUtf8().size()>255) { return false; } }
        return normalized.toUtf8().size()<=1024;
    }
    static bool valid(const State& state,Clock::time_point began,qint64 budget) {
        struct stat root{};
        if (state.root<0 || ::fstat(state.root,&root)!=0 || !same(root,state.original)
                || ::lstat(QFile::encodeName(state.path).constData(),&root)!=0 || !same(root,state.original)) { return false; }
        // Original kernel inode/size/mtime/ctime records, not a cached existence
        // flag. Directory records also detect additions and removed children.
        for (const auto& node:state.nodes) {
            struct stat current{};
            if (elapsed(began)>budget || ::fstatat(state.root,node.raw.constData(),&current,AT_SYMLINK_NOFOLLOW)!=0
                    || !same(node.original,current)) { return false; }
        }
        return elapsed(began)<=budget;
    }
    static void word(QByteArray& output,quint64 value,int width) {
        for (int n=width-1;n>=0;--n) { output.append(static_cast<char>((value>>(n*8))&255)); }
    }
    static bool collect(State& state,Clock::time_point began) {
        state.root=::open(QFile::encodeName(state.path).constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if (state.root<0 || ::fstat(state.root,&state.original)!=0 || !S_ISDIR(state.original.st_mode)) { return false; }
        quint64 total{0};int files{0};QSet<QString> names;
        const auto empty=QCryptographicHash::hash(QByteArray(),QCryptographicHash::Sha256);
        std::function<bool(int,const QByteArray&)> walk=[&](int fd,const QByteArray& prefix) {
            const auto duplicate=::dup(fd);if (duplicate<0) { return false; }
            DIR* directory=::fdopendir(duplicate);if (!directory) { ::close(duplicate);return false; }
            bool okay{true};errno=0;
            while (auto entry=::readdir(directory)) {
                const QByteArray component(entry->d_name);if (component=="." || component=="..") { errno=0;continue; }
                const auto raw=prefix.isEmpty()?component:prefix+'/'+component;QString normalized;
                if (elapsed(began)>90000 || state.nodes.size()>=MAX_NODES || !safe(raw,normalized)
                        || names.contains(normalized.toCaseFolded())) { okay=false;break; }
                names.insert(normalized.toCaseFolded());Node node;node.raw=raw;node.path=normalized.toUtf8();
                if (::fstatat(fd,component.constData(),&node.original,AT_SYMLINK_NOFOLLOW)!=0) { okay=false;break; }
                node.directory=S_ISDIR(node.original.st_mode);
                if (!node.directory && (!S_ISREG(node.original.st_mode) || node.original.st_nlink!=1
                        || node.original.st_size<0 || static_cast<quint64>(node.original.st_size)>MAX_FILE)) { okay=false;break; }
                FD original(::openat(fd,component.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK|(node.directory?O_DIRECTORY:0)));
                struct stat opened{};
                if (original.value<0 || ::fstat(original.value,&opened)!=0 || !same(opened,node.original)) { okay=false;break; }
                if (node.directory) {
                    node.sha=empty;state.nodes.append(node);
                    if (!walk(original.value,raw)) { okay=false;break; }
                } else {
                    total+=static_cast<quint64>(node.original.st_size);if (total>MAX_BYTES) { okay=false;break; }
                    QCryptographicHash digest(QCryptographicHash::Sha256);QByteArray block(1024*1024,'\0');quint64 count{0};
                    while (true) {
                        const auto size=::read(original.value,block.data(),static_cast<size_t>(block.size()));
                        if (size<0 && errno==EINTR) { continue; }
                        if (size<0 || elapsed(began)>90000) { okay=false;break; }if (!size) { break; }
                        count+=static_cast<quint64>(size);
                        if (count>static_cast<quint64>(node.original.st_size)) { okay=false;break; }
                        digest.addData(block.constData(),static_cast<int>(size));
                    }
                    if (!okay || count!=static_cast<quint64>(node.original.st_size)) { okay=false;break; }
                    node.sha=digest.result();state.nodes.append(node);++files;
                }
                struct stat after{};
                if (::fstat(original.value,&after)!=0 || !same(after,node.original)) { okay=false;break; }errno=0;
            }
            if (errno) { okay=false; }::closedir(directory);return okay;
        };
        if (!walk(state.root,{}) || files<1 || total<1 || !valid(state,began,90000)) { return false; }
        std::sort(state.nodes.begin(),state.nodes.end(),[](const Node& a,const Node& b) { return a.path<b.path; });
        QCryptographicHash digest(QCryptographicHash::Sha256);digest.addData(QByteArrayLiteral("overte-ios-installed-bundle-v1"));digest.addData("\0",1);
        QByteArray executableSha;
        for (const auto& node:state.nodes) {
            QByteArray record;record.append(node.directory?'D':'F');word(record,static_cast<quint64>(node.path.size()),4);record.append(node.path);
            word(record,node.directory?0:static_cast<quint64>(node.original.st_size),8);record.append(node.sha);digest.addData(record);
            if (!node.directory && node.path==state.executable.toUtf8()) { executableSha=node.sha; }
        }
        if (executableSha.size()!=32 || elapsed(began)>90000) { return false; }
        state.result={{"bundleContractVersion",1},{"bundleId",state.bundle},{"bundleSha256",QString::fromLatin1(digest.result().toHex())},
            {"executableSha256",QString::fromLatin1(executableSha.toHex())},{"nodeCount",state.nodes.size()},
            {"fileCount",files},{"totalBytes",static_cast<qulonglong>(total)}};
        return true;
    }
    std::shared_ptr<State> _state;bool _failed{false};qint64 _epoch{0};quint64 _sequence{0};
#if defined(OVERTE_IOS_E2E_TEST_BUILD)
    quint64 _imageSequence{0};
#endif
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
} // namespace overte::e2e
#endif
