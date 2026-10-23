//
//  PacketTests.cpp
//  tests/networking/src
//
//  Created by Stephen Birarda on 07/14/15.
//  Copyright 2015 High Fidelity, Inc.
//  Copyright 2021 Vircadia contributors.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "PacketTests.h"
#include <test-utils/QTestExtensions.h>

#include <NLPacket.h>
#include <DomainCheckInPacket.h>
#include <ReceivedMessage.h>
#include <QtNetwork/QUdpSocket>

QTEST_MAIN(PacketTests)

void PacketTests::largeDomainCredentialMessageTest() {
    const QString username = QString::fromUtf8("domain-user-\xC3\xA4");
    const QString credential = QString(2000, QLatin1Char('a')) + ":" + QString(600, QLatin1Char('r'));
    QByteArray payload;
    QDataStream output(&payload, QIODevice::WriteOnly);
    output << username << credential;
    QCOMPARE(output.status(), QDataStream::Ok);
    QVERIFY(payload.size() > NLPacket::maxPayloadSize(PacketType::DomainConnectRequest));

    const auto version = PacketVersion(versionForPacketType(PacketType::DomainConnectRequest) + 1);
    auto packet = overte::network::domainCheckInPacket(PacketType::DomainConnectRequest, version, payload);
    QVERIFY(packet);
    QVERIFY(!packet->isReliable() && !packet->isPartOfMessage());
    QCOMPARE(packet->getVersion(), version);
    QCOMPARE(packet->getPayloadSize(), qint64(payload.size()));
    QVERIFY(packet->getDataSize() <= overte::network::MAX_DOMAIN_CHECK_IN_DATAGRAM_BYTES);

    // An actual UDP receive followed by the existing receiver's decoding path.
    QUdpSocket sender, receiver;
    QVERIFY(receiver.bind(QHostAddress(QHostAddress::LocalHost), quint16(0)));
    QCOMPARE(sender.writeDatagram(packet->getData(), packet->getDataSize(),
                                 QHostAddress::LocalHost, receiver.localPort()), packet->getDataSize());
    QVERIFY(receiver.waitForReadyRead(3000));
    const auto wireSize = receiver.pendingDatagramSize();
    auto wire = std::make_unique<char[]>(wireSize);
    QCOMPARE(receiver.readDatagram(wire.get(), wireSize), wireSize);
    auto decoded = NLPacket::fromReceivedPacket(std::move(wire), wireSize, SockAddr());
    ReceivedMessage received(*decoded);
    QCOMPARE(received.getType(), PacketType::DomainConnectRequest);
    QCOMPARE(received.getVersion(), version);
    QCOMPARE(received.getMessage(), payload);
    QDataStream input(received.getMessage());
    QString actualUsername, actualCredential;
    input >> actualUsername >> actualCredential;
    QCOMPARE(input.status(), QDataStream::Ok);
    QVERIFY(input.atEnd());
    QCOMPARE(actualUsername, username);
    QCOMPARE(actualCredential, credential);

    auto shortPacket = overte::network::domainCheckInPacket(PacketType::DomainConnectRequest, version, "short");
    QVERIFY(shortPacket && shortPacket->getPayloadSize() == 5);
    QVERIFY(!shortPacket->isReliable() && !shortPacket->isPartOfMessage());
    const auto maximum = overte::network::MAX_DOMAIN_CHECK_IN_DATAGRAM_BYTES -
        NLPacket::totalHeaderSize(PacketType::DomainConnectRequest);
    auto boundary = overte::network::domainCheckInPacket(PacketType::DomainConnectRequest, version, QByteArray(maximum, 'x'));
    QVERIFY(boundary);
    QCOMPARE(boundary->getDataSize(), overte::network::MAX_DOMAIN_CHECK_IN_DATAGRAM_BYTES);
    QVERIFY(!overte::network::domainCheckInPacket(PacketType::DomainConnectRequest, version, QByteArray(maximum + 1, 'x')));
    QVERIFY(!overte::network::domainCheckInPacket(PacketType::MixedAudio, version, "short"));
}

std::unique_ptr<NLPacket> copyToReadPacket(std::unique_ptr<NLPacket>& packet) {
    auto size = packet->getDataSize();
    auto data = std::unique_ptr<char[]>(new char[size]);
    memcpy(data.get(), packet->getData(), size);
    return NLPacket::fromReceivedPacket(std::move(data), size, SockAddr());
}

void PacketTests::emptyPacketTest() {
    auto packet = NLPacket::create(PacketType::Unknown);

    QCOMPARE(packet->getType(), PacketType::Unknown);
    QCOMPARE(packet->getPayloadSize(), 0);
    QCOMPARE(packet->getDataSize(), NLPacket::totalHeaderSize(packet->getType()));
    QCOMPARE(packet->bytesLeftToRead(), 0);
    QCOMPARE(packet->bytesAvailableForWrite(), packet->getPayloadCapacity());
}

void PacketTests::packetTypeTest() {
    auto packet = NLPacket::create(PacketType::EntityAdd);

    QCOMPARE(packet->getType(), PacketType::EntityAdd);

    packet->setType(PacketType::MixedAudio);
    QCOMPARE(packet->getType(), PacketType::MixedAudio);

    packet->setType(PacketType::MuteEnvironment);
    QCOMPARE(packet->getType(), PacketType::MuteEnvironment);
}

void PacketTests::writeTest() {
    auto packet = NLPacket::create(PacketType::Unknown);

    QCOMPARE(packet->getPayloadSize(), 0);

    QCOMPARE(packet->write("somedata"), 8);
    QCOMPARE(packet->getPayloadSize(), 8);

    QCOMPARE(packet->write("moredata"), 8);
    QCOMPARE(packet->getPayloadSize(), 16);

    COMPARE_DATA(packet->getPayload(), "somedatamoredata", 16);
}

void PacketTests::readTest() {
    // Test reads for several different size packets
    for (int i = 1; i < 4; i++) {
        auto packet = NLPacket::create(PacketType::Unknown);

        auto size = packet->getPayloadCapacity();
        size /= i;

        char* data = new char[size];

        // Fill with "random" data
        for (qint64 i = 0; i < size; i++) {
            data[i] = i;
        }

        QCOMPARE(packet->write(data, size), size);

        auto readPacket = copyToReadPacket(packet);

        QCOMPARE(readPacket->getDataSize(), packet->getDataSize());
        QCOMPARE(readPacket->getPayloadSize(), packet->getPayloadSize());
        COMPARE_DATA(readPacket->getData(), packet->getData(), packet->getDataSize());
        COMPARE_DATA(readPacket->getPayload(), packet->getPayload(), packet->getPayloadSize());

        auto payloadSize = readPacket->getPayloadSize();
        char* readData = new char[payloadSize];
        QCOMPARE(readPacket->read(readData, payloadSize), payloadSize);
        COMPARE_DATA(readData, data, payloadSize);
    }
}

void PacketTests::writePastCapacityTest() {
    #ifndef QT_NO_DEBUG
    QSKIP("This test triggers an assertion when built in debug mode");
    #else
    auto packet = NLPacket::create(PacketType::Unknown);

    auto size = packet->getPayloadCapacity();
    char* data = new char[size];

    // Fill with "random" data
    for (qint64 i = 0; i < size; i++) {
        data[i] = i;
    }

    QCOMPARE(packet->getPayloadSize(), 0);

    QCOMPARE(packet->write(data, size), size);

    QCOMPARE(packet->getPayloadSize(), size);
    COMPARE_DATA(packet->getPayload(), data, size);

    QCOMPARE(packet->bytesAvailableForWrite(), 0);
    QCOMPARE(packet->getPayloadSize(), size);

    QCOMPARE(NLPacket::PACKET_WRITE_ERROR, packet->write("data")); // asserts in DEBUG

    // NLPacket::write() shouldn't allow the caller to write if no space is left
    QCOMPARE(packet->getPayloadSize(), size);
    #endif
}

void PacketTests::primitiveTest() {
    auto packet = NLPacket::create(PacketType::Unknown);

    int value1 = 5;
    char value2 = 10;
    bool value3 = true;
    qint64 value4 = -93404;

    packet->writePrimitive(value1);
    packet->writePrimitive(value2);
    packet->writePrimitive(value3);
    packet->writePrimitive(value4);

    auto recvPacket = copyToReadPacket(packet);

    // Peek & read first value
    {
        int peekValue = 0;
        QCOMPARE(recvPacket->peekPrimitive(&peekValue), (int)sizeof(peekValue));
        QCOMPARE(peekValue, value1);
        int readValue = 0;
        QCOMPARE(recvPacket->readPrimitive(&readValue), (int)sizeof(readValue));
        QCOMPARE(readValue, value1);
    }

    // Peek & read second value
    {
        char peekValue = 0;
        QCOMPARE(recvPacket->peekPrimitive(&peekValue), (int)sizeof(peekValue));
        QCOMPARE(peekValue, value2);

        char readValue = 0;
        QCOMPARE(recvPacket->readPrimitive(&readValue), (int)sizeof(readValue));
        QCOMPARE(readValue, value2);
    }

    // Peek & read third value
    {
        bool peekValue = 0;
        QCOMPARE(recvPacket->peekPrimitive(&peekValue), (int)sizeof(peekValue));
        QCOMPARE(peekValue, value3);

        bool readValue = 0;
        QCOMPARE(recvPacket->readPrimitive(&readValue), (int)sizeof(readValue));
        QCOMPARE(readValue, value3);
    }

    // Peek & read fourth value
    {
        qint64 peekValue = 0;
        QCOMPARE(recvPacket->peekPrimitive(&peekValue), (int)sizeof(peekValue));
        QCOMPARE(peekValue, value4);

        qint64 readValue = 0;
        QCOMPARE(recvPacket->readPrimitive(&readValue), (int)sizeof(readValue));
        QCOMPARE(readValue, value4);
    }

    // We should be at the end of the packet, with no more to peek or read
    int noValue;
    QCOMPARE(recvPacket->peekPrimitive(&noValue), 0);
    QCOMPARE(recvPacket->readPrimitive(&noValue), 0);
}
