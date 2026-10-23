// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <cstring>
#include "NLPacket.h"

namespace overte { namespace network {
constexpr qint64 MAX_DOMAIN_CHECK_IN_DATAGRAM_BYTES = 8192;

// Domain admission precedes the server's reliable-channel admission filter.
// Keep its existing single-datagram wire format. Only these bounded, infrequent
// check-ins may exceed the ordinary MTU; the IP stack handles fragmentation.
inline std::unique_ptr<NLPacket> domainCheckInPacket(PacketType type, PacketVersion version,
                                                   const QByteArray& payload) {
    if (type != PacketType::DomainConnectRequest && type != PacketType::DomainListRequest) {
        return {};
    }
    auto packet = NLPacket::create(type, -1, false, false, version);
    const auto headerSize = packet->getDataSize();
    const auto wireSize = headerSize + payload.size();
    if (wireSize > MAX_DOMAIN_CHECK_IN_DATAGRAM_BYTES) {
        return {};
    }
    if (payload.size() <= packet->bytesAvailableForWrite()) {
        packet->write(payload);
        return packet;
    }
    // Use the existing complete-wire-buffer decoder, which already accepts
    // reassembled UDP datagrams. This changes neither the protocol nor the
    // ordinary packet allocator and introduces no pre-auth reliable channel.
    auto wire = std::make_unique<char[]>(wireSize);
    std::memcpy(wire.get(), packet->getData(), headerSize);
    std::memcpy(wire.get() + headerSize, payload.constData(), payload.size());
    return NLPacket::fromReceivedPacket(std::move(wire), wireSize, SockAddr());
}
} }
