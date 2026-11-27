"""Emparejamiento (amistoso aleatorio / ranked por ELO) y salas que corren el bucle autoritario."""
import asyncio
import time

from . import config, database
from .match import Match


class Player:
    def __init__(self, ws, row):
        self.ws = ws
        self.key = row["llave_maestra"]
        self.name = row["usuario"]
        self.elo = row["elo"]
        self.team = "Argentina"
        self.room = None
        self.side = None
        self.since = time.time()

    async def send(self, msg):
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass


class Room:
    def __init__(self, mode, p0, p1):
        self.players = [p0, p1]
        self.match = Match(mode, [p0.key, p1.key], [p0.team, p1.team])
        for side, p in enumerate(self.players):
            p.room, p.side = self, side
        self.task = None

    async def run(self):
        m = self.match
        start = {"type": "match_start", "match_id": m.id, "mode": m.mode, "teams": m.teams,
                 "names": [p.name for p in self.players], "elo": [p.elo for p in self.players]}
        for p in self.players:
            await p.send(dict(start, side=p.side))
        dt = 1.0 / config.TICK_HZ
        every = max(1, config.TICK_HZ // config.SNAPSHOT_HZ)
        n = 0
        nxt = time.perf_counter()
        while not m.finished:
            m.update(dt)
            n += 1
            ev = m.pop_events()
            if ev or n % every == 0:
                snap = m.snapshot()
                snap["events"] = ev
                await asyncio.gather(*(p.send(snap) for p in self.players))
            nxt += dt
            await asyncio.sleep(max(0.0, nxt - time.perf_counter()))
        delta = database.save_match(m)
        for p in self.players:
            row = database.account(p.key)
            await p.send({"type": "match_end", "winner": m.winner, "score": m.score,
                          "elo_change": delta if p.side == 0 else -delta,
                          "me": database.public(row), "events": m.pop_events()})
            p.room = None

    def input(self, player, msg):
        kind = msg.get("type")
        if kind == "shoot":
            try:
                self.match.shoot(player.side, int(msg["body"]), float(msg["dx"]), float(msg["dy"]))
            except (KeyError, TypeError, ValueError):
                pass
        elif kind == "ability":
            self.match.ability(player.side, str(msg.get("name")))
        elif kind == "surrender":
            self.match.forfeit(player.side)


class Lobby:
    def __init__(self):
        self.queues = {"amistoso": [], "ranked": []}
        self.rooms = set()

    def remove(self, player):
        for q in self.queues.values():
            if player in q:
                q.remove(player)

    async def enqueue(self, player, mode):
        if mode not in self.queues:
            return
        self.remove(player)
        q = self.queues[mode]
        rival = None
        if mode == "amistoso":
            rival = q[0] if q else None
        else:
            waited = time.time() - player.since
            for other in sorted(q, key=lambda o: abs(o.elo - player.elo)):
                window = 100 + 25 * max(waited, time.time() - other.since)
                if abs(other.elo - player.elo) <= window:
                    rival = other
                    break
        if rival is None:
            player.since = time.time()
            q.append(player)
            await player.send({"type": "queued", "mode": mode, "waiting": len(q)})
            return
        q.remove(rival)
        room = Room(mode, rival, player)
        self.rooms.add(room)
        room.task = asyncio.create_task(self._run(room))

    async def _run(self, room):
        try:
            await room.run()
        finally:
            self.rooms.discard(room)

    async def retry_ranked(self):
        """Amplía la ventana de ELO con el tiempo de espera."""
        while True:
            await asyncio.sleep(3)
            q = self.queues["ranked"]
            if len(q) >= 2:
                p = q.pop(0)
                await self.enqueue(p, "ranked")
