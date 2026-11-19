/**
 * MUNDIALITO — MOTOR WEB OFICIAL (Canvas HTML5 + WebSockets)
 * Fiel al juego original de Python/Kivy:
 * - 24 Selecciones Nacionales completas con sus patrones, colores y ratings exactos.
 * - Habilidades especiales completas: FUEGO, PAUSA, CAMPO MAGNÉTICO (con sus 4 ranuras).
 * - Arquero manual con cámara lenta 50% al arrastrar y límite al área grande.
 * - Modos: 2 Jugadores Local, Multijugador Online (WebSocket WSS) y 1P vs CPU.
 */

// Dimensiones de la cancha lógica (idénticas a main.py)
const FX0 = 60, FY0 = 80, FX1 = 1040, FY1 = 680;
const MY = (FY0 + FY1) / 2;
const GOAL_H = 140;
const GY0 = MY - GOAL_H / 2;
const GY1 = MY + GOAL_H / 2;
const GD = 45;

const PR = 18; // Radio ficha
const BR = 11; // Radio balón
const PM = 3.0; // Masa ficha
const BM = 1.0; // Masa balón
const FRICTION = 0.985;
const PLAYER_FRICTION = 0.982;
const MAX_DRAG = 160;
const POWER = 0.14;
const COOLDOWN = 1.0;

// Constantes de Habilidades
const FIRE_POWER = 1.5;
const FIRE_SLOWMO = 0.5;
const FIRE_RECHARGE = 20.0;
const FIRE_DURATION = 1.5;

const PAUSA_SPEED = 0.15;
const PAUSA_DURATION = 2.0;
const PAUSA_RECHARGE = 20.0;

const CAMPO_DURATION = 12.0;
const CAMPO_RECHARGE = 30.0;

const SLOWMO_GK = 0.5;
const GK_POWER_FACTOR = 0.5;

// Formación 1-2-2-1
const FORMATION = [
    { x: 0.04, y: 0.5, keeper: true },
    { x: 0.18, y: 0.3, keeper: false },
    { x: 0.18, y: 0.7, keeper: false },
    { x: 0.32, y: 0.38, keeper: false },
    { x: 0.32, y: 0.62, keeper: false },
    { x: 0.44, y: 0.5, keeper: false }
];

// Las 24 Selecciones del juego original (patrón, color1, color2, borde, rating, extra)
const TEAMS_DATABASE = {
    "España":         { pat: "chestband", c1: "#ff1a2e", c2: "#ffd400", edge: "#ffd400", rating: 88, extra: ["#ffd400", "#ff1a2e", "#ffd400"] },
    "Francia":        { pat: "chestband", c1: "#2453ff", c2: "#ffffff", edge: "#ff2b3a", rating: 90, extra: ["#2453ff", "#ffffff", "#ff2b3a"] },
    "Alemania":       { pat: "chestband", c1: "#ffffff", c2: "#111111", edge: "#111111", rating: 87, extra: ["#222222", "#ff2020", "#ffcc00"] },
    "Inglaterra":     { pat: "sash",      c1: "#ffffff", c2: "#ff1f3d", edge: "#1d3cff", rating: 88, extra: null },
    "Italia":         { pat: "chestband", c1: "#1e90ff", c2: "#ffffff", edge: "#ffd700", rating: 85, extra: ["#00c853", "#ffffff", "#ff1744"] },
    "Portugal":       { pat: "half",      c1: "#ff1f3d", c2: "#00c853", edge: "#ffd400", rating: 87, extra: null },
    "Países Bajos":   { pat: "solid",     c1: "#ff7a00", c2: "#ffffff", edge: "#1b1b6b", rating: 86, extra: null },
    "Bélgica":        { pat: "sash",      c1: "#ff2020", c2: "#ffd400", edge: "#111111", rating: 84, extra: null },
    "Croacia":        { pat: "checks",    c1: "#ffffff", c2: "#ff1f2f", edge: "#1e4bff", rating: 84, extra: null },
    "Argentina":      { pat: "vstripes",  c1: "#ffffff", c2: "#5ec8ff", edge: "#1a2a6c", rating: 91, extra: null },
    "Brasil":         { pat: "chestband", c1: "#ffe600", c2: "#00b84f", edge: "#00b84f", rating: 90, extra: ["#00b84f", "#ffe600", "#2b5cff"] },
    "Uruguay":        { pat: "solid",     c1: "#4fc3ff", c2: "#ffffff", edge: "#ffffff", rating: 83, extra: null },
    "Colombia":       { pat: "hoops",     c1: "#ffd60a", c2: "#2a5bff", edge: "#ff1f3d", rating: 82, extra: null },
    "México":         { pat: "sash",      c1: "#00b560", c2: "#ff2b3a", edge: "#ffffff", rating: 81, extra: null },
    "Estados Unidos": { pat: "hoops",     c1: "#ffffff", c2: "#ff2b3a", edge: "#1f4dff", rating: 80, extra: null },
    "Chile":          { pat: "half",      c1: "#ff2a1f", c2: "#1f55ff", edge: "#ffffff", rating: 79, extra: null },
    "Suecia":         { pat: "chestband", c1: "#ffd800", c2: "#1a5cff", edge: "#1a5cff", rating: 80, extra: ["#1a5cff", "#ffd800", "#1a5cff"] },
    "Dinamarca":      { pat: "vstripes",  c1: "#ff1f2f", c2: "#ffffff", edge: "#ffffff", rating: 81, extra: null },
    "Suiza":          { pat: "cross",     c1: "#ff1a1a", c2: "#ffffff", edge: "#ffffff", rating: 80, extra: null },
    "Polonia":        { pat: "half",      c1: "#ffffff", c2: "#ff1f3d", edge: "#ff1f3d", rating: 79, extra: null },
    "Hungría":        { pat: "chestband", c1: "#ff2030", c2: "#ffffff", edge: "#00b050", rating: 78, extra: ["#ffffff", "#00c060", "#ffffff"] },
    "Paraguay":       { pat: "vstripes",  c1: "#ffffff", c2: "#ff1f2f", edge: "#1f4dff", rating: 78, extra: null },
    "Perú":           { pat: "sash",      c1: "#ffffff", c2: "#ff1f2f", edge: "#ff1f2f", rating: 79, extra: null },
    "Ecuador":        { pat: "chestband", c1: "#ffe100", c2: "#1f4dff", edge: "#1f4dff", rating: 78, extra: ["#1f4dff", "#ff1f2f", "#1f4dff"] }
};

class SoundFX {
    constructor() { this.ctx = null; }
    init() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
    }
    kick() {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        osc.connect(g); g.connect(this.ctx.destination);
        osc.frequency.setValueAtTime(150, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(35, this.ctx.currentTime + 0.12);
        g.gain.setValueAtTime(0.35, this.ctx.currentTime);
        g.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.12);
        osc.start(); osc.stop(this.ctx.currentTime + 0.12);
    }
    whistle() {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        osc.connect(g); g.connect(this.ctx.destination);
        osc.frequency.setValueAtTime(2300, this.ctx.currentTime);
        g.gain.setValueAtTime(0.25, this.ctx.currentTime);
        g.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.28);
        osc.start(); osc.stop(this.ctx.currentTime + 0.28);
    }
    powerSound() {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const g = this.ctx.createGain();
        osc.connect(g); g.connect(this.ctx.destination);
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(300, this.ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(750, this.ctx.currentTime + 0.25);
        g.gain.setValueAtTime(0.2, this.ctx.currentTime);
        g.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.25);
        osc.start(); osc.stop(this.ctx.currentTime + 0.25);
    }
    goal() {
        if (!this.ctx) return;
        this.whistle();
        setTimeout(() => this.whistle(), 250);
        setTimeout(() => this.whistle(), 550);
    }
}

class Body {
    constructor(x, y, r, m, team = null, keeper = false, num = 10) {
        this.x = x;
        this.y = y;
        this.vx = 0;
        this.vy = 0;
        this.r = r;
        this.m = m;
        this.team = team;
        this.keeper = keeper;
        this.num = num;
        this.stunnedUntil = 0;
    }
}

class GameEngine {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.sound = new SoundFX();

        // Estado del partido
        this.mode = 'match';
        this.matchType = 'local'; // 'local', 'cpu', 'online'
        this.localPlayerIdx = 0;
        this.teams = ["Argentina", "Brasil"];
        this.score = [0, 0];
        this.clock = 0;
        this.nextShotAt = [0, 0];
        this.gkNextShotAt = [0, 0];
        this.kickTeam = null;

        // Entidades
        this.bodies = [];
        this.ball = null;

        // Arrastre e interacción
        this.drag = null;
        this.dragPos = { x: 0, y: 0 };
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;

        // Habilidades
        this.fireArmed = [false, false];
        this.fireSelected = [null, null];
        this.fireFlightUntil = 0;
        this.fireReadyAt = [0, 0];

        this.pausaUntil = 0;
        this.pausaReadyAt = [0, 0];

        this.campoUntil = [0, 0];
        this.campoReadyAt = [0, 0];

        this.infoOpen = null;

        // Cámara lenta activa
        this.currentSlowmo = 1.0;

        // UI & WebSocket
        this.goalMessage = "";
        this.goalUntil = 0;
        this.ws = null;
        this.roomCode = "";
        this.onlineStatus = "Desconectado";
        this.searching = false;

        this.initCanvasSize();
        window.addEventListener('resize', () => this.initCanvasSize());
        this.bindEvents();
        this.resetPositions();

        this.lastTime = performance.now();
        requestAnimationFrame((t) => this.loop(t));
    }

    initCanvasSize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        // Altura adaptada para dar espacio al campo y a la barra de habilidades inferior
        this.canvas.height = Math.min(rect.width * 0.72, window.innerHeight * 0.75);

        const worldW = (FX1 + GD + 20) - (FX0 - GD - 20);
        const worldH = (FY1 + 20) - (FY0 - 20);
        // Dejamos un margen inferior de 60px para la barra de 4 habilidades
        const availableH = this.canvas.height - 65;
        this.scale = Math.min(this.canvas.width / worldW, availableH / worldH) * 0.95;
        this.offsetX = (this.canvas.width - worldW * this.scale) / 2 - (FX0 - GD - 20) * this.scale;
        this.offsetY = 38 + (availableH - worldH * this.scale) / 2 - (FY0 - 20) * this.scale;
    }

    toWorld(sx, sy) {
        return {
            x: (sx - this.offsetX) / this.scale,
            y: (sy - this.offsetY) / this.scale
        };
    }

    resetPositions() {
        this.bodies = [];
        // Equipo 0
        for (let i = 0; i < FORMATION.length; i++) {
            const f = FORMATION[i];
            const x = FX0 + f.x * (FX1 - FX0);
            const y = FY0 + f.y * (FY1 - FY0);
            this.bodies.push(new Body(x, y, PR, PM, 0, f.keeper, f.keeper ? 1 : (i === 1 ? 10 : 8 - i)));
        }
        // Equipo 1
        for (let i = 0; i < FORMATION.length; i++) {
            const f = FORMATION[i];
            const x = FX0 + (1 - f.x) * (FX1 - FX0);
            const y = FY0 + f.y * (FY1 - FY0);
            this.bodies.push(new Body(x, y, PR, PM, 1, f.keeper, f.keeper ? 1 : (i === 1 ? 10 : 8 - i)));
        }
        // Balón
        this.ball = new Body((FX0 + FX1) / 2, MY, BR, BM, null);
        this.bodies.push(this.ball);
        this.drag = null;
        this.fireSelected = [null, null];
    }

    canShoot(team, isKeeper = false) {
        const now = performance.now() / 1000;
        if (this.kickTeam !== null) return team === this.kickTeam;
        if (isKeeper) return now >= this.gkNextShotAt[team];
        return now >= this.nextShotAt[team];
    }

    // --- ACTIVACIÓN DE PODERES ---
    useFire(team = 0) {
        const now = performance.now() / 1000;
        if (now < this.fireReadyAt[team]) return;
        this.fireArmed[team] = !this.fireArmed[team];
        this.sound.powerSound();
    }

    usePausa(team = 0) {
        const now = performance.now() / 1000;
        if (now < this.pausaReadyAt[team]) return;
        this.pausaUntil = now + PAUSA_DURATION;
        this.pausaReadyAt[team] = now + PAUSA_RECHARGE;
        this.sound.powerSound();
    }

    useCampo(team = 0) {
        const now = performance.now() / 1000;
        if (now < this.campoReadyAt[team]) return;
        this.campoUntil[team] = now + CAMPO_DURATION;
        this.campoReadyAt[team] = now + CAMPO_RECHARGE;
        this.sound.powerSound();
    }

    shoot(body, vx, vy) {
        const now = performance.now() / 1000;
        const team = body.team;

        // Si la ficha tenía fuego activado
        if (this.fireSelected[team] === body) {
            vx *= FIRE_POWER;
            vy *= FIRE_POWER;
            this.fireSelected[team] = null;
            this.fireArmed[team] = false;
            this.fireFlightUntil = now + FIRE_DURATION;
            this.fireReadyAt[team] = now + FIRE_RECHARGE;
        }

        // Si es arquero: potencia a la mitad
        if (body.keeper) {
            vx *= GK_POWER_FACTOR;
            vy *= GK_POWER_FACTOR;
            this.gkNextShotAt[team] = now + COOLDOWN;
        } else {
            this.nextShotAt[team] = now + COOLDOWN;
        }

        body.vx = vx;
        body.vy = vy;
        this.sound.kick();
        this.kickTeam = null;
    }

    startLocalMatch(team0, team1) {
        this.sound.init();
        this.matchType = 'local';
        this.teams = [team0, team1];
        this.score = [0, 0];
        this.clock = 0;
        this.resetPositions();
        this.mode = 'match';
        this.sound.whistle();
    }

    startCpuMatch(team0, team1) {
        this.sound.init();
        this.matchType = 'cpu';
        this.teams = [team0, team1];
        this.score = [0, 0];
        this.clock = 0;
        this.resetPositions();
        this.mode = 'match';
        this.sound.whistle();
    }

    searchOnlineMatch(chosenTeam = "Argentina") {
        this.sound.init();
        this.searching = true;
        this.onlineStatus = "Buscando oponente en línea...";
        this.connectWebSocket(chosenTeam);
    }

    connectWebSocket(chosenTeam) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'quick_match', team: chosenTeam }));
            return;
        }
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${window.location.host}`);

        this.ws.onopen = () => {
            this.onlineStatus = "Conectado al VPS";
            this.ws.send(JSON.stringify({ action: 'quick_match', team: chosenTeam }));
        };

        this.ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                this.handleNetworkMessage(msg);
            } catch (e) {
                console.error(e);
            }
        };

        this.ws.onclose = () => {
            this.onlineStatus = "Desconectado";
            this.searching = false;
        };
    }

    handleNetworkMessage(msg) {
        if (msg.type === 'waiting_opponent') {
            this.roomCode = msg.room_id;
            this.onlineStatus = `Esperando oponente en el servidor... (PIN: ${this.roomCode})`;
        } else if (msg.type === 'match_start') {
            this.matchType = 'online';
            this.localPlayerIdx = msg.player_idx;
            this.teams = msg.teams;
            this.score = [0, 0];
            this.clock = 0;
            this.resetPositions();
            this.mode = 'match';
            this.searching = false;
            this.sound.whistle();
        } else if (msg.action === 'shoot') {
            const body = this.bodies[msg.body_idx];
            if (body) {
                this.shoot(body, msg.vx, msg.vy);
            }
        } else if (msg.action === 'ability') {
            const slot = msg.slot;
            const t = msg.team;
            if (slot === 0) this.useFire(t);
            else if (slot === 1) this.usePausa(t);
            else if (slot === 2) this.useCampo(t);
        } else if (msg.type === 'opponent_disconnected') {
            this.goalMessage = "¡RIVAL DESCONECTADO (VICTORIA)!";
            this.goalUntil = performance.now() + 4500;
        }
    }

    bindEvents() {
        const getCanvasCoords = (e) => {
            const r = this.canvas.getBoundingClientRect();
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            return {
                x: clientX - r.left,
                y: clientY - r.top
            };
        };

        const onDown = (e) => {
            this.sound.init();
            const pos = getCanvasCoords(e);

            // Clic en la barra inferior de habilidades
            if (pos.y >= this.canvas.height - 62) {
                this.handleAbilityClick(pos.x, pos.y);
                return;
            }

            const w = this.toWorld(pos.x, pos.y);
            const now = performance.now() / 1000;

            let best = null, bestDist = PR * 2.3;
            for (const b of this.bodies) {
                if (b.team === null) continue;
                if (now < b.stunnedUntil) continue; // Aturdido por campo magnético

                const allowed = (this.matchType === 'local') ? true :
                                (this.matchType === 'online') ? b.team === this.localPlayerIdx :
                                b.team === 0;

                if (!allowed) continue;

                const d = Math.hypot(b.x - w.x, b.y - w.y);
                if (d < bestDist) {
                    best = b;
                    bestDist = d;
                }
            }

            if (best && this.canShoot(best.team, best.keeper)) {
                this.drag = best;
                this.dragPos = w;
                // Si el poder de fuego está armado y no es el arquero
                if (this.fireArmed[best.team] && !best.keeper) {
                    this.fireSelected[best.team] = best;
                }
            }
        };

        const onMove = (e) => {
            if (!this.drag) return;
            const pos = getCanvasCoords(e);
            this.dragPos = this.toWorld(pos.x, pos.y);

            // Clamp del arquero al área grande mientras se arrastra
            if (this.drag.keeper) {
                const b = this.drag;
                if (b.team === 0) {
                    this.dragPos.x = Math.min(Math.max(this.dragPos.x, FX0 + PR), FX0 + 150 - PR);
                } else {
                    this.dragPos.x = Math.min(Math.max(this.dragPos.x, FX1 - 150 + PR), FX1 - PR);
                }
                this.dragPos.y = Math.min(Math.max(this.dragPos.y, MY - 150 + PR), MY + 150 - PR);
            }
        };

        const onUp = () => {
            if (!this.drag) return;
            const p = this.drag;
            this.drag = null;

            const dx = p.x - this.dragPos.x;
            const dy = p.y - this.dragPos.y;
            const dist = Math.hypot(dx, dy);

            if (dist > 8) {
                const pull = Math.min(dist, MAX_DRAG);
                const spd = pull * POWER;
                const vx = (dx / dist) * spd;
                const vy = (dy / dist) * spd;

                this.shoot(p, vx, vy);

                if (this.matchType === 'online' && this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const idx = this.bodies.indexOf(p);
                    this.ws.send(JSON.stringify({
                        action: 'shoot',
                        body_idx: idx,
                        vx: vx,
                        vy: vy
                    }));
                }
            }
        };

        this.canvas.addEventListener('mousedown', onDown);
        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onUp);

        this.canvas.addEventListener('touchstart', (e) => { onDown(e); e.preventDefault(); }, { passive: false });
        window.addEventListener('touchmove', (e) => { onMove(e); }, { passive: false });
        window.addEventListener('touchend', onUp);
    }

    handleAbilityClick(sx, sy) {
        const slotW = this.canvas.width / 4;
        const slot = Math.floor(sx / slotW);
        const team = (this.matchType === 'online') ? this.localPlayerIdx : 0;

        // Comprobar si tocó la 'i' de información (esquina superior derecha del slot)
        const cx = (slot + 0.5) * slotW;
        const cy = this.canvas.height - 30;
        const infoX = cx + 20, infoY = cy - 20;

        if (Math.hypot(sx - infoX, sy - infoY) < 14) {
            this.infoOpen = (this.infoOpen === slot) ? null : slot;
            return;
        }

        this.infoOpen = null;
        if (slot === 0) this.useFire(team);
        else if (slot === 1) this.usePausa(team);
        else if (slot === 2) this.useCampo(team);

        if (this.matchType === 'online' && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'ability', slot: slot, team: team }));
        }
    }

    updatePhysics(dt) {
        if (this.mode !== 'match') return;

        const now = performance.now() / 1000;

        // Factor de cámara lenta combinado
        let slowFactor = 1.0;
        if (now < this.pausaUntil) slowFactor = PAUSA_SPEED;
        else if (this.drag && (this.drag.keeper || this.fireSelected[this.drag.team])) slowFactor = SLOWMO_GK;

        const effectiveDt = dt * slowFactor;

        // Fricción y movimiento
        for (const b of this.bodies) {
            b.x += b.vx * slowFactor;
            b.y += b.vy * slowFactor;
            const f = (b.team === null) ? FRICTION : PLAYER_FRICTION;
            b.vx *= f;
            b.vy *= f;
            if (Math.hypot(b.vx, b.vy) < 0.03) {
                b.vx = 0;
                b.vy = 0;
            }

            // Límite de área grande para arqueros
            if (b.keeper) {
                if (b.team === 0) {
                    b.x = Math.min(Math.max(b.x, FX0 + b.r), FX0 + 150 - b.r);
                } else {
                    b.x = Math.min(Math.max(b.x, FX1 - 150 + b.r), FX1 - b.r);
                }
                b.y = Math.min(Math.max(b.y, MY - 150 + b.r), MY + 150 - b.r);
            }
        }

        // Rebotes en paredes
        for (const b of this.bodies) {
            if (b.y - b.r < FY0) {
                b.y = FY0 + b.r;
                b.vy = -b.vy * 0.8;
            } else if (b.y + b.r > FY1) {
                b.y = FY1 - b.r;
                b.vy = -b.vy * 0.8;
            }

            // Fondo izquierdo
            if (b.x - b.r < FX0) {
                if (b.y >= GY0 && b.y <= GY1) {
                    if (b === this.ball && b.x + b.r < FX0 - 15) {
                        this.scoreGoal(1);
                    } else if (b.x - b.r < FX0 - GD) {
                        b.x = FX0 - GD + b.r;
                        b.vx = -b.vx * 0.8;
                    }
                } else {
                    b.x = FX0 + b.r;
                    b.vx = -b.vx * 0.8;
                }
            }

            // Fondo derecho
            if (b.x + b.r > FX1) {
                if (b.y >= GY0 && b.y <= GY1) {
                    if (b === this.ball && b.x - b.r > FX1 + 15) {
                        this.scoreGoal(0);
                    } else if (b.x + b.r > FX1 + GD) {
                        b.x = FX1 + GD - b.r;
                        b.vx = -b.vx * 0.8;
                    }
                } else {
                    b.x = FX1 - b.r;
                    b.vx = -b.vx * 0.8;
                }
            }
        }

        const isFireFlight = now < this.fireFlightUntil;

        // Colisiones elásticas entre cuerpos
        for (let i = 0; i < this.bodies.length; i++) {
            for (let j = i + 1; j < this.bodies.length; j++) {
                const a = this.bodies[i];
                const b = this.bodies[j];

                // Si el balón está en vuelo de fuego
                if (isFireFlight && (a === this.ball || b === this.ball)) {
                    const other = (a === this.ball) ? b : a;
                    // El fuego solo choca con el arquero rival en su propia mitad
                    if (other.keeper) {
                        const inOwnHalf = (other.team === 0 && other.x < (FX0 + FX1) / 2) ||
                                          (other.team === 1 && other.x > (FX0 + FX1) / 2);
                        if (inOwnHalf) {
                            this.fireFlightUntil = 0; // El arquero bloquea el fuego
                            this.goalMessage = "¡BLOQUEO DEL ARQUERO!";
                            this.goalUntil = performance.now() + 1800;
                        } else {
                            continue; // Atraviesa
                        }
                    } else {
                        continue; // Atraviesa todas las fichas de campo
                    }
                }

                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.hypot(dx, dy);
                const minDist = a.r + b.r;

                if (dist < minDist && dist > 0) {
                    // Verificación de campo magnético activo
                    const aProtected = a.team !== null && now < this.campoUntil[a.team];
                    const bProtected = b.team !== null && now < this.campoUntil[b.team];

                    // Si A está protegido por campo magnético y B es rival
                    if (aProtected && b.team !== null && b.team !== a.team) {
                        b.vx = -b.vx * 0.6;
                        b.vy = -b.vy * 0.6;
                        b.stunnedUntil = now + 1.0;
                        continue;
                    }
                    if (bProtected && a.team !== null && a.team !== b.team) {
                        a.vx = -a.vx * 0.6;
                        a.vy = -a.vy * 0.6;
                        a.stunnedUntil = now + 1.0;
                        continue;
                    }

                    const overlap = 0.5 * (minDist - dist);
                    const nx = dx / dist;
                    const ny = dy / dist;

                    a.x -= nx * overlap;
                    a.y -= ny * overlap;
                    b.x += nx * overlap;
                    b.y += ny * overlap;

                    const kx = a.vx - b.vx;
                    const ky = a.vy - b.vy;
                    const p = 2 * (nx * kx + ny * ky) / (a.m + b.m);

                    a.vx -= p * b.m * nx;
                    a.vy -= p * b.m * ny;
                    b.vx += p * a.m * nx;
                    b.vy += p * a.m * ny;
                }
            }
        }

        // IA rival
        if (this.matchType === 'cpu' && this.canShoot(1) && this.ball) {
            this.cpuThink();
        }
    }

    cpuThink() {
        const cpuPlayers = this.bodies.filter(b => b.team === 1 && !b.keeper);
        const p = cpuPlayers[Math.floor(Math.random() * cpuPlayers.length)];
        if (!p) return;

        const dx = (FX0 - 10) - this.ball.x;
        const dy = MY - this.ball.y;
        const d = Math.hypot(dx, dy);

        const aimX = this.ball.x + (dx / d) * 12;
        const aimY = this.ball.y + (dy / d) * 12;

        const shootDx = aimX - p.x;
        const shootDy = aimY - p.y;
        const shootDist = Math.hypot(shootDx, shootDy);

        if (shootDist > 0) {
            const spd = Math.min(shootDist * 0.12, 14);
            this.shoot(p, (shootDx / shootDist) * spd, (shootDy / shootDist) * spd);
        }
    }

    scoreGoal(team) {
        this.score[team]++;
        this.sound.goal();
        const scorer = this.teams[team];
        this.goalMessage = `¡¡GOOOOL DE ${scorer.toUpperCase()}!!`;
        this.goalUntil = performance.now() + 2500;
        this.kickTeam = 1 - team;
        this.resetPositions();
    }

    render() {
        const ctx = this.ctx;
        const now = performance.now() / 1000;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        ctx.save();
        ctx.translate(this.offsetX, this.offsetY);
        ctx.scale(this.scale, this.scale);

        // Cancha con césped de alta definición y franjas
        ctx.fillStyle = "#0a5628";
        ctx.fillRect(FX0 - GD - 10, FY0 - 10, (FX1 - FX0) + (GD * 2) + 20, (FY1 - FY0) + 20);

        ctx.fillStyle = "#0c6731";
        const stripeW = (FX1 - FX0) / 10;
        for (let i = 0; i < 10; i += 2) {
            ctx.fillRect(FX0 + i * stripeW, FY0, stripeW, FY1 - FY0);
        }

        // Líneas de juego
        ctx.strokeStyle = "rgba(255, 255, 255, 0.88)";
        ctx.lineWidth = 3.5;
        ctx.strokeRect(FX0, FY0, FX1 - FX0, FY1 - FY0);

        const midX = (FX0 + FX1) / 2;
        ctx.beginPath();
        ctx.moveTo(midX, FY0);
        ctx.lineTo(midX, FY1);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(midX, MY, 75, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(midX, MY, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeRect(FX0, MY - 150, 150, 300);
        ctx.strokeRect(FX1 - 150, MY - 150, 150, 300);

        ctx.strokeRect(FX0 - GD, GY0, GD, GOAL_H);
        ctx.strokeRect(FX1, GY0, GD, GOAL_H);

        // Tinte helado si está la PAUSA activa
        if (now < this.pausaUntil) {
            ctx.fillStyle = "rgba(50, 180, 255, 0.22)";
            ctx.fillRect(FX0 - GD - 10, FY0 - 10, (FX1 - FX0) + (GD * 2) + 20, (FY1 - FY0) + 20);
        }

        // Dibujar fichas con equipaciones oficiales
        for (const b of this.bodies) {
            if (b.team === null) {
                // Balón (normal o con fuego)
                ctx.save();
                if (now < this.fireFlightUntil) {
                    ctx.fillStyle = "#ff6a00";
                    ctx.shadowColor = "#ffd400";
                    ctx.shadowBlur = 18;
                } else {
                    ctx.fillStyle = "#ffffff";
                }
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = "#111111";
                ctx.lineWidth = 1.5;
                ctx.stroke();

                ctx.fillStyle = (now < this.fireFlightUntil) ? "#ffd400" : "#111111";
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r * 0.45, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            } else {
                // Chapita de Selección
                this.drawJersey(ctx, b, now);
            }
        }

        // Flecha de arrastre / puntería
        if (this.drag) {
            const p = this.drag;
            const dx = p.x - this.dragPos.x;
            const dy = p.y - this.dragPos.y;
            const dist = Math.hypot(dx, dy);

            if (dist > 8) {
                const pull = Math.min(dist, MAX_DRAG);
                const powerRatio = pull / MAX_DRAG;

                ctx.save();
                const isFire = (this.fireSelected[p.team] === p);
                ctx.strokeStyle = isFire ? `rgba(255, ${Math.floor(100 * (1 - powerRatio))}, 0, 0.95)` :
                                           `rgba(255, ${Math.floor(255 * (1 - powerRatio))}, 0, 0.9)`;
                ctx.lineWidth = isFire ? 6 : 4;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p.x + dx * (pull / dist), p.y + dy * (pull / dist));
                ctx.stroke();

                ctx.fillStyle = isFire ? `rgba(255, 60, 0, 0.5)` : `rgba(255, ${Math.floor(200 * (1 - powerRatio))}, 0, 0.4)`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r + pull * 0.28, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }
        }

        ctx.restore();

        // HUD superior (Marcador)
        this.renderHUD();

        // Barra inferior de 4 Habilidades
        this.renderAbilityBar();

        // Panel de información de habilidad emergente
        if (this.infoOpen !== null) {
            this.renderInfoPanel(this.infoOpen);
        }

        // Cartel de Gol flotante
        if (performance.now() < this.goalUntil && this.goalMessage) {
            ctx.save();
            ctx.fillStyle = "rgba(0, 0, 0, 0.8)";
            ctx.fillRect(0, this.canvas.height / 2 - 50, this.canvas.width, 100);
            ctx.fillStyle = "#ffd400";
            ctx.font = "bold 40px Oswald, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(this.goalMessage, this.canvas.width / 2, this.canvas.height / 2);
            ctx.restore();
        }
    }

    drawJersey(ctx, b, now) {
        const teamName = this.teams[b.team] || "Argentina";
        const kit = TEAMS_DATABASE[teamName] || TEAMS_DATABASE["Argentina"];

        ctx.save();

        // 1. Efecto Campo Magnético
        if (now < this.campoUntil[b.team]) {
            ctx.strokeStyle = "rgba(50, 240, 160, 0.85)";
            ctx.lineWidth = 3;
            ctx.shadowColor = "#35e4c2";
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r + 7 + Math.sin(now * 12) * 2, 0, Math.PI * 2);
            ctx.stroke();
            ctx.shadowBlur = 0;
        }

        // 2. Efecto Fuego seleccionado
        if (this.fireSelected[b.team] === b) {
            ctx.strokeStyle = "rgba(255, 75, 0, 0.9)";
            ctx.lineWidth = 4;
            ctx.shadowColor = "#ff2200";
            ctx.shadowBlur = 14;
            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r + 6, 0, Math.PI * 2);
            ctx.stroke();
            ctx.shadowBlur = 0;
        }

        // 3. Anillo de tiro disponible
        if (this.canShoot(b.team, b.keeper) && !this.fireSelected[b.team]) {
            ctx.strokeStyle = "rgba(56, 239, 125, 0.7)";
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r + 4, 0, Math.PI * 2);
            ctx.stroke();
        }

        // 4. Sombra de chapa
        ctx.fillStyle = "rgba(4, 25, 12, 0.5)";
        ctx.beginPath();
        ctx.arc(b.x + 2, b.y + 3, b.r, 0, Math.PI * 2);
        ctx.fill();

        // 5. Base circular recortada para pintar el patrón
        ctx.save();
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.clip();

        // Color base
        if (b.keeper) {
            ctx.fillStyle = (b.team === 0) ? "#b6ff00" : "#ff4fd8";
        } else {
            ctx.fillStyle = kit.c1;
        }
        ctx.fillRect(b.x - b.r, b.y - b.r, b.r * 2, b.r * 2);

        // Patrón vectorial sobre la ficha
        if (!b.keeper) {
            ctx.fillStyle = kit.c2;
            const pat = kit.pat;

            if (pat === "vstripes") {
                const w = (b.r * 2) / 5;
                ctx.fillRect(b.x - b.r + w, b.y - b.r, w, b.r * 2);
                ctx.fillRect(b.x - b.r + w * 3, b.y - b.r, w, b.r * 2);
            } else if (pat === "sash") {
                ctx.save();
                ctx.translate(b.x, b.y);
                ctx.rotate(Math.PI / 4);
                ctx.fillRect(-b.r * 0.35, -b.r * 1.5, b.r * 0.7, b.r * 3);
                ctx.restore();
            } else if (pat === "half") {
                ctx.fillRect(b.x, b.y - b.r, b.r, b.r * 2);
            } else if (pat === "chestband") {
                if (kit.extra) {
                    const bh = b.r * 0.35;
                    for (let k = 0; k < kit.extra.length; k++) {
                        ctx.fillStyle = kit.extra[k];
                        ctx.fillRect(b.x - b.r, b.y - b.r * 0.5 + k * bh, b.r * 2, bh);
                    }
                } else {
                    ctx.fillRect(b.x - b.r, b.y - b.r * 0.35, b.r * 2, b.r * 0.7);
                }
            } else if (pat === "checks") {
                const s = b.r * 0.5;
                for (let i = 0; i < 4; i++) {
                    for (let j = 0; j < 4; j++) {
                        if ((i + j) % 2) {
                            ctx.fillRect(b.x - b.r + i * s, b.y - b.r + j * s, s, s);
                        }
                    }
                }
            } else if (pat === "hoops") {
                const h = (b.r * 2) / 5;
                ctx.fillRect(b.x - b.r, b.y - b.r + h, b.r * 2, h);
                ctx.fillRect(b.x - b.r, b.y - b.r + h * 3, b.r * 2, h);
            } else if (pat === "cross") {
                ctx.fillRect(b.x - b.r * 0.25, b.y - b.r, b.r * 0.5, b.r * 2);
                ctx.fillRect(b.x - b.r, b.y - b.r * 0.25, b.r * 2, b.r * 0.5);
            }
        } else {
            // Franja negra del arquero
            ctx.fillStyle = "#111111";
            ctx.fillRect(b.x - b.r, b.y - b.r * 0.2, b.r * 2, b.r * 0.4);
        }

        ctx.restore(); // Termina clip

        // Borde de la chapa
        ctx.strokeStyle = kit.edge;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.stroke();

        // Dorsal
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 9px Oswald, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.shadowColor = "#000000";
        ctx.shadowBlur = 3;
        ctx.fillText(b.num.toString(), b.x, b.y);

        ctx.restore();
    }

    renderHUD() {
        const ctx = this.ctx;
        ctx.save();
        ctx.fillStyle = "rgba(6, 30, 20, 0.92)";
        ctx.fillRect(0, 0, this.canvas.width, 38);

        ctx.fillStyle = "#ffd400";
        ctx.font = "bold 18px Oswald, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const t0 = this.teams[0].toUpperCase();
        const t1 = this.teams[1].toUpperCase();
        const scoreText = `${t0}  ${this.score[0]} - ${this.score[1]}  ${t1}`;
        ctx.fillText(scoreText, this.canvas.width / 2, 19);

        // Turno
        ctx.font = "12px Outfit, sans-serif";
        ctx.textAlign = "left";
        const ready = this.canShoot(0);
        ctx.fillStyle = ready ? "#38ef7d" : "#ff9f3c";
        ctx.fillText(ready ? "🟢 ¡TIRA!" : "⏳ Recargando...", 16, 19);

        ctx.textAlign = "right";
        const modeLabel = (this.matchType === 'online') ? `🌐 En Línea (PIN: ${this.roomCode || '---'})` :
                          (this.matchType === 'local') ? "👥 2P Local" : "🤖 vs CPU";
        ctx.fillStyle = "#95b8a5";
        ctx.fillText(modeLabel, this.canvas.width - 16, 19);
        ctx.restore();
    }

    renderAbilityBar() {
        const ctx = this.ctx;
        const now = performance.now() / 1000;
        const barH = 55;
        const startY = this.canvas.height - barH;
        const slotW = this.canvas.width / 4;

        ctx.save();
        ctx.fillStyle = "rgba(4, 22, 14, 0.95)";
        ctx.fillRect(0, startY, this.canvas.width, barH);
        ctx.strokeStyle = "rgba(56, 239, 125, 0.2)";
        ctx.lineWidth = 1;
        ctx.strokeRect(0, startY, this.canvas.width, barH);

        const team = (this.matchType === 'online') ? this.localPlayerIdx : 0;

        const abilities = [
            { name: "FUEGO", icon: "🔥", color: "#ff6a00", readyAt: this.fireReadyAt[team], cd: FIRE_RECHARGE, active: this.fireArmed[team] },
            { name: "PAUSA", icon: "⏸", color: "#38b6ff", readyAt: this.pausaReadyAt[team], cd: PAUSA_RECHARGE, active: now < this.pausaUntil },
            { name: "CAMPO", icon: "⚡", color: "#35e4c2", readyAt: this.campoReadyAt[team], cd: CAMPO_RECHARGE, active: now < this.campoUntil[team] },
            { name: "RESERVA", icon: "🔒", color: "#6a7b72", readyAt: 0, cd: 0, active: false }
        ];

        for (let i = 0; i < 4; i++) {
            const ab = abilities[i];
            const cx = (i + 0.5) * slotW;
            const cy = startY + barH / 2;
            const r = 20;

            // Círculo base del botón
            ctx.fillStyle = ab.active ? ab.color : "#0b3422";
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = ab.active ? "#ffffff" : "rgba(255,255,255,0.4)";
            ctx.lineWidth = ab.active ? 3 : 1.5;
            ctx.stroke();

            // Ícono
            ctx.fillStyle = ab.active ? "#111111" : "#ffffff";
            ctx.font = "16px Oswald, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(ab.icon, cx, cy);

            // Cooldown circular
            if (now < ab.readyAt) {
                const remaining = ab.readyAt - now;
                const frac = remaining / ab.cd;

                ctx.fillStyle = "rgba(7, 27, 19, 0.75)";
                ctx.beginPath();
                ctx.arc(cx, cy, r, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 3;
                ctx.beginPath();
                ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (1 - frac));
                ctx.stroke();

                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 13px Oswald, sans-serif";
                ctx.fillText(Math.ceil(remaining).toString(), cx, cy);
            }

            // Letra 'i' de información en la esquina
            if (i < 3) {
                const ix = cx + 18, iy = cy - 16;
                ctx.fillStyle = "#2ec5ff";
                ctx.beginPath();
                ctx.arc(ix, iy, 7, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = "#ffffff";
                ctx.font = "bold 9px sans-serif";
                ctx.fillText("i", ix, iy);
            }
        }
        ctx.restore();
    }

    renderInfoPanel(slot) {
        const ctx = this.ctx;
        const infoData = [
            { title: "FUEGO", lines: ["Potencia máx: +50%", "Cámara lenta: 50%", "Atraviesa todas las fichas", "Recarga: 20 s", "Arquero rival puede bloquear"] },
            { title: "PAUSA", lines: ["Velocidad del juego: 15%", "Duración: 2.0 s", "Recarga: 20 s", "Permite apuntar con calma"] },
            { title: "CAMPO MAGNÉTICO", lines: ["Escudo protector: 12 s", "Repele al rival con 60% energía", "Aturde rivales al contacto", "Recarga: 30 s"] }
        ];

        const data = infoData[slot];
        if (!data) return;

        const pw = Math.min(this.canvas.width * 0.85, 300);
        const ph = 145;
        const px = Math.min(Math.max(10, (slot + 0.5) * (this.canvas.width / 4) - pw / 2), this.canvas.width - pw - 10);
        const py = this.canvas.height - 65 - ph;

        ctx.save();
        ctx.fillStyle = "rgba(6, 40, 58, 0.96)";
        ctx.strokeStyle = "#2ec5ff";
        ctx.lineWidth = 2;
        ctx.fillRect(px, py, pw, ph);
        ctx.strokeRect(px, py, pw, ph);

        ctx.fillStyle = "#2ec5ff";
        ctx.font = "bold 16px Oswald, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(data.title, px + 14, py + 22);

        ctx.fillStyle = "#ffffff";
        ctx.font = "12px Outfit, sans-serif";
        for (let i = 0; i < data.lines.length; i++) {
            ctx.fillText("• " + data.lines[i], px + 14, py + 48 + i * 20);
        }
        ctx.restore();
    }

    loop(t) {
        const dt = (t - this.lastTime) / 1000;
        this.lastTime = t;

        this.updatePhysics(dt);
        this.render();

        requestAnimationFrame((time) => this.loop(time));
    }
}

// Inicialización global
window.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    if (canvas) {
        window.mundialitoGame = new GameEngine(canvas);
    }
});
