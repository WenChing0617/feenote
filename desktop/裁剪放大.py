# -*- coding: utf-8 -*-
"""纯标准库的 PNG 裁剪 + 放大工具（本机没有 Pillow，用它看截图细节）

用法：
    python 裁剪放大.py 输入.png 输出.png x0,y0,x1,y1 [倍数]
    python 裁剪放大.py 输入.png 输出.png x0,y0,x1,y1 2

为什么要放大再看：1px 的边框、被截断的列头，在缩略显示时会消失或看不出，
放大 2~3 倍才能确认到底是「没画出来」还是「画了但被挤掉了」。
"""
import struct
import sys
import zlib


def read_png(path):
    """读 8bit RGB/RGBA 的 PNG，返回 (w, h, 每行 RGBA 的 bytearray 列表)"""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('不是 PNG 文件')
    pos = 8
    w = h = depth = ctype = None
    idat = bytearray()
    while pos < len(data):
        (ln,) = struct.unpack('>I', data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b'IHDR':
            w, h, depth, ctype, _c, _f, _i = struct.unpack('>IIBBBBB', payload)
        elif tag == b'IDAT':
            idat += payload
        elif tag == b'IEND':
            break
    if depth != 8 or ctype not in (2, 6):
        raise ValueError('只支持 8bit RGB/RGBA，实际 depth=%s ctype=%s' % (depth, ctype))
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = w * bpp
    rows = []
    prev = bytearray(stride)
    p = 0
    for _y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:      # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:    # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:    # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError('未知的 filter %d' % ft)
        prev = line
        # 统一成 RGBA
        if bpp == 4:
            rows.append(bytearray(line))
        else:
            rgba = bytearray(w * 4)
            for x in range(w):
                rgba[x * 4:x * 4 + 3] = line[x * 3:x * 3 + 3]
                rgba[x * 4 + 3] = 255
            rows.append(rgba)
    return w, h, rows


def write_png(path, w, h, rows):
    raw = bytearray()
    for r in rows:
        raw.append(0)
        raw += r

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload +
                struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF))

    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(bytes(raw), 6))
    out += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(out)


def crop_zoom(src, dst, box, zoom=2):
    x0, y0, x1, y1 = box
    w, h, rows = read_png(src)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    cw, ch = x1 - x0, y1 - y0
    out_rows = []
    for y in range(y0, y1):
        line = bytearray()
        for x in range(x0, x1):
            px = rows[y][x * 4:x * 4 + 4]
            line += px * zoom
        for _ in range(zoom):
            out_rows.append(bytearray(line))
    write_png(dst, cw * zoom, ch * zoom, out_rows)
    return cw * zoom, ch * zoom


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], sys.argv[2]
    box = tuple(int(v) for v in sys.argv[3].replace(' ', '').split(','))
    z = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    cw, ch = crop_zoom(src, dst, box, z)
    print('%s  [%s]  放大 %dx  →  %s  (%dx%d)' % (src, box, z, dst, cw, ch))
