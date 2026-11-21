/* Bounded native interpreter for the common classic instruction formats.
 * Return BEFORE executing an instruction if it needs the Python interpreter.
 * All addresses are guest offsets; no guest code is executed by the host. */
#include <stdint.h>
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

static int plain(uint32_t a, unsigned width, const uint8_t *pages) {
    return a <= 65536u - width && !pages[a >> 8] && !pages[(a + width - 1) >> 8];
}
static unsigned load(const uint8_t *m, unsigned a, unsigned w) {
    return w == 1 ? m[a] : m[a] | ((unsigned)m[a+1] << 8);
}
static int fetch(const uint8_t *m, const uint8_t *pages, unsigned *pc, unsigned *v) {
    if (!plain(*pc, 2, pages)) return 0;
    *v = load(m, *pc, 2);
    *pc = (*pc + 2) & 0xffff;
    return 1;
}
EXPORT unsigned run_batch(uint8_t *m, const uint8_t *pages, uint32_t *r,
                          unsigned limit, uint32_t *cycles) {
    unsigned done = 0;
    *cycles = 0;
    while (done < limit) {
        unsigned pc = r[0], op, x, y, address = 0, off, cost, result;
        if (!fetch(m, pages, &pc, &op)) break;
        if ((op & 0xe000) == 0x2000) {
            unsigned sr = r[2], z = !!(sr & 2), n = !!(sr & 4), v = !!(sr & 256);
            unsigned take[] = {!z, z, !(sr&1), sr&1, n, n==v, n!=v, 1};
            if (take[(op>>10)&7]) {
                int delta = (int)(op & 1023) - ((op & 512) ? 1024 : 0);
                pc = (pc + 2 * delta) & 0xffff;
            }
            r[0] = pc; *cycles += 2; ++done; continue;
        }
        unsigned code = op >> 12, src = (op >> 8) & 15, dst = op & 15;
        unsigned ad = op & 128, mode = (op >> 4) & 3, w = op & 64 ? 1 : 2;
        unsigned mask = w == 1 ? 255 : 65535, sign = (mask + 1) >> 1;
        /* Special destination registers, autoincrement side effects and DADD
         * stay in the reference interpreter. No speculative writes. */
        if (code < 4 || code == 10 || (!ad && dst < 4) || (ad && dst == 0)) break;
        if (src == 3 || (src == 2 && mode >= 2)) {
            const unsigned cg[] = {0,1,2,65535};
            x = src == 3 ? cg[mode] : (mode == 2 ? 4 : 8); cost = 1;
        } else if (src == 0 && mode == 3) {
            if (!fetch(m, pages, &pc, &x)) break;
            cost = 2;
        } else if (!mode) {
            x = src ? r[src] : pc; cost = 1;
        } else {
            if (mode == 3 || src == 0) break;
            address = r[src]; cost = 2;
            if (mode == 1) {
                if (!fetch(m, pages, &pc, &off)) break;
                address = src == 2 ? off : (address + off) & 65535; cost = 3;
            }
            if (!plain(address, w, pages)) break;
            x = load(m, address, w);
        }
        x &= mask;
        if (ad) {
            if (!fetch(m, pages, &pc, &off)) break;
            address = dst == 2 ? off : (r[dst] + off) & 65535;
            if (!plain(address, w, pages)) break;
            y = code == 4 ? 0 : load(m, address, w);
            cost += 3 - (code == 4 || code == 9 || code == 11);
        } else y = r[dst] & mask;
        unsigned flags = 0, carry = 0, overflow = 0;
        switch (code) {
        case 4: result = x; break;
        case 5: case 6:
            result = y + x + (code == 6 && (r[2]&1));
            flags = 1; carry = result > mask; overflow = !!(~(y^x) & (y^result) & sign); break;
        case 7: case 8: case 9:
            result = y + (mask ^ x) + (code != 7 || (r[2]&1));
            flags = 1; carry = result > mask; overflow = !!((y^x) & (y^result) & sign); break;
        case 12: result = y & ~x; break;
        case 13: result = y | x; break;
        case 14: result = y ^ x; flags = 1; carry = result != 0; overflow = !!(y & x & sign); break;
        default: result = y & x; flags = 1; carry = result != 0; break; /* BIT, AND */
        }
        result &= mask;
        r[0] = pc;
        if (flags) r[2] = (r[2] & ~0x107u) | carry | ((!result)<<1) |
                          ((!!(result & sign))<<2) | (overflow<<8);
        if (code != 9 && code != 11) {
            if (!ad) r[dst] = result;
            else { m[address] = (uint8_t)result; if (w == 2) m[address+1] = (uint8_t)(result>>8); }
        }
        *cycles += cost; ++done;
    }
    return done;
}
