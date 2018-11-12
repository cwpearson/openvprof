from collections import namedtuple, defaultdict


class Device(object):
    def __init__(self, id_=None):
        self.id_ = id_


RUNTIME_CBID_NAME = {
    3: "cudaGetDeviceCount",
    4: "cudaGetDeviceProperties",
    10: "cudaGetLastError",
    16: "cudaSetDevice",
    17: "cudaGetDevice",
    20: "cudaMalloc",
    22: "cudaFree",
    27: "cudaHostAlloc",
    28: "cudaHostGetDevicePointer",
    31: "cudaMemcpy",
    41: "cudaMemcpyAsync",
    51: "cudaMemsetAsync",
    55: "cudaBindTexture",
    58: "cudaUnbindTexture",
    129: "cudaStreamCreate",
    131: "cudaStreamSynchronize",
    133: "cudaEventCreate",
    134: "cudaEventCreateWithFlags",
    135: "cudaEventRecord",
    136: "cudaEventDestroy",
    137: "cudaEventSynchronize",
    147: "cudaStreamWaitEvent",
    152: "cudaHostRegister",
    153: "cudaHostUnregister",
    165: "cudaDeviceSynchronize",
    197: "cudaStreamAddCallback",
    198: "cudaStreamCreateWithFlags",
    200: "cudaDeviceGetAttribute",
    202: "cudaStreamCreateWithPriority",
    205: "cudaDeviceGetStreamPriorityRange",
    211: "cudaLaunchKernel",
    273: "cudaFuncSetAttribute",
}


class Runtime(namedtuple('Runtime', ['cbid', 'start', 'end', 'pid', 'tid', 'correlation_id', 'return_value'])):
    __slots__ = ()

    def from_nvprof_row(row, strings):
        tid = row[5]
        if tid < 0:
            tid += 2**32
            assert tid >= 0
        return Runtime(*row[1:5], tid, *row[6:])

    def name(self):
        if self.cbid in RUNTIME_CBID_NAME:
            return RUNTIME_CBID_NAME[self.cbid]
        else:
            return str(self.cbid)

    def __str__(self):
        s = "Runtime::" + str(self.pid) + "::" + str(self.tid) + "::"
        if self.cbid in RUNTIME_CBID_NAME:
            s += RUNTIME_CBID_NAME[self.cbid]
        else:
            s += str(self.cbid)
        return s


class ConcurrentKernel(namedtuple('ConcurrentKernel', ['start', 'end', 'completed', 'device_id', 'name'])):
    __slots__ = ()

    def from_nvprof_row(row, strings):
        return ConcurrentKernel(*row[6:10], strings[row[24]])


class Memcpy(namedtuple('Memcpy', ['copy_kind', 'src_kind', 'dst_kind', 'bytes', 'start', 'end', 'device_id'])):
    __slots__ = ()

    def from_nvprof_row(row, strings):
        return Memcpy(*row[1:4], *row[5:9])


class Marker(namedtuple('Marker', ['timestamp', 'id_', 'name'])):
    __slots__ = ()

    def from_nvprof_row(row, strings):
        return Marker(*row[2:4], strings[row[6]])

# could be produced with a query like
# SELECT start, end, name, domain from (
# SELECT
# count(*) as num_markers,
# Max(timestamp) as start,
#  Min(timestamp) as end,
#  Max(name) as name,
#  domain
# FROM CUPTI_ACTIVITY_KIND_MARKER group by id
# ) where num_markers == 2


class Range(namedtuple('Range', ['start', 'end', 'name', 'domain'])):
    """Represents a paired set of markers from nvprof"""
    __slots__ = ()

    def from_nvprof_row(row, strings):
        return Range(*row[0:2], strings[row[2]], strings[row[3]])


"""
cbids for runtime functions
// *************************************************************************
//      Definitions of indices for API functions, unique across entire API
// *************************************************************************

// This file is generated.  Any changes you make will be lost during the next clean build.
// CUDA public interface, for type definitions and cu* function prototypes

typedef enum CUpti_runtime_api_trace_cbid_enum {
    CUPTI_RUNTIME_TRACE_CBID_INVALID                                                       = 0,
    CUPTI_RUNTIME_TRACE_CBID_cudaDriverGetVersion_v3020                                    = 1,
    CUPTI_RUNTIME_TRACE_CBID_cudaRuntimeGetVersion_v3020                                   = 2,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetDeviceCount_v3020                                      = 3,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetDeviceProperties_v3020                                 = 4,
    CUPTI_RUNTIME_TRACE_CBID_cudaChooseDevice_v3020                                        = 5,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetChannelDesc_v3020                                      = 6,
    CUPTI_RUNTIME_TRACE_CBID_cudaCreateChannelDesc_v3020                                   = 7,
    CUPTI_RUNTIME_TRACE_CBID_cudaConfigureCall_v3020                                       = 8,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetupArgument_v3020                                       = 9,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetLastError_v3020                                        = 10,
    CUPTI_RUNTIME_TRACE_CBID_cudaPeekAtLastError_v3020                                     = 11,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetErrorString_v3020                                      = 12,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunch_v3020                                              = 13,
    CUPTI_RUNTIME_TRACE_CBID_cudaFuncSetCacheConfig_v3020                                  = 14,
    CUPTI_RUNTIME_TRACE_CBID_cudaFuncGetAttributes_v3020                                   = 15,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetDevice_v3020                                           = 16,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetDevice_v3020                                           = 17,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetValidDevices_v3020                                     = 18,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetDeviceFlags_v3020                                      = 19,
    CUPTI_RUNTIME_TRACE_CBID_cudaMalloc_v3020                                              = 20,
    CUPTI_RUNTIME_TRACE_CBID_cudaMallocPitch_v3020                                         = 21,
    CUPTI_RUNTIME_TRACE_CBID_cudaFree_v3020                                                = 22,
    CUPTI_RUNTIME_TRACE_CBID_cudaMallocArray_v3020                                         = 23,
    CUPTI_RUNTIME_TRACE_CBID_cudaFreeArray_v3020                                           = 24,
    CUPTI_RUNTIME_TRACE_CBID_cudaMallocHost_v3020                                          = 25,
    CUPTI_RUNTIME_TRACE_CBID_cudaFreeHost_v3020                                            = 26,
    CUPTI_RUNTIME_TRACE_CBID_cudaHostAlloc_v3020                                           = 27,
    CUPTI_RUNTIME_TRACE_CBID_cudaHostGetDevicePointer_v3020                                = 28,
    CUPTI_RUNTIME_TRACE_CBID_cudaHostGetFlags_v3020                                        = 29,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemGetInfo_v3020                                          = 30,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy_v3020                                              = 31,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2D_v3020                                            = 32,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToArray_v3020                                       = 33,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DToArray_v3020                                     = 34,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromArray_v3020                                     = 35,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DFromArray_v3020                                   = 36,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyArrayToArray_v3020                                  = 37,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DArrayToArray_v3020                                = 38,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToSymbol_v3020                                      = 39,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromSymbol_v3020                                    = 40,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyAsync_v3020                                         = 41,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToArrayAsync_v3020                                  = 42,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromArrayAsync_v3020                                = 43,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DAsync_v3020                                       = 44,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DToArrayAsync_v3020                                = 45,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DFromArrayAsync_v3020                              = 46,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToSymbolAsync_v3020                                 = 47,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromSymbolAsync_v3020                               = 48,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset_v3020                                              = 49,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset2D_v3020                                            = 50,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemsetAsync_v3020                                         = 51,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset2DAsync_v3020                                       = 52,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetSymbolAddress_v3020                                    = 53,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetSymbolSize_v3020                                       = 54,
    CUPTI_RUNTIME_TRACE_CBID_cudaBindTexture_v3020                                         = 55,
    CUPTI_RUNTIME_TRACE_CBID_cudaBindTexture2D_v3020                                       = 56,
    CUPTI_RUNTIME_TRACE_CBID_cudaBindTextureToArray_v3020                                  = 57,
    CUPTI_RUNTIME_TRACE_CBID_cudaUnbindTexture_v3020                                       = 58,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetTextureAlignmentOffset_v3020                           = 59,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetTextureReference_v3020                                 = 60,
    CUPTI_RUNTIME_TRACE_CBID_cudaBindSurfaceToArray_v3020                                  = 61,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetSurfaceReference_v3020                                 = 62,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLSetGLDevice_v3020                                       = 63,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLRegisterBufferObject_v3020                              = 64,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLMapBufferObject_v3020                                   = 65,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLUnmapBufferObject_v3020                                 = 66,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLUnregisterBufferObject_v3020                            = 67,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLSetBufferObjectMapFlags_v3020                           = 68,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLMapBufferObjectAsync_v3020                              = 69,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLUnmapBufferObjectAsync_v3020                            = 70,
    CUPTI_RUNTIME_TRACE_CBID_cudaWGLGetDevice_v3020                                        = 71,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsGLRegisterImage_v3020                             = 72,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsGLRegisterBuffer_v3020                            = 73,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsUnregisterResource_v3020                          = 74,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsResourceSetMapFlags_v3020                         = 75,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsMapResources_v3020                                = 76,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsUnmapResources_v3020                              = 77,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsResourceGetMappedPointer_v3020                    = 78,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsSubResourceGetMappedArray_v3020                   = 79,
    CUPTI_RUNTIME_TRACE_CBID_cudaVDPAUGetDevice_v3020                                      = 80,
    CUPTI_RUNTIME_TRACE_CBID_cudaVDPAUSetVDPAUDevice_v3020                                 = 81,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsVDPAURegisterVideoSurface_v3020                   = 82,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsVDPAURegisterOutputSurface_v3020                  = 83,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D11GetDevice_v3020                                      = 84,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D11GetDevices_v3020                                     = 85,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D11SetDirect3DDevice_v3020                              = 86,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsD3D11RegisterResource_v3020                       = 87,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10GetDevice_v3020                                      = 88,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10GetDevices_v3020                                     = 89,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10SetDirect3DDevice_v3020                              = 90,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsD3D10RegisterResource_v3020                       = 91,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10RegisterResource_v3020                               = 92,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10UnregisterResource_v3020                             = 93,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10MapResources_v3020                                   = 94,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10UnmapResources_v3020                                 = 95,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceSetMapFlags_v3020                            = 96,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceGetSurfaceDimensions_v3020                   = 97,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceGetMappedArray_v3020                         = 98,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceGetMappedPointer_v3020                       = 99,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceGetMappedSize_v3020                          = 100,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10ResourceGetMappedPitch_v3020                         = 101,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9GetDevice_v3020                                       = 102,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9GetDevices_v3020                                      = 103,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9SetDirect3DDevice_v3020                               = 104,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9GetDirect3DDevice_v3020                               = 105,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsD3D9RegisterResource_v3020                        = 106,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9RegisterResource_v3020                                = 107,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9UnregisterResource_v3020                              = 108,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9MapResources_v3020                                    = 109,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9UnmapResources_v3020                                  = 110,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceSetMapFlags_v3020                             = 111,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceGetSurfaceDimensions_v3020                    = 112,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceGetMappedArray_v3020                          = 113,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceGetMappedPointer_v3020                        = 114,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceGetMappedSize_v3020                           = 115,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9ResourceGetMappedPitch_v3020                          = 116,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9Begin_v3020                                           = 117,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9End_v3020                                             = 118,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9RegisterVertexBuffer_v3020                            = 119,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9UnregisterVertexBuffer_v3020                          = 120,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9MapVertexBuffer_v3020                                 = 121,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D9UnmapVertexBuffer_v3020                               = 122,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadExit_v3020                                          = 123,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetDoubleForDevice_v3020                                  = 124,
    CUPTI_RUNTIME_TRACE_CBID_cudaSetDoubleForHost_v3020                                    = 125,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadSynchronize_v3020                                   = 126,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadGetLimit_v3020                                      = 127,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadSetLimit_v3020                                      = 128,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamCreate_v3020                                        = 129,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamDestroy_v3020                                       = 130,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamSynchronize_v3020                                   = 131,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamQuery_v3020                                         = 132,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventCreate_v3020                                         = 133,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventCreateWithFlags_v3020                                = 134,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventRecord_v3020                                         = 135,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventDestroy_v3020                                        = 136,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventSynchronize_v3020                                    = 137,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventQuery_v3020                                          = 138,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventElapsedTime_v3020                                    = 139,
    CUPTI_RUNTIME_TRACE_CBID_cudaMalloc3D_v3020                                            = 140,
    CUPTI_RUNTIME_TRACE_CBID_cudaMalloc3DArray_v3020                                       = 141,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset3D_v3020                                            = 142,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset3DAsync_v3020                                       = 143,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3D_v3020                                            = 144,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DAsync_v3020                                       = 145,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadSetCacheConfig_v3020                                = 146,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamWaitEvent_v3020                                     = 147,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D11GetDirect3DDevice_v3020                              = 148,
    CUPTI_RUNTIME_TRACE_CBID_cudaD3D10GetDirect3DDevice_v3020                              = 149,
    CUPTI_RUNTIME_TRACE_CBID_cudaThreadGetCacheConfig_v3020                                = 150,
    CUPTI_RUNTIME_TRACE_CBID_cudaPointerGetAttributes_v4000                                = 151,
    CUPTI_RUNTIME_TRACE_CBID_cudaHostRegister_v4000                                        = 152,
    CUPTI_RUNTIME_TRACE_CBID_cudaHostUnregister_v4000                                      = 153,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceCanAccessPeer_v4000                                 = 154,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceEnablePeerAccess_v4000                              = 155,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceDisablePeerAccess_v4000                             = 156,
    CUPTI_RUNTIME_TRACE_CBID_cudaPeerRegister_v4000                                        = 157,
    CUPTI_RUNTIME_TRACE_CBID_cudaPeerUnregister_v4000                                      = 158,
    CUPTI_RUNTIME_TRACE_CBID_cudaPeerGetDevicePointer_v4000                                = 159,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyPeer_v4000                                          = 160,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyPeerAsync_v4000                                     = 161,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DPeer_v4000                                        = 162,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DPeerAsync_v4000                                   = 163,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceReset_v3020                                         = 164,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceSynchronize_v3020                                   = 165,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetLimit_v3020                                      = 166,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceSetLimit_v3020                                      = 167,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetCacheConfig_v3020                                = 168,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceSetCacheConfig_v3020                                = 169,
    CUPTI_RUNTIME_TRACE_CBID_cudaProfilerInitialize_v4000                                  = 170,
    CUPTI_RUNTIME_TRACE_CBID_cudaProfilerStart_v4000                                       = 171,
    CUPTI_RUNTIME_TRACE_CBID_cudaProfilerStop_v4000                                        = 172,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetByPCIBusId_v4010                                 = 173,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetPCIBusId_v4010                                   = 174,
    CUPTI_RUNTIME_TRACE_CBID_cudaGLGetDevices_v4010                                        = 175,
    CUPTI_RUNTIME_TRACE_CBID_cudaIpcGetEventHandle_v4010                                   = 176,
    CUPTI_RUNTIME_TRACE_CBID_cudaIpcOpenEventHandle_v4010                                  = 177,
    CUPTI_RUNTIME_TRACE_CBID_cudaIpcGetMemHandle_v4010                                     = 178,
    CUPTI_RUNTIME_TRACE_CBID_cudaIpcOpenMemHandle_v4010                                    = 179,
    CUPTI_RUNTIME_TRACE_CBID_cudaIpcCloseMemHandle_v4010                                   = 180,
    CUPTI_RUNTIME_TRACE_CBID_cudaArrayGetInfo_v4010                                        = 181,
    CUPTI_RUNTIME_TRACE_CBID_cudaFuncSetSharedMemConfig_v4020                              = 182,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetSharedMemConfig_v4020                            = 183,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceSetSharedMemConfig_v4020                            = 184,
    CUPTI_RUNTIME_TRACE_CBID_cudaCreateTextureObject_v5000                                 = 185,
    CUPTI_RUNTIME_TRACE_CBID_cudaDestroyTextureObject_v5000                                = 186,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetTextureObjectResourceDesc_v5000                        = 187,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetTextureObjectTextureDesc_v5000                         = 188,
    CUPTI_RUNTIME_TRACE_CBID_cudaCreateSurfaceObject_v5000                                 = 189,
    CUPTI_RUNTIME_TRACE_CBID_cudaDestroySurfaceObject_v5000                                = 190,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetSurfaceObjectResourceDesc_v5000                        = 191,
    CUPTI_RUNTIME_TRACE_CBID_cudaMallocMipmappedArray_v5000                                = 192,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetMipmappedArrayLevel_v5000                              = 193,
    CUPTI_RUNTIME_TRACE_CBID_cudaFreeMipmappedArray_v5000                                  = 194,
    CUPTI_RUNTIME_TRACE_CBID_cudaBindTextureToMipmappedArray_v5000                         = 195,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsResourceGetMappedMipmappedArray_v5000             = 196,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamAddCallback_v5000                                   = 197,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamCreateWithFlags_v5000                               = 198,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetTextureObjectResourceViewDesc_v5000                    = 199,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetAttribute_v5000                                  = 200,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamDestroy_v5050                                       = 201,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamCreateWithPriority_v5050                            = 202,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamGetPriority_v5050                                   = 203,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamGetFlags_v5050                                      = 204,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetStreamPriorityRange_v5050                        = 205,
    CUPTI_RUNTIME_TRACE_CBID_cudaMallocManaged_v6000                                       = 206,
    CUPTI_RUNTIME_TRACE_CBID_cudaOccupancyMaxActiveBlocksPerMultiprocessor_v6000           = 207,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamAttachMemAsync_v6000                                = 208,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetErrorName_v6050                                        = 209,
    CUPTI_RUNTIME_TRACE_CBID_cudaOccupancyMaxActiveBlocksPerMultiprocessor_v6050           = 210,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunchKernel_v7000                                        = 211,
    CUPTI_RUNTIME_TRACE_CBID_cudaGetDeviceFlags_v7000                                      = 212,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunch_ptsz_v7000                                         = 213,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunchKernel_ptsz_v7000                                   = 214,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy_ptds_v7000                                         = 215,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2D_ptds_v7000                                       = 216,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToArray_ptds_v7000                                  = 217,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DToArray_ptds_v7000                                = 218,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromArray_ptds_v7000                                = 219,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DFromArray_ptds_v7000                              = 220,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyArrayToArray_ptds_v7000                             = 221,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DArrayToArray_ptds_v7000                           = 222,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToSymbol_ptds_v7000                                 = 223,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromSymbol_ptds_v7000                               = 224,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyAsync_ptsz_v7000                                    = 225,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToArrayAsync_ptsz_v7000                             = 226,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromArrayAsync_ptsz_v7000                           = 227,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DAsync_ptsz_v7000                                  = 228,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DToArrayAsync_ptsz_v7000                           = 229,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy2DFromArrayAsync_ptsz_v7000                         = 230,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyToSymbolAsync_ptsz_v7000                            = 231,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpyFromSymbolAsync_ptsz_v7000                          = 232,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset_ptds_v7000                                         = 233,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset2D_ptds_v7000                                       = 234,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemsetAsync_ptsz_v7000                                    = 235,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset2DAsync_ptsz_v7000                                  = 236,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamGetPriority_ptsz_v7000                              = 237,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamGetFlags_ptsz_v7000                                 = 238,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamSynchronize_ptsz_v7000                              = 239,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamQuery_ptsz_v7000                                    = 240,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamAttachMemAsync_ptsz_v7000                           = 241,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventRecord_ptsz_v7000                                    = 242,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset3D_ptds_v7000                                       = 243,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemset3DAsync_ptsz_v7000                                  = 244,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3D_ptds_v7000                                       = 245,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DAsync_ptsz_v7000                                  = 246,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamWaitEvent_ptsz_v7000                                = 247,
    CUPTI_RUNTIME_TRACE_CBID_cudaStreamAddCallback_ptsz_v7000                              = 248,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DPeer_ptds_v7000                                   = 249,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemcpy3DPeerAsync_ptsz_v7000                              = 250,
    CUPTI_RUNTIME_TRACE_CBID_cudaOccupancyMaxActiveBlocksPerMultiprocessorWithFlags_v7000  = 251,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemPrefetchAsync_v8000                                    = 252,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemPrefetchAsync_ptsz_v8000                               = 253,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemAdvise_v8000                                           = 254,
    CUPTI_RUNTIME_TRACE_CBID_cudaDeviceGetP2PAttribute_v8000                               = 255,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsEGLRegisterImage_v7000                            = 256,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamConsumerConnect_v7000                            = 257,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamConsumerDisconnect_v7000                         = 258,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamConsumerAcquireFrame_v7000                       = 259,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamConsumerReleaseFrame_v7000                       = 260,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamProducerConnect_v7000                            = 261,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamProducerDisconnect_v7000                         = 262,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamProducerPresentFrame_v7000                       = 263,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamProducerReturnFrame_v7000                        = 264,
    CUPTI_RUNTIME_TRACE_CBID_cudaGraphicsResourceGetMappedEglFrame_v7000                   = 265,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemRangeGetAttribute_v8000                                = 266,
    CUPTI_RUNTIME_TRACE_CBID_cudaMemRangeGetAttributes_v8000                               = 267,
    CUPTI_RUNTIME_TRACE_CBID_cudaEGLStreamConsumerConnectWithFlags_v7000                   = 268,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunchCooperativeKernel_v9000                             = 269,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunchCooperativeKernel_ptsz_v9000                        = 270,
    CUPTI_RUNTIME_TRACE_CBID_cudaEventCreateFromEGLSync_v9000                              = 271,
    CUPTI_RUNTIME_TRACE_CBID_cudaLaunchCooperativeKernelMultiDevice_v9000                  = 272,
    CUPTI_RUNTIME_TRACE_CBID_cudaFuncSetAttribute_v9000                                    = 273,
    CUPTI_RUNTIME_TRACE_CBID_SIZE                                                          = 274,
    CUPTI_RUNTIME_TRACE_CBID_FORCE_INT                                                     = 0x7fffffff
} CUpti_runtime_api_trace_cbid;

"""


class Comm(object):
    pass
