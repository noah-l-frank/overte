// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original header; only the clock is an explicit host seam. No system clock is changed.
#include <QtCore>
#include <QDateTime>
#include <QCoreApplication>
#include <QThread>
#include <cassert>
struct OriginalClockBoundary {
    static qint64 offset;
    static qint64 currentMSecsSinceEpoch(){return QDateTime::currentMSecsSinceEpoch()+offset;}
};
qint64 OriginalClockBoundary::offset{0};
#define QDateTime OriginalClockBoundary
#include "libraries/audio-client/src/RecordedPreviewDeferred.h"
#undef QDateTime

int main(int argc,char** argv){
    QCoreApplication app(argc,argv);QObject receiver;
    for(const auto stage:{"entry","destruction"}){
        overte::e2e::RecordedPreviewDeferred tracker;
        auto lease=tracker.registerCallback(&receiver,1,1000);assert(lease);
        OriginalClockBoundary::offset=2000;assert(!tracker.snapshot(&receiver).isEmpty());
        OriginalClockBoundary::offset=0;
        if(QString::fromLatin1(stage)=="entry"){const auto invocation=overte::e2e::RecordedPreviewDeferred::enter(lease);}
        else {lease.reset();}
        OriginalClockBoundary::offset=2000;assert(tracker.snapshot(&receiver).isEmpty());
        lease.reset();OriginalClockBoundary::offset=0;
    }
    overte::e2e::RecordedPreviewDeferred wrongThread;auto lease=wrongThread.registerCallback(&receiver,1,1000);assert(lease);
    QThread thread;QObject executor;executor.moveToThread(&thread);thread.start();
    auto held=std::make_shared<std::shared_ptr<overte::e2e::RecordedPreviewDeferred::Lease>>(std::move(lease));
    assert(QMetaObject::invokeMethod(&executor,[held]{held->reset();},Qt::BlockingQueuedConnection));
    assert(wrongThread.snapshot(&receiver).isEmpty());
    assert(QMetaObject::invokeMethod(&executor,[&]{executor.moveToThread(app.thread());},Qt::BlockingQueuedConnection));thread.quit();assert(thread.wait(3000));
    overte::e2e::RecordedPreviewDeferred replacement;assert(!replacement.snapshot(&receiver).isEmpty());QObject other;
    assert(replacement.snapshot(&other).isEmpty());assert(replacement.snapshot(&receiver).isEmpty());
}
