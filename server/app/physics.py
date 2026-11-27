"""Física copiada SIN CAMBIOS del motor Kivy (main.py v11): Body, walls, collide, step.
No importa Kivy; corre en el VPS (ARM64/x86) como única autoridad."""
import math

FX0, FY0, FX1, FY1 = 60, 80, 1040, 680
MY = (FY0 + FY1) / 2
GOAL_H = 140
GY0, GY1 = MY - GOAL_H / 2, MY + GOAL_H / 2
GD = 40
PR, BR = 18, 10
PM, BM = 3.0, 1.0
FRICTION = 0.985
PLAYER_FRICTION = 1 - (1 - FRICTION) / 0.85
SUB = 4
MAX_DRAG = 160
POWER = 0.14
GK_POWER = 0.50
BIG_W, BIG_H = 150, 150
FORMATION = [(0.04, 0.5), (0.18, 0.3), (0.18, 0.7), (0.32, 0.38), (0.32, 0.62), (0.44, 0.5)]


class Body:
    def __init__(self, x, y, r, m, team=None, keeper=False, num=0):
        self.x, self.y, self.vx, self.vy = x, y, 0.0, 0.0
        self.r, self.m, self.team, self.keeper, self.num = r, m, team, keeper, num

    def speed(self):
        return math.hypot(self.vx, self.vy)


def walls(b, is_ball, goal=None):
    gy0, gy1, depth = (GY0, GY1, GD) if goal is None else goal
    if b.y - b.r < FY0 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY0 + b.r; b.vy = -b.vy * 0.8
    if b.y + b.r > FY1 and not (is_ball and (b.x < FX0 or b.x > FX1)):
        b.y = FY1 - b.r; b.vy = -b.vy * 0.8
    in_goal = is_ball and gy0 < b.y < gy1
    for side in (-1, 1):
        line = FX0 if side < 0 else FX1
        past = (b.x - b.r < line) if side < 0 else (b.x + b.r > line)
        if not past:
            continue
        if in_goal:
            back = line - depth if side < 0 else line + depth
            if side < 0 and b.x - b.r < back:
                b.x = back + b.r; b.vx = -b.vx * 0.3
            if side > 0 and b.x + b.r > back:
                b.x = back - b.r; b.vx = -b.vx * 0.3
            if (side < 0 and b.x < line) or (side > 0 and b.x > line):
                if b.y - b.r < gy0: b.y = gy0 + b.r; b.vy = -b.vy * 0.5
                if b.y + b.r > gy1: b.y = gy1 - b.r; b.vy = -b.vy * 0.5
        else:
            b.x = line + b.r if side < 0 else line - b.r
            b.vx = -b.vx * 0.8


def collide(a, b):
    dx, dy = b.x - a.x, b.y - a.y
    d = math.hypot(dx, dy)
    mind = a.r + b.r
    if d == 0 or d >= mind:
        return False
    nx, ny = dx / d, dy / d
    over = mind - d
    ta = b.m / (a.m + b.m)
    a.x -= nx * over * ta; a.y -= ny * over * ta
    b.x += nx * over * (1 - ta); b.y += ny * over * (1 - ta)
    rv = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
    if rv > 0:
        return True
    j = -(1 + 0.92) * rv / (1 / a.m + 1 / b.m)
    a.vx -= j * nx / a.m; a.vy -= j * ny / a.m
    b.vx += j * nx / b.m; b.vy += j * ny / b.m
    return True


def keeper_limit(b):
    """Barrera del área grande, solo para arqueros (v8)."""
    if b.team == 0:
        b.x = min(max(b.x, FX0 + b.r), FX0 + BIG_W)
    else:
        b.x = max(min(b.x, FX1 - b.r), FX1 - BIG_W)
    b.y = min(max(b.y, MY - BIG_H), MY + BIG_H)


def step(bodies, ball, scale=1.0, limit=keeper_limit, collision_policy=None, body_scale=None, on_contact=None):
    """Igual que step() original; on_contact(a, b) avisa contactos (habilidades)."""
    for _ in range(SUB):
        for b in bodies:
            k = scale / SUB
            if body_scale is not None:
                f_b = body_scale(b)
                if f_b == 0.0:
                    b.vx = b.vy = 0.0
                k *= f_b
            b.x += b.vx * k; b.y += b.vy * k
            walls(b, b is ball)
            if limit is not None and b.keeper:
                limit(b)
        for i in range(len(bodies)):
            for k in range(i + 1, len(bodies)):
                a, c = bodies[i], bodies[k]
                if collision_policy is None or collision_policy(a, c):
                    if collide(a, c) and on_contact is not None:
                        on_contact(a, c)
    for b in bodies:
        f = FRICTION if b is ball else PLAYER_FRICTION
        if scale != 1.0:
            f = f ** scale
        b.vx *= f; b.vy *= f
        if b.speed() < 0.06:
            b.vx = b.vy = 0.0


def make_team(team):
    out = []
    for i, (fx, fy) in enumerate(FORMATION):
        x = FX0 + fx * (FX1 - FX0)
        if team == 1:
            x = FX1 - fx * (FX1 - FX0)
        y = FY0 + fy * (FY1 - FY0)
        out.append(Body(x, y, PR, PM, team, keeper=(i == 0), num=1 if i == 0 else i + 1))
    return out


def ball_in_goal(ball):
    """Devuelve el equipo que anota (0/1) o None."""
    if GY0 < ball.y < GY1:
        if ball.x + ball.r < FX0:
            return 1
        if ball.x - ball.r > FX1:
            return 0
    return None
