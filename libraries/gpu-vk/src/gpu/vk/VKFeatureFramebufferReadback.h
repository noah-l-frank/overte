// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <gpu/FeatureFramebufferReadback.h>
#include <vk/VulkanDevice.h>
#include <QImage>
#include <cstring>
#include <memory>
#include <utility>

namespace gpu::vk {
// This allocation is never mapped/read before the existing submission fence
// succeeds. The frame owner retains unknown submissions, including their buffer.
class FeatureFramebufferReadback final : public gpu::FeatureFramebufferReadback {
public:
    FeatureFramebufferReadback(std::shared_ptr<vks::VulkanDevice> device,int width,int height,VkFormat format)
        : _device(std::move(device)),_width(width),_height(height),_format(format) {}
    ~FeatureFramebufferReadback() override { clear(); }
    bool allocate() {
        if (!_device || _device->logicalDevice==VK_NULL_HANDLE || _width<1 || _height<1
                || _width>4096 || _height>4096 || static_cast<quint64>(_width)*_height>8388608ULL
                || (_format!=VK_FORMAT_R8G8B8A8_UNORM && _format!=VK_FORMAT_R8G8B8A8_SRGB
                    && _format!=VK_FORMAT_B8G8R8A8_UNORM && _format!=VK_FORMAT_B8G8R8A8_SRGB)) { return false; }
        VkBufferCreateInfo bufferInfo {};bufferInfo.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
        bufferInfo.size=static_cast<VkDeviceSize>(_width)*_height*4;
        bufferInfo.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT;bufferInfo.sharingMode=VK_SHARING_MODE_EXCLUSIVE;
        if (vkCreateBuffer(_device->logicalDevice,&bufferInfo,nullptr,&_buffer)!=VK_SUCCESS) { return false; }
        VkMemoryRequirements requirements {};vkGetBufferMemoryRequirements(_device->logicalDevice,_buffer,&requirements);
        if (requirements.size<bufferInfo.size || requirements.size>67108864ULL) { return false; }
        VkBool32 found {VK_FALSE};
        const auto type=_device->getMemoryType(requirements.memoryTypeBits,
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,&found);
        if (found!=VK_TRUE) { return false; }
        VkMemoryAllocateInfo allocation {};allocation.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        allocation.allocationSize=requirements.size;allocation.memoryTypeIndex=type;
        if (vkAllocateMemory(_device->logicalDevice,&allocation,nullptr,&_memory)!=VK_SUCCESS) { return false; }
        _bytes=requirements.size;
        return vkBindBufferMemory(_device->logicalDevice,_buffer,_memory,0)==VK_SUCCESS;
    }
    VkBuffer buffer() const { return _buffer; }
    quint64 bytes() const override { return _bytes; }
    bool complete(QImage& result) override {
        result=QImage();
        void* mapped {nullptr};
        if (!_buffer || !_memory || vkMapMemory(_device->logicalDevice,_memory,0,_bytes,0,&mapped)!=VK_SUCCESS || !mapped) { return false; }
        QImage original(_width,_height,QImage::Format_RGBA8888);
        const bool okay=!original.isNull() && original.bytesPerLine()==_width*4;
        if (okay) {
            const auto source=static_cast<const unsigned char*>(mapped);auto target=original.bits();
            if (_format==VK_FORMAT_R8G8B8A8_UNORM || _format==VK_FORMAT_R8G8B8A8_SRGB) {
                std::memcpy(target,source,static_cast<size_t>(_width)*_height*4);
            } else {
                for (quint64 pixel=0;pixel<static_cast<quint64>(_width)*_height;++pixel) {
                    target[pixel*4]=source[pixel*4+2];target[pixel*4+1]=source[pixel*4+1];
                    target[pixel*4+2]=source[pixel*4];target[pixel*4+3]=source[pixel*4+3];
                }
            }
        }
        vkUnmapMemory(_device->logicalDevice,_memory);clear();
        if (okay) { result=std::move(original); }
        return okay;
    }
private:
    void clear() {
        if (_device && _device->logicalDevice!=VK_NULL_HANDLE) {
            if (_buffer) { vkDestroyBuffer(_device->logicalDevice,_buffer,nullptr);_buffer=VK_NULL_HANDLE; }
            if (_memory) { vkFreeMemory(_device->logicalDevice,_memory,nullptr);_memory=VK_NULL_HANDLE; }
        }
        _bytes=0;
    }
    std::shared_ptr<vks::VulkanDevice> _device;
    int _width {0},_height {0};VkFormat _format {VK_FORMAT_UNDEFINED};
    VkBuffer _buffer {VK_NULL_HANDLE};VkDeviceMemory _memory {VK_NULL_HANDLE};quint64 _bytes {0};
};
}
#endif
