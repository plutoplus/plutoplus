#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run extracted SPI NOR EAR functions against a mock bus; never access hardware.

Usage: python3 scripts/test_winbond_ear.py PATH/TO/spi-nor.c
Requires Python 3 and clang with AddressSanitizer/UndefinedBehaviorSanitizer.
The pinned unpatched kernel is expected to fail; the patched source must pass.
This focused test does not execute the full probe/read/write/erase paths.
"""
import pathlib
import tempfile
import subprocess
import sys

source = pathlib.Path(sys.argv[1]).read_text()

def function(name):
    start = source.index('static int ' + name + '(')
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

names = ['write_enable', 'write_disable', 'macronix_set_4byte']
if 'static int spi_nor_write_ear_raw(' in source:
    names += ['spi_nor_write_ear_raw']
names += ['spi_nor_write_ear', 'winbond_set_4byte', 'read_ear']
prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define SPINOR_OP_WREN 0x06
#define SPINOR_OP_WRDI 0x04
#define SPINOR_OP_EN4B 0xb7
#define SPINOR_OP_EX4B 0xe9
#define SPINOR_OP_WREAR 0xc5
#define SPINOR_OP_RDEAR 0xc8
#define SPINOR_OP_BRWR 0x17
#define SPINOR_OP_BRRD 0x16
#define SNOR_MFR_WINBOND 0xef
#define CFI_MFR_ST 0x20
#define CFI_MFR_MACRONIX 0xc2
#define SNOR_MFR_ISSI 0x9d
#define CFI_MFR_AMD 0x01
#define JEDEC_MFR(info) ((info)->id)
#define pr_err(...) ((void)0)
struct flash_info { int id; };
struct mtd_info { uint64_t size; };
struct spi_mem_op { int code, len, in; u8 *data; };
#define SPI_MEM_OP(cmd, addr, dummy, data) {cmd, data}
#define SPI_MEM_OP_CMD(c, w) .code=c
#define SPI_MEM_OP_NO_ADDR 0
#define SPI_MEM_OP_NO_DUMMY 0
#define SPI_MEM_OP_NO_DATA .len=0
#define SPI_MEM_OP_DATA_OUT(n, p, w) .data=p, .len=n, .in=0
#define SPI_MEM_OP_DATA_IN(n, p, w) .data=p, .len=n, .in=1
struct spi_nor {
    struct mtd_info mtd;
    int shift, isstacked, curbank, jedec_id;
    u8 bouncebuf[8];
    void *spimem;
    int (*write_reg)(struct spi_nor *, u8, u8 *, int);
    int (*read_reg)(struct spi_nor *, u8, u8 *, int);
};
static int ear, wel, fail_op, fail_after, writes, commands;
static int bus(int code, u8 *data, int len, int in) {
    commands++;
    if (code == fail_op && !fail_after) return -EIO;
    switch(code) {
    case SPINOR_OP_WREN: wel=1; break;
    case SPINOR_OP_WRDI: wel=0; break;
    case SPINOR_OP_EN4B: break;
    case SPINOR_OP_EX4B: ear=1; break;
    case SPINOR_OP_WREAR:
        /* W25Q256 does not write EAR without the write-enable latch. */
        if(wel && len==1 && !in) { ear=*data; writes++; wel=0; }
        break;
    case SPINOR_OP_BRWR: ear=*data; writes++; break;
    case SPINOR_OP_RDEAR: case SPINOR_OP_BRRD: *data=ear; break;
    default: abort();
    }
    return code==fail_op ? -EIO : 0;
}
static int spi_mem_exec_op(void *mem, struct spi_mem_op *op) {
    (void)mem; return bus(op->code,op->data,op->len,op->in);
}
static int wr(struct spi_nor *n, u8 code, u8 *data, int len) {
    (void)n; return bus(code,data,len,0);
}
static int rd(struct spi_nor *n, u8 code, u8 *data, int len) {
    (void)n; return bus(code,data,len,1);
}
static int failures, checks;
#define CHECK(x) do {checks++; if(!(x)) { failures++; fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); }} while(0)
static struct spi_nor init(int spimem) {
    ear=0; wel=0; fail_op=-1; fail_after=0; writes=0; commands=0;
    struct spi_nor n={0}; n.mtd.size=32*1024*1024;
    n.jedec_id=SNOR_MFR_WINBOND; n.spimem=spimem ? (void *)1 : NULL;
    n.write_reg=wr; n.read_reg=rd; return n;
}
'''
tests = r'''
int main(void) {
  for(int api=0; api<2; api++) {
    struct spi_nor n=init(api); struct flash_info info={SNOR_MFR_WINBOND};
    /* EX4B selects bank 1 while the software cache still says 0. */
    CHECK(winbond_set_4byte(&n,false)==0);
    CHECK(ear==0); CHECK(writes==1); CHECK(wel==0);
    CHECK(read_ear(&n,&info)==0);
    ear=1; CHECK(read_ear(&n,&info)==1);

    n=init(api);
    const u32 offsets[]={0,0xfffffe,0x1000000,0x1000001,0x1ffffff,0x100000,0x1200000,0};
    for(unsigned i=0;i<sizeof(offsets)/sizeof(*offsets);i++) {
        CHECK(spi_nor_write_ear(&n,offsets[i])==0);
        CHECK((((u32)ear<<24)|(offsets[i]&0xffffff))==offsets[i]);
    }
    int count=commands; CHECK(spi_nor_write_ear(&n,0)==0); CHECK(commands==count);

    n=init(api); fail_op=SPINOR_OP_WREN;
    CHECK(spi_nor_write_ear(&n,0x1000000)==-EIO); CHECK(writes==0);
    CHECK(winbond_set_4byte(&n,false)==-EIO);

    n=init(api); fail_op=SPINOR_OP_WREAR;
    CHECK(spi_nor_write_ear(&n,0x1000000)==-EIO); CHECK(n.curbank==0xff);
    fail_op=-1; CHECK(spi_nor_write_ear(&n,0x1000000)==0); CHECK(ear==1);

    /* A transfer may change hardware before reporting an error. */
    n=init(api); fail_op=SPINOR_OP_WREAR; fail_after=1;
    CHECK(spi_nor_write_ear(&n,0x1000000)==-EIO); CHECK(ear==1);
    fail_op=-1; CHECK(spi_nor_write_ear(&n,0)==0); CHECK(ear==0);

    n=init(api); fail_op=SPINOR_OP_RDEAR; CHECK(read_ear(&n,&info)==-EIO);
    n=init(api); fail_op=SPINOR_OP_EX4B;
    CHECK(winbond_set_4byte(&n,false)==-EIO); CHECK(writes==0);
    n=init(api); fail_op=SPINOR_OP_WREAR;
    CHECK(winbond_set_4byte(&n,false)==-EIO); CHECK(wel==0);
    n=init(api); CHECK(winbond_set_4byte(&n,true)==0); CHECK(writes==0);
    n=init(api); info.id=0x55; CHECK(read_ear(&n,&info)==-EINVAL);
    n=init(api); n.jedec_id=CFI_MFR_ST; info.id=CFI_MFR_ST;
    CHECK(spi_nor_write_ear(&n,0x1000000)==0); CHECK(read_ear(&n,&info)==1);
    n=init(api); n.jedec_id=CFI_MFR_AMD; info.id=CFI_MFR_AMD;
    CHECK(spi_nor_write_ear(&n,0x1000000)==0); CHECK(read_ear(&n,&info)==1);
  }
  printf("checks=%d failures=%d\n",checks,failures);
  return failures ? 1 : 0;
}
'''
with tempfile.TemporaryDirectory(prefix="plutoplus-ear-test-") as directory:
    generated = pathlib.Path(directory) / 'ear-test.c'
    generated.write_text(prefix + '\n'.join(map(function,names)) + tests)
    binary = generated.with_suffix('')
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-fsanitize=address,undefined',
                    '-g', str(generated), '-o', str(binary)], check=True)
    sys.exit(subprocess.run([str(binary)]).returncode)
