// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Fixed Phone5527 real-codec worker test seams; actual Pico body below.
#include <QChar>
#include <QBitArray>
#include <iostream>
#include <QJsonDocument>

#include <cstdio>
#include <stdexcept>
#include <QCoreApplication>
#include <QImage>
#include <QImageReader>
#include <QVector>
#include <QDir>
#include <QFile>
#include <QCryptographicHash>
#include <GifCreator.h>
#include "interface/src/ui/SnapshotCapture.h"
#include "interface/src/ui/SnapshotStorage.h"
#include "tests/device/native/PicoSnapshotCaptureFiles.h"
static SnapshotCapture cancelDuringWrite;
static bool actualFrame(GifWriter* writer,const uint8_t* bytes,uint32_t width,uint32_t height,uint32_t delay) {
    const bool result=GifWriteFrame(writer,bytes,width,height,delay);
    if(cancelDuringWrite)cancelDuringWrite->cancel();
    return result;
}
#define GifWriteFrame actualFrame
class SnapshotAnimated { public:static bool processFrames(QVector<QImage> frames,QVector<qint64> delays,QString path,SnapshotCapture request); };

#include "original-snapshot-gif.inc"

static void need(bool value){if(!value)throw std::runtime_error("Original real GIF owner contract");}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);app.setApplicationName("actual-snapshot-gif-owner");
    const QString mode=argv[1],root=overte::snapshot::storageRoot(),run(32,'a'),plan(32,'b'),prefix="e2e-"+run,capture="actual_gif_worker",path=QDir(root).filePath(prefix+"-"+capture+".gif");
    need(QDir().mkpath(root));auto request=std::make_shared<SnapshotCaptureRequest>(capture);
    QImage image(16,16,QImage::Format_RGBA8888);image.fill(Qt::green);QVector<QImage> frames{image,image};QVector<qint64> delays{4,4};
    if(mode=="failure")frames[1]=QImage(1,1,QImage::Format_RGBA8888);
    if(mode=="cancel")cancelDuringWrite=request;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    auto& owner=overte::e2e::PicoSnapshotCaptureFiles::get();need(owner.plan(run,prefix,plan,root));owner.begin(capture);
#endif
    const auto result=SnapshotAnimated::processFrames(frames,delays,path,request);need(result==(mode=="success"));
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    owner.terminal(capture,result ? "complete" : mode=="cancel" ? "cancelled" : "error",result ? path : QString());
    const auto source=owner.snapshot();
    std::cout<<QJsonDocument::fromVariant(source).toJson(QJsonDocument::Compact).toStdString()<<std::endl;need(source.value("complete")==true && source.value("rows").toList().size()==1);
    const auto original=source.value("rows").toList().front().toMap();need(original.value("opened")==true && original.value("closed")==true);
    if(result) { QFile actual(path);need(actual.open(QIODevice::ReadOnly));const auto bytes=actual.readAll();actual.close();need(original.value("sha256")==QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())); }
    else need(original.value("nativeRemoved")==true);
    need(owner.retire(run,original.value("id").toString(),QString(32,'c')) && !QFileInfo(path).exists());need(owner.seal(run,plan,QString(32,'d')));
#else
    need(QFileInfo(path).exists()==result);
#endif
    return 0;
}
