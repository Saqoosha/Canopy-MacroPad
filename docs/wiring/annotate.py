"""Redraw docs/wiring/wiring-six-key.jpg from the photograph beside it.

    python3 docs/wiring/annotate.py        # needs Pillow

`boards.jpg` is the assembled six-key unit with the shell turned over, so
the face in it is the one the wires go on. Every coordinate below is a
pixel position on that image at its native 4032 x 3024 -- resize the
photograph and the whole overlay slides off the pads, silently, because
nothing here derives a scale from the image. Replace the photograph and
the positions have to be re-read.

Numbers that belong to the case are pointed at rather than copied. The
lane this harness runs in changed shape an hour after the image was
first drawn, and a legend carrying its width would have been wrong the
same day; `case/README.md` owns those and moves with them.

The pad *names* are not read off the silk in the photograph. They come
out of Adafruit's Eagle .brd files for the 4978 and the 4980. The boards
sit rotated in the case, so the silk in the picture runs the opposite way
from the wiring table in README.md -- which is the mistake this file
exists to make impossible.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

im = Image.open(os.path.join(HERE, 'boards.jpg')).convert('RGB')
im = ImageEnhance.Brightness(im).enhance(0.72)
d = ImageDraw.Draw(im, 'RGBA')
JP = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
EN = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
fj = lambda s: ImageFont.truetype(JP, s)
fe = lambda s: ImageFont.truetype(EN, s)
RED, WHITE, GREEN, YELL, CYAN = (255,69,58),(245,245,245),(48,209,88),(255,214,10),(10,200,255)
DIM = (150,150,160)

TOP, BOT = 1199, 1591
def row(x0, y): return [(x0 + i*57, y) for i in range(5)]
A_T, B_T = row(463, TOP), row(905, TOP)          # VDD G IN S+ S-
A_B, B_B = row(463, BOT), row(905, BOT)          # +   -  O  A  C
A = {'VDD':A_T[0],'G':A_T[1],'IN':A_T[2],'S+':A_T[3],'S-':A_T[4],
     '+':A_B[0],'-':A_B[1],'O':A_B[2],'A':A_B[3],'C':A_B[4],'OUTr':(769,1339)}
B = {'VDD':B_T[0],'G':B_T[1],'IN':B_T[2],'S+':B_T[3],'S-':B_T[4],
     '+':B_B[0],'-':B_B[1],'O':B_B[2],'A':B_B[3],'C':B_B[4],'INl':(832,1339)}
N = {k:(x,1582) for k,x in (('VIN',1938),('3',1995),('-',2052),
                            ('C',2107),('D',2162),('INT',2218))}
Q = {'RX':(3237,1216),'SCK':(3290,1216),'MI':(3350,1216),'MO':(3407,1216),
     '3V':(3463,1216),'GND':(3523,1216),'5V':(3577,1216)}

def poly(pts, col, w):
    d.line(pts, fill=(0,0,0,190), width=w+9, joint='curve')
    d.line(pts, fill=col+(255,), width=w, joint='curve')
def dot(p, col, r=17):
    x,y = p
    d.ellipse([x-r-4,y-r-4,x+r+4,y+r+4], fill=(0,0,0,205))
    d.ellipse([x-r,y-r,x+r,y+r], outline=col+(255,), width=8)
def label(p, txt, col, font, dx=0, dy=0):
    x,y = p[0]+dx, p[1]+dy
    for ox in (-3,0,3):
        for oy in (-3,0,3):
            d.text((x+ox,y+oy), txt, font=font, fill=(0,0,0,235), anchor='mm')
    d.text((x,y), txt, font=font, fill=col+(255,), anchor='mm')

# signals: QT Py -> top row
for s, t, col, by in ((Q['MO'], A['IN'], GREEN, 760), (Q['MI'], A['S+'], YELL, 820),
                      (Q['SCK'], B['S+'], CYAN, 880)):
    poly([s, (s[0], by), (t[0], by), t], col, 11)
poly([A['OUTr'], B['INl']], GREEN, 11)
# power: NeoKey header -> bottom row, one bus per net
poly([N['VIN'], (N['VIN'][0],1690), (A['+'][0],1690), A['+']], RED, 11)
poly([(B['+'][0],1690), B['+']], RED, 11)
poly([N['-'],   (N['-'][0],1737),   (A['-'][0],1737), A['-']], WHITE, 11)
poly([(B['-'][0],1737), B['-']], WHITE, 11)
# SWITCHC to ground, both on the bottom row
poly([A['-'], (A['-'][0],1645), (A['C'][0],1645), A['C']], WHITE, 9)
poly([B['-'], (B['-'][0],1645), (B['C'][0],1645), B['C']], WHITE, 9)

f28, fsm = fe(30), fe(26)
for pads in (A, B):
    for k, c in (('VDD',DIM),('G',DIM),('IN',GREEN),('S+',YELL),('S-',DIM),
                 ('+',RED),('-',WHITE),('O',DIM),('A',DIM),('C',WHITE)):
        if pads is B and k in ('IN','O'): continue
        cc = CYAN if (pads is B and k == 'S+') else c
        r = 11 if cc is DIM else 17
        dot(pads[k], cc, r)
        label(pads[k], k, cc, f28, dy=54 if pads[k][1] == TOP else -52)
dot(A['OUTr'], GREEN); label(A['OUTr'], 'OUT', GREEN, f28, dx=-62, dy=50)
dot(B['INl'], GREEN);  label(B['INl'],  'IN',  GREEN, f28, dx=56, dy=50)
for k, c, off in (('RX',DIM,52),('SCK',CYAN,100),('MI',YELL,52),('MO',GREEN,100),
                  ('3V',DIM,52),('GND',DIM,100),('5V',DIM,52)):
    dot(Q[k], c, 15 if c is not DIM else 11); label(Q[k], k, c, f28, dy=off)
for k, c in (('VIN',RED),('-',WHITE)):
    dot(N[k], c); label(N[k], k if k=='VIN' else 'G', c, f28, dy=-52)
for k in ('3','C','D','INT'):
    dot(N[k], DIM, 11); label(N[k], k, DIM, fsm, dy=-48)
label((2078,1500), 'NeoKey header. No connector used.', DIM, fe(32))

fbig = fj(58)
label((583,1825), 'key 0', YELL, fbig)
label((1018,1825), 'key 1', CYAN, fbig)
label((2400,1825), 'keys 2-5   NeoKey 1x4', DIM, fbig)
label((3400,1825), 'QT Py RP2040', DIM, fbig)

CROP = (170, 600, 3880, 1880)
base = im.crop(CROP); W = base.width
out = Image.new('RGB', (W, base.height + 980), (18,18,20))
out.paste(base, (0,0)); dd = ImageDraw.Draw(out)
y0 = base.height + 30
fh, fr, frm, fnote = fe(46), fe(34), fe(38), fe(32)
dd.text((60, y0), 'Wiring - no connectors. Top row is signal, bottom row is power and ground.', font=fh, fill=(255,255,255))
rows = [
    (GREEN, 'QT Py   MO',  '->  key0 IN',  'key0 OUT -> key1 IN   (side pads, 2.54 apart)'),
    (YELL,  'QT Py   MI',  '->  key0 S+',  ''),
    (CYAN,  'QT Py   SCK', '->  key1 S+',  ''),
    (RED,   'NeoKey VIN',  '->  key1 +  ->  key0 +',  ''),
    (WHITE, 'NeoKey G',    '->  key1 -  ->  key0 -',  'each board:  -  ->  C'),
]
yy = y0 + 78
for col, a, b, c in rows:
    dd.rectangle([60, yy+12, 108, yy+40], fill=col)
    dd.text((130, yy), a, font=frm, fill=(255,255,255))
    dd.text((420, yy), b, font=frm, fill=col)
    dd.text((880, yy), c, font=fr, fill=(190,190,195))
    yy += 62
notes = [
    "This photo is the shell turned over. The face you see is the underside of each board, the one carrying the sockets -- solder there.",
    "The bottom row is the same five nets as the top, with IN replaced by OUT: left to right + - O A C. The other face reads C A O - +.",
    "Take VIN. The pin marked 3 is the AP2112K's output and must not carry 120 mA of pixel.",
    "QT Py 3V, Qwiic V+, NeoKey VCC and VIN are one net already. VIN is not chosen for being the same node -- it is chosen for where the load current flows.",
    "Tapping VIN drops the cable's share out of the difference between the halves; the in-case wire's share stays on both. Six at ffffff, B 100, read as one white.",
    "Power off the NeoKey means the Qwiic cable carries it: pull that cable and all six keys go dark, not four.",
    "The wires run under the boards in a groove in the bottom plate, and both pad rows sit clear of its edges. case/README.md carries its width, headroom and the gauge that fits.",
    "Pad names and positions are read out of Adafruit's Eagle .brd files for the 4978 and the 4980, not off the silk in this photo.",
]

yy += 14
# A note wider than the canvas is not an error anywhere: PIL draws it,
# the file is valid, the page looks finished, and the sentence simply
# ends in mid-air off the right edge. So measure the shape instead of
# trusting the exit code. Watched failing at 342 px over, with the
# longer wording of the lane note this one replaced.
for n in notes:
    text = '•  ' + n
    over = 60 + dd.textlength(text, font=fnote) - (W - 60)
    assert over <= 0, 'note overruns the canvas by {:.0f} px: {!r}'.format(over, n[:60])
    dd.text((60, yy), text, font=fnote, fill=(172,172,180)); yy += 48
out = out.resize((3000, round(out.height * 3000 / out.width)), Image.LANCZOS)
out.save(os.path.join(HERE, 'wiring-six-key.jpg'), quality=92, subsampling=0)
print('wrote', out.size)
