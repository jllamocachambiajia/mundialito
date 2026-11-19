/**
 * MUNDIALITO WEB ENGINE (Canvas HTML5 + WebSockets)
 * Física en tiempo real, colisiones elásticas, rebote de bandas y multijugador online.
 */

// Dimensiones de la cancha lógica (idénticas a main.py)
const FX0 = 60, FY0 = 80, FX1 = 1040, FY1 = 680;
const MY = (FY0 + FY1) / 2;
const GOAL_H = 140;
const GY0 = MY - GOAL_H / 2;
const GY1 = MY + GOAL_H / 2;
const GD = 45;

const PR = 18; // Radio jugador
const BR = 11; // Radio balón
const PM = 3.0; // Masa jugador
const BM = 1.0; // Masa balón
const FRICTION = 0.985;
const PLAYER_FRICTION = 0.982;
const MAX_DRAG = 160;
const POWER = 0.14;
const COOLDOWN = 1.0;

const FORMATION = [
    { x: 0.04, y: 0.5, keeper: true },
    { x: 0.18, y: 0.3, keeper: false },
    { x: 0.18, y: 0.7, keeper: false },
    { x: 0.32, y: 0.38, keeper: false },
    { x: 0.32, y: 0.62, keeper: false },
    { x: 0.44, y: 0.5, keeper: false }
];

const TEAMS_INFO = {
    "Argentina": { c1: "#75aadb", c2: "#ffffff", border: "#f4b41a" },
    "Brasil": { c1: "#ffd800", c2: "#009b3a", border: "#002776" },
    "Alemania": { c1: "#ffffff", c2: "#111111", border: "#dd0000" },
    "Francia": { c1: "#002654", c2: "#ffffff", border: "#ed2939" },
    "España": { c1: "#c60b1e", c2: "#ffc400", border: "#ffc400" },
    "Italia": { c1: "#0047ab", c2: "#ffffff", border: "#ffffff" },
    "Portugal": { c1: "#d40000", c2: "#006600", border: "#ffd800" },
    "Uruguay": { c1: "#5c9cd8", c2: "#ffffff", border: "#111111" }
};

// Generador de audio Web Audio API
class SoundFX {
    constructor() {
        this.ctx = null;
    }
    init() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
    }
    kick() {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.frequency.setValueAtTime(140, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(30, this.ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.3, this.ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.12);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.12);
    }
    whistle() {
        if (!this.ctx) return;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.frequency.setValueAtTime(2200, this.ctx.currentTime);
        gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, this.ctx.currentTime + 0.25);
        osc.start();
        osc.stop(this.ctx.currentTime + 0.25);
    }
    goal() {
        if (!this.ctx) return;
        this.whistle();
        setTimeout(() => this.whistle(), 300);
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
    }
}

class GameEngine {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.sound = new SoundFX();

        // Estado del juego
        this.mode = 'menu'; // 'menu', 'match'
        this.matchType = 'local'; // 'local', 'cpu', 'online'
        this.localPlayerIdx = 0; // 0 = Team 0, 1 = Team 1
        this.teams = ["Argentina", "Brasil"];
        this.score = [0, 0];
        this.clock = 0;
        this.nextShotAt = [0, 0];
        this.kickTeam = null;

        // Entidades
        this.bodies = [];
        this.ball = null;

        // Drag e input
        this.drag = null;
        this.dragPos = { x: 0, y: 0 };
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;

        // Efectos
        this.goalMessage = "";
        this.goalUntil = 0;

        // WebSocket
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
        this.canvas.height = Math.min(rect.width * 0.65, window.innerHeight * 0.7);

        const worldW = (FX1 + GD + 20) - (FX0 - GD - 20);
        const worldH = (FY1 + 20) - (FY0 - 20);
        this.scale = Math.min(this.canvas.width / worldW, this.canvas.height / worldH) * 0.94;
        this.offsetX = (this.canvas.width - worldW * this.scale) / 2 - (FX0 - GD - 20) * this.scale;
        this.offsetY = (this.canvas.height - worldH * this.scale) / 2 - (FY0 - 20) * this.scale;
    }

    toWorld(sx, sy) {
        return {
            x: (sx - this.offsetX) / this.scale,
            y: (sy - this.offsetY) / this.scale
        };
    }

    resetPositions() {
        this.bodies = [];
        // Equipo 0 (Izquierda)
        for (let i = 0; i < FORMATION.length; i++) {
            const f = FORMATION[i];
            const x = FX0 + f.x * (FX1 - FX0);
            const y = FY0 + f.y * (FY1 - FY0);
            this.bodies.push(new Body(x, y, PR, PM, 0, f.keeper, f.keeper ? 1 : 10 - i));
        }
        // Equipo 1 (Derecha)
        for (let i = 0; i < FORMATION.length; i++) {
            const f = FORMATION[i];
            const x = FX0 + (1 - f.x) * (FX1 - FX0);
            const y = FY0 + f.y * (FY1 - FY0);
            this.bodies.push(new Body(x, y, PR, PM, 1, f.keeper, f.keeper ? 1 : 10 - i));
        }
        // Balón
        this.ball = new Body((FX0 + FX1) / 2, MY, BR, BM, null);
        this.bodies.push(this.ball);
        this.drag = null;
    }

    canShoot(team) {
        const now = performance.now() / 1000;
        if (this.kickTeam !== null) return team === this.kickTeam;
        return now >= this.nextShotAt[team];
    }

    shoot(body, vx, vy) {
        body.vx = vx;
        body.vy = vy;
        this.sound.kick();
        const now = performance.now() / 1000;
        this.nextShotAt[body.team] = now + COOLDOWN;
        this.kickTeam = null;
    }

    startLocalMatch(team0 = "Argentina", team1 = "Brasil") {
        this.sound.init();
        this.matchType = 'local';
        this.teams = [team0, team1];
        this.score = [0, 0];
        this.clock = 0;
        this.resetPositions();
        this.mode = 'match';
        this.sound.whistle();
    }

    startCpuMatch(team0 = "Argentina", team1 = "Alemania") {
        this.sound.init();
        this.matchType = 'cpu';
        this.teams = [team0, team1];
        this.score = [0, 0];
        this.clock = 0;
        this.resetPositions();
        this.mode = 'match';
        this.sound.whistle();
    }

    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return;
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${window.location.host}`);

        this.ws.onopen = () => {
            this.onlineStatus = "Conectado al VPS";
            if (this.searching) {
                this.ws.send(JSON.stringify({ action: 'quick_match', team: this.teams[0] }));
            }
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

        this.ws.onerror = () => {
            this.onlineStatus = "Error de conexión";
            this.searching = false;
        };
    }

    searchOnlineMatch() {
        this.sound.init();
        this.searching = true;
        this.onlineStatus = "Buscando oponente en línea...";
        this.connectWebSocket();
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'quick_match', team: "Argentina" }));
        }
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
        } else if (msg.action === 'sync') {
            if (this.localPlayerIdx === 1 && this.ball) {
                const [bx, by, bvx, bvy] = msg.ball;
                this.ball.x = bx;
                this.ball.y = by;
                this.ball.vx = bvx;
                this.ball.vy = bvy;
                this.score = msg.score;
            }
        } else if (msg.type === 'opponent_disconnected') {
            this.goalMessage = "¡RIVAL DESCONECTADO!";
            this.goalUntil = performance.now() + 4000;
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
            if (this.mode !== 'match') return;
            const pos = getCanvasCoords(e);
            const w = this.toWorld(pos.x, pos.y);

            let best = null, bestDist = PR * 2.2;
            for (const b of this.bodies) {
                if (b.team === null) continue;
                // En local: se puede tocar cualquier equipo
                // En online: solo el equipo local
                // En cpu: solo equipo 0
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

            if (best && this.canShoot(best.team)) {
                this.drag = best;
                this.dragPos = w;
            }
        };

        const onMove = (e) => {
            if (!this.drag) return;
            const pos = getCanvasCoords(e);
            this.dragPos = this.toWorld(pos.x, pos.y);
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

                // Transmitir disparo en red si es online
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

    updatePhysics(dt) {
        if (this.mode !== 'match') return;

        // Fricción y movimiento
        for (const b of this.bodies) {
            b.x += b.vx;
            b.y += b.vy;
            const f = (b.team === null) ? FRICTION : PLAYER_FRICTION;
            b.vx *= f;
            b.vy *= f;
            if (Math.hypot(b.vx, b.vy) < 0.03) {
                b.vx = 0;
                b.vy = 0;
            }
        }

        // Rebotes en paredes
        for (const b of this.bodies) {
            // Límites superior e inferior
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
                    // Portería izquierda (GOL de Equipo 1 si entra el balón)
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
                    // Portería derecha (GOL de Equipo 0 si entra el balón)
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

        // Colisiones elásticas entre cuerpos
        for (let i = 0; i < this.bodies.length; i++) {
            for (let j = i + 1; j < this.bodies.length; j++) {
                const a = this.bodies[i];
                const b = this.bodies[j];
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dist = Math.hypot(dx, dy);
                const minDist = a.r + b.r;

                if (dist < minDist && dist > 0) {
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

        // IA simple si es vs CPU
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

        // Apuntar balón hacia portería rival
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
        this.kickTeam = 1 - team; // Saca el que recibió el gol
        this.resetPositions();
    }

    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        ctx.save();
        ctx.translate(this.offsetX, this.offsetY);
        ctx.scale(this.scale, this.scale);

        // 1. Cancha de césped con franjas
        ctx.fillStyle = "#0c5a2c";
        ctx.fillRect(FX0 - GD - 10, FY0 - 10, (FX1 - FX0) + (GD * 2) + 20, (FY1 - FY0) + 20);

        ctx.fillStyle = "#0f6c35";
        const stripeW = (FX1 - FX0) / 10;
        for (let i = 0; i < 10; i += 2) {
            ctx.fillRect(FX0 + i * stripeW, FY0, stripeW, FY1 - FY0);
        }

        // Líneas blancas de la cancha
        ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
        ctx.lineWidth = 3.5;

        // Borde exterior
        ctx.strokeRect(FX0, FY0, FX1 - FX0, FY1 - FY0);

        // Línea central
        const midX = (FX0 + FX1) / 2;
        ctx.beginPath();
        ctx.moveTo(midX, FY0);
        ctx.lineTo(midX, FY1);
        ctx.stroke();

        // Círculo central
        ctx.beginPath();
        ctx.arc(midX, MY, 75, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(midX, MY, 4, 0, Math.PI * 2);
        ctx.fill();

        // Áreas grandes
        ctx.strokeRect(FX0, MY - 150, 150, 300);
        ctx.strokeRect(FX1 - 150, MY - 150, 150, 300);

        // Porterías
        ctx.strokeRect(FX0 - GD, GY0, GD, GOAL_H);
        ctx.strokeRect(FX1, GY0, GD, GOAL_H);

        // 2. Dibujar cuerpos
        for (const b of this.bodies) {
            if (b.team === null) {
                // Balón de fútbol
                ctx.save();
                ctx.fillStyle = "#ffffff";
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = "#111111";
                ctx.lineWidth = 1.5;
                ctx.stroke();
                // Pentágono interior
                ctx.fillStyle = "#111111";
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r * 0.45, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            } else {
                // Chapita de jugador
                const teamName = this.teams[b.team] || "Argentina";
                const info = TEAMS_INFO[teamName] || { c1: "#ffffff", c2: "#111111", border: "#ffd800" };

                ctx.save();
                // Anillo de selección si está listo para tirar
                if (this.canShoot(b.team)) {
                    ctx.strokeStyle = "rgba(56, 239, 125, 0.7)";
                    ctx.lineWidth = 2.5;
                    ctx.beginPath();
                    ctx.arc(b.x, b.y, b.r + 4, 0, Math.PI * 2);
                    ctx.stroke();
                }

                // Cuerpo de la chapa
                ctx.fillStyle = info.c1;
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = info.border;
                ctx.lineWidth = 2.5;
                ctx.stroke();

                // Detalle central
                ctx.fillStyle = info.c2;
                ctx.beginPath();
                ctx.arc(b.x, b.y, b.r * 0.55, 0, Math.PI * 2);
                ctx.fill();

                // Dorsal
                ctx.fillStyle = (info.c2 === "#ffffff") ? "#111111" : "#ffffff";
                ctx.font = "bold 9px Oswald, sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(b.num.toString(), b.x, b.y);

                ctx.restore();
            }
        }

        // Flecha de disparo (drag)
        if (this.drag) {
            const p = this.drag;
            const dx = p.x - this.dragPos.x;
            const dy = p.y - this.dragPos.y;
            const dist = Math.hypot(dx, dy);

            if (dist > 8) {
                const pull = Math.min(dist, MAX_DRAG);
                const powerRatio = pull / MAX_DRAG;

                ctx.save();
                ctx.strokeStyle = `rgba(255, ${Math.floor(255 * (1 - powerRatio))}, 0, 0.9)`;
                ctx.lineWidth = 4;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p.x + dx * (pull / dist), p.y + dy * (pull / dist));
                ctx.stroke();

                // Círculo de potencia
                ctx.fillStyle = `rgba(255, ${Math.floor(200 * (1 - powerRatio))}, 0, 0.4)`;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r + pull * 0.25, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }
        }

        ctx.restore();

        // 3. Marcador y HUD superior
        this.renderHUD();

        // Cartel de Gol flotante
        if (performance.now() < this.goalUntil && this.goalMessage) {
            ctx.save();
            ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
            ctx.fillRect(0, this.canvas.height / 2 - 50, this.canvas.width, 100);
            ctx.fillStyle = "#ffd400";
            ctx.font = "bold 38px Oswald, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(this.goalMessage, this.canvas.width / 2, this.canvas.height / 2);
            ctx.restore();
        }
    }

    renderHUD() {
        const ctx = this.ctx;
        ctx.save();
        ctx.fillStyle = "rgba(6, 30, 20, 0.88)";
        ctx.fillRect(0, 0, this.canvas.width, 42);

        ctx.fillStyle = "#ffd400";
        ctx.font = "bold 18px Oswald, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        const t0 = this.teams[0].toUpperCase();
        const t1 = this.teams[1].toUpperCase();
        const scoreText = `${t0}  ${this.score[0]} - ${this.score[1]}  ${t1}`;
        ctx.fillText(scoreText, this.canvas.width / 2, 21);

        // Estado del turno / recarga
        ctx.font = "13px Outfit, sans-serif";
        ctx.textAlign = "left";
        const teamTurn = this.canShoot(0) ? "🟢 Equipo 1 Listo" : "⏳ Recargando...";
        ctx.fillStyle = this.canShoot(0) ? "#38ef7d" : "#ff9f3c";
        ctx.fillText(teamTurn, 16, 21);

        ctx.textAlign = "right";
        const modeLabel = (this.matchType === 'online') ? `🌐 En Línea (PIN: ${this.roomCode || '---'})` :
                          (this.matchType === 'local') ? "👥 2 Jugadores Local" : "🤖 vs CPU";
        ctx.fillStyle = "#95b8a5";
        ctx.fillText(modeLabel, this.canvas.width - 16, 21);
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

// Inicializar motor en la ventana
window.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('game-canvas');
    if (canvas) {
        window.mundialitoGame = new GameEngine(canvas);
    }
});
