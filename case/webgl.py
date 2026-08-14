"""A real 3D viewer, because the flat renders lie about depth.

    .venv/bin/python webgl.py dump                    # stacked
    MPAD_LAYOUT=inline .venv/bin/python webgl.py dump # inline
    .venv/bin/python webgl.py page                    # -> out/viewer.html

`product.py` sorts triangles by distance and paints them back to front.
That is the only depth test matplotlib offers, and it is wrong wherever
two surfaces interpenetrate or one is concave -- which describes most of
this case. A GPU depth buffer resolves it per pixel and the artefacts go
away entirely.

Geometry rides in the page as int16, quantised over each layout's own
bounding box: about 0.002 mm a step over 130 mm, which is far finer than
anything printed here, and a quarter the size of float32.
"""

import base64
import json
import struct
import sys
from pathlib import Path

import numpy as np

import mock
import params as P
import product

# Keep-out volumes read as a check, not as a part of the object.
ENV_COLOR = "#ff3d8b"

OUT = Path(__file__).parent / "out"


def envelopes():
    """The check's stand-ins, minus the bare boards the viewer already draws.

    The two models are the same board: same outline, same corner radius,
    same Z. Drawn together they are coplanar everywhere, which has no
    correct depth ordering and shows up as the surfaces tearing at each
    other. Subtracting the board leaves exactly what the check claims
    *beyond* it -- sockets, connectors with a plug mated, the USB shell,
    the buttons -- which is the more useful picture anyway.

    The subtracted slab is grown by a hair so the shared faces are truly
    consumed rather than left touching, which would fight just the same.
    """
    e = 0.02
    neokey_slab = product.board(
        P.NEOKEY_W + e, P.NEOKEY_D + e, P.NEOKEY_CORNER_R,
        P.NEOKEY_CENTER[0], P.NEOKEY_CENTER[1],
        P.Z_NEOKEY_BOTTOM - e, P.NEOKEY_T + 2 * e)
    breakout_slabs = None
    for cx, cy in P.BREAKOUT_CENTERS:
        slab = product.board(
            P.BREAKOUT_W + e, P.BREAKOUT_D + e, P.BREAKOUT_CORNER_R,
            cx, cy, P.Z_NEOKEY_BOTTOM - e, P.BREAKOUT_T + 2 * e)
        breakout_slabs = slab if breakout_slabs is None else breakout_slabs + slab
    boards = {
        "NeoKey + sockets": neokey_slab,
        "breakouts + sockets": breakout_slabs,
        # The switch bodies start exactly on a board's top face, so they
        # need the same slabs taken out of them for the same reason --
        # and now that is all three boards, not just the one.
        "switch bodies": neokey_slab + breakout_slabs,
        "QT Py + parts": product.board(
            P.QTPY_PLAN_W + e, P.QTPY_PLAN_D + e, P.QTPY_CORNER_R,
            P.QTPY_CENTER[0], P.QTPY_CENTER[1],
            P.Z_QTPY_LOW - e, P.QTPY_T + 2 * e),
    }
    return {k: (v - boards[k]) for k, v in mock.everything().items()}


def dump():
    """Tessellate this layout's scene and write it next to its STLs."""
    parts = []
    blobs = []
    # The viewer's boards are bare slabs; these are the envelopes the
    # interference check actually runs against. Shipping both means the
    # thing on screen can be compared with the thing that was verified,
    # instead of being taken on faith.
    lift_of = {"NeoKey + sockets": 20.0, "breakouts + sockets": 20.0,
               "switch bodies": 46.0, "QT Py + parts": 8.0}
    scene = list(product.scene()) + [
        (f"env-{k}", v, ENV_COLOR, 0.34, lift_of[k])
        for k, v in envelopes().items()
    ]
    for name, solid, color, alpha, lift in scene:
        mesh = product.mesh_of(name, solid)
        tris = mesh.vertices[mesh.faces].reshape(-1, 3)
        parts.append({
            "name": name,
            "color": color,
            "alpha": alpha,
            "lift": lift,
            "count": len(tris),
        })
        blobs.append(tris.astype(np.float64))

    allv = np.concatenate(blobs)
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    span = np.maximum(hi - lo, 1e-6)
    quant = []
    for v in blobs:
        q = np.round((v - lo) / span * 65534.0 - 32767.0)
        quant.append(np.clip(q, -32767, 32767).astype("<i2"))
    data = np.concatenate(quant).tobytes()

    payload = {
        "layout": P.LAYOUT,
        "case": [P.CASE_W, P.CASE_D, P.CASE_H],
        "keycapTop": float(allv[:, 2].max()),
        "lo": lo.tolist(),
        "span": span.tolist(),
        "parts": parts,
        "data": base64.b64encode(data).decode(),
    }
    path = OUT / P.LAYOUT / "geom.json"
    path.write_text(json.dumps(payload))
    print(f"  {path}  {len(data) / 1024:.0f} KB of int16, "
          f"{sum(p['count'] for p in parts) // 3} triangles")


# The part list is also the legend, so the labels have to say what a
# person would call the thing, not what the mesh is named.
LABELS = {
    "shell": ("Shell", "printed"),
    "bottom": ("Bottom plate", "printed"),
    "neokey": ("NeoKey 1x4 QT", "ADA-4980, keys 2-5 on I2C"),
    "breakout": ("NeoKey Breakout \u00d72", "ADA-4978, keys 0-1 on GPIO"),
    "qtpy": ("QT Py RP2040", "ADA-4900"),
    "sw": ("Switches", "Durock Ice King"),
    "cap": ("Keycaps", "1U clear ABS"),
    "led": ("NeoPixels", "under each key"),
}
STATUS = [
    ("idle", product.KEY_COLORS[0]),
    ("running", product.KEY_COLORS[1]),
    ("awaiting approval", product.KEY_COLORS[2]),
    ("done, unread", product.KEY_COLORS[3]),
]


def page():
    geoms = {}
    for layout in ("stacked", "inline"):
        f = OUT / layout / "geom.json"
        if not f.exists():
            sys.exit(f"missing {f} -- run `dump` for both layouts first")
        geoms[layout] = json.loads(f.read_text())

    html = TEMPLATE.replace("__DATA__", json.dumps(geoms))
    html = html.replace("__LABELS__", json.dumps(LABELS))
    html = html.replace("__STATUS__", json.dumps(STATUS))
    path = OUT / "viewer.html"
    path.write_text(html)
    print(f"  {path}  {path.stat().st_size / 1024:.0f} KB")


TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Canopy MacroPad — case viewer</title>
<style>
/* Light is the base set; the two blocks below only re-point tokens, so
   nothing is defined solely behind a media query or a theme stamp. */
:root {
  --bg:#e9ecf1; --panel:#ffffff; --line:#d3d9e2;
  --ink:#111721; --dim:#5f6a7a; --faint:#8b95a4;
  --accent:#0b3fd6; --accent-ink:#ffffff;
  --grid:rgba(17,23,33,.055);
  --sky-a:#dfe4ec; --sky-b:#f3f5f8;
  --cut:#c8443a;
  color-scheme:light dark;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#0d1015; --panel:#161b23; --line:#262e3a;
    --ink:#e6ecf5; --dim:#98a3b3; --faint:#6c7787;
    --accent:#6f95ff; --accent-ink:#0d1015;
    --grid:rgba(230,236,245,.06);
    --sky-a:#0a0d12; --sky-b:#161b23;
    --cut:#e0574c;
  }
}
:root[data-theme="dark"]{
  --bg:#0d1015; --panel:#161b23; --line:#262e3a;
  --ink:#e6ecf5; --dim:#98a3b3; --faint:#6c7787;
  --accent:#6f95ff; --accent-ink:#0d1015;
  --grid:rgba(230,236,245,.06);
  --sky-a:#0a0d12; --sky-b:#161b23;
  --cut:#e0574c;
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:400 14px/1.5 ui-sans-serif,-apple-system,"SF Pro Text",
       "Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.mono{font-family:ui-monospace,"SF Mono","JetBrains Mono",Menlo,
      Consolas,monospace; font-variant-numeric:tabular-nums}

.app{display:grid; grid-template-columns:264px 1fr; height:100%}
@media (max-width:820px){ .app{grid-template-columns:1fr; grid-template-rows:1fr auto} }

/* --- stage --- */
.stage{position:relative; min-width:0; min-height:0;
  background:radial-gradient(120% 90% at 50% 15%,var(--sky-b),var(--sky-a))}
canvas{display:block; width:100%; height:100%; touch-action:none; cursor:grab}
canvas:active{cursor:grabbing}
.hud{position:absolute; left:16px; bottom:14px; display:flex; gap:14px;
  color:var(--faint); font-size:11px; letter-spacing:.06em;
  text-transform:uppercase; pointer-events:none}
.stamp{position:absolute; right:16px; top:14px; text-align:right;
  color:var(--faint); font-size:11px; letter-spacing:.06em}
.stamp b{display:block; color:var(--dim); font-size:15px; letter-spacing:0;
  font-weight:500}

/* --- rail --- */
.rail{background:var(--panel); border-right:1px solid var(--line);
  overflow-y:auto; display:flex; flex-direction:column}
@media (max-width:820px){ .rail{border-right:0; border-top:1px solid var(--line);
  max-height:46vh} }
.head{padding:14px 14px 11px; border-bottom:1px solid var(--line)}
.head h1{margin:0; font-size:14px; font-weight:600; letter-spacing:-.01em}
.head p{margin:3px 0 0; color:var(--dim); font-size:11.5px}
.grp{padding:11px 14px; border-bottom:1px solid var(--line)}
.lbl{margin:0 0 7px; font-size:10px; letter-spacing:.11em;
  text-transform:uppercase; color:var(--faint)}
/* A heading that shares its line with a control, so the control does not
   cost a row of its own. */
.hrow{display:flex; align-items:center; justify-content:space-between;
  gap:10px; margin:0 0 7px}
.hrow .lbl{margin:0}
.mini{appearance:none; border:1px solid var(--line); background:transparent;
  color:var(--dim); border-radius:6px; padding:3px 9px; font:inherit;
  font-size:11px; cursor:pointer}
.mini:hover{color:var(--ink)}
.mini[aria-pressed="true"]{background:var(--accent); color:var(--accent-ink);
  border-color:var(--accent)}

.seg{display:grid; grid-template-columns:1fr 1fr; gap:6px}
.seg3{grid-template-columns:repeat(3,1fr)}
.seg4{grid-template-columns:repeat(4,1fr)}
.seg4 button{padding:7px 2px; font-size:12px}
.seg button{appearance:none; border:1px solid var(--line); background:transparent;
  color:var(--dim); border-radius:6px; padding:6px 5px; font:inherit;
  font-size:12px; cursor:pointer; transition:background .12s,color .12s}
.seg button:hover{color:var(--ink)}
.seg button[aria-pressed="true"]{background:var(--accent); color:var(--accent-ink);
  border-color:var(--accent)}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}

.row{display:flex; align-items:center; justify-content:space-between; gap:10px}
input[type=range]{width:100%; accent-color:var(--accent)}

.parts{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:1px}
.parts button{display:flex; align-items:center; gap:9px; width:100%;
  appearance:none; background:transparent; border:0; padding:4px 5px;
  border-radius:6px; font:inherit; color:inherit; cursor:pointer; text-align:left}
.parts button:hover{background:var(--grid)}
.parts button[aria-pressed="false"]{opacity:.38}
.sw{width:11px; height:11px; border-radius:3px; flex:none;
  border:1px solid rgba(128,128,128,.45)}
.pn{flex:1; min-width:0; font-size:12.5px; line-height:1.25}
.pn small{display:block; color:var(--faint); font-size:10.5px}
.hint{margin:7px 0 0; color:var(--faint); font-size:10.5px; line-height:1.45}
.hint code{font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:10.5px}

.keys{display:flex; flex-direction:column; gap:4px}
.keys div{display:flex; align-items:center; gap:8px; font-size:11.5px;
  color:var(--dim)}
.dims{display:flex; flex-direction:column; gap:4px; font-size:12px}
.dims div{display:flex; justify-content:space-between; gap:10px}
.dims span:first-child{color:var(--dim)}
.note{padding:11px 14px 16px; color:var(--faint); font-size:11px;
  line-height:1.5}
@media (prefers-reduced-motion:reduce){ *{transition:none!important} }
</style>

<div class="app">
  <aside class="rail">
    <div class="head">
      <h1>Canopy MacroPad</h1>
      <p>Printed case, two layouts</p>
    </div>

    <div class="grp">
      <div class="seg" id="layout">
        <button data-v="stacked" aria-pressed="false">Stacked</button>
        <button data-v="inline" aria-pressed="true">Inline</button>
      </div>
      <div class="seg" id="proj" style="margin-top:6px">
        <button data-v="persp" aria-pressed="true">Perspective</button>
        <button data-v="ortho" aria-pressed="false">Ortho</button>
      </div>
      <div class="seg seg4" id="preset" style="margin-top:6px">
        <button data-v="iso">Iso</button>
        <button data-v="top">Top</button>
        <button data-v="front">Front</button>
        <button data-v="left">Left</button>
      </div>
    </div>

    <div class="grp">
      <div class="hrow"><p class="lbl">Section</p>
        <button class="mini" id="sectflip" aria-pressed="false">Flip</button>
      </div>
      <div class="seg seg4" id="sect">
        <button data-v="" aria-pressed="true">Off</button>
        <button data-v="x" aria-pressed="false">YZ</button>
        <button data-v="y" aria-pressed="false">XZ</button>
        <button data-v="z" aria-pressed="false">XY</button>
      </div>
      <input type="range" id="sectAt" min="0" max="1000" value="500"
             style="margin-top:7px" aria-label="Move the section plane">
      <p class="hint">The cut face is filled solid, so a wall reads as a
        wall and not as a hole.</p>
    </div>

    <div class="grp">
      <div class="hrow"><p class="lbl">Case</p>
        <button class="mini" id="env" aria-pressed="false">Envelopes</button>
      </div>
      <div class="seg seg3" id="shellmode">
        <button data-v="solid" aria-pressed="true">Solid</button>
        <button data-v="ghost" aria-pressed="false">Glass</button>
        <button data-v="hidden" aria-pressed="false">Off</button>
      </div>
      <p class="hint">Glass reads the inside with the lid shut, which is
        how it is assembled. Envelopes swaps the bare board slabs for the
        volumes <code>build.py</code> booleans against — sockets,
        connectors with a plug mated, buttons, the USB shell.</p>
    </div>

    <div class="grp">
      <div class="hrow"><p class="lbl">Explode</p></div>
      <input type="range" id="explode" min="0" max="100" value="0"
             aria-label="Explode the assembly">
    </div>

    <div class="grp">
      <ul class="parts" id="parts"></ul>
    </div>

    <div class="grp">
      <p class="lbl">Key colour = pane state</p>
      <div class="keys" id="keys"></div>
    </div>

    <div class="grp">
      <div class="dims mono" id="dims"></div>
    </div>

    <p class="note">Drag to orbit, scroll to zoom, double-click to reset.
      Depth is resolved per pixel here, so the transparent keycaps and the
      case interior sort correctly — which the flat renders could not do.</p>
  </aside>

  <div class="stage">
    <canvas id="gl"></canvas>
    <div class="stamp"><b id="stampSize">—</b><span id="stampName">—</span></div>
    <div class="hud"><span>drag · orbit</span><span>right-drag · pan</span>
      <span>scroll · zoom</span></div>
  </div>
</div>

<script>
const GEOM = __DATA__, LABELS = __LABELS__, STATUS = __STATUS__;

/* ---------- gl ---------- */
const cv = document.getElementById('gl');
const gl = cv.getContext('webgl2', {antialias:true, alpha:false, stencil:true});
const HAS_FLOAT = gl && gl.getExtension('EXT_color_buffer_float');
if (!gl) document.querySelector('.stage').innerHTML =
  '<p style="padding:2rem;color:var(--dim)">This browser has no WebGL2.</p>';

/* The canvas is created with antialias:true, and it does nothing: every
   pass goes into our own framebuffer, and the canvas's multisampling
   only ever covers what is drawn straight to it. Supersampling the
   offscreen targets and box-resolving them in the composite is both
   simpler than multisampled renderbuffers and exact -- no MSAA pattern,
   no per-attachment blit, and it antialiases the OIT edges too. */
const SS = 2;
const FOV = 0.46;  /* ~26 deg: long and low reads badly through a wide lens */
/* The presets are still written as azimuth and elevation, because that
   is how a person says "look at it from the top". They are turned into
   an orientation once, on the way in, and nothing downstream carries two
   angles -- see `qFromAzEl`. Nothing clamps them either: the camera has
   no pole to stay away from any more.

   The 1.5697 that used to be here was 0.0011 rad short of straight down,
   on the stated grounds that the view matrix collapsed at the pole. It
   does not -- the residual in `Math.cos(Math.PI/2)` carries the right
   direction and the normalise recovers a unit vector from it, checked
   against the old code side by side. What the two angles really lose at
   the pole is a degree of freedom, which no amount of care in building
   the matrix gives back. */
const EL_MAX = Math.PI / 2;

/* Weighted-blended OIT (McGuire & Bavoil). Sorting transparent objects
   back to front cannot be right here: a keycap's skirt and the switch
   housing inside it interpenetrate, so no ordering of the two is correct
   from every angle. This weights each fragment by depth and coverage and
   resolves them in one composite, with no ordering at all. */
const VS = `#version 300 es
layout(location=0) in vec3 p;
uniform mat4 uMVP, uMV; uniform vec3 uLift; out vec3 vP; out vec3 vW;
void main(){ vec3 q = p + uLift; vP = (uMV * vec4(q,1.0)).xyz; vW = q;
  gl_Position = uMVP * vec4(q,1.0); }`;

const FS = `#version 300 es
precision highp float; in vec3 vP; in vec3 vW;
layout(location=0) out vec4 oOpaque;
layout(location=1) out vec4 oAccum;
layout(location=2) out vec4 oReveal;
uniform vec3 uColor; uniform float uAlpha; uniform int uMode;
uniform vec2 uDepth;  // near, far
/* Section plane, in model space. xyz is the normal and w the offset
   along it; an all-zero normal means no section, so one uniform carries
   both the plane and the switch. */
uniform vec4 uPlane;
vec3 shade(){
  /* Flat normal from screen-space derivatives: the mesh ships without
     normals, and faceted is the honest look for tessellated CAD. */
  vec3 n = normalize(cross(dFdx(vP), dFdy(vP)));
  vec3 L = normalize(vec3(0.35,0.45,0.82));
  float rim = pow(1.0 - abs(normalize(-vP).z), 2.0);
  return uColor * (0.34 + 0.66*abs(dot(n,L))) + rim*0.16;
}
void main(){
  if (dot(uPlane.xyz, uPlane.xyz) > 0.0 && dot(vW, uPlane.xyz) > uPlane.w)
    discard;
  vec3 c = shade();
  if (uMode == 0){ oOpaque = vec4(c, 1.0); return; }
  float a = uAlpha;
  /* Normalised depth, not millimetres. Feeding raw view distance into
     the canonical weight sends every fragment past the clamp, and the
     accumulation degenerates into a flat average -- which is exactly
     what "everything looks like fog" means. */
  float z = clamp((-vP.z - uDepth.x) / max(uDepth.y - uDepth.x, 1e-3),
                  0.0, 1.0);
  /* Depth-dominant weight. The canonical "weight 3" function is built
     for many nearly-transparent fragments; at a = 0.86 its coverage term
     saturates, every fragment pins to the clamp, and the accumulation
     becomes an unweighted average -- four keycaps rendered as one fog.
     This keeps three decades of range across the depth span instead. */
  float w = a * clamp(3e3 * pow(1.0 - z, 3.0), 1e-2, 3e3);
  if (uMode == 1) oAccum = vec4(c*a, a) * w;
  else            oReveal = vec4(a);
}`;

const CVS = `#version 300 es
void main(){ vec2 p = vec2((gl_VertexID<<1)&2, gl_VertexID&2);
  gl_Position = vec4(p*2.0-1.0, 0.0, 1.0); }`;
const CFS = `#version 300 es
precision highp float; out vec4 o;
uniform sampler2D tOpaque, tAccum, tReveal;
uniform vec3 uSkyA, uSkyB; uniform vec2 uRes; uniform int uSS;
void main(){
  /* Box-resolve the supersampled targets. Averaging the three buffers
     separately and compositing after is what keeps the transparent
     edges antialiased as well as the opaque ones. */
  ivec2 b = ivec2(gl_FragCoord.xy) * uSS;
  vec4 op = vec4(0.0); vec4 ac = vec4(0.0); float rv = 0.0;
  for (int y = 0; y < uSS; y++) for (int x = 0; x < uSS; x++){
    ivec2 t = b + ivec2(x,y);
    op += texelFetch(tOpaque, t, 0);
    ac += texelFetch(tAccum, t, 0);
    rv += texelFetch(tReveal, t, 0).r;
  }
  float n = float(uSS*uSS);
  op /= n; ac /= n; rv /= n;
  vec2 uv = gl_FragCoord.xy / uRes;
  float d = distance(uv, vec2(0.5, 0.85));
  vec3 bg = mix(uSkyB, uSkyA, clamp(d*1.35, 0.0, 1.0));
  vec3 base = mix(bg, op.rgb, op.a);
  vec3 trans = ac.rgb / max(ac.a, 1e-5);
  o = vec4(mix(base, trans, 1.0 - rv), 1.0);
}`;

/* The cut face. Clipping alone leaves a hollow shell -- you see the
   inside of the far wall through the opening and the part reads as a
   tube rather than a solid, which is exactly the thing a section view
   exists to avoid. So the plane is drawn as real geometry wherever the
   stencil says it is inside a body. */
const KVS = `#version 300 es
layout(location=0) in vec3 p; uniform mat4 uMVP;
void main(){ gl_Position = uMVP * vec4(p,1.0); }`;
const KFS = `#version 300 es
precision highp float; uniform vec3 uColor;
layout(location=0) out vec4 o;
void main(){ o = vec4(uColor, 1.0); }`;

function sh(t, src){ const x = gl.createShader(t); gl.shaderSource(x, src);
  gl.compileShader(x);
  if(!gl.getShaderParameter(x, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(x);
  return x; }
function link(vs, fs){ const pr = gl.createProgram();
  gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs));
  gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(pr);
  if(!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw gl.getProgramInfoLog(pr);
  return pr; }

const prog = link(VS, FS), comp = link(CVS, CFS), capp = link(KVS, KFS);
const U = (pr,n) => gl.getUniformLocation(pr, n);
const uMVP=U(prog,'uMVP'), uMV=U(prog,'uMV'), uColor=U(prog,'uColor'),
      uAlpha=U(prog,'uAlpha'), uLift=U(prog,'uLift'), uMode=U(prog,'uMode'),
      uDepth=U(prog,'uDepth'), uPlane=U(prog,'uPlane');
const kMVP=U(capp,'uMVP'), kColor=U(capp,'uColor');
const capVBO = gl.createBuffer();
const capVAO = gl.createVertexArray();
gl.bindVertexArray(capVAO);
gl.bindBuffer(gl.ARRAY_BUFFER, capVBO);
gl.enableVertexAttribArray(0);
gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
gl.bindVertexArray(null);
const cOpaque=U(comp,'tOpaque'), cAccum=U(comp,'tAccum'),
      cReveal=U(comp,'tReveal'), cSkyA=U(comp,'uSkyA'), cSkyB=U(comp,'uSkyB'),
      cRes=U(comp,'uRes'), cSS=U(comp,'uSS');
const emptyVAO = gl.createVertexArray();

/* ---------- offscreen targets ---------- */
let FB = null, TEX = {}, fbSize = [0,0];
function target(w, h, internal, fmt, type){
  const t = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, fmt, type, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return t;
}
function resize(w, h){
  if (fbSize[0] === w && fbSize[1] === h) return;
  fbSize = [w, h];
  if (FB) { gl.deleteFramebuffer(FB);
    Object.values(TEX).forEach(t => t.rb ? gl.deleteRenderbuffer(t)
                                         : gl.deleteTexture(t)); }
  FB = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, FB);
  TEX.opaque = target(w, h, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE);
  TEX.accum  = target(w, h, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
  TEX.reveal = target(w, h, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
  const db = gl.createRenderbuffer();
  gl.bindRenderbuffer(gl.RENDERBUFFER, db);
  gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH24_STENCIL8, w, h);
  TEX.depth = db; TEX.depth.rb = true;
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
    gl.TEXTURE_2D, TEX.opaque, 0);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1,
    gl.TEXTURE_2D, TEX.accum, 0);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT2,
    gl.TEXTURE_2D, TEX.reveal, 0);
  gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_STENCIL_ATTACHMENT,
    gl.RENDERBUFFER, db);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
}

/* ---------- scenes ---------- */
function hex(h){ return [parseInt(h.slice(1,3),16)/255,
  parseInt(h.slice(3,5),16)/255, parseInt(h.slice(5,7),16)/255]; }
function group(name){
  const m = name.match(/^(shell|bottom|neokey|breakout|qtpy|sw|cap|led)/);
  return m ? m[1] : name;
}

const scenes = {};
for (const [key, g] of Object.entries(GEOM)) {
  const raw = Uint8Array.from(atob(g.data), c => c.charCodeAt(0));
  const q = new Int16Array(raw.buffer);
  const f = new Float32Array(q.length);
  for (let i = 0; i < q.length; i += 3)
    for (let k = 0; k < 3; k++)
      f[i+k] = g.lo[k] + (q[i+k] + 32767) / 65534 * g.span[k];
  const vbo = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, f, gl.STATIC_DRAW);
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  gl.bindVertexArray(null);

  let off = 0;
  const parts = g.parts.map(p => {
    const start = off; off += p.count;
    return {...p, start, grp: group(p.name), rgb: hex(p.color),
            env: p.name.startsWith('env-')};
  });
  scenes[key] = {...g, vao, parts,
    centre:[g.lo[0]+g.span[0]/2, g.lo[1]+g.span[1]/2, g.lo[2]+g.span[2]/2],
    radius: Math.hypot(g.span[0], g.span[1], g.span[2]) / 2};
}

/* ---------- state ---------- */
const S = {layout:'inline', explode:0, env:false, shellMode:'solid',
           ortho:false, hidden:new Set(),
           sect:'', sectT:0.5, sectFlip:false,
           q:[0,0,0,1], tq:[0,0,0,1], dist:1, tDist:1,
           pan:[0,0,0], tPan:[0,0,0]};
S.q = S.tq = qFromAzEl(-0.72, 0.42);
/* Frame on the widest axis and the viewport's aspect, not on a constant:
   a 120 mm bar and a 98 mm one need different pull-backs. */
/* Project the bounding box onto the screen axes for the direction we are
   actually heading to. Framing on the widest axis regardless of direction
   is right from the front and leaves the end view a postage stamp. */
function fit(){
  const sc = scenes[S.layout], sp = sc.span;
  const asp = Math.max(cv.clientWidth / Math.max(cv.clientHeight, 1), 0.35);
  const [right, up] = qBasis(S.tq);
  const ext = v => 0.5 * (Math.abs(sp[0]*v[0]) + Math.abs(sp[1]*v[1])
                          + Math.abs(sp[2]*v[2]));
  const need = Math.max(ext(right) / asp, ext(up));
  S.tDist = need / Math.tan(FOV/2) * 1.18;
  S.dist = S.tDist;
}
fit();

/* ---------- matrices ---------- */
const mul = (a,b)=>{const o=new Float32Array(16);
  for(let i=0;i<4;i++)for(let j=0;j<4;j++){let s=0;
    for(let k=0;k<4;k++)s+=a[k*4+j]*b[i*4+k]; o[i*4+j]=s;} return o;};
function persp(fov,asp,n,f){const t=1/Math.tan(fov/2);
  return new Float32Array([t/asp,0,0,0, 0,t,0,0, 0,0,(f+n)/(n-f),-1,
    0,0,2*f*n/(n-f),0]);}
/* Half-height is taken from the same distance and field of view, so
   switching projection holds the framing instead of jumping. */
function ortho(hh,asp,n,f){const hw=hh*asp;
  return new Float32Array([1/hw,0,0,0, 0,1/hh,0,0, 0,0,-2/(f-n),0,
    0,0,-(f+n)/(f-n),1]);}
/* ---------- orientation ----------
 *
 * The camera used to be two angles, and two angles lose a degree of
 * freedom where they meet: at the pole, turning the azimuth and rolling
 * about the view axis are the same motion, so one of the two drags stops
 * doing anything new. That is gimbal lock, and it is a property of the
 * parameterisation -- building the basis more carefully does not remove
 * it, which was worth finding out before rewriting this.
 *
 * A quaternion has no poles. Drags rotate it about the *camera's* own
 * axes, so the model turns the way it is grabbed from any attitude, and
 * there is no limit to clamp: it tumbles over the top and keeps going.
 * The cost is that the horizon is no longer held level, which is why the
 * four presets exist.
 */
/* Declarations rather than `const` arrows, and that is load-bearing:
   the state block sets the opening orientation and sits above this, so a
   `const` here is still in its temporal dead zone when the page runs and
   the whole viewer throws before it draws anything. */
function qmul(a,b){ return [
  a[3]*b[0] + a[0]*b[3] + a[1]*b[2] - a[2]*b[1],
  a[3]*b[1] - a[0]*b[2] + a[1]*b[3] + a[2]*b[0],
  a[3]*b[2] + a[0]*b[1] - a[1]*b[0] + a[2]*b[3],
  a[3]*b[3] - a[0]*b[0] - a[1]*b[1] - a[2]*b[2]]; }
function qnorm(q){ const l = Math.hypot(q[0],q[1],q[2],q[3]) || 1;
  return [q[0]/l, q[1]/l, q[2]/l, q[3]/l]; }
/* A rotation about a camera-space axis, which is what a drag is. */
function qAxis(ax, ang){ const h = ang/2, s = Math.sin(h);
  return [ax[0]*s, ax[1]*s, ax[2]*s, Math.cos(h)]; }

/* The three view axes as world vectors: rows of the rotation the
   quaternion stands for. x is screen right, y screen up, z runs from the
   centre out to the eye. */
function qBasis(q){
  const [x,y,z,w] = q;
  return [[1-2*(y*y+z*z),   2*(x*y+z*w),   2*(x*z-y*w)],
          [  2*(x*y-z*w), 1-2*(x*x+z*z),   2*(y*z+x*w)],
          [  2*(x*z+y*w),   2*(y*z-x*w), 1-2*(x*x+y*y)]];
}

/* Presets are still spoken as azimuth and elevation. This is the only
   place the two ever appear, and it is one-way. */
function qFromAzEl(az, el){
  const ca=Math.cos(az), sa=Math.sin(az), ce=Math.cos(el), se=Math.sin(el);
  return mat2q([[-sa, ca, 0],
                [-se*ca, -se*sa, ce],
                [ce*ca, ce*sa, se]]);
}
function mat2q(m){
  const t = m[0][0] + m[1][1] + m[2][2];
  if (t > 0) { const s = Math.sqrt(t+1)*2;
    return qnorm([(m[1][2]-m[2][1])/s, (m[2][0]-m[0][2])/s,
                  (m[0][1]-m[1][0])/s, s/4]); }
  if (m[0][0] > m[1][1] && m[0][0] > m[2][2]) {
    const s = Math.sqrt(1+m[0][0]-m[1][1]-m[2][2])*2;
    return qnorm([s/4, (m[1][0]+m[0][1])/s, (m[2][0]+m[0][2])/s,
                  (m[1][2]-m[2][1])/s]); }
  if (m[1][1] > m[2][2]) {
    const s = Math.sqrt(1+m[1][1]-m[0][0]-m[2][2])*2;
    return qnorm([(m[1][0]+m[0][1])/s, s/4, (m[2][1]+m[1][2])/s,
                  (m[2][0]-m[0][2])/s]); }
  const s = Math.sqrt(1+m[2][2]-m[0][0]-m[1][1])*2;
  return qnorm([(m[2][0]+m[0][2])/s, (m[2][1]+m[1][2])/s, s/4,
                (m[0][1]-m[1][0])/s]);
}

function orbitView(q, eye){
  const [x, y, z] = qBasis(q);
  return new Float32Array([x[0],y[0],z[0],0, x[1],y[1],z[1],0,
    x[2],y[2],z[2],0, -dot(x,eye),-dot(y,eye),-dot(z,eye),1]);
}
function dot(a,b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
function dot4(a,b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]+a[3]*b[3]; }

function css(name){
  const v = getComputedStyle(document.documentElement)
              .getPropertyValue(name).trim();
  return hex(v.length === 4
    ? '#'+v[1]+v[1]+v[2]+v[2]+v[3]+v[3] : v);
}

/* ---------- draw ---------- */
function render(){
  const sc = scenes[S.layout];
  const dpr = Math.min(devicePixelRatio||1, 1.5);
  const w = Math.max(cv.clientWidth*dpr|0, 1), h = Math.max(cv.clientHeight*dpr|0, 1);
  if (cv.width !== w || cv.height !== h){ cv.width=w; cv.height=h; }
  const W = w*SS, H = h*SS;
  resize(W, H);
  gl.viewport(0,0,W,H);

  const d = S.dist;
  const c = [sc.centre[0] + S.pan[0], sc.centre[1] + S.pan[1],
             sc.centre[2] + S.pan[2]];
  const out = qBasis(S.q)[2];
  const eye = [c[0] + d*out[0], c[1] + d*out[1], c[2] + d*out[2]];
  const V = orbitView(S.q, eye);
  /* Clamped hard to the model: a 0.05d..6d range spends most of a 24-bit
     depth buffer on empty space, and the switch flanges sitting flat on
     the plate then fight over the same depth value. */
  /* Orthographic depth is linear, so it does not need the near plane
     pushed out to stay precise -- and pushing it out would clip the near
     half of the model instead. */
  const near = S.ortho ? d - sc.radius*1.6
                       : Math.max(d - sc.radius*1.6, d*0.02);
  const far = d + sc.radius*1.6;
  const P4 = S.ortho ? ortho(d*Math.tan(FOV/2), w/h, near, far)
                     : persp(FOV, w/h, near, far);
  const MVP = mul(P4, V);

  gl.bindFramebuffer(gl.FRAMEBUFFER, FB);
  gl.useProgram(prog);
  gl.uniformMatrix4fv(uMV, false, V);
  gl.uniformMatrix4fv(uMVP, false, MVP);
  gl.uniform2f(uDepth, near, far);
  const PL = sectPlane();
  gl.uniform4f(uPlane, ...(PL ? [...PL.n, PL.d] : [0,0,0,0]));
  gl.bindVertexArray(sc.vao);

  /* The case can be turned to glass so the inside can be read with the
     lid on. Nothing special is needed for it: the printed parts simply
     move into the transparent pass, their near walls blend over the
     boards, and their far walls fail the depth test against those same
     boards and drop out. */
  const CASE = new Set(['shell', 'bottom']);
  const alphaOf = p => (CASE.has(p.grp) && S.shellMode === 'ghost')
    ? 0.20 : p.alpha;
  const live = sc.parts.filter(p =>
    p.env ? S.env
          : !S.hidden.has(p.grp)
            && !(CASE.has(p.grp) && S.shellMode === 'hidden'));
  const draw = p => {
    gl.uniform3f(uColor, p.rgb[0], p.rgb[1], p.rgb[2]);
    gl.uniform1f(uAlpha, alphaOf(p));
    gl.uniform3f(uLift, 0, 0, p.lift * S.explode);
    gl.drawArrays(gl.TRIANGLES, p.start, p.count);
  };

  // 1. opaque, depth on
  gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.NONE, gl.NONE]);
  gl.clearBufferfv(gl.COLOR, 0, [0,0,0,0]);
  gl.clearBufferfi(gl.DEPTH_STENCIL, 0, 1.0, 0);
  gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
  gl.uniform1i(uMode, 0);
  const solid = live.filter(p => alphaOf(p) >= 1);
  solid.forEach(draw);

  /* 1b. cap the cut. Per part, because Fusion fills each body in its own
     colour and a single grey cap loses which wall you are looking at.
     The stencil counts front faces against back faces with the clip
     active: where the plane is inside a closed body the two do not
     cancel, and that is exactly where the quad is allowed to paint.

     Depth is off while counting so every layer is seen, and back on for
     the quad so the cut face is occluded by anything nearer. */
  if (PL) {
    /* One colour for every cut face rather than each part's own. A
       section is read for where material is, and a single flat fill says
       that in one glance where twelve tinted ones make you match each
       patch back to a legend first. */
    const CUT = css('--cut');
    gl.bindBuffer(gl.ARRAY_BUFFER, capVBO);
    gl.bufferData(gl.ARRAY_BUFFER, capQuad(PL), gl.DYNAMIC_DRAW);
    gl.enable(gl.STENCIL_TEST);
    for (const p of solid) {
      gl.clearBufferiv(gl.STENCIL, 0, new Int32Array([0]));
      gl.useProgram(prog);
      gl.bindVertexArray(sc.vao);
      gl.disable(gl.DEPTH_TEST); gl.depthMask(false);
      gl.colorMask(false, false, false, false);
      gl.stencilFunc(gl.ALWAYS, 0, 0xff);
      gl.stencilOpSeparate(gl.FRONT, gl.KEEP, gl.KEEP, gl.INCR_WRAP);
      gl.stencilOpSeparate(gl.BACK,  gl.KEEP, gl.KEEP, gl.DECR_WRAP);
      draw(p);

      gl.colorMask(true, true, true, true);
      gl.enable(gl.DEPTH_TEST); gl.depthMask(true);
      gl.stencilFunc(gl.NOTEQUAL, 0, 0xff);
      gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
      gl.useProgram(capp);
      gl.uniformMatrix4fv(kMVP, false, MVP);
      gl.uniform3fv(kColor, CUT);
      gl.bindVertexArray(capVAO);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
    gl.disable(gl.STENCIL_TEST);
    gl.useProgram(prog);
    gl.bindVertexArray(sc.vao);
    gl.uniform1i(uMode, 0);
  }

  const clear = live.filter(p => alphaOf(p) < 1);
  gl.depthMask(false); gl.enable(gl.BLEND);

  // 2. accumulate weighted colour
  gl.drawBuffers([gl.NONE, gl.COLOR_ATTACHMENT1, gl.NONE]);
  gl.clearBufferfv(gl.COLOR, 1, [0,0,0,0]);
  gl.blendFunc(gl.ONE, gl.ONE);
  gl.uniform1i(uMode, 1);
  clear.forEach(draw);

  // 3. accumulate coverage: reveal *= (1 - a)
  gl.drawBuffers([gl.NONE, gl.NONE, gl.COLOR_ATTACHMENT2]);
  gl.clearBufferfv(gl.COLOR, 2, [1,1,1,1]);
  gl.blendFunc(gl.ZERO, gl.ONE_MINUS_SRC_COLOR);
  gl.uniform1i(uMode, 2);
  clear.forEach(draw);

  // 4. resolve
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND); gl.depthMask(true);
  gl.useProgram(comp);
  gl.bindVertexArray(emptyVAO);
  [['opaque',cOpaque],['accum',cAccum],['reveal',cReveal]]
    .forEach(([k,u], i) => { gl.activeTexture(gl.TEXTURE0+i);
      gl.bindTexture(gl.TEXTURE_2D, TEX[k]); gl.uniform1i(u, i); });
  gl.uniform3fv(cSkyA, css('--sky-a'));
  gl.uniform3fv(cSkyB, css('--sky-b'));
  gl.viewport(0,0,w,h);
  gl.uniform2f(cRes, w, h);
  gl.uniform1i(cSS, SS);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.bindVertexArray(null);
}

/* The plane, in model space, as the shader wants it: normal in xyz and
   offset in w, all zeros when off. The slider is 0..1 across the scene's
   own extent on that axis, padded a hair past each end so the extremes
   really do show the whole part and really do hide it. */
function sectPlane(){
  if (!S.sect) return null;
  const sc = scenes[S.layout];
  const i = {x:0, y:1, z:2}[S.sect];
  const sgn = S.sectFlip ? -1 : 1;
  const nrm = [0,0,0]; nrm[i] = sgn;
  const pad = 0.01 * sc.span[i];
  const at = sc.lo[i] - pad + S.sectT * (sc.span[i] + 2*pad);
  return {n: nrm, d: sgn * at, axis: i, at};
}

/* Two triangles lying on the plane, big enough to cover the scene from
   any angle. Rebuilt per frame because it is six vertices and caching it
   would mean invalidating it on layout, slider and flip. */
function capQuad(pl){
  const sc = scenes[S.layout];
  const r = sc.radius * 1.6;
  const c = sc.centre.slice(); c[pl.axis] = pl.at;
  const u = [0,0,0], v = [0,0,0];
  u[(pl.axis+1)%3] = r; v[(pl.axis+2)%3] = r;
  const pt = (a,b) => [c[0]+a*u[0]+b*v[0], c[1]+a*u[1]+b*v[1],
                       c[2]+a*u[2]+b*v[2]];
  const q = [pt(-1,-1), pt(1,-1), pt(1,1), pt(-1,-1), pt(1,1), pt(-1,1)];
  return new Float32Array(q.flat());
}

/* Supersampling costs real fill, so only pay it when something moved. */
let dirty = true;
const touch = () => { dirty = true; };
function tick(){
  const k = 0.18;
  /* Normalised lerp rather than a slerp: the step is small and the two
     are indistinguishable under 90 degrees, which a preset change is.
     Take the near end of the double cover first, or a preset can spin
     the long way round for no reason. */
  const sgn = dot4(S.q, S.tq) < 0 ? -1 : 1;
  let d0 = Math.abs(S.tDist - S.dist);
  const nq = [0,0,0,0];
  for (let i = 0; i < 4; i++) {
    const t = sgn * S.tq[i];
    nq[i] = S.q[i] + (t - S.q[i]) * k;
    d0 += Math.abs(t - S.q[i]);
  }
  S.q = qnorm(nq);
  for (let i = 0; i < 3; i++) {
    d0 += Math.abs(S.tPan[i] - S.pan[i]);
    S.pan[i] += (S.tPan[i] - S.pan[i]) * k;
  }
  S.dist += (S.tDist-S.dist)*k;
  if (dirty || d0 > 1e-4){ render(); dirty = d0 > 1e-4; }
  requestAnimationFrame(tick);
}
if (gl && HAS_FLOAT) tick();
else if (gl) document.querySelector('.stage').innerHTML =
  '<p style="padding:2rem;color:var(--dim)">This browser cannot render to '
  + 'float buffers, which the transparency needs.</p>';
addEventListener('resize', () => { fit(); touch(); });

/* ---------- input ---------- */
let drag = null;
cv.addEventListener('pointerdown', e => {
  drag = {x:e.clientX, y:e.clientY, pan: e.button === 2 || e.shiftKey};
  cv.setPointerCapture(e.pointerId);
});
/* Right-drag is pan, so the menu it would otherwise open has to go. */
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('pointermove', e => {
  if (!drag) return;
  const px = e.clientX - drag.x, py = e.clientY - drag.y;
  if (drag.pan) {
    /* One pixel of drag moves the model one pixel, whatever the zoom:
       the viewport spans 2*d*tan(FOV/2) of world across its height, so
       that over the pixel height is the scale. Along the camera's own
       right and up, which is what makes it feel like sliding the part
       rather than steering the camera. */
    const [rx, uy] = qBasis(S.tq);
    const k = 2 * S.dist * Math.tan(FOV/2) / Math.max(cv.clientHeight, 1);
    for (let i = 0; i < 3; i++)
      S.tPan[i] -= rx[i]*px*k - uy[i]*py*k;
  } else {
    /* About the camera's own axes, so the grab feels the same whichever
       way up the model already is -- and so there is no attitude at which
       one of the two drags stops doing anything.
    
       The increment goes on the *right* of the product, and that is not a
       stylistic choice. `qBasis` hands back the rows of the world-to-
       camera rotation, which is its transpose, so composing on the left
       applies the increment in world space instead: shipped that way, a
       horizontal drag from the front view turned the model about its long
       axis rather than about the one it stands on. Measured, not
       reasoned: the old camera turned about world [0,0,1] and this now
       does too, where `qmul(incr, q)` gave [0,-1,0]. */
    S.tq = qnorm(qmul(S.tq, qmul(qAxis([0,1,0], -px*0.008),
                                 qAxis([1,0,0], -py*0.008))));
  }
  drag = {x:e.clientX, y:e.clientY, pan: drag.pan};
});
addEventListener('pointerup', () => drag = null);
cv.addEventListener('wheel', e => {
  e.preventDefault();
  S.tDist = Math.max(scenes[S.layout].radius*1.1,
            Math.min(scenes[S.layout].radius*6, S.tDist * (1 + e.deltaY*0.0012)));
}, {passive:false});
cv.addEventListener('dblclick', () => setView('iso'));

const VIEWS = {
  iso:   [-0.72, 0.42],
  top:   [-Math.PI/2, EL_MAX],
  front: [-Math.PI/2, 0],
  left:  [Math.PI, 0],
};
function setView(k){
  S.tq = qFromAzEl(...VIEWS[k]);
  S.tPan = [0,0,0];   /* a named view is a view of the whole thing */
  fit();
}

/* ---------- rail ---------- */
const partsEl = document.getElementById('parts');
function buildParts(){
  const sc = scenes[S.layout];
  const seen = [];
  sc.parts.forEach(p => { if (!p.env && !seen.some(s => s.grp === p.grp))
    seen.push(p); });
  /* Top of the stack first, the order you take it apart in. */
  seen.sort((a, b) => b.lift - a.lift);
  partsEl.innerHTML = '';
  seen.forEach(p => {
    const [name, note] = LABELS[p.grp] || [p.grp, ''];
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.setAttribute('aria-pressed', String(!S.hidden.has(p.grp)));
    b.innerHTML = `<span class="sw" style="background:${p.color}"></span>
      <span class="pn">${name}<small>${note}</small></span>`;
    b.onclick = () => {
      S.hidden.has(p.grp) ? S.hidden.delete(p.grp) : S.hidden.add(p.grp);
      b.setAttribute('aria-pressed', String(!S.hidden.has(p.grp)));
      touch();
    };
    li.appendChild(b); partsEl.appendChild(li);
  });
}
function buildDims(){
  const sc = scenes[S.layout];
  const [w,d,h] = sc.case;
  document.getElementById('dims').innerHTML = [
    ['Width', w], ['Depth', d], ['Case height', h],
    ['To keycap top', sc.keycapTop],
  ].map(([k,v]) => `<div><span>${k}</span><span>${v.toFixed(2)} mm</span></div>`)
   .join('');
  document.getElementById('stampSize').textContent =
    `${w.toFixed(1)} × ${d.toFixed(1)} × ${h.toFixed(1)} mm`;
  document.getElementById('stampName').textContent = sc.layout;
}
document.getElementById('keys').innerHTML = STATUS.map(([n,c]) =>
  `<div><span class="sw" style="background:${c}"></span>${n}</div>`).join('');

document.getElementById('layout').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  S.layout = b.dataset.v;
  [...e.currentTarget.children].forEach(x =>
    x.setAttribute('aria-pressed', String(x === b)));
  fit(); buildParts(); buildDims(); touch();
});
document.getElementById('explode').addEventListener('input', e => {
  S.explode = e.target.value / 100; touch();
});
document.getElementById('sect').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  S.sect = b.dataset.v;
  [...e.currentTarget.children].forEach(x =>
    x.setAttribute('aria-pressed', String(x === b)));
  touch();
});
document.getElementById('sectAt').addEventListener('input', e => {
  S.sectT = e.target.value / 1000; touch();
});
document.getElementById('sectflip').addEventListener('click', e => {
  S.sectFlip = !S.sectFlip;
  e.currentTarget.setAttribute('aria-pressed', String(S.sectFlip));
  touch();
});
document.getElementById('proj').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  S.ortho = b.dataset.v === 'ortho'; touch();
  [...e.currentTarget.children].forEach(x =>
    x.setAttribute('aria-pressed', String(x === b)));
});
document.getElementById('preset').addEventListener('click', e => {
  const b = e.target.closest('button'); if (b) setView(b.dataset.v);
});
document.getElementById('shellmode').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  S.shellMode = b.dataset.v; touch();
  [...e.currentTarget.children].forEach(x =>
    x.setAttribute('aria-pressed', String(x === b)));
});
document.getElementById('env').addEventListener('click', e => {
  S.env = !S.env; touch();
  e.currentTarget.setAttribute('aria-pressed', String(S.env));
});
buildParts(); buildDims();
</script>
"""


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "dump"
    {"dump": dump, "page": page}[mode]()
