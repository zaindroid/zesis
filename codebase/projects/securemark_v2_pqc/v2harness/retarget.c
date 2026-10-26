/*
 * printf retarget for SecureMark-TLS on FRDM-MCXN947.
 * Routes newlib's printf/_write to the board UART (debug console).
 */
#include "fsl_lpuart.h"
#include "board.h"
#include <sys/stat.h>
#include <errno.h>

/* The debug console UART handle - defined by the SDK hello_world board files */
/* Route stdout to the debug UART (polling) */
int _write(int fd, char *ptr, int len)
{
    (void)fd;
    LPUART_WriteBlocking((LPUART_Type *)BOARD_DEBUG_UART_BASEADDR, (const uint8_t *)ptr, (uint32_t)len);
    return len;
}

int _read(int fd, char *ptr, int len)
{
    (void)fd; (void)ptr; (void)len;
    return 0;
}

int _close(int fd) { (void)fd; return -1; }
int _fstat(int fd, struct stat *st) { (void)fd; st->st_mode = S_IFCHR; return 0; }
int _isatty(int fd) { (void)fd; return 1; }
int _lseek(int fd, int off, int whence) { (void)fd; (void)off; (void)whence; return 0; }
int _getpid(void) { return 1; }
int _kill(int pid, int sig) { (void)pid; (void)sig; errno = EINVAL; return -1; }
