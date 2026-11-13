"""Match-only MODO FURIA latch and goal-directed fire planning."""
import math

ENHANCED_COOLDOWN = .4                 # MODO FURIA: recarga para mover chapitas de la CPU
FURY_FIRE_RECHARGE = {2: 25.0, 3: 40.0}   # semifinal / final, solo CPU en MODO FURIA

def difficulty_threshold(stage):
    return 1 if stage == 3 else 3

class RivalAI:
    def ai_reset(self):
        self.ai_enhanced = False

    def ai_hard(self):
        return self.state == 'match' and getattr(self, 'ai_enhanced', False)

    def ai_update_difficulty(self):
        if self.state != 'match' or self.ai_enhanced or self.score[0] < difficulty_threshold(self.round):
            return
        from main import vnow
        self.ai_enhanced = True
        self.flash('¡MODO FURIA RIVAL!', 1.6)
        now = vnow()
        self.next_shot_at[1] = min(self.next_shot_at[1], now + ENHANCED_COOLDOWN)
        self.ai_at = min(self.ai_at, self.next_shot_at[1])

    def ai_fire_recharge(self):
        """CPU fire recharge: normal per-round table, FURIA overrides semis/final."""
        from fire import AI_RECHARGE
        if self.ai_hard() and self.round in FURY_FIRE_RECHARGE:
            return FURY_FIRE_RECHARGE[self.round]
        return AI_RECHARGE[self.round]

    def ai_fire_plan(self, field):
        """Only accept the trajectory actually produced by disc-to-ball transfer.

        Aiming at a contact offset with an arbitrary disc used to send fire sideways.
        Aim through the predicted ball centre; validate its projected direct/bank path.
        """
        from main import FX0, FY0, FY1, GY0, GY1, MY, BR, PR, MAX_DRAG, POWER, PLAYER_FRICTION
        from fire import POWER_FACTOR
        ball = self.ball
        cap = MAX_DRAG * POWER * POWER_FACTOR
        keeper = next((p for p in self.bodies if p.team == 0 and p.keeper), None)
        plans = []
        for p in field:
            bx, by = ball.x, ball.y
            for _ in range(3):
                distance = math.hypot(bx-p.x, by-p.y)
                frames = max(0, distance-PR-BR) / cap
                bx, by = self.predict(ball, min(22, frames))
            dx, dy = bx-p.x, by-p.y
            distance = math.hypot(dx, dy)
            reach_limit = 320 if self.ai_hard() else 260
            if not 0 < distance < reach_limit or dx >= -distance*.3:
                continue
            # Unfold the touchline reflection; a bank must still finish inside goal.
            height = FY1-FY0-2*BR
            projected = by + dy/dx*(FX0-bx)
            folded = (projected-(FY0+BR)) % (2*height)
            gy = FY0+BR+(folded if folded <= height else 2*height-folded)
            bank = not FY0+BR <= projected <= FY1-BR
            if not GY0+BR+3 < gy < GY1-BR-3:
                continue
            if not bank and dx >= -distance*.55:
                continue                           # direct fire must point at the goal
            path = math.hypot(FX0-bx, projected-by)
            # Enough remaining momentum after the disc approach and optional bank.
            contact_speed = max(0, cap-distance*(1-PLAYER_FRICTION))
            reach = contact_speed*1.44/(1-.985) * (.8 if bank else 1)
            if path > reach*.85:
                continue
            separation = abs(gy-keeper.y) if keeper else abs(gy-MY)
            score = distance + path*.08 - min(separation,100)*.6 + (30 if bank else 0)
            plans.append((score,p,bx,by,gy,bank))
        return min(plans, key=lambda plan:plan[0]) if plans else None

    # ---- Funciones auxiliares que usa ai_shoot() en main.py (faltaban -> cierre al primer disparo)
    def cpu_normal_factor(self):
        return 1.0

    def cpu_fire_factor(self):
        from fire import POWER_FACTOR
        return POWER_FACTOR

    def lead_point(self, m, bx, by):
        """Punto delante del compañero m (la CPU ataca hacia la izquierda)."""
        from main import FX0, FY0, FY1, BR
        x = max(FX0 + 30, m.x - 40)
        y = min(max(m.y + m.vy * 8, FY0 + BR + 5), FY1 - BR - 5)
        return x, y

    def best_forward(self, field, bx, by):
        """Compañero más adelantado (más cerca del arco rival) con línea de pase libre."""
        best, bx_min = None, bx - 40
        for m in field:
            if m.x < bx_min and self.lane_free(bx, by, m.x, m.y, 1):
                best, bx_min = m, m.x
        return best

    def own_blocker(self, bx, by):
        """Compañero detrás del balón (pase atrás) con línea libre."""
        for m in self.bodies:
            if m.team == 1 and not m.keeper and m.x > bx + 30 and self.lane_free(bx, by, m.x, m.y, 1):
                return m
        return None

    def bank_point(self, bx, by, gy):
        """Punto en la banda para un rebote que termine en el arco; None si no sirve."""
        from main import FX0, FY0, FY1, BR
        if bx - FX0 < 60:
            return None
        wall = FY0 + BR if by < (FY0 + FY1) / 2 else FY1 - BR
        d1, d2 = abs(by - wall), abs(gy - wall)
        if d1 + d2 == 0:
            return None
        x = bx - (bx - FX0) * d1 / (d1 + d2)
        return (x, wall) if self.lane_free(bx, by, x, wall, 1) else None

    def push_rival(self, field):
        """Empuja al rival más cercano al balón si un compañero está cerca de él."""
        b = self.ball
        rivals = [p for p in self.bodies if p.team == 0 and not p.keeper]
        if not rivals or not field:
            return False
        r = min(rivals, key=lambda p: math.hypot(p.x - b.x, p.y - b.y))
        p = min(field, key=lambda q: math.hypot(q.x - r.x, q.y - r.y))
        if math.hypot(p.x - r.x, p.y - r.y) > 200:
            return False
        self.strike(p, r.x, r.y, 0, 0.02)
        return True
