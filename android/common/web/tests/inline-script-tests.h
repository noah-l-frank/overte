// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QNetworkReply>
#include <QTcpServer>
#include <QTcpSocket>
#include <QElapsedTimer>

// Android evaluation is an explicit output observer; the fetch, redirect,
// native descriptor consent, Qt reply cancellation and JNI remain production.
static void runInlineScriptCancellationTests(JNIEnv* env,jclass boundary,const QString& backendPath) {
    QQmlEngine engine; engine.addImportPath(QFileInfo(backendPath).absoluteDir().absoluteFilePath("../.."));
    QQmlFileSelector selector(&engine); selector.setExtraSelectors({"android"});
    QQmlComponent component(&engine);
    component.setData("import QtQuick 2.7\nimport controls 1.0 as Controls\nControls.EmbeddedWebView { width: 100; height: 100; url: authored; scriptUrl: approvedScript }",QUrl()); assert(component.isReady());
    auto spinUntil=[](auto predicate) { QElapsedTimer timer;timer.start();while(!predicate() && timer.elapsed()<5000) QCoreApplication::processEvents(QEventLoop::AllEvents,10);assert(predicate()); };
    auto evaluations=[&] { return env->GetStaticIntField(boundary,env->GetStaticFieldID(boundary,"evaluations","I")); };
    for(int replacement=0;replacement<4;++replacement) {
        const bool redirectAndRevoke=replacement==1;
        QTcpServer server;assert(server.listen(QHostAddress::LocalHost));
        const QString script="http://127.0.0.1:"+QString::number(server.serverPort())+"/approved.js";
        const QString source="data:text/html,<p>script cancellation";
        QQmlContext context(engine.rootContext()); overte::web::InlineHtmlDocumentOwner owner;
        const auto descriptor=owner.issue(&context,"script-owner",source,script);
        context.setContextProperty("nativeInlineHtmlDocument",QVariant::fromValue(descriptor));
        context.setContextProperty("nativeWebSourceIdentity","script-owner");
        context.setContextProperty("authored",source);context.setContextProperty("approvedScript",script);
        std::unique_ptr<QObject> root(component.create(&context));assert(root);QCoreApplication::processEvents();
        auto* view=root->findChild<NativeWebViewItem*>();assert(view && view->generation());
        auto grant=view->generation();const auto url=descriptor.transportURL();view->acceptPage(grant,1,url);
        const auto before=evaluations();view->acceptState(grant,1,url,false,false,false,true,0);
        spinUntil([&]{return server.hasPendingConnections();});
        QPointer<QTcpSocket> socket=server.nextPendingConnection();assert(socket);spinUntil([&]{return socket->bytesAvailable()>0;});socket->readAll();
        if(redirectAndRevoke) {
            socket->write("HTTP/1.1 302 Found\r\nLocation: /delayed.js\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");socket->flush();socket->disconnectFromHost();
            spinUntil([&]{return server.hasPendingConnections();});socket=server.nextPendingConnection();assert(socket);
            spinUntil([&]{return socket->bytesAvailable()>0;});socket->readAll();
        }
        QPointer<QNetworkReply> pending;
        for(auto* reply:view->findChildren<QNetworkReply*>()) if(!reply->isFinished()) pending=reply;
        assert(pending);assert(pending->url().path()==(redirectAndRevoke?"/delayed.js":"/approved.js"));
        bool finished=false;QNetworkReply::NetworkError failure=QNetworkReply::NoError;
        QObject::connect(pending,&QNetworkReply::finished,&engine,[&]{finished=true;failure=pending->error();});
        if(redirectAndRevoke) owner.revoke();
        else if(replacement==2) view->setSourceIdentity("replacement-owner");
        else if(replacement==3) view->setUrl(source+" replacement");
        else view->setScriptUrl(script+"#unapproved-change");
        spinUntil([&]{return finished;});assert(failure==QNetworkReply::OperationCanceledError);assert(!view->generation());
        if(socket && socket->state()==QAbstractSocket::ConnectedState) {
            const QByteArray body="window.staleOwnerScriptExecuted=true;";
            socket->write("HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->flush();socket->disconnectFromHost();
        }
        QCoreApplication::processEvents();assert(evaluations()==before);assert(!env->ExceptionCheck());
    }

    // Retaining a supported WebView across suspension preserves the page ID.
    // The old HTTP reply must not consume that page's one approved injection.
    for(bool inlineMode:{false,true}) for(bool visibility:{false,true}) for(bool completed:{false,true}) {
        QTcpServer server;assert(server.listen(QHostAddress::LocalHost));
        const QString script="http://127.0.0.1:"+QString::number(server.serverPort())+"/resume.js";
        const QString source=inlineMode?"data:text/html,<p>resume script":"https://owned.test/resume";
        QQmlContext context(engine.rootContext());overte::web::InlineHtmlDocumentOwner owner;
        const auto descriptor=inlineMode?owner.issue(&context,"resume-owner",source,script):overte::web::InlineHtmlDocument();
        context.setContextProperty("nativeInlineHtmlDocument",inlineMode?QVariant::fromValue(descriptor):QVariant());
        context.setContextProperty("nativeWebSourceIdentity","resume-owner");
        context.setContextProperty("authored",source);context.setContextProperty("approvedScript",script);
        std::unique_ptr<QObject> root(component.create(&context));assert(root);QCoreApplication::processEvents();
        auto* view=root->findChild<NativeWebViewItem*>();assert(view && view->generation());
        const QUrl url=inlineMode?descriptor.transportURL():QUrl(source);const auto grant=view->generation();
        view->acceptPage(grant,1,url);const auto before=evaluations();view->acceptState(grant,1,url,false,false,false,true,0);
        auto receive=[&]{spinUntil([&]{return server.hasPendingConnections();});auto* socket=server.nextPendingConnection();
            spinUntil([&]{return socket->bytesAvailable()>0;});socket->readAll();return socket;};
        auto respond=[](QTcpSocket* socket){const QByteArray body="window.approvedResumeScript=true;";
            socket->write("HTTP/1.1 200 OK\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->flush();socket->disconnectFromHost();};
        QPointer<QTcpSocket> old=receive();
        if(completed){respond(old);spinUntil([&]{return evaluations()==before+1;});}
        if(visibility){view->setVisible(false);QCoreApplication::processEvents();view->setVisible(true);}
        else {view->acceptForeground(false);QCoreApplication::processEvents();view->acceptForeground(true);}
        QCoreApplication::processEvents();const auto resumed=view->generation();assert(resumed && resumed!=grant);
        view->acceptState(resumed,1,url,false,false,false,true,0);QCoreApplication::processEvents();
        if(!completed){auto* retry=receive();if(old && old->state()==QAbstractSocket::ConnectedState)respond(old);
            QCoreApplication::processEvents();assert(evaluations()==before);respond(retry);spinUntil([&]{return evaluations()==before+1;});}
        // Repeated state notifications and further lifecycle grants cannot replay
        // the script already submitted for this still-current document.
        view->acceptState(resumed,1,url,false,false,false,true,0);QCoreApplication::processEvents();
        view->acceptForeground(false);QCoreApplication::processEvents();view->acceptForeground(true);QCoreApplication::processEvents();
        view->acceptState(view->generation(),1,url,false,false,false,true,0);QCoreApplication::processEvents();
        assert(evaluations()==before+1);assert(!server.hasPendingConnections());assert(!env->ExceptionCheck());
    }
    puts("PASS: delayed authorized HTTP scripts retry after same-page foreground/visibility resume for inline and HTTPS; completed scripts are not replayed");
    puts("PASS: actual Qt HTTP script fetch and redirect are aborted by exact script-tuple change or owner revoke; delayed old script cannot reach JNI evaluation");
}
