// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// This includes no Java callback/effect model. Missing Java originals stay pending.
        auto arm=command("arm-current-consumption");arm.insert("focusNonce",focusCommand.value("commandId"));
        const auto armed=NativeWebViewItem::featurePicoWorldCurrentConsumption(arm);
        assert(armed.value("status")=="ready");
        const auto attempt=consumeScopes.value(run)->attempts.value(arm.value("commandId").toString());
        assert(attempt && attempt->frames.isEmpty() && !attempt->terminal);
        record("consumption-arm",{{"request",arm},{"packet",armed}});
        auto collision=arm;collision.insert("ownerToken",QString(32,'8'));
        assert(NativeWebViewItem::featurePicoWorldCurrentConsumption(collision).isEmpty());
        auto second=arm;second.insert("commandId",nonce());
        assert(NativeWebViewItem::featurePicoWorldCurrentConsumption(second).isEmpty());
        const auto currentQueries=consumeScopes.value(run)->queries.size();
        QVariantMap wrongThread;
        std::thread worker([&]{wrongThread=NativeWebViewItem::featurePicoWorldCurrentConsumption(arm);});worker.join();
        assert(wrongThread.isEmpty() && consumeScopes.value(run)->queries.size()==currentQueries);
        app.entities.handler=&window;
        Keyboard keyboard;keyboard._inputTarget=QUuid("12345678-1234-1234-1234-123456789abc");
        const int oldEdits=count("edits");
        const bool ime=QCoreApplication::arguments().contains("--consumption-ime");
        if(ime){
            app.setKeyboardFocusEntity(keyboard._inputTarget);
            QInputMethodEvent event;event.setCommitString(QString::fromUtf8("Grüße 🌍"));
            assert(app.handleInputMethodEventForFocusedEntity(&event));
        }else{
            // The complete production dispatch restores its original selected
            // target. No real OpenXR trigger is claimed by this host boundary.
            assert(app.getKeyboardFocusEntity().isNull());
            keyboard.dispatchKey(Qt::Key_A,Qt::NoModifier,QStringLiteral("a"));
            assert(app.getKeyboardFocusEntity()==keyboard._inputTarget);
        }
        events();assert(count("edits")==oldEdits+1 && !attempt->terminal && attempt->reason.isEmpty());
        const int total=attempt->frames.size();assert(total==(ime ? 2 : 6));
        QVariantList originals;QStringList kinds,origins;QString jniId;
        for(int cursor=0;cursor<total;++cursor){
            auto observe=command("observe-current-consumption");observe.insert("attemptNonce",arm.value("commandId"));observe.insert("afterSequence",cursor);
            const auto packet=NativeWebViewItem::featurePicoWorldCurrentConsumption(observe);
            assert(packet.value("status")=="ready" && NativeWebViewItem::featurePicoWorldCurrentConsumption(observe)==packet);
            const auto frame=packet.value("source").toMap().value("frame").toMap();
            kinds.append(frame.value("kind").toString());origins.append(frame.value("origin").toString());
            const auto raw=QJsonDocument::fromJson(frame.value("raw").toString().toUtf8()).object().toVariantMap();
            if(frame.value("kind")=="jni-command"){
                jniId=frame.value("eventId").toString();const auto units=QByteArray::fromHex(raw.value("commandUtf16Hex").toString().toLatin1());
                QString exact;for(int i=0;i<units.size();i+=2)exact.append(QChar((quint8(units[i])<<8)|quint8(units[i+1])));
                assert(raw.value("commandUtf8Hex")==QString::fromLatin1(exact.toUtf8().toHex()));
            }
            originals.append(QVariantMap{{"request",observe},{"packet",packet}});
        }
        assert(!jniId.isEmpty());
        if(ime){assert(kinds==QStringList({"jni-command","native-input"}));assert(origins==QStringList({"qt-ime","qt-ime"}));}
        else{
            assert(kinds==QStringList({"keyboard-event","jni-command","native-input","application-target","keyboard-event","application-target"}));
            for(const auto& origin:origins)assert(origin=="keyboard-dispatch");
            assert(attempt->frames[0].toMap().value("eventId")==jniId && attempt->frames[2].toMap().value("eventId")==jniId
                && attempt->frames[3].toMap().value("eventId")==jniId);
            const auto target=QJsonDocument::fromJson(attempt->frames[3].toMap().value("raw").toString().toUtf8()).object();
            assert(target.value("handled").toBool() && target.value("handlerMatchesWindow").toBool() && target.value("focusItemMatches").toBool());
        }
        const auto faultIndex=QCoreApplication::arguments().indexOf("--consumption-fault");
        const auto fault=faultIndex<0 ? QString() : QCoreApplication::arguments().value(faultIndex+1);
        if(!fault.isEmpty()){
            if(fault=="death")item.reset();
            else if(fault=="context")context.reset();
            else if(fault=="window")root.setParentItem(nullptr);
            else if(fault=="grant"){
                Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,false);
                Java_org_overte_web_EmbeddedWebView_nativeForeground(env,javaClass,true);
            }else if(fault=="page")item->acceptPage(returnedGrant,2,QUrl(url));
            else if(fault=="source")item->setUrl(fixture+"tickets/"+nonce()+"/index.html");
            else assert(false);
            events();
            // Explicit synthetic callback counter, not actual Java or DOM
            // proof: the JNI receiver must retain raw bytes after weak loss
            // while preserving its unavailable verdict and original owner.
            QVariantMap callback;
            for(const auto& row:attempt->frames){const auto frame=row.toMap();if(frame.value("kind")=="jni-command"){
                const auto raw=QJsonDocument::fromJson(frame.value("raw").toString().toUtf8()).object().toVariantMap();
                for(const auto& key:{"handle","grant","page","url","commandUtf16Hex","commandUtf8Hex"})callback.insert(key,raw.value(key));
            }}
            callback.insert("isMainThread",false);callback.insert("capturedEpochMs",QDateTime::currentMSecsSinceEpoch());
            callback.insert("capturedElapsedMs",attempt->clock->nowMonotonic());
            const auto callbackRaw=QJsonDocument::fromVariant(callback).toJson(QJsonDocument::Compact);
            const auto callbackClass=static_cast<jclass>(env->NewGlobalRef(javaClass));assert(callbackClass);
            std::thread callbackThread([&]{
                JNIEnv* other=nullptr;assert(machine->AttachCurrentThread(reinterpret_cast<void**>(&other),nullptr)==JNI_OK);
                const auto jId=other->NewString(reinterpret_cast<const jchar*>(jniId.utf16()),jniId.size());
                const auto jStage=other->NewStringUTF("java-entry");const auto raw=QString::fromUtf8(callbackRaw);
                const auto jRaw=other->NewString(reinterpret_cast<const jchar*>(raw.utf16()),raw.size());
                Java_org_overte_web_EmbeddedWebView_nativePicoConsumptionEvent(other,callbackClass,jId,jStage,jRaw);
                other->DeleteLocalRef(jId);other->DeleteLocalRef(jStage);other->DeleteLocalRef(jRaw);
                assert(machine->DetachCurrentThread()==JNI_OK);
            });callbackThread.join();env->DeleteGlobalRef(callbackClass);events();
            assert(attempt->callbackOriginals.size()==1 && attempt->callbackOriginals[0]==callbackRaw && attempt->frames.size()==total+1);
            auto observe=command("observe-current-consumption");observe.insert("attemptNonce",arm.value("commandId"));observe.insert("afterSequence",total);
            const auto unavailable=NativeWebViewItem::featurePicoWorldCurrentConsumption(observe);
            assert(unavailable.value("status")=="unavailable" && attempt->terminal && count("edits")==oldEdits+1);
            record("consumption-counter",{{"case",fault},{"request",observe},{"packet",unavailable},{"callbackRaw",QString::fromUtf8(callbackRaw)},
                {"callbackOriginals",attempt->callbackOriginals.size()},{"edits",count("edits")-oldEdits},{"syntheticJavaCounter",true}});
            puts("PASS actual weak/lifetime JNI late-callback unavailable counter");
        }else{
        auto waiting=command("observe-current-consumption");waiting.insert("attemptNonce",arm.value("commandId"));waiting.insert("afterSequence",total);
        const auto pending=NativeWebViewItem::featurePicoWorldCurrentConsumption(waiting);assert(pending.value("status")=="pending");
        // No Java callback was supplied. Dispatch alone cannot become consume
        // or independent DOM success; the original attempt clock expires.
        // Qt's ordinary coarse timer may wake before its nominal interval.
        // Wait for the recorder's actual original monotonic age, bounded here
        // by a separate host watchdog; do not change the product clock/cap.
        QElapsedTimer watchdog;watchdog.start();
        while(attempt->clock->nowMonotonic()-attempt->clock->monotonic<=5000 && watchdog.elapsed()<5500)events(5);
        auto expired=waiting;expired.insert("commandId",nonce());
        const auto unavailable=NativeWebViewItem::featurePicoWorldCurrentConsumption(expired);
        record("consumption-expiry-diagnostic",{{"request",expired},{"packet",unavailable},
            {"actualAttemptAgeMs",attempt->clock->nowMonotonic()-attempt->clock->monotonic},{"watchdogMs",watchdog.elapsed()}});
        assert(unavailable.value("status")=="unavailable" && unavailable.value("source").toMap().value("reason")=="expired");
        assert(attempt->frames.size()==total && count("edits")==oldEdits+1 && consumeStack.isEmpty());
        record("consumption-originals",{{"frames",originals},{"kinds",kinds},{"origins",origins},{"edits",count("edits")-oldEdits},
            {"pending",pending},{"expiredRequest",expired},{"expired",unavailable},
            {"seams","EntityTree/HUD, Android Java/DOM and controller trigger; original Application/Keyboard/Native/Qt/JNI bodies execute"}});
        puts("PASS actual consumption original dispatch and missing Java callback expiry");
        }
