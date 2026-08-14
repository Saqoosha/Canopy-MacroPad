"""A real 3D viewer, because the flat renders lie about depth.

    .venv/bin/python webgl.py dump
    .venv/bin/python webgl.py page                    # -> out/viewer.html

`product.py` sorts triangles by distance and paints them back to front.
That is the only depth test matplotlib offers, and it is wrong wherever
two surfaces interpenetrate or one is concave -- which describes most of
this case. A GPU depth buffer resolves it per pixel and the artefacts go
away entirely.

Geometry rides in the page as int16, quantised over the bounding box:
about 0.002 mm a step over 130 mm, which is far finer than anything
printed here, and a quarter the size of float32.
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
    board_slab = product.board(
        P.BOARD_W + e, P.BOARD_D + e, P.BOARD_CORNER_R,
        P.BOARD_CENTER[0], P.BOARD_CENTER[1],
        P.Z_BOARD_BOTTOM - e, P.BOARD_T + 2 * e)
    boards = {
        "board + sockets + USB": board_slab,
        # The switch bodies start exactly on the board's top face, so they
        # need the same slab taken out of them for the same reason.
        "switch bodies": board_slab,
    }
    return {k: (v - boards[k]) for k, v in mock.everything().items()}


def dump():
    """Tessellate the scene and write it next to its STLs."""
    parts = []
    blobs = []
    # The viewer's boards are bare slabs; these are the envelopes the
    # interference check actually runs against. Shipping both means the
    # thing on screen can be compared with the thing that was verified,
    # instead of being taken on faith.
    lift_of = {"board + sockets + USB": 20.0, "switch bodies": 46.0}
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
        "layout": P.OUT_NAME,
        "case": [P.CASE_W, P.CASE_D, P.CASE_H],
        "keycapTop": float(allv[:, 2].max()),
        "lo": lo.tolist(),
        "span": span.tolist(),
        "parts": parts,
        "data": base64.b64encode(data).decode(),
    }
    path = OUT / P.OUT_NAME / "geom.json"
    path.write_text(json.dumps(payload))
    print(f"  {path}  {len(data) / 1024:.0f} KB of int16, "
          f"{sum(p['count'] for p in parts) // 3} triangles")


# The part list is also the legend, so the labels have to say what a
# person would call the thing, not what the mesh is named.
LABELS = {
    "shell": ("Shell", "printed"),
    "bottom": ("Bottom plate", "printed"),
    "board": ("PCB", "custom, 6\u00d7 Choc v2"),
    "sw": ("Switches", "Kailh Choc v2"),
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
    f = OUT / P.OUT_NAME / "geom.json"
    if not f.exists():
        sys.exit(f"missing {f} -- run `dump` first")
    geoms[P.OUT_NAME] = json.loads(f.read_text())

    html = TEMPLATE.replace("__DATA__", json.dumps(geoms))
    html = html.replace("__LABELS__", json.dumps(LABELS))
    html = html.replace("__STATUS__", json.dumps(STATUS))
    path = OUT / "viewer.html"
    path.write_text(html)
    print(f"  {path}  {path.stat().st_size / 1024:.0f} KB")


TEMPLATE = r"""<title>Canopy MacroPad — case viewer</title>
<style>
/* Light is the base set; the two blocks below only re-point tokens, so
   nothing is defined solely behind a media query or a theme stamp. */
:root {
  --bg:#e9ecf1; --panel:#ffffff; --line:#d3d9e2;
  --ink:#111721; --dim:#5f6a7a; --faint:#8b95a4;
  --accent:#0b3fd6; --accent-ink:#ffffff;
  --grid:rgba(17,23,33,.055);
  --sky-a:#dfe4ec; --sky-b:#f3f5f8;
  color-scheme:light dark;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#0d1015; --panel:#161b23; --line:#262e3a;
    --ink:#e6ecf5; --dim:#98a3b3; --faint:#6c7787;
    --accent:#6f95ff; --accent-ink:#0d1015;
    --grid:rgba(230,236,245,.06);
    --sky-a:#0a0d12; --sky-b:#161b23;
  }
}
:root[data-theme="dark"]{
  --bg:#0d1015; --panel:#161b23; --line:#262e3a;
  --ink:#e6ecf5; --dim:#98a3b3; --faint:#6c7787;
  --accent:#6f95ff; --accent-ink:#0d1015;
  --grid:rgba(230,236,245,.06);
  --sky-a:#0a0d12; --sky-b:#161b23;
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
.head{padding:20px 18px 14px; border-bottom:1px solid var(--line)}
.head h1{margin:0; font-size:15px; font-weight:600; letter-spacing:-.01em}
.head p{margin:5px 0 0; color:var(--dim); font-size:12px}
.grp{padding:16px 18px; border-bottom:1px solid var(--line)}
.lbl{margin:0 0 10px; font-size:10.5px; letter-spacing:.11em;
  text-transform:uppercase; color:var(--faint)}

.seg{display:grid; grid-template-columns:1fr 1fr; gap:6px}
.seg3{grid-template-columns:repeat(3,1fr)}
.seg4{grid-template-columns:repeat(4,1fr)}
.seg4 button{padding:7px 2px; font-size:12px}
.seg button{appearance:none; border:1px solid var(--line); background:transparent;
  color:var(--dim); border-radius:7px; padding:8px 6px; font:inherit;
  font-size:12.5px; cursor:pointer; transition:background .12s,color .12s}
.seg button:hover{color:var(--ink)}
.seg button[aria-pressed="true"]{background:var(--accent); color:var(--accent-ink);
  border-color:var(--accent)}
button:focus-visible,input:focus-visible{outline:2px solid var(--accent);
  outline-offset:2px}

.row{display:flex; align-items:center; justify-content:space-between; gap:10px}
input[type=range]{width:100%; accent-color:var(--accent)}

.parts{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:1px}
.parts button{display:flex; align-items:center; gap:10px; width:100%;
  appearance:none; background:transparent; border:0; padding:7px 6px;
  border-radius:6px; font:inherit; color:inherit; cursor:pointer; text-align:left}
.parts button:hover{background:var(--grid)}
.parts button[aria-pressed="false"]{opacity:.38}
.sw{width:11px; height:11px; border-radius:3px; flex:none;
  border:1px solid rgba(128,128,128,.45)}
.pn{flex:1; min-width:0; font-size:13px}
.pn small{display:block; color:var(--faint); font-size:11px}
.hint{margin:10px 0 0; color:var(--faint); font-size:11px; line-height:1.5}
.hint code{font-family:ui-monospace,"SF Mono",Menlo,monospace; font-size:10.5px}

.keys{display:flex; flex-direction:column; gap:6px}
.keys div{display:flex; align-items:center; gap:9px; font-size:12px;
  color:var(--dim)}
.dims{display:flex; flex-direction:column; gap:6px; font-size:12.5px}
.dims div{display:flex; justify-content:space-between; gap:10px}
.dims span:first-child{color:var(--dim)}
.note{padding:14px 18px 20px; color:var(--faint); font-size:11.5px;
  line-height:1.55}
@media (prefers-reduced-motion:reduce){ *{transition:none!important} }
</style>

<div class="app">
  <aside class="rail">
    <div class="head">
      <h1>Canopy MacroPad</h1>
      <p>Printed case</p>
    </div>

    <div class="grp">
      <p class="lbl">View</p>
      <div class="seg" id="proj">
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
      <p class="lbl">Explode</p>
      <input type="range" id="explode" min="0" max="100" value="0"
             aria-label="Explode the assembly">
    </div>

    <div class="grp">
      <p class="lbl">Case</p>
      <div class="seg seg3" id="shellmode">
        <button data-v="solid" aria-pressed="true">Solid</button>
        <button data-v="ghost" aria-pressed="false">Glass</button>
        <button data-v="hidden" aria-pressed="false">Off</button>
      </div>
      <p class="hint">Glass reads the inside with the lid shut — which is
        the state it is actually assembled in.</p>
    </div>

    <div class="grp">
      <p class="lbl">Parts</p>
      <ul class="parts" id="parts"></ul>
    </div>

    <div class="grp">
      <p class="lbl">What the checks see</p>
      <div class="seg" id="envseg" style="grid-template-columns:1fr">
        <button id="env" aria-pressed="false">Clearance envelopes</button>
      </div>
      <p class="hint">The boards above are drawn as bare slabs. These are
        the volumes <code>build.py</code> actually booleans the case
        against — sockets, connectors with a plug mated, buttons, the USB
        shell and its overhang.</p>
    </div>

    <div class="grp">
      <p class="lbl">Key colour = pane state</p>
      <div class="keys" id="keys"></div>
    </div>

    <div class="grp">
      <p class="lbl">Dimensions</p>
      <div class="dims mono" id="dims"></div>
    </div>

    <p class="note">Drag to orbit, scroll to zoom, double-click to reset.
      Depth is resolved per pixel here, so the transparent keycaps and the
      case interior sort correctly — which the flat renders could not do.</p>
  </aside>

  <div class="stage">
    <canvas id="gl"></canvas>
    <div class="stamp"><b id="stampSize">—</b><span id="stampName">—</span></div>
    <div class="hud"><span>drag · orbit</span><span>scroll · zoom</span></div>
  </div>
</div>

<script>
const GEOM = __DATA__, LABELS = __LABELS__, STATUS = __STATUS__;

/* ---------- gl ---------- */
const cv = document.getElementById('gl');
const gl = cv.getContext('webgl2', {antialias:true, alpha:false});
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
/* Just shy of straight down: at exactly 90 the up vector and the view
   direction are parallel and the view matrix collapses. */
const EL_MAX = 1.5697;

/* Weighted-blended OIT (McGuire & Bavoil). Sorting transparent objects
   back to front cannot be right here: a keycap's skirt and the switch
   housing inside it interpenetrate, so no ordering of the two is correct
   from every angle. This weights each fragment by depth and coverage and
   resolves them in one composite, with no ordering at all. */
const VS = `#version 300 es
layout(location=0) in vec3 p;
uniform mat4 uMVP, uMV; uniform vec3 uLift; out vec3 vP;
void main(){ vec3 q = p + uLift; vP = (uMV * vec4(q,1.0)).xyz;
  gl_Position = uMVP * vec4(q,1.0); }`;

const FS = `#version 300 es
precision highp float; in vec3 vP;
layout(location=0) out vec4 oOpaque;
layout(location=1) out vec4 oAccum;
layout(location=2) out vec4 oReveal;
uniform vec3 uColor; uniform float uAlpha; uniform int uMode;
uniform vec2 uDepth;  // near, far
vec3 shade(){
  /* Flat normal from screen-space derivatives: the mesh ships without
     normals, and faceted is the honest look for tessellated CAD. */
  vec3 n = normalize(cross(dFdx(vP), dFdy(vP)));
  vec3 L = normalize(vec3(0.35,0.45,0.82));
  float rim = pow(1.0 - abs(normalize(-vP).z), 2.0);
  return uColor * (0.34 + 0.66*abs(dot(n,L))) + rim*0.16;
}
void main(){
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

const prog = link(VS, FS), comp = link(CVS, CFS);
const U = (pr,n) => gl.getUniformLocation(pr, n);
const uMVP=U(prog,'uMVP'), uMV=U(prog,'uMV'), uColor=U(prog,'uColor'),
      uAlpha=U(prog,'uAlpha'), uLift=U(prog,'uLift'), uMode=U(prog,'uMode'),
      uDepth=U(prog,'uDepth');
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
  gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
  TEX.depth = db; TEX.depth.rb = true;
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
    gl.TEXTURE_2D, TEX.opaque, 0);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1,
    gl.TEXTURE_2D, TEX.accum, 0);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT2,
    gl.TEXTURE_2D, TEX.reveal, 0);
  gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT,
    gl.RENDERBUFFER, db);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
}

/* ---------- scenes ---------- */
function hex(h){ return [parseInt(h.slice(1,3),16)/255,
  parseInt(h.slice(3,5),16)/255, parseInt(h.slice(5,7),16)/255]; }
function group(name){
  const m = name.match(/^(shell|bottom|board|sw|cap|led)/);
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
const S = {layout:Object.keys(GEOM)[0], explode:0, env:false, shellMode:'solid',
           ortho:false, hidden:new Set(),
           az:-0.72, el:0.42, dist:1, tAz:-0.72, tEl:0.42, tDist:1};
/* Frame on the widest axis and the viewport's aspect, not on a constant:
   a 120 mm bar and a 98 mm one need different pull-backs. */
/* Project the bounding box onto the screen axes for the direction we are
   actually heading to. Framing on the widest axis regardless of direction
   is right from the front and leaves the end view a postage stamp. */
function fit(){
  const sc = scenes[S.layout], sp = sc.span;
  const asp = Math.max(cv.clientWidth / Math.max(cv.clientHeight, 1), 0.35);
  const a = S.tAz, e = S.tEl;
  const right = [-Math.sin(a), Math.cos(a), 0];
  const up = [-Math.sin(e)*Math.cos(a), -Math.sin(e)*Math.sin(a), Math.cos(e)];
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
function lookAt(e,c,u){
  const z=norm(sub(e,c)), x=norm(cross(u,z)), y=cross(z,x);
  return new Float32Array([x[0],y[0],z[0],0, x[1],y[1],z[1],0,
    x[2],y[2],z[2],0, -dot(x,e),-dot(y,e),-dot(z,e),1]);}
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm=a=>{const l=Math.hypot(...a)||1; return [a[0]/l,a[1]/l,a[2]/l];};

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

  const c = sc.centre, d = S.dist;
  const eye = [c[0] + d*Math.cos(S.el)*Math.cos(S.az),
               c[1] + d*Math.cos(S.el)*Math.sin(S.az),
               c[2] + d*Math.sin(S.el)];
  const V = lookAt(eye, c, [0,0,1]);
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
  live.filter(p => alphaOf(p) >= 1).forEach(draw);

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

/* Supersampling costs real fill, so only pay it when something moved. */
let dirty = true;
const touch = () => { dirty = true; };
function tick(){
  const k = 0.18;
  const d0 = Math.abs(S.tAz-S.az) + Math.abs(S.tEl-S.el)
           + Math.abs(S.tDist-S.dist);
  S.az += (S.tAz-S.az)*k; S.el += (S.tEl-S.el)*k;
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
  drag = {x:e.clientX, y:e.clientY}; cv.setPointerCapture(e.pointerId); });
cv.addEventListener('pointermove', e => {
  if (!drag) return;
  S.tAz -= (e.clientX-drag.x)*0.008;
  S.tEl = Math.max(-EL_MAX, Math.min(EL_MAX, S.tEl + (e.clientY-drag.y)*0.006));
  drag = {x:e.clientX, y:e.clientY};
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
function setView(k){ [S.tAz, S.tEl] = VIEWS[k]; fit(); }

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

document.getElementById('explode').addEventListener('input', e => {
  S.explode = e.target.value / 100; touch();
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
