// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Original factory/URL bodies below. Manager startup/cache and HTTP/File are
// explicit endpoints; this fixture borrows the real AssetClient worker thread.
#include <mutex>
#include <thread>
#include <atomic>
#include "tests/device/native/AudioSettingsQueue.h"
class FileResourceRequest:public ResourceRequest {
public:using ResourceRequest::ResourceRequest;
private:void doSend()override{qFatal("File transport is outside the ATP factory qualification");}
};
class HTTPResourceRequest:public ResourceRequest {
public:using ResourceRequest::ResourceRequest;
private:void doSend()override{qFatal("HTTP transport is outside the ATP factory qualification");}
};
class ResourceManager {
public:
 explicit ResourceManager(QThread& actualClientThread):_thread(actualClientThread){}
 QString normalizeURL(const QString&);QUrl normalizeURL(const QUrl&);
 ResourceRequest* createResourceRequest(QObject*,const QUrl&,bool=true,qint64=-1,const QString& = "");
 using PrefixMap=std::map<QString,QString>;
 QThread& _thread;bool _atpSupportEnabled{true};PrefixMap _prefixMap;QMutex _prefixMapLock;
};
#include "AssetsResourceManagerOriginals.inc"

// GUI pumping belongs to this declared local server endpoint. The unmodified
// bounded weak queue still captures on the actual AssetClient/reader thread;
// a late/failed delivery cannot return a retimed source value.
static QJsonObject assetsOwnerSnapshot(overte::e2e::AudioSettingsQueue& queue,
        const QSharedPointer<AssetClient>& client,const std::function<QJsonObject(QObject*)>& capture) {
 struct Result {std::atomic<bool> done{false},cancelled{false};overte::e2e::AudioSettingsPart part;};
 const auto result=std::make_shared<Result>();QElapsedTimer budget;budget.start();
 std::thread caller([client,result,&queue,capture] {
  if(!result->cancelled.load()) {
   result->part=queue.read("client",client.data(),[capture](QObject* actual) {
    const auto frame=capture(actual);return overte::e2e::AudioSettingsPart{{{"frame",frame.toVariantMap()}},{}};
   });
  }
  result->done.store(true,std::memory_order_release);
 });
 while(!result->done.load(std::memory_order_acquire) && budget.elapsed()<1500) {QTest::qWait(1);}
 if(!result->done.load(std::memory_order_acquire)) {result->cancelled.store(true);}
 caller.join();
 if(result->cancelled.load() || budget.elapsed()>=1500 || !queue.settled()) {return {};}
 return QJsonObject::fromVariantMap(result->part.values.value("frame").toMap());
}
