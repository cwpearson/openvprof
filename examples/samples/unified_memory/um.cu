/*
 * Copyright 2014-2015 NVIDIA Corporation. All rights reserved.
 *
 * Sample CUPTI app to demonstrate the usage of unified memory counter profiling
 *
 */

 #include <stdio.h>
 #include <cuda.h>
 #include <stdlib.h>
 
 #define CUPTI_CALL(call)                                                    \
 do {                                                                        \
     CUptiResult _status = call;                                             \
     if (_status != CUPTI_SUCCESS) {                                         \
       const char *errstr;                                                   \
       cuptiGetResultString(_status, &errstr);                               \
       fprintf(stderr, "%s:%d: error: function %s failed with error %s.\n",  \
               __FILE__, __LINE__, #call, errstr);                           \
       exit(-1);                                                             \
     }                                                                       \
 } while (0)
 
 #define DRIVER_API_CALL(apiFuncCall)                                           \
 do {                                                                           \
     CUresult _status = apiFuncCall;                                            \
     if (_status != CUDA_SUCCESS) {                                             \
         fprintf(stderr, "%s:%d: error: function %s failed with error %d.\n",   \
                 __FILE__, __LINE__, #apiFuncCall, _status);                    \
         exit(-1);                                                              \
     }                                                                          \
 } while (0)
 
 #define RUNTIME_API_CALL(apiFuncCall)                                          \
 do {                                                                           \
     cudaError_t _status = apiFuncCall;                                         \
     if (_status != cudaSuccess) {                                              \
         fprintf(stderr, "%s:%d: error: function %s failed with error %s.\n",   \
                 __FILE__, __LINE__, #apiFuncCall, cudaGetErrorString(_status));\
         exit(-1);                                                              \
     }                                                                          \
 } while (0)
 

 
 template<class T>
 __host__ __device__ void checkData(const char *loc, T *data, int size, int expectedVal) {
     int i;
 
     for (i = 0; i < size / (int)sizeof(T); i++) {
         if (data[i] != expectedVal) {
             printf("Mismatch found on %s\n", loc);
             printf("Address 0x%p, Observed = 0x%x Expected = 0x%x\n", data+i, data[i], expectedVal);
             break;
         }
     }
 }
 
 template<class T>
 __host__ __device__ void writeData(T *data, int size, int writeVal) {
     int i;
 
     for (i = 0; i < size / (int)sizeof(T); i++) {
         data[i] = writeVal;
     }
 }
 
 __global__ void testKernel(int *data, int size, int expectedVal)
 {
     checkData("GPU", data, size, expectedVal);
     writeData(data, size, -expectedVal);
 }
 
 int main(int argc, char **argv)
 {
     int deviceCount;
     int *data = NULL;
     int size = 64*1024;     // 64 KB
     int i = 123;
 
     DRIVER_API_CALL(cuInit(0));
     DRIVER_API_CALL(cuDeviceGetCount(&deviceCount));
 
     if (deviceCount == 0) {
         printf("There is no device supporting CUDA.\n");
         exit(-1);
     }
 
 
     // allocate unified memory
     printf("Allocation size in bytes %d\n", size);
     RUNTIME_API_CALL(cudaMallocManaged(&data, size));
 
     // CPU access
     writeData(data, size, i);
     // kernel launch
     testKernel<<<1,1>>>(data, size, i);
     RUNTIME_API_CALL(cudaDeviceSynchronize());
     // CPU access
     checkData("CPU", data, size, -i);
 
     // free unified memory
     RUNTIME_API_CALL(cudaFree(data));
 
 
     cudaDeviceReset();
 
     return 0;
 }
 