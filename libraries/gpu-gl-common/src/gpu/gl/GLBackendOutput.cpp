//
//  GLBackendTexture.cpp
//  libraries/gpu/src/gpu
//
//  Created by Sam Gateau on 1/19/2015.
//  Copyright 2014 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//
#include "GLBackend.h"
#include "GLShared.h"
#include "GLFramebuffer.h"

#include <QtGui/QImage>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QtCore/QCoreApplication>
#include <QtGui/QOpenGLContext>
#endif

using namespace gpu;
using namespace gpu::gl;

void GLBackend::syncOutputStateCache() {
    GLint currentFBO;
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &currentFBO);

    _output._drawFBO = currentFBO;
    reset(_output._framebuffer);
}

void GLBackend::resetOutputStage() {
    if (valid(_output._framebuffer)) {
        reset(_output._framebuffer);
        _output._drawFBO = 0;
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
    }

    glEnable(GL_FRAMEBUFFER_SRGB);
}

void GLBackend::do_setFramebuffer(const Batch& batch, size_t paramOffset) {
    const auto& framebuffer = batch._framebuffers.get(batch._params[paramOffset]._uint);
    setFramebuffer(framebuffer);
}

void GLBackend::do_setFramebufferSwapChain(const Batch& batch, size_t paramOffset) {
    auto swapChain = std::static_pointer_cast<FramebufferSwapChain>(batch._swapChains.get(batch._params[paramOffset]._uint));
    if (swapChain) {
        auto index = batch._params[paramOffset + 1]._uint;
        const auto& framebuffer = swapChain->get(index);
        setFramebuffer(framebuffer);
    }
}

void GLBackend::setFramebuffer(const FramebufferPointer& framebuffer) {
    if (!compare(_output._framebuffer, framebuffer)) {
        auto newFBO = getFramebufferID(framebuffer);
        if (_output._drawFBO != newFBO) {
            _output._drawFBO = newFBO;
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, newFBO);
        }
        assign(_output._framebuffer, framebuffer);
    }
}

void GLBackend::do_advance(const Batch& batch, size_t paramOffset) {
    auto ringbuffer = batch._swapChains.get(batch._params[paramOffset]._uint);
    if (ringbuffer) {
        ringbuffer->advance();
    }
}

void GLBackend::do_clearFramebuffer(const Batch& batch, size_t paramOffset) {
    if (_stereo.isStereo() && !_pipeline._stateCache.flags.scissorEnable) {
        qWarning("Clear without scissor in stereo mode");
    }

    uint32 masks = batch._params[paramOffset + 7]._uint;
    Vec4 color;
    color.x = batch._params[paramOffset + 6]._float;
    color.y = batch._params[paramOffset + 5]._float;
    color.z = batch._params[paramOffset + 4]._float;
    color.w = batch._params[paramOffset + 3]._float;
    float depth = batch._params[paramOffset + 2]._float;
    int stencil = batch._params[paramOffset + 1]._int;
    int useScissor = batch._params[paramOffset + 0]._int;

    GLuint glmask = 0;
    bool restoreStencilMask = false;
    uint8_t cacheStencilMask = 0xFF;
    if (masks & Framebuffer::BUFFER_STENCIL) {
        glClearStencil(stencil);
        glmask |= GL_STENCIL_BUFFER_BIT;

        cacheStencilMask = _pipeline._stateCache.stencilActivation.getWriteMaskFront();
        if (cacheStencilMask != 0xFF) {
            restoreStencilMask = true;
            glStencilMask( 0xFF);
        }
    }

    bool restoreDepthMask = false;
    if (masks & Framebuffer::BUFFER_DEPTH) {
        glClearDepthf(depth);
        glmask |= GL_DEPTH_BUFFER_BIT;
        
        bool cacheDepthMask = _pipeline._stateCache.depthTest.getWriteMask();
        if (!cacheDepthMask) {
            restoreDepthMask = true;
            glDepthMask(GL_TRUE);
        }
    }

    std::vector<GLenum> drawBuffers;
    auto framebuffer = acquire(_output._framebuffer);
    if (masks & Framebuffer::BUFFER_COLORS) {
        if (framebuffer) {
            for (unsigned int i = 0; i < Framebuffer::MAX_NUM_RENDER_BUFFERS; i++) {
                if (masks & (1 << i)) {
                    drawBuffers.push_back(GL_COLOR_ATTACHMENT0 + i);
                }
            }

            if (!drawBuffers.empty()) {
                glDrawBuffers((GLsizei)drawBuffers.size(), drawBuffers.data());
                glClearColor(color.x, color.y, color.z, color.w);
                glmask |= GL_COLOR_BUFFER_BIT;
            
                (void) CHECK_GL_ERROR();
            }
        } else {
            glClearColor(color.x, color.y, color.z, color.w);
            glmask |= GL_COLOR_BUFFER_BIT;
        }
        
        // Force the color mask cache to WRITE_ALL if not the case
        do_setStateColorWriteMask(State::ColorMask::WRITE_ALL);
    }

    // Apply scissor if needed and if not already on
    bool doEnableScissor = (useScissor && (!_pipeline._stateCache.flags.scissorEnable));
    if (doEnableScissor) {
        glEnable(GL_SCISSOR_TEST);
    }

    // Clear!
    glClear(glmask);

    // Restore scissor if needed
    if (doEnableScissor) {
        glDisable(GL_SCISSOR_TEST);
    }

    // Restore Stencil write mask
    if (restoreStencilMask) {
        glStencilMask(cacheStencilMask);
    }

    // Restore write mask meaning turn back off
    if (restoreDepthMask) {
        glDepthMask(GL_FALSE);
    }
    
    // Restore the color draw buffers only if a frmaebuffer is bound
    if (framebuffer && !drawBuffers.empty()) {
        auto glFramebuffer = syncGPUObject(*framebuffer);
        if (glFramebuffer) {
            glDrawBuffers((GLsizei)glFramebuffer->_colorBuffers.size(), glFramebuffer->_colorBuffers.data());
        }
    }

    (void) CHECK_GL_ERROR();
}

void GLBackend::downloadFramebuffer(const FramebufferPointer& srcFramebuffer, const Vec4i& region, QImage& destImage) {
    auto readFBO = getFramebufferID(srcFramebuffer);
    if (srcFramebuffer && readFBO) {
        if ((srcFramebuffer->getWidth() < (region.x + region.z)) || (srcFramebuffer->getHeight() < (region.y + region.w))) {
          qCWarning(gpugllogging) << "GLBackend::downloadFramebuffer : srcFramebuffer is too small to provide the region queried";
          return;
        }
    }

    if ((destImage.width() < region.z) || (destImage.height() < region.w)) {
          qCWarning(gpugllogging) << "GLBackend::downloadFramebuffer : destImage is too small to receive the region of the framebuffer";
          return;
    }

    GLenum format = GL_BGRA;
    auto backendApi = hifi::properties::getGraphicsAPI();
    if (backendApi == hifi::properties::GraphicsAPI::GLES32) {
        format = GL_RGBA;
    }
    if (destImage.format() != QImage::Format_ARGB32) {
          qCWarning(gpugllogging) << "GLBackend::downloadFramebuffer : destImage format must be FORMAT_ARGB32 to receive the region of the framebuffer";
          return;
    }

    glBindFramebuffer(GL_READ_FRAMEBUFFER, getFramebufferID(srcFramebuffer));
    glReadPixels(region.x, region.y, region.z, region.w, format, GL_UNSIGNED_BYTE, destImage.bits());
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);

    (void) CHECK_GL_ERROR();
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
bool GLBackend::featureReadFramebuffer(const FramebufferPointer& framebuffer, QImage& image) {
    image = QImage();
    if (!QCoreApplication::arguments().contains("--testScript") || !QOpenGLContext::currentContext()
            || !framebuffer || framebuffer->getWidth() < 1 || framebuffer->getHeight() < 1
            || framebuffer->getWidth() > 4096 || framebuffer->getHeight() > 4096
            || static_cast<quint64>(framebuffer->getWidth())*framebuffer->getHeight() > 8388608ULL) { return false; }
    // The original completed draw must already have created this exact GPU
    // object. Do not synchronize/create a framebuffer or read the default UI
    // target as a fallback. GPU backend family is fixed by Context::init.
    const auto object = Backend::getGPUObject<GLFramebuffer>(*framebuffer);
    if (!object || !object->_fbo || object->_colorBuffers.empty()) { return false; }
    GLint drawFbo {0}, drawBuffer {0};
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&drawFbo);
    glGetIntegerv(GL_DRAW_BUFFER0,&drawBuffer);
    if (static_cast<GLuint>(drawFbo) != object->_fbo || drawBuffer != GL_COLOR_ATTACHMENT0) { return false; }
    QImage pixels(framebuffer->getWidth(),framebuffer->getHeight(),QImage::Format_RGBA8888);
    if (pixels.isNull() || pixels.bytesPerLine() != pixels.width()*4) { return false; }

    GLint readFbo {0}, packBuffer {0}, alignment {0}, rowLength {0}, skipRows {0}, skipPixels {0};
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,&readFbo);
    glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING,&packBuffer);
    glGetIntegerv(GL_PACK_ALIGNMENT,&alignment);
    glGetIntegerv(GL_PACK_ROW_LENGTH,&rowLength);
    glGetIntegerv(GL_PACK_SKIP_ROWS,&skipRows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS,&skipPixels);
    glBindFramebuffer(GL_READ_FRAMEBUFFER,object->_fbo);
    GLint sourceReadBuffer {0}; glGetIntegerv(GL_READ_BUFFER,&sourceReadBuffer);
    glReadBuffer(GL_COLOR_ATTACHMENT0);
    glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
    glPixelStorei(GL_PACK_ALIGNMENT,1);
    glPixelStorei(GL_PACK_ROW_LENGTH,0);
    glPixelStorei(GL_PACK_SKIP_ROWS,0);
    glPixelStorei(GL_PACK_SKIP_PIXELS,0);
    const bool complete = glCheckFramebufferStatus(GL_READ_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE;
    if (complete) {
        // RGBA byte order is explicit on both desktop GL and GLES. This
        // synchronous read completes earlier writes to the original target.
        glReadPixels(0,0,pixels.width(),pixels.height(),GL_RGBA,GL_UNSIGNED_BYTE,pixels.bits());
    }
    // Restore source FBO's own read selection, previous read binding and all
    // pack state, including a caller's PBO. Draw binding/cache is untouched.
    glReadBuffer(static_cast<GLenum>(sourceReadBuffer));
    glBindFramebuffer(GL_READ_FRAMEBUFFER,static_cast<GLuint>(readFbo));
    glBindBuffer(GL_PIXEL_PACK_BUFFER,static_cast<GLuint>(packBuffer));
    glPixelStorei(GL_PACK_ALIGNMENT,alignment);
    glPixelStorei(GL_PACK_ROW_LENGTH,rowLength);
    glPixelStorei(GL_PACK_SKIP_ROWS,skipRows);
    glPixelStorei(GL_PACK_SKIP_PIXELS,skipPixels);
    // An existing or acquisition/restoration GL error cannot yield evidence.
    if (!complete || glGetError() != GL_NO_ERROR) { return false; }
    auto upright = pixels.mirrored(false,true); // Lossless native coordinate origin conversion.
    if (upright.isNull()) { return false; }
    image = std::move(upright);
    return true;
}
#endif
