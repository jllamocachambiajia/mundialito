"""Match-only difficulty latch and goal-directed fire planning."""
import math

ENHANCED_COOLDOWN = .5

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
        now = vnow()
        self.next_shot_at[1] = min(self.next_shot_at[1], now + ENHANCED_COOLDOWN)
        self.ai_at = min(self.ai_at, self.next_shot_at[1])

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
            if not 0 < distance < 260 or dx >= -distance*.2:
                continue
            # Unfold the touchline reflection; a bank must still finish inside goal.
            height = FY1-FY0-2*BR
            projected = by + dy/dx*(FX0-bx)
            folded = (projected-(FY0+BR)) % (2*height)
            gy = FY0+BR+(folded if folded <= height else 2*height-folded)
            bank = not FY0+BR <= projected <= FY1-BR
            if not GY0+BR+3 < gy < GY1-BR-3:
                continue
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
