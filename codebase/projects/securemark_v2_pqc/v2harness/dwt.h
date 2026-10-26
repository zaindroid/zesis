#ifndef DWT_H
#define DWT_H

#include "fsl_device_registers.h" 

static inline void dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk; // Enable DWT
    DWT->CYCCNT = 0; // Reset the cycle counter
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk; // Enable the cycle counter
}

static inline uint32_t dwt_get(void)
{
    return DWT->CYCCNT;
}

static inline void dwt_reset(void){

DWT->CYCCNT = 0; // Reset the cycle counter

}

#endif // DWT_H