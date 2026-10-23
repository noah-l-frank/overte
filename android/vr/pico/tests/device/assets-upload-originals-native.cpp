// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QThread>
#include <QTimer>
#include <cassert>
#include "PicoAssetsUploadOriginals.h"
using overte::e2e::PicoAssetsUploadOriginals;
int main(int argc,char** argv) {
 QCoreApplication app(argc,argv);PicoAssetsUploadOriginals original;const auto run=QString(32,'a');
 if(!app.arguments().contains("--testScript")) {original.entry("bundle",{});assert(original.observe(run).isEmpty());return 0;}
 auto source=original.observe(run);assert(source.value("totalCalls")==0 && source.value("valid")==true);
 original.entry("bundle",{{"paths",QStringList{"/real/invalid/input"}},{"destination","/outside"}});
 source=original.observe(run);assert(source.value("totalCalls")==1 && source.value("calls").toList().first().toMap().value("kind")=="bundle");
 const auto id=QString("original-bundle-id"),root="/private/feature-assets-"+run+"/gltf-bundle";
 const QVariantMap connection{{"original-domain-birth","b"}};
 assert(original.begin(id,{root+"/main.gltf"},{"main.gltf"},"/e2e-"+run+"/","main.gltf",connection));
 QObject* request=new QObject;const auto requestId=original.issue(id,"upload",connection,request);assert(!requestId.isEmpty());
 auto finishedCapture=std::make_shared<int>(0),destroyedCapture=std::make_shared<int>(0);
 // Explicit completion seam below only exercises collector lifetime logic.
 const auto finished=QObject::connect(request,&QObject::objectNameChanged,request,[&original,id,requestId,finishedCapture] {
  original.finished(id,requestId,{{"original-sha","actual-owner-thread-copy"}});
 });
 const auto destroyed=QObject::connect(request,&QObject::destroyed,[&original,id,requestId,destroyedCapture] {original.destroyed(id,requestId);});
 assert(original.callback(requestId,"finished",finished,finishedCapture));assert(original.callback(requestId,"destroyed",destroyed,destroyedCapture));
 request->setObjectName("actual-finish-signal");original.end(id,{});
 auto row=original.observe(run).value("bundles").toList().first().toMap().value("requests").toList().first().toMap();
 assert(row.value("lifetime").toMap().value("requestAlive")==true);
 assert(original.release(run,source.value("instance").toString(),{id}).isEmpty());
 request->deleteLater();QElapsedTimer clock;clock.start();
 // The ordinary Qt event loop performs deleteLater. Capture anchors remain held.
 QTimer::singleShot(10,&app,&QCoreApplication::quit);app.exec();
 row=original.observe(run).value("bundles").toList().first().toMap().value("requests").toList().first().toMap();
 assert(row.value("lifetime").toMap().value("requestAlive")==false);
 assert(row.value("lifetime").toMap().value("finishedCaptureAlive")==true);
 assert(original.release(run,source.value("instance").toString(),{id}).isEmpty());
 finishedCapture.reset();destroyedCapture.reset();
 const auto retired=original.release(run,source.value("instance").toString(),{id});assert(retired.value("retired")==true);
 assert(retired.value("liveRequests")==0 && retired.value("bundles").toList().isEmpty());
 assert(!original.begin(id,{root+"/main.gltf"},{"main.gltf"},"/e2e-"+run+"/","main.gltf",connection));
 assert(original.observe(run).value("valid")==false);
 PicoAssetsUploadOriginals finite;for(int i=0;i<512;++i)finite.entry("single",{{"path","/original"}});
 assert(finite.observe(run).value("valid")==true);finite.entry("cancel",{});assert(finite.observe(run).value("valid")==false);
 PicoAssetsUploadOriginals foreignThread;auto worker=QThread::create([&foreignThread] {foreignThread.entry("bundle",{});});
 worker->start();assert(worker->wait(1000));delete worker;assert(foreignThread.observe(run).value("valid")==false);
 return 0;
}
