// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QLoggingCategory>
#include <QMutex>
#include <QPointer>
#include <QRunnable>
#include <QThread>
#include <QThreadPool>
#include <QTimer>
#include <QUrl>
#include <QVariant>
#include <QSharedPointer>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <functional>

// Dependency registration and previously acquired ATP-byte delivery are host
// endpoints. The parser receives the complete original packet, not a filename
// or an independently supplied success value. No endpoint creates an HFM model.
#define hifi_DependencyManager_h // Original shared headers use a relative include.
class Dependency {public:virtual ~Dependency()=default;};
#define SINGLETON_DEPENDENCY
class DependencyManager {
public:
 template<class T> static QSharedPointer<T>& slot(){static QSharedPointer<T> value;return value;}
 template<class T> static QSharedPointer<T> get(){return slot<T>();}
 template<class T> static bool isSet(){return !slot<T>().isNull();}
 template<class T> static void set(const QSharedPointer<T>& value){slot<T>()=value;}
};
class ResourceRequest:public QObject {
 Q_OBJECT
public:
 enum Result{Success=0,Error=1};
 ResourceRequest(const QUrl& url,const QByteArray& bytes):_url(url),_bytes(bytes){}
 void send(){QTimer::singleShot(0,this,[this]{emit finished();});}
 Result getResult()const{return Success;}
 QByteArray getData()const{return _bytes;}
 QString getWebMediaType()const{return {};}
 QUrl _url;QByteArray _bytes;
signals:void finished();
};
class ResourceManager:public Dependency {
public:
 QHash<QUrl,QByteArray> originalBytes;
 QList<QPointer<ResourceRequest>> requests;
 QJsonArray transportOriginals;
 QUrl normalizeURL(const QUrl& url){if(url.scheme()!="atp"){qFatal("Only recorded original ATP bytes are admitted");}return url;}
 ResourceRequest* createResourceRequest(QObject*,const QUrl& url,bool,qint64,const QString& extra){
  if(!originalBytes.contains(url)){qFatal("Parser requested an unbound original URL");}
  auto request=new ResourceRequest(url,originalBytes.value(url));requests.append(request);
  transportOriginals.append(QJsonObject{{"url",url.toString()},{"extra",extra},{"bytes",request->_bytes.size()},
   {"sha256",QString::fromLatin1(QCryptographicHash::hash(request->_bytes,QCryptographicHash::Sha256).toHex())},
   {"thread",QString::number(reinterpret_cast<quintptr>(QThread::currentThread()),16)}});
  return request;
 }
};
class PathUtils {public:static QUrl expandToLocalDataAbsolutePath(const QUrl&){qFatal("Local paths are outside this parser join");return {};}};

// Original GeometryReader requires a weak Resource target. This bounded target
// is explicitly a host receiver, NOT an original GeometryResource/data owner.
// The queued false result proves the Baker boundary was not called ready.
class Resource:public QObject {
 Q_OBJECT
public:bool completed{false},success{false};int completions{0};
public slots:void finishedLoading(bool value){completed=true;success=value;++completions;}
};
struct StatTracker:Dependency {
 QHash<QString,int> stats;std::mutex mutex;
 void incrementStat(const QString& key){std::lock_guard<std::mutex> lock(mutex);++stats[key];}
 void decrementStat(const QString& key){std::lock_guard<std::mutex> lock(mutex);--stats[key];}
};
struct CounterStat {QString key;explicit CounterStat(QString value):key(value){DependencyManager::get<StatTracker>()->incrementStat(key);}
 ~CounterStat(){DependencyManager::get<StatTracker>()->decrementStat(key);}};
using GeometryMappingPair=std::pair<QUrl,QVariantHash>;
Q_DECLARE_LOGGING_CATEGORY(modelnetworking)
