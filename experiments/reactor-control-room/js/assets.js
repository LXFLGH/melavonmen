/* ============================================================
   assets.js — procedural textures, 1970s industrial palette
   References pulled before modelling:
   · Nixie (IN-18 class): deep red-orange wire numerals on black,
     nickel base, dark red acrylic window.
   · Solari split-flap: near-black flaps, warm off-white grotesque
     characters, hard horizontal seam.
   · HP 5082-7000 (1969): 5x7 GaAsP dot matrix, 655 nm red,
     dim unlit dots in a dark red epoxy window.
   ============================================================ */
(function () {
  var RC = window.RC || (window.RC = {});

  /* ---------- seeded random ---------- */
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  RC.rng = mulberry32(19740426);
  RC.rnd = function (a, b) { if (b === undefined) { b = a; a = 0; } return a + (b - a) * RC.rng(); };
  RC.rndi = function (a, b) { return Math.floor(RC.rnd(a, b + 1)); };
  RC.pick = function (arr) { return arr[Math.floor(RC.rng() * arr.length)]; };

  function cv(w, h) { var c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  RC.cv = cv;

  function tex(canvas, rx, ry, srgb) {
    var t = new THREE.CanvasTexture(canvas);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    if (rx || ry) t.repeat.set(rx || 1, ry || 1);
    if (srgb !== false) t.encoding = THREE.sRGBEncoding;
    t.anisotropy = 8;
    return t;
  }
  RC.texFrom = tex;

  var FONT = '"Bahnschrift SemiCondensed", "Bahnschrift", "Arial Narrow", Arial, sans-serif';
  var MONO = '"Consolas", "Lucida Console", monospace';
  RC.FONT = FONT; RC.MONO = MONO;

  var T = RC.tex = {};

  /* ============================================================
     CONCRETE — poured panels, form-tie holes, drip stains
     ============================================================ */
  T.concrete = (function () {
    var S = 1024, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#77796d'; x.fillRect(0, 0, S, S);

    for (var i = 0; i < 190; i++) {
      var px = RC.rnd(0, S), py = RC.rnd(0, S), r = RC.rnd(25, 260);
      var g = x.createRadialGradient(px, py, 0, px, py, r);
      var bright = RC.rng() > 0.52, a = RC.rnd(0.02, 0.075);
      g.addColorStop(0, bright ? 'rgba(214,214,196,' + a + ')' : 'rgba(26,28,22,' + (a * 1.5) + ')');
      g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.beginPath(); x.arc(px, py, r, 0, 6.283); x.fill();
    }
    // fine aggregate
    for (i = 0; i < 5200; i++) {
      x.fillStyle = RC.rng() > 0.5 ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,240,0.05)';
      x.fillRect(RC.rnd(0, S), RC.rnd(0, S), RC.rnd(1, 2.4), RC.rnd(1, 2.4));
    }
    // panel seams (texture = one 4m x 3m pour)
    x.strokeStyle = 'rgba(20,22,18,0.35)'; x.lineWidth = 3;
    x.strokeRect(1.5, 1.5, S - 3, S - 3);
    x.strokeStyle = 'rgba(255,255,235,0.06)'; x.lineWidth = 1;
    x.strokeRect(4.5, 4.5, S - 9, S - 9);
    // form tie holes
    for (var gy = 0; gy < 4; gy++) for (var gx = 0; gx < 4; gx++) {
      var tx = 150 + gx * 240, ty = 140 + gy * 250;
      x.fillStyle = 'rgba(18,19,15,0.55)'; x.beginPath(); x.arc(tx, ty, 5.5, 0, 6.283); x.fill();
      x.strokeStyle = 'rgba(210,210,190,0.10)'; x.lineWidth = 2;
      x.beginPath(); x.arc(tx, ty, 8, 0, 6.283); x.stroke();
    }
    // water drips
    for (i = 0; i < 46; i++) {
      var dx = RC.rnd(0, S), dy = RC.rnd(0, S * 0.6), len = RC.rnd(60, 420), w = RC.rnd(2, 13);
      var lg = x.createLinearGradient(dx, dy, dx, dy + len);
      lg.addColorStop(0, 'rgba(30,28,20,0.13)');
      lg.addColorStop(1, 'rgba(30,28,20,0)');
      x.fillStyle = lg; x.fillRect(dx, dy, w, len);
    }
    // hairline cracks
    x.strokeStyle = 'rgba(22,22,18,0.30)'; x.lineWidth = 1.4;
    for (i = 0; i < 7; i++) {
      var cx = RC.rnd(0, S), cy = RC.rnd(0, S); x.beginPath(); x.moveTo(cx, cy);
      for (var k = 0; k < 14; k++) { cx += RC.rnd(-26, 26); cy += RC.rnd(6, 30); x.lineTo(cx, cy); }
      x.stroke();
    }
    return tex(c, 1, 1);
  })();

  /* ============================================================
     PAINTED STEEL PANEL — cabinet skins / walls wainscot
     ============================================================ */
  function steelPanel(base, opts) {
    opts = opts || {};
    var S = 512, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = base; x.fillRect(0, 0, S, S);
    // vertical brush
    for (var i = 0; i < 260; i++) {
      x.strokeStyle = RC.rng() > 0.5 ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.045)';
      x.lineWidth = RC.rnd(0.6, 2.2);
      var px = RC.rnd(0, S);
      x.beginPath(); x.moveTo(px, 0); x.lineTo(px + RC.rnd(-2, 2), S); x.stroke();
    }
    // grime blobs
    for (i = 0; i < 40; i++) {
      var bx = RC.rnd(0, S), by = RC.rnd(0, S), br = RC.rnd(20, 120);
      var g = x.createRadialGradient(bx, by, 0, bx, by, br);
      g.addColorStop(0, 'rgba(24,22,16,' + RC.rnd(0.02, 0.09) + ')'); g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.beginPath(); x.arc(bx, by, br, 0, 6.283); x.fill();
    }
    // scratches
    for (i = 0; i < 26; i++) {
      x.strokeStyle = 'rgba(230,230,210,' + RC.rnd(0.04, 0.13) + ')'; x.lineWidth = RC.rnd(0.5, 1.2);
      var sx = RC.rnd(0, S), sy = RC.rnd(0, S);
      x.beginPath(); x.moveTo(sx, sy); x.lineTo(sx + RC.rnd(-70, 70), sy + RC.rnd(-16, 16)); x.stroke();
    }
    if (opts.rivets) {
      for (var ry = 18; ry < S; ry += S - 36) for (var rx = 18; rx < S; rx += S - 36) {
        x.fillStyle = 'rgba(0,0,0,0.32)'; x.beginPath(); x.arc(rx, ry + 1.5, 4, 0, 6.283); x.fill();
        x.fillStyle = 'rgba(225,225,205,0.20)'; x.beginPath(); x.arc(rx, ry, 3.4, 0, 6.283); x.fill();
      }
    }
    return tex(c, 1, 1);
  }
  T.cabinet = steelPanel('#8e9280', { rivets: false });
  T.cabinetDark = steelPanel('#4d5347', { rivets: true });
  T.wainscot = steelPanel('#3f4a3f', { rivets: true });

  /* ============================================================
     FLOOR — steel plate, seams, rust, scuffs
     ============================================================ */
  T.floor = (function () {
    var S = 1024, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#5b5f5a'; x.fillRect(0, 0, S, S);
    // plates: 2 x 2
    for (var py = 0; py < 2; py++) for (var px = 0; px < 2; px++) {
      var shade = RC.rnd(-10, 10);
      x.fillStyle = 'rgb(' + (91 + shade) + ',' + (95 + shade) + ',' + (90 + shade) + ')';
      x.fillRect(px * 512 + 3, py * 512 + 3, 506, 506);
      // plate grain
      for (var i = 0; i < 220; i++) {
        x.strokeStyle = RC.rng() > 0.5 ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.05)';
        x.lineWidth = RC.rnd(0.5, 1.6);
        var yy = py * 512 + RC.rnd(4, 508);
        x.beginPath(); x.moveTo(px * 512 + RC.rnd(4, 508), yy); x.lineTo(px * 512 + RC.rnd(4, 508), yy + RC.rnd(-1, 1)); x.stroke();
      }
      // rivets
      for (i = 0; i < 18; i++) {
        var rx = px * 512 + 12 + (i % 6) * 96, ry = py * 512 + 14 + Math.floor(i / 6) * 240;
        x.fillStyle = 'rgba(0,0,0,0.30)'; x.beginPath(); x.arc(rx, ry + 1, 3.2, 0, 6.283); x.fill();
        x.fillStyle = 'rgba(230,230,215,0.16)'; x.beginPath(); x.arc(rx, ry, 2.6, 0, 6.283); x.fill();
      }
    }
    // seam shadow
    x.strokeStyle = 'rgba(12,14,12,0.65)'; x.lineWidth = 5;
    x.strokeRect(2, 2, S - 4, S - 4);
    x.beginPath(); x.moveTo(512, 0); x.lineTo(512, S); x.moveTo(0, 512); x.lineTo(S, 512); x.stroke();
    // rust patches
    for (i = 0; i < 26; i++) {
      var bx = RC.rnd(0, S), by = RC.rnd(0, S), br = RC.rnd(14, 90);
      var g = x.createRadialGradient(bx, by, 0, bx, by, br);
      g.addColorStop(0, 'rgba(96,50,26,' + RC.rnd(0.10, 0.26) + ')');
      g.addColorStop(0.6, 'rgba(72,40,22,0.10)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.beginPath(); x.arc(bx, by, br, 0, 6.283); x.fill();
    }
    // drag scuffs
    for (i = 0; i < 22; i++) {
      x.strokeStyle = 'rgba(210,210,200,' + RC.rnd(0.03, 0.09) + ')'; x.lineWidth = RC.rnd(1, 4);
      var sx = RC.rnd(0, S), sy = RC.rnd(0, S), ang = RC.rnd(0, 6.283), len = RC.rnd(40, 260);
      x.beginPath(); x.moveTo(sx, sy); x.lineTo(sx + Math.cos(ang) * len, sy + Math.sin(ang) * len); x.stroke();
    }
    return tex(c, 6, 5);
  })();

  /* ============================================================
     HAZARD STRIPES
     ============================================================ */
  T.hazard = (function () {
    var S = 256, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#b7902a'; x.fillRect(0, 0, S, S);
    x.save(); x.translate(S / 2, S / 2); x.rotate(-Math.PI / 4); x.translate(-S, -S);
    for (var i = 0; i < 8; i++) { x.fillStyle = i % 2 ? '#1b1a14' : '#c9a432'; x.fillRect(i * 96, 0, 96, S * 3); }
    x.restore();
    for (i = 0; i < 900; i++) {
      x.fillStyle = RC.rng() > 0.5 ? 'rgba(0,0,0,0.16)' : 'rgba(220,220,190,0.07)';
      x.fillRect(RC.rnd(0, S), RC.rnd(0, S), RC.rnd(1, 5), RC.rnd(1, 5));
    }
    return tex(c, 1, 1);
  })();

  /* ============================================================
     NIXIE ATLAS — 10 wire numerals, red-orange neon
     ============================================================ */
  T.nixie = (function () {
    var CW = 160, CH = 320, c = cv(CW * 10, CH), x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, c.width, c.height);
    for (var d = 0; d <= 9; d++) {
      var ox = d * CW + CW / 2, oy = CH / 2;
      x.save();
      x.textAlign = 'center'; x.textBaseline = 'middle';
      x.font = '700 224px ' + FONT;
      // outer bloom
      x.shadowColor = 'rgba(255,58,10,0.95)'; x.shadowBlur = 46;
      x.strokeStyle = 'rgba(255,46,8,0.55)'; x.lineWidth = 12;
      x.strokeText(String(d), ox, oy + 6);
      x.strokeText(String(d), ox, oy + 6);
      // wire core
      x.shadowBlur = 18; x.shadowColor = 'rgba(255,140,60,0.9)';
      x.strokeStyle = 'rgba(255,150,70,0.95)'; x.lineWidth = 4.5;
      x.strokeText(String(d), ox, oy + 6);
      // hot filament
      x.shadowBlur = 4; x.strokeStyle = 'rgba(255,236,200,0.95)'; x.lineWidth = 1.6;
      x.strokeText(String(d), ox, oy + 6);
      x.restore();
    }
    return tex(c, 1, 1);
  })();
  T.nixie.encoding = THREE.sRGBEncoding;

  /* ============================================================
     SPLIT-FLAP ATLAS — 8x8 cells, cream on black
     ============================================================ */
  var FLAP_CHARS = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-/:+%*<>=';
  T.flapChars = FLAP_CHARS;
  T.flap = (function () {
    var CW = 128, CH = 168, cols = 8, rows = 8;
    var c = cv(CW * cols, CH * rows), x = c.getContext('2d');
    x.fillStyle = '#0a0a0b'; x.fillRect(0, 0, c.width, c.height);
    for (var i = 0; i < FLAP_CHARS.length; i++) {
      var col = i % cols, row = Math.floor(i / cols);
      var ox = col * CW, oy = row * CH;
      // flap face
      var g = x.createLinearGradient(ox, oy, ox, oy + CH);
      g.addColorStop(0, '#1d1d1f'); g.addColorStop(0.5, '#141416');
      g.addColorStop(0.51, '#1a1a1c'); g.addColorStop(1, '#0e0e10');
      x.fillStyle = g; x.fillRect(ox + 2, oy + 2, CW - 4, CH - 4);
      // seam
      x.fillStyle = 'rgba(0,0,0,0.85)'; x.fillRect(ox + 2, oy + CH / 2 - 1, CW - 4, 2);
      x.fillStyle = 'rgba(255,255,255,0.05)'; x.fillRect(ox + 2, oy + CH / 2 + 1, CW - 4, 1);
      // char
      x.save();
      x.textAlign = 'center'; x.textBaseline = 'middle';
      x.font = '600 104px ' + FONT;
      x.fillStyle = '#e6dfc6';
      x.fillText(FLAP_CHARS[i], ox + CW / 2, oy + CH / 2 + 6);
      x.fillStyle = 'rgba(120,110,80,0.15)';
      x.fillText(FLAP_CHARS[i], ox + CW / 2 + 1, oy + CH / 2 + 7);
      x.restore();
      // edge wear
      for (var k = 0; k < 14; k++) {
        x.fillStyle = 'rgba(0,0,0,0.35)';
        x.fillRect(ox + RC.rnd(4, CW - 6), oy + RC.rnd(4, CH - 6), RC.rnd(1, 3), 1);
      }
    }
    return tex(c, 1, 1);
  })();
  T.flapCols = 8; T.flapRows = 8; T.flapCW = 128; T.flapCH = 168;
  T.flapIndex = function (ch) { var i = FLAP_CHARS.indexOf(ch); return i < 0 ? 0 : i; };

  /* ============================================================
     DIAL FACES
     ============================================================ */
  T.dial = function (o) {
    o = o || {};
    var S = 512, c = cv(S, S), x = c.getContext('2d');
    var cx = S / 2, cy = S * 0.56, R = S * 0.40;
    x.fillStyle = o.paper || '#cec5a6'; x.fillRect(0, 0, S, S);
    // aged paper
    for (var i = 0; i < 70; i++) {
      var g = x.createRadialGradient(RC.rnd(0, S), RC.rnd(0, S), 0, RC.rnd(0, S), RC.rnd(0, S), RC.rnd(20, 150));
      g.addColorStop(0, 'rgba(120,100,60,0.05)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      x.fillStyle = g; x.fillRect(0, 0, S, S);
    }
    var a0 = Math.PI * 0.75, a1 = Math.PI * 2.25;
    // arc scale
    x.strokeStyle = '#22201a'; x.lineWidth = 3;
    x.beginPath(); x.arc(cx, cy, R, a0, a1); x.stroke();
    // red zone
    var rz = o.redFrom === undefined ? 0.82 : o.redFrom;
    x.strokeStyle = '#8d1b12'; x.lineWidth = 13;
    x.beginPath(); x.arc(cx, cy, R - 4, a0 + rz * (a1 - a0), a1); x.stroke();
    // ticks
    for (i = 0; i <= 50; i++) {
      var t = i / 50, a = a0 + t * (a1 - a0);
      var major = i % 5 === 0;
      var r1 = R - (major ? 26 : 16), r2 = R - 4;
      x.strokeStyle = '#25231c'; x.lineWidth = major ? 3.2 : 1.6;
      x.beginPath();
      x.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
      x.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
      x.stroke();
      if (major) {
        var label = o.ticks ? o.ticks[i / 5] : String((o.max === undefined ? 100 : o.max) * t);
        x.save();
        x.translate(cx + Math.cos(a) * (R - 52), cy + Math.sin(a) * (R - 52));
        x.rotate(a + Math.PI / 2);
        x.fillStyle = '#25231c'; x.textAlign = 'center'; x.textBaseline = 'middle';
        x.font = '600 26px ' + FONT;
        x.fillText(label, 0, 0);
        x.restore();
      }
    }
    // text
    x.fillStyle = '#2a2820'; x.textAlign = 'center';
    x.font = '600 30px ' + FONT;
    x.fillText(o.label || 'MEGAWATTS', cx, cy - 8);
    x.font = '500 22px ' + FONT;
    x.fillStyle = '#4a4535';
    x.fillText(o.unit || 'PERCENT OF RATED', cx, cy + 26);
    x.font = '500 15px ' + MONO;
    x.fillStyle = '#5b5540';
    x.fillText(o.sub || 'CLASS 1.5  ·  GE', cx, cy + 100);
    // glass dust
    for (i = 0; i < 40; i++) {
      x.fillStyle = 'rgba(60,55,40,0.12)';
      x.fillRect(RC.rnd(20, S - 20), RC.rnd(20, S - 20), 1.5, 1.5);
    }
    return tex(c, 1, 1);
  };

  /* ============================================================
     ENGRAVED LABEL PLATES
     ============================================================ */
  T.label = function (main, sub, o) {
    o = o || {};
    var W = o.w || 512, H = o.h || 128, c = cv(W, H), x = c.getContext('2d');
    x.fillStyle = o.bg || '#111110'; x.fillRect(0, 0, W, H);
    x.strokeStyle = o.edge || 'rgba(214,206,180,0.28)'; x.lineWidth = 3;
    x.strokeRect(5, 5, W - 10, H - 10);
    // roughness
    for (var i = 0; i < 260; i++) {
      x.fillStyle = RC.rng() > 0.5 ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.18)';
      x.fillRect(RC.rnd(0, W), RC.rnd(0, H), RC.rnd(1, 3), RC.rnd(1, 2));
    }
    x.textAlign = 'center';
    x.fillStyle = o.fg || '#ded6ba';
    x.font = '600 ' + (o.mainSize || 54) + 'px ' + FONT;
    x.fillText(main, W / 2, sub ? H * 0.46 : H * 0.64);
    if (sub) {
      x.font = '500 ' + (o.subSize || 26) + 'px ' + FONT;
      x.fillStyle = o.subFg || 'rgba(214,206,180,0.62)';
      x.fillText(sub, W / 2, H * 0.76);
    }
    return tex(c, 1, 1);
  };

  /* stencil lettering, transparent bg (wall paint) */
  T.stencil = function (text, o) {
    o = o || {};
    var W = o.w || 1024, H = o.h || 256, c = cv(W, H), x = c.getContext('2d');
    x.clearRect(0, 0, W, H);
    x.textAlign = 'center'; x.textBaseline = 'middle';
    x.font = '700 ' + (o.size || 150) + 'px ' + FONT;
    x.fillStyle = o.color || 'rgba(206,198,168,0.72)';
    if (o.spacing) {
      // manual letterspacing
      var chars = text.split(''), widths = [], total = 0, i;
      for (i = 0; i < chars.length; i++) { widths[i] = x.measureText(chars[i]).width; total += widths[i]; }
      total += o.spacing * (chars.length - 1);
      var cx0 = W / 2 - total / 2;
      for (i = 0; i < chars.length; i++) {
        x.textAlign = 'left';
        x.fillText(chars[i], cx0, H / 2);
        cx0 += widths[i] + o.spacing;
      }
    } else x.fillText(text, W / 2, H / 2);
    // chipped paint
    x.globalCompositeOperation = 'destination-out';
    for (var k = 0; k < 160; k++) {
      x.fillStyle = 'rgba(0,0,0,' + RC.rnd(0.25, 0.85) + ')';
      x.beginPath(); x.arc(RC.rnd(0, W), RC.rnd(0, H), RC.rnd(0.6, 3.4), 0, 6.283); x.fill();
    }
    x.globalCompositeOperation = 'source-over';
    return tex(c, 1, 1);
  };

  /* ============================================================
     MIMIC DIAGRAM (backlit synoptic board)
     ============================================================ */
  T.mimic = (function () {
    var W = 2048, H = 1100, c = cv(W, H), x = c.getContext('2d');
    var nodes = [];
    x.fillStyle = '#20241c'; x.fillRect(0, 0, W, H);
    // grid
    x.strokeStyle = 'rgba(180,180,140,0.06)'; x.lineWidth = 1;
    for (var gx = 0; gx < W; gx += 64) { x.beginPath(); x.moveTo(gx, 0); x.lineTo(gx, H); x.stroke(); }
    for (var gy = 0; gy < H; gy += 64) { x.beginPath(); x.moveTo(0, gy); x.lineTo(W, gy); x.stroke(); }

    function line(pts, w, col) {
      x.strokeStyle = col || 'rgba(201,193,160,0.75)'; x.lineWidth = w || 5; x.lineJoin = 'round'; x.lineCap = 'round';
      x.beginPath(); x.moveTo(pts[0][0], pts[0][1]);
      for (var i = 1; i < pts.length; i++) x.lineTo(pts[i][0], pts[i][1]);
      x.stroke();
    }
    function txt(t, px, py, size, col, align) {
      x.fillStyle = col || 'rgba(214,206,180,0.85)';
      x.font = '600 ' + (size || 28) + 'px ' + FONT;
      x.textAlign = align || 'center'; x.textBaseline = 'middle';
      x.fillText(t, px, py);
    }
    // ---- primary loop: core (left) -> SGs -> turbine (right)
    // core
    x.strokeStyle = 'rgba(205,196,160,0.9)'; x.lineWidth = 6;
    x.strokeRect(300, 300, 260, 420);
    x.strokeStyle = 'rgba(150,145,120,0.5)'; x.lineWidth = 2;
    for (var ci = 0; ci < 12; ci++) { x.beginPath(); x.moveTo(318, 320 + ci * 33); x.lineTo(542, 320 + ci * 33); x.stroke(); }
    for (ci = 0; ci < 7; ci++) { x.beginPath(); x.moveTo(324 + ci * 33, 312); x.lineTo(324 + ci * 33, 708); x.stroke(); }
    txt('REACTOR CORE', 430, 762, 34);
    txt('211 CHANNELS', 430, 800, 22, 'rgba(200,192,160,0.55)');

    // hot leg
    line([[560, 400], [720, 400], [720, 250], [1010, 250]], 7);
    line([[560, 620], [720, 620], [720, 780], [1010, 780]], 7);
    txt('HOT LEG 291 C', 860, 218, 24);
    txt('COLD LEG 268 C', 860, 812, 24);

    // steam generators
    function sg(px, py) {
      x.strokeStyle = 'rgba(205,196,160,0.9)'; x.lineWidth = 5;
      x.beginPath(); x.arc(px, py, 82, 0, 6.283); x.stroke();
      x.beginPath(); x.arc(px, py, 54, 0, 6.283); x.stroke();
      line([[px - 54, py], [px + 54, py]], 2, 'rgba(180,175,145,0.5)');
      txt('SG', px, py - 10, 32);
    }
    sg(1010, 250); sg(1010, 780);

    // steam to turbine
    line([[1092, 250], [1240, 250], [1240, 420]], 6);
    line([[1092, 780], [1240, 780], [1240, 640]], 6);
    // turbine
    x.strokeStyle = 'rgba(205,196,160,0.9)'; x.lineWidth = 6;
    x.beginPath(); x.moveTo(1240, 420); x.lineTo(1400, 470); x.lineTo(1400, 590); x.lineTo(1240, 640); x.closePath(); x.stroke();
    txt('TURBINE', 1320, 532, 32);
    txt('GEN', 1320, 690, 26);
    // condenser
    line([[1400, 532], [1520, 532]], 6);
    x.strokeRect(1520, 470, 180, 124);
    txt('CONDENSER', 1610, 532, 26);
    // feedwater return
    line([[1700, 596], [1760, 596], [1760, 940], [1010, 940], [1010, 862]], 5, 'rgba(150,190,180,0.55)');
    txt('FEEDWATER', 1400, 968, 22, 'rgba(150,190,180,0.65)');

    // rods drive
    line([[430, 300], [430, 190], [620, 190]], 5);
    txt('CONTROL ROD DRIVES', 760, 160, 26);
    for (var ri = 0; ri < 10; ri++) {
      x.fillStyle = 'rgba(201,193,160,0.25)'; x.fillRect(640 + ri * 46, 178, 30, 22);
      x.strokeStyle = 'rgba(201,193,160,0.6)'; x.lineWidth = 2; x.strokeRect(640 + ri * 46, 178, 30, 22);
    }

    // lamp node markers
    function node(px, py, col, label) {
      x.beginPath(); x.arc(px, py, 15, 0, 6.283);
      x.fillStyle = 'rgba(0,0,0,0.55)'; x.fill();
      x.strokeStyle = col; x.lineWidth = 3; x.stroke();
      nodes.push({ x: px / W, y: 1 - py / H, color: col, label: label });
    }
    node(560, 400, '#4dff7a', 'HOT LEG FLOW');
    node(560, 620, '#4dff7a', 'COLD LEG FLOW');
    node(1010, 250, '#ffb43c', 'SG A LEVEL');
    node(1010, 780, '#ffb43c', 'SG B LEVEL');
    node(1240, 532, '#4dff7a', 'TURBINE TRIP');
    node(1610, 470, '#46d8ff', 'COND VACUUM');
    node(430, 190, '#ffb43c', 'ROD DRIVE');

    // legend
    txt('UNIT 4  ·  PRIMARY COOLANT SYSTEM', 1024, 60, 40);
    txt('SYNOPTIC  PANEL  SK-4', 1024, 102, 22, 'rgba(200,192,160,0.5)');
    x.strokeStyle = 'rgba(200,192,160,0.35)'; x.lineWidth = 2; x.strokeRect(28, 28, W - 56, H - 56);

    var t = tex(c, 1, 1);
    T.mimicNodes = nodes;
    return t;
  })();

  /* ============================================================
     SMALL UTILITY TEXTURES
     ============================================================ */
  T.mesh = (function () {
    var S = 256, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#000'; x.fillRect(0, 0, S, S);
    x.strokeStyle = 'rgba(150,150,145,0.85)'; x.lineWidth = 2;
    for (var i = 0; i <= 16; i++) {
      x.beginPath(); x.moveTo(i * 16, 0); x.lineTo(i * 16, S); x.stroke();
      x.beginPath(); x.moveTo(0, i * 16); x.lineTo(S, i * 16); x.stroke();
    }
    var t = tex(c, 1, 1); t.encoding = THREE.LinearEncoding; return t;
  })();

  T.perf = (function () {
    var S = 128, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#1a1a18'; x.fillRect(0, 0, S, S);
    for (var i = 0; i < 10; i++) for (var j = 0; j < 10; j++) {
      x.fillStyle = '#000'; x.beginPath(); x.arc(10 + i * 12, 10 + j * 12, 3.4, 0, 6.283); x.fill();
    }
    return tex(c, 1, 1);
  })();

  T.paper = (function () {
    var S = 256, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#cfc7a8'; x.fillRect(0, 0, S, S);
    for (var i = 0; i < 1400; i++) {
      x.fillStyle = 'rgba(110,100,70,' + RC.rnd(0.02, 0.07) + ')';
      x.fillRect(RC.rnd(0, S), RC.rnd(0, S), RC.rnd(1, 3), RC.rnd(1, 3));
    }
    x.strokeStyle = 'rgba(90,80,55,0.18)'; x.lineWidth = 1;
    for (i = 20; i < S; i += 22) { x.beginPath(); x.moveTo(0, i); x.lineTo(S, i); x.stroke(); }
    return tex(c, 1, 1);
  })();

  T.contact = (function () {
    var S = 256, c = cv(S, S), x = c.getContext('2d');
    var g = x.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
    g.addColorStop(0, 'rgba(0,0,0,0.55)'); g.addColorStop(0.55, 'rgba(0,0,0,0.28)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    x.fillStyle = g; x.fillRect(0, 0, S, S);
    var t = new THREE.CanvasTexture(c); t.encoding = THREE.LinearEncoding; return t;
  })();

  /* clock face */
  T.clock = (function () {
    var S = 512, c = cv(S, S), x = c.getContext('2d');
    x.fillStyle = '#d8cfae'; x.beginPath(); x.arc(256, 256, 250, 0, 6.283); x.fill();
    x.strokeStyle = '#26241d'; x.lineWidth = 10; x.beginPath(); x.arc(256, 256, 244, 0, 6.283); x.stroke();
    for (var i = 0; i < 60; i++) {
      var a = i / 60 * Math.PI * 2, major = i % 5 === 0;
      x.strokeStyle = '#26241d'; x.lineWidth = major ? 6 : 2;
      x.beginPath();
      x.moveTo(256 + Math.cos(a) * (major ? 200 : 216), 256 + Math.sin(a) * (major ? 200 : 216));
      x.lineTo(256 + Math.cos(a) * 232, 256 + Math.sin(a) * 232);
      x.stroke();
      if (major) {
        x.fillStyle = '#26241d'; x.font = '600 46px ' + FONT;
        x.textAlign = 'center'; x.textBaseline = 'middle';
        x.fillText(String((i / 5) || 12), 256 + Math.cos(a) * 168, 256 + Math.sin(a) * 168);
      }
    }
    x.fillStyle = '#4a4535'; x.font = '500 18px ' + MONO; x.textAlign = 'center';
    x.fillText('SETH THOMAS', 256, 330);
    return tex(c, 1, 1);
  })();
})();
