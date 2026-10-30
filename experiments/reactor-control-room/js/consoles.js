/* ============================================================
   consoles.js — main operator console + 4 satellite consoles
   ============================================================ */
(function () {
  var RC = window.RC || (window.RC = {});
  var B = RC.build;
  var U = RC.ui = {};

  function tag(obj, label, action) {
    obj.userData.__ia = { label: label, action: action };
    for (var i = 0; i < obj.children.length; i++) markDown(obj.children[i], obj);
    RC.pickables.push(obj);
    return obj;
  }
  function markDown(o, root) { o.userData.__root = root; for (var i = 0; i < o.children.length; i++) markDown(o.children[i], root); }

  function plateTex(main, sub, w, h) { return RC.tex.label(main, sub, { w: w || 512, h: h || 128, mainSize: 50, subSize: 26 }); }

  RC.pickables = [];
  RC.state = {
    power: 72.4, coolant: 291.0, rods: 184, flow: 86.2, xenon: 3.2,
    scram: false, msg: 0, mode: 0, alarm: 0, powerTarget: 72.4
  };
  RC.colliders = RC.colliders || [];

  /* ============================================================
     MAIN CONSOLE
     ============================================================ */
  RC.buildMainConsole = function (scene) {
    var g = new THREE.Group();
    g.position.set(0, 0, 1.75);
    scene.add(g);

    var steel = RC.mat.cabinet;
    var body = B.box(4.2, 0.74, 0.98, RC.mat.cabinetDark);
    body.position.set(0, 0.37, 0.08);
    g.add(body);

    var kick = B.box(4.16, 0.12, 0.94, RC.mat.black);
    kick.position.set(0, 0.06, 0.09);
    g.add(kick);

    var hz = new THREE.Mesh(new THREE.PlaneGeometry(4.2, 0.115),
      new THREE.MeshStandardMaterial({ map: RC.tex.hazard.clone(), roughness: 0.8, metalness: 0.15 }));
    hz.material.map.wrapS = hz.material.map.wrapT = THREE.RepeatWrapping;
    hz.material.map.repeat.set(16, 0.7);
    hz.position.set(0, 0.065, 0.565);
    g.add(hz);

    var top = B.box(4.3, 0.045, 1.08, new THREE.MeshStandardMaterial({ color: 0x14150f, roughness: 0.72, metalness: 0.05, envMapIntensity: 0.22 }));
    top.position.set(0, 0.7625, 0.05);
    g.add(top);

    var lip = B.box(4.3, 0.05, 0.025, RC.mat.steel);
    lip.position.set(0, 0.79, 0.585);
    g.add(lip);

    // back cabinet
    var back = B.box(4.2, 0.80, 0.52, RC.mat.cabinetDark);
    back.position.set(0, 1.155, -0.72);
    g.add(back);
    var backTop = B.box(4.28, 0.04, 0.54, RC.mat.steelDark);
    backTop.position.set(0, 1.575, -0.73);
    g.add(backTop);
    var backFace = B.box(4.16, 0.78, 0.02, new THREE.MeshStandardMaterial({ color: 0x262b24, roughness: 0.74, metalness: 0.08, envMapIntensity: 0.2 }));
    backFace.position.set(0, 1.155, -0.455);
    g.add(backFace);

    /* ---- sloped instrument panel ---- */
    var panel = new THREE.Group();
    panel.position.set(0, 0.905, -0.22);
    panel.rotation.x = -0.44;
    g.add(panel);

    var panelBody = B.box(4.0, 0.48, 0.06, RC.mat.cabinet);
    panel.add(panelBody);
    var panelFace = B.box(3.94, 0.44, 0.01, new THREE.MeshStandardMaterial({ color: 0x2c3129, roughness: 0.72, metalness: 0.08, envMapIntensity: 0.2 }));
    panelFace.position.z = 0.032;
    panel.add(panelFace);

    function P(x, y, z) { return new THREE.Vector3(x, y, z); }

    // meters
    var meterDefs = [
      { x: -1.62, label: 'REACTOR POWER', unit: 'PERCENT', max: 120, value: 72 },
      { x: -1.18, label: 'COOLANT FLOW', unit: 'KG/SEC', max: 100, value: 86 },
      { x: -0.74, label: 'CORE TEMP', unit: 'DEG C', max: 400, value: 291, redFrom: 0.72 }
    ];
    U.meters = [];
    meterDefs.forEach(function (d) {
      var face = RC.tex.dial({ label: d.label, unit: d.unit, max: d.max, redFrom: d.redFrom, sub: 'CLASS 1.5  ·  TYPE 4A' });
      var m = B.meter({ r: 0.078, face: face, max: d.max, value: d.value });
      m.position.set(d.x, 0.07, 0.045);
      panel.add(m);
      U.meters.push(m);
      var lp = B.plate(0.20, 0.05, plateTex(d.label, '', 512, 128));
      lp.position.set(d.x, -0.085, 0.04);
      panel.add(lp);
    });

    // digital readouts
    var seg1 = B.segReadout({ digits: 5, w: 0.28, h: 0.085, value: '00724', label: 'MW' });
    seg1.position.set(-0.14, 0.10, 0.045);
    panel.add(seg1);
    U.segPower = seg1;
    var lp1 = B.plate(0.20, 0.035, plateTex('POWER', '', 512, 96));
    lp1.position.set(-0.14, -0.01, 0.04);
    panel.add(lp1);

    var seg2 = B.segReadout({ digits: 4, w: 0.22, h: 0.085, value: '0184', label: 'RODS', color: '#ff5a12' });
    seg2.position.set(0.32, 0.10, 0.045);
    panel.add(seg2);
    U.segRods = seg2;
    var lp2 = B.plate(0.16, 0.035, plateTex('ROD POS', '', 512, 96));
    lp2.position.set(0.32, -0.01, 0.04);
    panel.add(lp2);

    // knobs
    var k1 = B.knob(0.028, 0.018, RC.mat.bakelite);
    k1.position.set(1.05, 0.09, 0.05);
    tag(k1, 'ROD WITHDRAW  (POWER +2%)', function () { RC.adjustPower(2); });
    panel.add(k1);
    U.knobPower = k1;
    var k2 = B.knob(0.028, 0.018, RC.mat.bakelite);
    k2.position.set(1.32, 0.09, 0.05);
    tag(k2, 'ROD INSERT  (POWER -2%)', function () { RC.adjustPower(-2); });
    panel.add(k2);

    var kl1 = B.plate(0.15, 0.032, plateTex('ROD OUT', '', 512, 96)); kl1.position.set(1.05, 0.005, 0.04); panel.add(kl1);
    var kl2 = B.plate(0.15, 0.032, plateTex('ROD IN', '', 512, 96)); kl2.position.set(1.32, 0.005, 0.04); panel.add(kl2);

    // toggles
    for (var t = 0; t < 5; t++) {
      var tg = B.toggle(null);
      tg.position.set(1.62 + t * 0.055, -0.13, 0.045);
      panel.add(tg);
    }
    var tp = B.plate(0.26, 0.03, plateTex('COOLANT PUMPS', '', 512, 96));
    tp.position.set(1.72, -0.055, 0.04);
    panel.add(tp);

    // small lamps
    var lampMat = new THREE.MeshBasicMaterial({ color: 0xff3020 });
    for (var lm = 0; lm < 3; lm++) {
      var bulb = new THREE.Mesh(new THREE.SphereGeometry(0.012, 10, 8), lampMat);
      bulb.position.set(1.62 + lm * 0.05, 0.13, 0.06);
      panel.add(bulb);
      var rng = new THREE.Mesh(new THREE.TorusGeometry(0.016, 0.003, 6, 12), RC.mat.chrome);
      rng.position.copy(bulb.position); panel.add(rng);
    }

    /* ---- back face: scope + annunciators ---- */
    var scope = B.scope({ w: 0.40, h: 0.30 });
    scope.position.set(0, 1.26, -0.44);
    g.add(scope);
    U.scope = scope;

    var title = B.plate(0.62, 0.05, plateTex('NEUTRON FLUX MONITOR', '', 512, 96));
    title.position.set(0, 1.47, -0.443);
    g.add(title);

    U.annun = [];
    var annunDefs = [
      ['ROD BOT', 'LIMIT', '#ffb43c'], ['HIGH', 'FLUX', '#ff3020'], ['COOLANT', 'LOW FLOW', '#ff3020'],
      ['TURBINE', 'TRIP', '#ffb43c'], ['GEN', 'ON LINE', '#4dff7a'], ['XENON', 'HIGH', '#ffb43c']
    ];
    for (var a = 0; a < 6; a++) {
      var col = a % 3, row = Math.floor(a / 3);
      var an = B.annunciator(annunDefs[a][0], annunDefs[a][1], annunDefs[a][2]);
      an.position.set(-1.72 + col * 0.13, 1.30 - row * 0.078, -0.432);
      g.add(an);
      U.annun.push(an);
    }
    U.annun[4].userData.setLit(true);
    U.annun[3].userData.setLit(false);

    // right side: reset/ack + readout
    var ack = B.annunciator('ACK', 'ALARM', '#ffb43c');
    ack.position.set(1.66, 1.30, -0.432);
    g.add(ack);
    tag(ack, 'ACKNOWLEDGE ALARMS', function () { RC.ackAlarms(); });
    U.ack = ack;

    var segRods2 = B.segReadout({ digits: 3, w: 0.17, h: 0.07, value: '184', label: '', color: '#ff2a10' });
    segRods2.position.set(1.40, 1.15, -0.43);
    g.add(segRods2);
    U.segRods2 = segRods2;

    // rod-bank lamp column (fills the left panel)
    var rodCol = new THREE.Group();
    rodCol.position.set(-1.05, 1.24, -0.432);
    var rbBase = B.box(0.075, 0.34, 0.012, RC.mat.black);
    rodCol.add(rbBase);
    for (var rb = 0; rb < 10; rb++) {
      var on = rb < 7;
      var seg = new THREE.Mesh(new THREE.PlaneGeometry(0.045, 0.018),
        new THREE.MeshBasicMaterial({ color: on ? (rb > 7 ? 0xff3020 : 0xffb43c) : 0x2a1a08 }));
      seg.position.set(0, 0.135 - rb * 0.030, 0.008);
      rodCol.add(seg);
    }
    var rbLbl = B.plate(0.10, 0.03, RC.tex.label('ROD', 'BANK', { w: 256, h: 96, mainSize: 34, subSize: 20 }));
    rbLbl.position.set(0, -0.185, 0.008);
    rodCol.add(rbLbl);
    g.add(rodCol);

    // long engraved strip under the panel
    var strip = B.plate(3.5, 0.055, RC.tex.label('CONSOLE 4-A   ·   REACTOR CONTROL   ·   GENERAL ELECTRIC   ·   TYPE 4A', '', { w: 2048, h: 128, mainSize: 34, subSize: 18, fg: 'rgba(214,206,180,0.55)' }));
    strip.position.set(0, 0.86, -0.452);
    g.add(strip);

    // panel screws
    [[-2.02, 0.92], [2.02, 0.92], [-2.02, 1.50], [2.02, 1.50]].forEach(function (sp2) {
      g.add(B.screw(sp2[0], sp2[1], -0.444));
    });

    // speaker grilles
    for (var sp = -1; sp <= 1; sp += 2) {
      var gr = new THREE.Mesh(new THREE.PlaneGeometry(0.20, 0.30),
        new THREE.MeshStandardMaterial({ map: RC.tex.perf, roughness: 0.85, metalness: 0.3, color: 0x8a8f80 }));
      gr.position.set(sp * 1.94, 1.26, -0.448);
      g.add(gr);
    }

    /* ---- desktop props ---- */
    // SCRAM
    var scram = new THREE.Group();
    scram.position.set(1.62, 0.786, 0.26);
    var sBase = B.cyl(0.075, 0.078, 0.022, RC.mat.steelDark, 26);
    sBase.position.y = 0.011; scram.add(sBase);
    var red = B.cyl(0.052, 0.058, 0.030, RC.mat.redBright, 26);
    red.position.y = 0.038; scram.add(red);
    var dome = new THREE.Mesh(new THREE.SphereGeometry(0.052, 20, 10, 0, 6.283, 0, Math.PI / 2), RC.mat.redBright);
    dome.scale.y = 0.55; dome.position.y = 0.053; scram.add(dome);
    var ring = new THREE.Mesh(new THREE.TorusGeometry(0.062, 0.006, 8, 24), RC.mat.steel);
    ring.rotation.x = Math.PI / 2; ring.position.y = 0.052; scram.add(ring);
    // guard
    var guardPivot = new THREE.Group();
    guardPivot.position.set(0, 0, -0.072);
    guardPivot.rotation.x = -1.0;
    var cover = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 0.055, 20, 1, true),
      new THREE.MeshStandardMaterial({ color: 0xff3020, transparent: true, opacity: 0.18, roughness: 0.15, metalness: 0.1, side: THREE.DoubleSide }));
    cover.rotation.x = Math.PI / 2;
    cover.position.set(0, 0.055, 0.072);
    guardPivot.add(cover);
    scram.add(guardPivot);
    var scramLabel = B.plate(0.20, 0.045, plateTex('SCRAM', 'REACTOR TRIP', 512, 160));
    scramLabel.rotation.x = -Math.PI / 2;
    scramLabel.position.set(0, 0.003, 0.10);
    scram.add(scramLabel);
    g.add(scram);
    tag(scram, 'SCRAM — REACTOR TRIP', function () { RC.toggleScram(); });
    U.scram = scram;
    U.scramDome = dome;

    // clipboard + pencil cup
    var clip = new THREE.Group();
    clip.position.set(-1.05, 0.80, 0.36);
    clip.rotation.y = 0.2;
    var board = B.box(0.24, 0.008, 0.33, new THREE.MeshStandardMaterial({ color: 0x5a4a32, roughness: 0.85 }));
    clip.add(board);
    var sheet = new THREE.Mesh(new THREE.PlaneGeometry(0.20, 0.28), new THREE.MeshStandardMaterial({ map: RC.tex.paper, color: 0xe4dcc0, roughness: 0.95 }));
    sheet.rotation.x = -Math.PI / 2; sheet.position.y = 0.006; clip.add(sheet);
    var clipTop = B.box(0.08, 0.014, 0.03, RC.mat.steel);
    clipTop.position.set(0, 0.012, -0.14); clip.add(clipTop);
    g.add(clip);

    var cup2 = new THREE.Group();
    cup2.position.set(-2.0, 0.786, 0.28);
    var cupBody = B.cyl(0.042, 0.038, 0.10, new THREE.MeshStandardMaterial({ color: 0x4a5248, roughness: 0.6, metalness: 0.3 }), 16);
    cupBody.position.y = 0.05;
    cup2.add(cupBody);
    for (var pc = 0; pc < 4; pc++) {
      var pencil = B.cyl(0.004, 0.004, 0.17, pc % 2 ? RC.mat.red : RC.mat.cream, 6);
      pencil.position.set(RC.rnd(-0.02, 0.02), 0.10, RC.rnd(-0.02, 0.02));
      pencil.rotation.z = RC.rnd(-0.14, 0.14); pencil.rotation.x = RC.rnd(-0.1, 0.1);
      cup2.add(pencil);
    }
    g.add(cup2);

    // phone
    var phone = B.phone();
    phone.position.set(-1.66, 0.786, 0.10);
    phone.rotation.y = 0.25;
    g.add(phone);

    // logbook
    var book = new THREE.Group();
    book.position.set(-0.55, 0.79, 0.26);
    book.rotation.y = -0.12;
    var paperMat = new THREE.MeshStandardMaterial({ map: RC.tex.paper, roughness: 0.95, color: 0xe2dabd });
    for (var pg = 0; pg < 2; pg++) {
      var page = B.box(0.19, 0.004, 0.27, paperMat);
      page.position.set(-0.096 + pg * 0.192, 0.002, 0);
      page.rotation.z = pg ? 0.02 : -0.02;
      book.add(page);
    }
    var spine = B.box(0.014, 0.01, 0.27, RC.mat.black);
    book.add(spine);
    var pen = B.cyl(0.004, 0.004, 0.14, RC.mat.steelDark, 8);
    pen.rotation.z = Math.PI / 2; pen.rotation.y = 0.4;
    pen.position.set(0.13, 0.008, 0.06);
    book.add(pen);
    g.add(book);

    // cup + ashtray
    var cup = B.cup();
    cup.position.set(0.92, 0.786, 0.42);
    g.add(cup);
    var ash = new THREE.Group();
    ash.position.set(1.20, 0.786, 0.42);
    var ashBody = B.cyl(0.055, 0.05, 0.018, new THREE.MeshStandardMaterial({ color: 0x2b2b26, roughness: 0.3, metalness: 0.5 }), 20);
    ashBody.position.y = 0.009; ash.add(ashBody);
    var cig = B.cyl(0.005, 0.005, 0.075, RC.mat.cream, 8);
    cig.rotation.z = Math.PI / 2; cig.rotation.y = 0.7; cig.position.y = 0.026; ash.add(cig);
    g.add(ash);

    // contact shadow
    g.add(B.contactShadow(5.2, 2.1, 0.85));

    // local light
    var gl = new THREE.PointLight(0x6dffb0, 0.30, 1.9, 2);
    gl.position.set(0, 1.20, -0.12);
    g.add(gl);
    U.crtLight = gl;

    RC.addCollider(0, 1.72, 4.35, 1.75);

    /* ---- chair ---- */
    var chair = new THREE.Group();
    chair.position.set(2.85, 0, 2.95);
    chair.rotation.y = -0.7;
    var seat = B.cyl(0.24, 0.22, 0.07, RC.mat.black, 20);
    seat.position.y = 0.48; chair.add(seat);
    var back = B.box(0.44, 0.36, 0.07, RC.mat.black);
    back.position.set(0, 0.75, -0.21); back.rotation.x = -0.12; chair.add(back);
    for (var cl = 0; cl < 5; cl++) {
      var ang = cl / 5 * Math.PI * 2;
      var leg = B.box(0.03, 0.03, 0.34, RC.mat.steelDark);
      leg.position.set(Math.cos(ang) * 0.16, 0.20, Math.sin(ang) * 0.16);
      leg.rotation.y = -ang;
      chair.add(leg);
      var castor = new THREE.Mesh(new THREE.SphereGeometry(0.030, 10, 8), RC.mat.rubber);
      castor.position.set(Math.cos(ang) * 0.31, 0.035, Math.sin(ang) * 0.31);
      chair.add(castor);
    }
    var stem = B.cyl(0.035, 0.035, 0.26, RC.mat.steel, 12);
    stem.position.y = 0.34; chair.add(stem);
    chair.add(B.contactShadow(0.8, 0.8, 0.7));
    scene.add(chair);
    RC.addCollider(2.85, 2.95, 0.7, 0.7);
  };

  /* ============================================================
     NIXIE CONSOLE  (west wall, faces +x)
     ============================================================ */
  RC.buildNixieConsole = function (scene) {
    var g = new THREE.Group();
    g.position.set(-3.35, 0, -6.03);
    scene.add(g);

    var body = B.box(2.4, 0.95, 0.62, RC.mat.cabinetDark);
    body.position.set(0, 0.475, 0);
    g.add(body);

    var top = B.box(2.46, 0.05, 0.68, new THREE.MeshStandardMaterial({ color: 0x2f332c, roughness: 0.5, metalness: 0.4 }));
    top.position.set(0, 0.975, 0.01);
    g.add(top);

    // upper cabinet, slightly tilted
    var upper = new THREE.Group();
    upper.position.set(0, 1.0, -0.02);
    g.add(upper);
    var upBody = B.box(2.4, 1.15, 0.44, RC.mat.cabinet);
    upBody.position.set(0, 0.575, 0);
    upper.add(upBody);
    var upTop = B.box(2.46, 0.04, 0.48, RC.mat.steelDark);
    upTop.position.set(0, 1.16, 0);
    upper.add(upTop);

    // header
    var header = B.plate(0.86, 0.075, RC.tex.label('CORE INSTRUMENTATION', 'NIXIE ANNUNCIATOR', { w: 1024, h: 160, mainSize: 48, subSize: 26, fg: '#ddd3ae' }));
    header.position.set(0, 1.05, 0.221);
    upper.add(header);

    // protruding hood with the nixie bank (open at the front)
    var bay = new THREE.Group();
    bay.position.set(-0.58, 0.56, 0.215);
    upper.add(bay);

    var darkMat = new THREE.MeshStandardMaterial({ color: 0x080807, roughness: 0.92, metalness: 0.08 });
    var BW = 1.00, BH = 0.68, BD = 0.20;

    var backP = B.box(BW, BH, 0.02, darkMat);
    backP.position.z = 0.0;
    bay.add(backP);

    var wallT = B.box(BW, 0.035, BD, RC.mat.steelDark); wallT.position.set(0, BH / 2, BD / 2);
    var wallB = B.box(BW, 0.035, BD, RC.mat.steelDark); wallB.position.set(0, -BH / 2, BD / 2);
    var wallL = B.box(0.035, BH, BD, RC.mat.steelDark); wallL.position.set(-BW / 2, 0, BD / 2);
    var wallR = B.box(0.035, BH, BD, RC.mat.steelDark); wallR.position.set(BW / 2, 0, BD / 2);
    bay.add(wallT); bay.add(wallB); bay.add(wallL); bay.add(wallR);

    // tubes: 3 rows x 5 digits
    var rowLabels = ['POWER  %', 'COOLANT  °C', 'ROD POS /211'];
    var tubeGroups = [];
    for (var r = 0; r < 3; r++) {
      var tg = B.nixieBank({ cols: 5, rows: 1, dx: 0.045, dy: 0 });
      tg.scale.setScalar(2.6);
      tg.position.set(0.13, 0.12 - r * 0.21, 0.075);
      bay.add(tg);
      tubeGroups.push(tg);
      var lbl = B.plate(0.24, 0.036, RC.tex.label(rowLabels[r], '', { w: 512, h: 96, mainSize: 30, subSize: 18, fg: '#cfe3c6' }));
      lbl.material.emissive.setHex(0xffffff);
      lbl.material.emissiveIntensity = 0.55;
      lbl.position.set(-0.345, 0.213 - r * 0.21, 0.016);
      bay.add(lbl);
    }
    U.nixie = tubeGroups;

    // smoked acrylic window + flange
    var win = new THREE.Mesh(new THREE.PlaneGeometry(BW - 0.07, BH - 0.07), RC.mat.smoked);
    win.position.set(0, 0, BD + 0.002);
    bay.add(win);
    [[0, BH / 2 + 0.028, BW + 0.09, 0.056], [0, -BH / 2 - 0.028, BW + 0.09, 0.056],
     [-BW / 2 - 0.028, 0, 0.056, BH + 0.09], [BW / 2 + 0.028, 0, 0.056, BH + 0.09]].forEach(function (f) {
      var s = B.box(f[2], f[3], 0.05, RC.mat.steelDark);
      s.position.set(f[0], f[1], BD + 0.018);
      bay.add(s);
    });
    for (var sc = 0; sc < 4; sc++) {
      var screw = B.screw(-0.45 + sc * 0.30, -BH / 2 - 0.028, BD + 0.048);
      bay.add(screw);
    }

    // right side meters
    var nf1 = RC.tex.dial({ label: 'ROD BANK A', unit: 'PERCENT OUT', max: 100, value: 62 });
    var nm1 = B.meter({ r: 0.085, face: nf1, max: 100, value: 62 });
    nm1.position.set(0.60, 0.80, 0.225);
    upper.add(nm1);
    U.nixieMeterA = nm1;
    var nf2 = RC.tex.dial({ label: 'ROD BANK B', unit: 'PERCENT OUT', max: 100, value: 78, redFrom: 0.9 });
    var nm2 = B.meter({ r: 0.085, face: nf2, max: 100, value: 78 });
    nm2.position.set(0.60, 0.52, 0.225);
    upper.add(nm2);
    U.nixieMeterB = nm2;

    var th = B.plate(0.44, 0.05, RC.tex.label('ROD POSITION', 'BANKS A / B', { w: 512, h: 96, mainSize: 34, subSize: 20 }));
    th.position.set(0.63, 0.36, 0.226);
    upper.add(th);

    // lower front: thumbwheels + switch row
    for (var tw = 0; tw < 6; tw++) {
      var wheel = B.cyl(0.021, 0.021, 0.012, RC.mat.bakelite, 14);
      wheel.rotation.x = Math.PI / 2;
      wheel.position.set(-0.86 + tw * 0.062, 0.84, 0.317);
      g.add(wheel);
      var slot = B.box(0.026, 0.012, 0.004, RC.mat.cream);
      slot.position.set(wheel.position.x, 0.84, 0.324);
      g.add(slot);
    }
    var twl = B.plate(0.5, 0.04, RC.tex.label('SETPOINT  ·  ROD SEQUENCE', '', { w: 512, h: 96, mainSize: 30, subSize: 18 }));
    twl.position.set(-0.65, 0.79, 0.32);
    g.add(twl);

    // lower meters
    var lf = RC.tex.dial({ label: 'COOLANT  T', unit: 'DEG C', max: 400, value: 291, redFrom: 0.8 });
    var lm = B.meter({ r: 0.10, face: lf, max: 400, value: 291 });
    lm.position.set(0.62, 0.52, 0.318);
    g.add(lm);
    U.nixieMeterC = lm;

    var choke = B.plate(0.7, 0.10, RC.tex.label('CORE COOLANT', 'LOOP 1 — LOOP 2', { w: 1024, h: 160, mainSize: 44, subSize: 24 }));
    choke.position.set(0.62, 0.80, 0.318);
    g.add(choke);

    tag(bay, 'CYCLE NIXIE DISPLAY GROUP', function () {
      RC.state.mode = (RC.state.mode + 1) % 3;
      RC.refreshNixie();
    });

    g.add(B.contactShadow(2.9, 1.2, 0.9));
    var glow = new THREE.PointLight(0xff5a18, 0.30, 2.8, 2);
    glow.position.set(-0.3, 1.62, 0.55);
    g.add(glow);
    RC.nixieGlow = glow;

    // wall-wash tube above the console
    var wash = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 1.9, 8),
      new THREE.MeshBasicMaterial({ color: 0xdfe4c4 }));
    wash.rotation.z = Math.PI / 2;
    wash.position.set(0, 2.42, 0.42);
    g.add(wash);
    var washHood = B.box(2.02, 0.07, 0.24, RC.mat.steelDark);
    washHood.position.set(0, 2.49, 0.40);
    g.add(washHood);
    var washLight = new THREE.PointLight(0xd8e0b8, 0.34, 3.4, 2);
    washLight.position.set(0, 2.30, 0.55);
    g.add(washLight);
    RC.nixieWash = washLight;
    RC.addCollider(-3.35, -6.03, 2.6, 0.95);
    return g;
  };

  /* ============================================================
     SPLIT-FLAP CONSOLE (north wall, faces +z)
     ============================================================ */
  RC.buildFlapConsole = function (scene) {
    var g = new THREE.Group();
    g.position.set(-7.40, 0, -0.25);
    g.rotation.y = Math.PI / 2;
    scene.add(g);

    var body = B.box(3.0, 0.82, 0.55, RC.mat.cabinetDark);
    body.position.set(0, 0.41, 0);
    g.add(body);
    var top = B.box(3.06, 0.05, 0.60, RC.mat.steelDark);
    top.position.set(0, 0.845, 0);
    g.add(top);

    // upper panel
    var up = new THREE.Group();
    up.position.set(0, 0.87, 0.02);
    up.rotation.x = -0.045;
    g.add(up);
    var upBody = B.box(3.0, 1.62, 0.30, RC.mat.cabinet);
    upBody.position.set(0, 0.81, 0);
    up.add(upBody);
    var upFrame = B.box(3.06, 1.68, 0.04, RC.mat.steelDark);
    upFrame.position.set(0, 0.81, 0.15);
    up.add(upFrame);
    var inner = B.box(2.86, 1.50, 0.02, new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.7, metalness: 0.2 }));
    inner.position.set(0, 0.81, 0.168);
    up.add(inner);

    // header
    var hdr = B.plate(1.5, 0.075, RC.tex.label('PLANT STATUS  /  SEQUENCE OF EVENTS', 'SOLARI TYPE  ·  12 x 6', { w: 1024, h: 128, mainSize: 40, subSize: 22, fg: '#d9d0b4' }));
    hdr.position.set(0, 1.575, 0.182);
    up.add(hdr);

    // flap display
    var disp = B.flapDisplay({ cols: 12, rows: 6, cw: 0.165, ch: 0.185 });
    disp.position.set(0, 0.86, 0.185);
    up.add(disp);
    U.flap = disp;

    // side lamps
    for (var s = -1; s <= 1; s += 2) {
      var lamp = new THREE.Mesh(new THREE.CircleGeometry(0.026, 16), new THREE.MeshBasicMaterial({ color: 0xff3020 }));
      lamp.position.set(s * 1.30, 1.575, 0.182);
      up.add(lamp);
      var housing = new THREE.Mesh(new THREE.TorusGeometry(0.032, 0.007, 8, 16), RC.mat.chrome);
      housing.position.copy(lamp.position); up.add(housing);
    }

    // lower: knobs and a phone
    for (var k = 0; k < 4; k++) {
      var kn = B.knob(0.026, 0.016, RC.mat.bakelite);
      kn.position.set(-1.15 + k * 0.10, 0.50, 0.285);
      g.add(kn);
    }
    var pl = B.plate(0.5, 0.06, RC.tex.label('MESSAGE SELECT', '', { w: 512, h: 96, mainSize: 40 }));
    pl.position.set(-1.0, 0.36, 0.285);
    g.add(pl);

    var seg = B.segReadout({ digits: 4, w: 0.22, h: 0.08, value: '0347', label: '' });
    seg.position.set(0.95, 0.50, 0.285);
    g.add(seg);
    U.flapClock = seg;

    tag(disp, 'ADVANCE STATUS MESSAGE', function () { RC.nextFlapMessage(); });

    g.add(B.contactShadow(3.6, 1.3, 0.9));
    var fglow = new THREE.PointLight(0xffd8a0, 0.26, 3.4, 2);
    fglow.position.set(0, 2.0, 0.8);
    g.add(fglow);
    RC.addCollider(-7.40, -0.25, 0.95, 3.2);
    return g;
  };

  /* ============================================================
     LED CONSOLE (east wall, faces -x)
     ============================================================ */
  RC.buildLedConsole = function (scene) {
    var g = new THREE.Group();
    g.position.set(3.35, 0, -6.03);
    scene.add(g);

    var body = B.box(2.4, 0.9, 0.62, RC.mat.cabinetDark);
    body.position.set(0, 0.45, 0);
    g.add(body);
    var top = B.box(2.46, 0.05, 0.68, RC.mat.steelDark);
    top.position.set(0, 0.925, 0.01);
    g.add(top);

    var up = new THREE.Group();
    up.position.set(0, 0.95, 0);
    g.add(up);
    var upBody = B.box(2.4, 1.25, 0.44, RC.mat.cabinet);
    upBody.position.set(0, 0.625, 0);
    up.add(upBody);
    var upTop = B.box(2.46, 0.04, 0.48, RC.mat.steelDark);
    upTop.position.set(0, 1.265, 0);
    up.add(upTop);

    var hdr = B.plate(1.1, 0.07, RC.tex.label('DIGITAL DATA DISPLAY', 'SOLID STATE  ·  5 x 7 MATRIX', { w: 1024, h: 128, mainSize: 40, subSize: 22 }));
    hdr.position.set(0, 1.17, 0.222);
    up.add(hdr);

    // main LED matrix — oversized dot panel
    var panel = B.ledPanel({ cols: 40, rows: 14, w: 1.52, h: 0.53, text: 'UNIT 4 ONLINE  ·  ALL SYSTEMS NOMINAL  ·  ' });
    panel.position.set(0, 0.84, 0.225);
    up.add(panel);
    U.ledMain = panel;

    var bezel = B.box(1.60, 0.61, 0.03, RC.mat.steelDark);
    bezel.position.set(0, 0.84, 0.208);
    up.add(bezel);
    var glass = new THREE.Mesh(new THREE.PlaneGeometry(1.53, 0.54), RC.mat.glass);
    glass.position.set(0, 0.84, 0.247);
    up.add(glass);
    // corner screws
    [[-0.77, 0.53], [0.77, 0.53], [-0.77, 0.23], [0.77, 0.23]].forEach(function (f) {
      var sc = B.screw(f[0], 0.84 + f[1] - 0.38, 0.252);
      up.add(sc);
    });

    // lower LED matrix (small, bars)
    var panel2 = B.ledPanel({ cols: 24, rows: 8, w: 0.30, h: 0.10, mode: 'bars', text: '' });
    panel2.position.set(-0.98, 1.02, 0.225);
    up.add(panel2);
    U.ledBars = panel2;

    // 7-seg readouts
    var segA = B.segReadout({ digits: 5, w: 0.28, h: 0.085, value: '00291', label: 'C' });
    segA.position.set(-0.38, 0.36, 0.23);
    up.add(segA);
    U.ledSegA = segA;
    var segB = B.segReadout({ digits: 5, w: 0.28, h: 0.085, value: '00086', label: 'KG/S' });
    segB.position.set(0.08, 0.36, 0.23);
    up.add(segB);
    U.ledSegB = segB;
    var segLbl = B.plate(0.55, 0.045, RC.tex.label('CORE TEMP        FLOW', '', { w: 1024, h: 96, mainSize: 30 }));
    segLbl.position.set(-0.15, 0.27, 0.23);
    up.add(segLbl);

    // bar graphs
    var bg1 = B.barGraph({ count: 14, w: 0.018, h: 0.009, gap: 0.0125, color: 0xff2a10, value: 0.72 });
    bg1.position.set(-1.06, 0.72, 0.226);
    up.add(bg1);
    U.bar1 = bg1;
    var bg2 = B.barGraph({ count: 14, w: 0.018, h: 0.009, gap: 0.0125, color: 0xff7a10, value: 0.45 });
    bg2.position.set(-0.96, 0.72, 0.226);
    up.add(bg2);
    U.bar2 = bg2;
    var bgl = B.plate(0.26, 0.04, RC.tex.label('ROD', 'FLOW', { w: 512, h: 128, mainSize: 36, subSize: 22 }));
    bgl.position.set(-1.01, 0.53, 0.226);
    up.add(bgl);

    // little status LEDs
    for (var i = 0; i < 6; i++) {
      var led = new THREE.Mesh(new THREE.CircleGeometry(0.008, 10),
        new THREE.MeshBasicMaterial({ color: [0xff2a10, 0xffa020, 0x40ff70, 0xff2a10, 0x40ff70, 0xffa020][i] }));
      led.position.set(0.92 + i * 0.045, 1.14, 0.226);
      up.add(led);
    }

    // patch panel on the base
    var pp = B.box(1.8, 0.34, 0.03, new THREE.MeshStandardMaterial({ color: 0x2b2f29, roughness: 0.7, metalness: 0.4 }));
    pp.position.set(-0.15, 0.55, 0.315);
    g.add(pp);
    for (var j = 0; j < 16; j++) {
      var jack = new THREE.Mesh(new THREE.CylinderGeometry(0.010, 0.010, 0.008, 10), RC.mat.steel);
      jack.rotation.x = Math.PI / 2;
      jack.position.set(-0.85 + (j % 8) * 0.10, 0.62 - Math.floor(j / 8) * 0.12, 0.332);
      g.add(jack);
    }
    var ppl = B.plate(0.4, 0.05, RC.tex.label('PATCH  ·  DATA', '', { w: 512, h: 96, mainSize: 32 }));
    ppl.position.set(0.72, 0.55, 0.33);
    g.add(ppl);

    tag(panel, 'CYCLE LED DISPLAY MODE', function () {
      RC.state.mode = (RC.state.mode + 1) % 3;
      RC.applyState();
    });

    g.add(B.contactShadow(2.9, 1.2, 0.9));
    var dglow = new THREE.PointLight(0xff3010, 0.22, 2.6, 2);
    dglow.position.set(0, 1.55, 0.55);
    g.add(dglow);
    RC.ledGlow = dglow;

    var wash2 = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 1.9, 8),
      new THREE.MeshBasicMaterial({ color: 0xdfe4c4 }));
    wash2.rotation.z = Math.PI / 2;
    wash2.position.set(0, 2.42, 0.42);
    g.add(wash2);
    var washHood2 = B.box(2.02, 0.07, 0.24, RC.mat.steelDark);
    washHood2.position.set(0, 2.49, 0.40);
    g.add(washHood2);
    var washLight2 = new THREE.PointLight(0xd8e0b8, 0.34, 3.4, 2);
    washLight2.position.set(0, 2.30, 0.55);
    g.add(washLight2);
    RC.addCollider(3.35, -6.03, 2.6, 0.95);
    return g;
  };

  /* ============================================================
     SYNOPTIC / MIMIC BOARD (north wall left, faces +z)
     ============================================================ */
  RC.buildMimicConsole = function (scene) {
    var g = new THREE.Group();
    g.position.set(7.40, 0, -0.25);
    g.rotation.y = -Math.PI / 2;
    scene.add(g);

    var body = B.box(3.6, 0.78, 0.52, RC.mat.cabinetDark);
    body.position.set(0, 0.39, 0);
    g.add(body);
    var top = B.box(3.66, 0.05, 0.58, RC.mat.steelDark);
    top.position.set(0, 0.805, 0.01);
    g.add(top);

    // board
    var board = new THREE.Group();
    board.position.set(0, 0.83, 0.06);
    g.add(board);
    var frame = B.box(3.54, 2.06, 0.22, RC.mat.steelDark);
    frame.position.set(0, 1.03, 0);
    board.add(frame);
    var inner = B.box(3.42, 1.94, 0.04, new THREE.MeshStandardMaterial({ color: 0x101208, roughness: 0.6, metalness: 0.2 }));
    inner.position.set(0, 1.03, 0.10);
    board.add(inner);

    var face = new THREE.Mesh(new THREE.PlaneGeometry(3.34, 1.80),
      new THREE.MeshStandardMaterial({
        map: RC.tex.mimic, emissiveMap: RC.tex.mimic, emissive: 0xffffff,
        emissiveIntensity: 0.8, roughness: 0.55, metalness: 0.05, envMapIntensity: 0.2
      }));
    face.position.set(0, 1.06, 0.125);
    board.add(face);

    var glass = new THREE.Mesh(new THREE.PlaneGeometry(3.34, 1.80), RC.mat.glass);
    glass.position.set(0, 1.06, 0.135);
    board.add(glass);

    // lamps on nodes
    U.mimicLamps = [];
    var nodeColor = {};
    RC.tex.mimicNodes.forEach(function (n, i) {
      var col = new THREE.Color(n.color);
      var mat = new THREE.MeshStandardMaterial({ color: col.clone().multiplyScalar(0.25), emissive: col, emissiveIntensity: 1.05, roughness: 0.3, metalness: 0.1 });
      var lamp = new THREE.Mesh(new THREE.SphereGeometry(0.024, 14, 10), mat);
      lamp.position.set((n.x - 0.5) * 3.34, 1.06 - (0.5 - n.y) * 1.80, 0.148);
      board.add(lamp);
      var ring = new THREE.Mesh(new THREE.TorusGeometry(0.030, 0.005, 6, 16), RC.mat.chrome);
      ring.position.copy(lamp.position); board.add(ring);
      U.mimicLamps.push({ mesh: lamp, mat: mat, base: col, phase: i });
    });
    // point light for the board glow
    var ml = new THREE.PointLight(0xffb060, 0.45, 3.4, 2);
    ml.position.set(0, 1.2, 0.8);
    board.add(ml);
    U.mimicLight = ml;

    // corner screws
    for (var cx = -1; cx <= 1; cx += 2) for (var cy = 0; cy <= 1; cy++) {
      var sc = B.screw(cx * 1.66, 0.16 + cy * 1.76, 0.135);
      board.add(sc);
    }

    var hdr = B.plate(1.2, 0.075, RC.tex.label('PRIMARY LOOP  ·  SYNOPTIC', 'BOARD SK-4', { w: 1024, h: 160, mainSize: 42, subSize: 24 }));
    hdr.position.set(0, 2.14, 0.132);
    board.add(hdr);

    // lower row: annunciators + meters
    var labels = [['PUMP A', 'RUN', '#4dff7a'], ['PUMP B', 'RUN', '#4dff7a'], ['SG A', 'LEVEL', '#ffb43c'], ['SG B', 'LEVEL', '#ffb43c']];
    U.mimicAnnun = [];
    for (var i2 = 0; i2 < 4; i2++) {
      var an = B.annunciator(labels[i2][0], labels[i2][1], labels[i2][2]);
      an.position.set(-1.38 + i2 * 0.145, 0.47, 0.272);
      g.add(an);
      U.mimicAnnun.push(an);
      if (i2 < 2) an.userData.setLit(true);
    }

    var f1 = RC.tex.dial({ label: 'CORE FLOW', unit: 'KG/SEC', max: 100, value: 86 });
    var m1 = B.meter({ r: 0.075, face: f1, max: 100, value: 86 });
    m1.position.set(0.52, 0.50, 0.28);
    g.add(m1);
    U.mimicMeter = m1;

    var f2 = RC.tex.dial({ label: 'STEAM PRESS', unit: 'KG/CM2', max: 80, value: 64, redFrom: 0.85 });
    var m2 = B.meter({ r: 0.075, face: f2, max: 80, value: 64 });
    m2.position.set(0.86, 0.50, 0.28);
    g.add(m2);

    var rec = B.chartRecorder({ w: 0.30, h: 0.36 });
    rec.position.set(1.42, 0.44, 0.14);
    g.add(rec);
    U.chart = rec;

    tag(face, 'RUN LAMP TEST', function () { RC.lampTest(); });

    g.add(B.contactShadow(4.0, 1.2, 0.9));
    RC.addCollider(7.40, -0.25, 0.95, 4.0);
    return g;
  };

  /* ============================================================
     STATE MACHINE
     ============================================================ */
  function pad(n, len) { var s = String(Math.abs(Math.round(n))); while (s.length < len) s = '0' + s; return s; }

  RC.refreshNixie = function () {
    if (!U.nixie) return;
    var s = RC.state;
    var vals;
    if (s.mode === 0) vals = [pad(s.power * 100, 5), pad(s.coolant * 10, 5), pad(s.rods, 5)];
    else if (s.mode === 1) vals = [pad(s.flow * 10, 5), pad(s.xenon * 10, 5), pad(211 - s.rods, 5)];
    else vals = [pad(s.power * 10, 5), pad(100 - s.power, 5), pad(s.rods, 5)];
    for (var i = 0; i < U.nixie.length; i++) U.nixie[i].userData.set(vals[i]);
  };

  RC.applyState = function () {
    var s = RC.state;
    if (U.meters) {
      U.meters[0].userData.set(s.power);
      U.meters[1].userData.set(s.flow);
      U.meters[2].userData.set(s.coolant);
    }
    if (U.segPower) U.segPower.userData.set(s.scram ? '00000' : pad(s.power * 10, 5), 'MW');
    if (U.segRods) U.segRods.userData.set(pad(s.rods, 4), 'RODS');
    if (U.segRods2) U.segRods2.userData.set(pad(s.rods, 3), '');
    if (U.ledSegA) U.ledSegA.userData.set(s.scram ? '00000' : pad(s.coolant * 10, 5), 'C');
    if (U.ledSegB) U.ledSegB.userData.set(s.scram ? '00000' : pad(s.flow * 10, 5), 'KG/S');
    if (U.ledMain) U.ledMain.userData.api.setText(s.scram
      ? '*** REACTOR TRIP ***  SCRAM INITIATED  ·  RODS DRIVEN IN  ·  '
      : 'UNIT 4 ONLINE  ·  PWR ' + s.power.toFixed(1) + ' %  ·  COOL ' + s.coolant.toFixed(1) + ' C  ·  RODS ' + Math.round(s.rods) + '/211  ·  ');
    if (U.bar1) U.bar1.userData.set(s.power / 100);
    if (U.bar2) U.bar2.userData.set(s.flow / 100);
    if (U.nixieMeterA) U.nixieMeterA.userData.set(s.rods / 211 * 100);
    if (U.nixieMeterB) U.nixieMeterB.userData.set(s.rods / 211 * 100 - 6);
    if (U.nixieMeterC) U.nixieMeterC.userData.set(s.coolant);
    if (U.mimicMeter) U.mimicMeter.userData.set(s.flow);
    RC.refreshNixie();
  };

  RC.adjustPower = function (d) {
    if (RC.state.scram) return;
    RC.state.power = THREE.MathUtils.clamp(RC.state.power + d, 0, 100);
    RC.state.rods = Math.round(211 * RC.state.power / 100);
    RC.applyState();
    RC.log('ROD ' + (d > 0 ? 'WITHDRAW' : 'INSERT') + ' — POWER ' + RC.state.power.toFixed(1) + '%');
  };

  var FLAP_MESSAGES = [
    ['UNIT 04     ', 'PWR  072.4 %', 'COOL 291.0 C', 'RODS 184/211', 'XENON 003.2%', 'SYSTEMS   OK'],
    ['SHIFT B     ', 'OPERATOR R12', 'TIME  03 47 ', 'LOG ENTRY   ', 'CHECK SG LVL', 'NO ABNORMAL '],
    ['COOL PUMP A ', 'FLOW  086.2 ', 'VIB   001.2 ', 'BRG   048 C ', 'NEXT PM 480H', 'MONITOR     '],
    ['SCRAM ACTIVE', 'RODS IN ALL ', 'POWER 000.0 ', 'FLUX  DOWN  ', 'COOL 281.4 C', 'AWAIT RESET ']
  ];


  RC.nextFlapMessage = function () {
    RC.state.msg = (RC.state.msg + 1) % FLAP_MESSAGES.length;
    RC.setFlapMessage(FLAP_MESSAGES[RC.state.msg]);
    RC.log('FLAP MESSAGE ' + (RC.state.msg + 1) + ' SELECTED');
  };

  RC.setFlapMessage = function (lines, instant) {
    if (!U.flap) return;
    U.flap.userData.setLines(lines, instant);
  };

  RC.log = function (t) {
    RC.lastLog = t;
    var el = document.getElementById('log-line');
    if (el) {
      el.textContent = t;
      el.classList.remove('flash');
      void el.offsetWidth;
      el.classList.add('flash');
    }
  };

  RC.ackAlarms = function () {
    if (RC.state.scram) {
      RC.state.scram = false;
      RC.state.power = 0;
      RC.state.rods = 0;
      RC.setScramVisual(false);
      RC.applyState();
      RC.log('ALARMS ACKNOWLEDGED — RODS IN MANUAL');
    } else {
      RC.log('ALARMS ACKNOWLEDGED');
    }
    U.annun.forEach(function (a) { a.userData.setLit(false); });
    U.annun[4].userData.setLit(true);
  };

  RC.toggleScram = function () {
    if (!RC.state.scram) {
      RC.state.scram = true;
      RC.state.power = 0;
      RC.state.rods = 0;
      RC.setScramVisual(true);
      RC.setFlapMessage(FLAP_MESSAGES[3]);
      RC.state.msg = 3;
      RC.applyState();
      RC.log('*** SCRAM ***  ALL RODS DRIVEN IN');
    } else {
      RC.ackAlarms();
    }
  };

  RC.setScramVisual = function (on) {
    if (U.scope) U.scope.userData.setFlat(on);
    if (U.annun) {
      U.annun[1].userData.setLit(on);
      U.annun[2].userData.setLit(on);
      U.annun[3].userData.setLit(on);
      U.annun[0].userData.setLit(on);
    }
    if (U.mimicAnnun) {
      U.mimicAnnun[2].userData.setLit(!on);
      U.mimicAnnun[3].userData.setLit(!on);
    }
    if (U.crtLight) U.crtLight.color.set(on ? 0xff4030 : 0x6dffb0);
    RC.alarmOn = on;
    RC.alarmT = 0;
  };

  RC.lampTest = function () {
    for (var i = 0; i < 6; i++) (function (i) {
      setTimeout(function () { if (U.annun[i]) U.annun[i].userData.setLit(true); }, i * 90);
      setTimeout(function () { if (U.annun[i]) U.annun[i].userData.setLit(false); }, 900 + i * 60);
    })(i);
    U.annun[4].userData.setLit(true);
    U.mimicAnnun.forEach(function (a, i) {
      setTimeout(function () { a.userData.setLit(true); }, i * 100);
      setTimeout(function () { a.userData.setLit(false); }, 800 + i * 80);
    });
    setTimeout(function () { U.mimicAnnun[0].userData.setLit(true); U.mimicAnnun[1].userData.setLit(true); }, 1300);
    RC.log('LAMP TEST');
  };

  RC.buildConsoles = function (scene) {
    RC.buildMainConsole(scene);
    RC.buildNixieConsole(scene);
    RC.buildFlapConsole(scene);
    RC.buildLedConsole(scene);
    RC.buildMimicConsole(scene);
    RC.setFlapMessage(FLAP_MESSAGES[0], true);
    RC.applyState();
  };
})();
