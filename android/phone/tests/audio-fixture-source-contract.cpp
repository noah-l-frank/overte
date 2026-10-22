// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "../../../libraries/audio-client/src/PhoneAudioFixtureInput.h"
#include "../../../tests/device/native/PhoneAudioFixtureHTTP.h"
#include "../../../tests/device/native/PrivatePreviewFiles.h"
#include <QBuffer>
#include <QSharedPointer>
#include <QThread>
#include <QTemporaryDir>
#include <QTcpServer>
#include <QTcpSocket>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <cassert>
#include <iostream>

// Only hardware/format descriptors and unrelated product state are fixtures.
// All four AudioClient methods and the Test entry below are extracted verbatim
// from their production sources by the build script.
namespace QAudio { enum State { ActiveState, StoppedState }; enum Error { NoError, IOError }; }
struct InputDescriptor {
    QAudio::State current {QAudio::ActiveState}; QAudio::Error failure {QAudio::NoError};
    QAudio::State state() const { return current; } QAudio::Error error() const { return failure; }
};
struct QAudioFormat {
    enum SampleType { SignedInt, Float }; enum Endian { LittleEndian, BigEndian };
    int rate {48000}, channels {2}, width {16}; SampleType type {SignedInt}; Endian order {LittleEndian};
    int sampleRate() const { return rate; } int channelCount() const { return channels; }
    int sampleSize() const { return width; } SampleType sampleType() const { return type; } Endian byteOrder() const { return order; }
};
class AudioClient : public QObject {
public:
    bool recordedVoiceTestInputAvailable() const;
    QVariantMap phoneAudioFixtureObservation() const;
    bool armPhoneAudioFixture(const QByteArray&, const QVariantMap&);
    void releasePhoneAudioFixture();
    QVariantMap featureRecordedVoiceObservation() const { return {{"fixture", "unrelated-product-history"}}; }
    overte::e2e::PhoneAudioFixtureInput _e2ePhoneAudioInput;
    QAudioFormat _inputFormat;
    InputDescriptor _input;
    InputDescriptor* _audioInput {&_input};
    QBuffer _device;
    QIODevice* _inputDevice {&_device};
    bool _recordedVoiceTestActive {false}, _audioLifecycleRunning {true}, _audioPaused {false}, _isMuted {false}, _voiceTestInputEnabled {false};
};
struct DependencyManager {
    template<class T> static QSharedPointer<T> get() { static auto value = QSharedPointer<T>::create(); return value; }
};
struct LifecycleDescriptor { QVariantMap snapshot() const { return {{"fixture", "live"}}; } };
class TestScriptingInterface : public QObject {
public:
    QVariantMap phoneAudioFixture(const QVariantMap&);
    QString _testResultsLocation;
    LifecycleDescriptor* _featureLifecycle {nullptr};
    std::shared_ptr<overte::e2e::PhoneAudioFixtureHTTP> _phoneAudioFixture;
};
#include AUDIO_ORIGINAL_ENTRY

static void settle(const std::function<bool()>& predicate) {
    QElapsedTimer bound; bound.start();
    while (!predicate() && bound.elapsed() < 3000) { QCoreApplication::processEvents(QEventLoop::AllEvents, 10); }
    assert(predicate());
}

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    using namespace overte::e2e;
    auto audio = DependencyManager::get<AudioClient>();
    if (!app.arguments().contains("--testScript")) {
        assert(!audio->armPhoneAudioFixture(QByteArray(144000, 0), {{"input", true}}));
        assert(audio->phoneAudioFixtureObservation().isEmpty());
        TestScriptingInterface test; assert(test.phoneAudioFixture({}).isEmpty());
        std::cout << "Actual AudioClient/Test entry rejects non-test launches\n"; return 0;
    }
    PhoneAudioFixtureInput input;
    QByteArray pcm(144000, 0);
    for (int i = 0; i < 72000; ++i) { qToLittleEndian<qint16>(i % 5000, reinterpret_cast<uchar*>(pcm.data()) + i * 2); }
    const QVariantMap provenance {{"original", "http"}};
    assert(audio->recordedVoiceTestInputAvailable());
    audio->_inputDevice = nullptr; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_inputDevice = &audio->_device;
    audio->_input.current = QAudio::StoppedState; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_input.current = QAudio::ActiveState;
    audio->_input.failure = QAudio::IOError; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_input.failure = QAudio::NoError;
    audio->_audioPaused = true; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_audioPaused = false;
    audio->_audioLifecycleRunning = false; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_audioLifecycleRunning = true;
    audio->_recordedVoiceTestActive = true; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_recordedVoiceTestActive = false;
    audio->_voiceTestInputEnabled = true; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_voiceTestInputEnabled = false;
    audio->_inputFormat.width = 32; assert(!audio->armPhoneAudioFixture(pcm, provenance)); audio->_inputFormat.width = 16;
    assert(audio->armPhoneAudioFixture(pcm, provenance)); assert(!audio->_recordedVoiceTestActive); audio->releasePhoneAudioFixture();
    assert(!input.arm(QByteArray(4, 0), provenance));
    assert(!input.arm(pcm, {}));
    assert(input.arm(pcm, provenance)); assert(!input.arm(pcm, provenance));
    QByteArray raw(1920, '\x7f');
    input.replace(raw, 48000, 2, false, 0); assert(raw == QByteArray(1920, 0));
    assert(input.snapshot().value("cycle").toULongLong() == 0);
    input.replace(raw, 48000, 2, true, 7);
    assert(qFromLittleEndian<qint16>(reinterpret_cast<const uchar*>(raw.constData()) + 8) == 1);
    assert(qFromLittleEndian<qint16>(reinterpret_cast<const uchar*>(raw.constData()) + 10) == 1);
    assert(input.snapshot().value("inputFrames").toULongLong() == 480);
    input.emitted(20, false, "actual-opus"); input.emitted(3, true, "actual-opus");
    assert(input.snapshot().value("packetEmits").toULongLong() == 2);
    assert(input.snapshot().value("encodedBytes").toULongLong() == 23);
    input.replace(raw, 48000, 2, true, 8); assert(!input.snapshot().value("complete").toBool());
    assert(raw == QByteArray(raw.size(), 0));
    input.clear(); assert(input.snapshot().value("pcmBytes").toInt() == 0);
    assert(input.snapshot().value("receipt").toMap().isEmpty());

    QTcpServer server; assert(server.listen(QHostAddress::LocalHost));
    QString mode = "normal"; QPointer<QTcpSocket> held;
    QObject::connect(&server, &QTcpServer::newConnection, &app, [&] {
        auto socket = server.nextPendingConnection();
        QObject::connect(socket, &QTcpSocket::readyRead, &app, [&, socket] {
            if (!socket->readAll().contains("\r\n\r\n")) { return; }
            if (mode == "held") { held = socket; return; }
            if (mode == "redirect") {
                socket->write("HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:1/forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
            } else {
                auto body = mode == "oversized" ? QByteArray(144001, 0) : pcm;
                const QByteArray response = mode == "bad-id" ? "invalid" : QByteArray(32, 'e');
                socket->write("HTTP/1.1 200 OK\r\nX-Overte-Fixture-Response: " + response + "\r\nContent-Length: "
                    + QByteArray::number(body.size()) + "\r\nConnection: close\r\n\r\n" + body);
            }
            socket->disconnectFromHost();
        });
    });
    int arms = 0;
    PhoneAudioFixtureHTTP http(&app, [&](const QByteArray& actual, const QVariantMap& receipt) {
        ++arms; assert(actual == pcm); assert(receipt.value("responseId").toString() == QString(32, 'e'));
        return input.arm(actual, receipt);
    }, [&] { return input.snapshot(); }, [&] { input.clear(); });
    int serial = 0;
    QVariantMap lastCommand;
    const QString run(32, 'a');
    auto request = [&](const QString& operation, QString ticket = {}) {
        QVariantMap command {{"schemaVersion", 1.0}, {"commandId", QString("%1").arg(++serial, 32, 16, QChar('0'))}, {"operation", operation}};
        if (operation == "arm") {
            command["runId"] = run; command["ticket"] = ticket;
            command["url"] = QString("http://127.0.0.1:%1/feature-fixture/v1/runs/%2/tickets/%3/preview-input.v1.pcm16le")
                .arg(server.serverPort()).arg(run, ticket);
        }
        lastCommand = command; return http.command(command);
    };
    assert(request("arm", QString(32, 'b')).value("pending").toBool());
    settle([&] { return !request("observe").value("pending").toBool(); });
    auto value = request("observe"); assert(arms == 1 && value.value("error").toString().isEmpty());
    assert(value.value("source").toMap().value("armed").toBool());
    assert(value.value("receipt").toMap().value("bytes").toInt() == 144000);
    request("release"); const auto oldRelease = lastCommand;
    assert(!request("observe").value("source").toMap().value("armed").toBool());
    assert(request("arm", QString(32, 'b')).isEmpty());
    for (const auto& bad : {QString("redirect"), QString("oversized"), QString("bad-id")}) {
        mode = bad; const QString ticket = QString("%1").arg(++serial, 32, 16, QChar('0'));
        assert(request("arm", ticket).value("pending").toBool());
        settle([&] { return !request("observe").value("pending").toBool(); });
        assert(!request("observe").value("error").toString().isEmpty() && arms == 1);
        request("release");
    }
    mode = "held"; request("arm", QString(32, 'c')); settle([&] { return !held.isNull(); });
    request("release");
    if (held) { held->write("HTTP/1.1 200 OK\r\nContent-Length: 144000\r\nX-Overte-Fixture-Response: " + QByteArray(32, 'e') + "\r\n\r\n" + pcm); held->disconnectFromHost(); }
    QCoreApplication::processEvents(); assert(arms == 1);
    value = request("observe"); assert(!value.value("pending").toBool() && value.value("pendingBytes").toInt() == 0);
    assert(value.value("source").toMap().value("pcmBytes").toInt() == 0);
    mode = "normal"; request("arm", QString(32, 'd'));
    settle([&] { return !request("observe").value("pending").toBool(); });
    assert(arms == 2 && input.snapshot().value("armed").toBool());
    assert(http.command(oldRelease).isEmpty()); // An old release cannot retire a new lease.
    assert(input.snapshot().value("armed").toBool());
    auto altered = lastCommand; altered["operation"] = "release";
    assert(http.command(altered).isEmpty() && input.snapshot().value("armed").toBool());
    request("release"); const auto original = request("observe");
    assert(http.command(lastCommand) == original); // Same original sequence/time, no retiming.
    QThread worker; audio->moveToThread(&worker); worker.start();
    QTemporaryDir privateDirectory;
    LifecycleDescriptor lifecycle;
    TestScriptingInterface test; test._testResultsLocation = privateDirectory.path(); test._featureLifecycle = &lifecycle;
    auto nativeRequest = [&](const QString& operation) {
        return test.phoneAudioFixture({{"schemaVersion", 1}, {"commandId", QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')}, {"operation", operation}});
    };
    auto native = nativeRequest("observe"); assert(native.value("source").toMap().value("inputAvailable").toBool());
    assert(!native.value("source").toMap().value("armed").toBool());
    assert(audio->phoneAudioFixtureObservation().isEmpty()); // Wrong thread cannot acquire or mutate.
    assert(!audio->armPhoneAudioFixture(pcm, provenance));
    nativeRequest("release"); native = nativeRequest("observe"); assert(!native.value("source").toMap().value("armed").toBool());
    QMetaObject::invokeMethod(audio.data(), [&] { audio->moveToThread(app.thread()); }, Qt::BlockingQueuedConnection);
    worker.quit(); worker.wait();
    std::cout << "Actual Phone PCM input and original HTTP reader contracts passed\n";
}
