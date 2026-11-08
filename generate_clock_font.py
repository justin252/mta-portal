#!/usr/bin/env python3
"""Generate fonts/clock.bdf: tom-thumb's digits and colon, spaced 1px apart.

tom-thumb is monospaced (every glyph advances 4px), so "12:52" spreads to 19px with wide
gaps around the narrow '1' and ':'. Here each glyph advances by its own width plus 1px,
so the clock reads as one compact unit (16px).
"""

SRC, DST = 'fonts/tom-thumb.bdf', 'fonts/clock.bdf'
CHARS = '0123456789:'


def main(dst=DST):
    lines = open(SRC).read().splitlines()
    header = lines[:lines.index('ENDPROPERTIES') + 1]
    header = ['FONT -mta-portal-Clock-Medium-R-Normal--6-60-75-75-P-40-ISO10646-1'
              if line.startswith('FONT ') else line for line in header]
    glyphs, i = [], 0
    while i < len(lines):
        if lines[i].startswith('STARTCHAR'):
            end = lines.index('ENDCHAR', i)
            block = lines[i:end + 1]
            code = int(next(b for b in block if b.startswith('ENCODING')).split()[1])
            if chr(code) in CHARS:
                w, h, _, yoff = (int(v) for v in next(b for b in block if b.startswith('BBX')).split()[1:])
                block = ['DWIDTH %d 0' % (w + 1) if b.startswith('DWIDTH') else
                         'BBX %d %d 0 %d' % (w, h, yoff) if b.startswith('BBX') else b for b in block]
                glyphs.append(block)
            i = end
        i += 1
    out = header + ['CHARS %d' % len(glyphs)] + [line for g in glyphs for line in g] + ['ENDFONT']
    with open(dst, 'w') as f:
        f.write('\n'.join(out) + '\n')
    print('Generated %s (%d glyphs)' % (dst, len(glyphs)))


if __name__ == '__main__':
    main()
