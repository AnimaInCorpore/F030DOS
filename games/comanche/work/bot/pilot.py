#!/usr/bin/env python3
"""A rule-based pilot for the Comanche port, flying through hbot.Session.

Reads the game's own state each step and holds keys the way a player would.
"""
import math, sys, time, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hbot import Session, K

TWO32 = 2 ** 32
CELL = 1 << 22


def wrapd(d):
    """Signed difference of two 32-bit map coordinates, in cells."""
    d &= 0xFFFFFFFF
    if d >= 0x80000000:
        d -= TWO32
    return d / CELL


def bearing_err(st, o):
    dx = wrapd(o.x - st.x)
    dy = wrapd(o.y - st.y)
    # forward motion is x += fwd*sin(a), y -= fwd*cos(a)
    want = math.atan2(dx, -dy)
    have = st.angle / TWO32 * 2 * math.pi
    e = (want - have + math.pi) % (2 * math.pi) - math.pi
    return e, math.hypot(dx, dy)


AIR = ('object_state_unit',)


class Pilot:
    kyle = False      # the Cheat column, shown once per program run
    def __init__(self, s, log, notch_target=0x40, cruise=9_000_000):
        self.s = s
        self.log = log
        self.notch_target = notch_target
        self.cruise = cruise
        self.target = None
        self.last_fire = 0
        self.last_cm = 0
        self.last_hull = None
        self.names = {}
        self.hits = 0
        self.flares = 0
        self.cheats = [0, 0]
        self.last_reload = 0
        self.allow_cheat = True
        self.hmap = None
        self.path = None
        self.defend_since = None
        self.no_defend_until = 0
        self.path_for = None
        self.path_at = 0
        self.t_start = time.time()
        self.wait_air = 120

    def note(self, msg):
        print(msg, flush=True)
        self.log.write(msg + "\n"); self.log.flush()

    def kind(self, o):
        if o.state not in self.names:
            self.names[o.state] = self.s.symbol(o.state)
        return self.names[o.state]

    def set_collective(self, st):
        if st.notch < self.notch_target:
            self.s.tap(K['E'], 0.06)
        elif st.notch > self.notch_target + 0x0F:
            self.s.tap(K['D'], 0.06)

    def choose(self, st):
        live = [o for o in st.goals if o.active]
        if not live:
            return None
        def score(o):
            e, d = bearing_err(st, o)
            air = self.kind(o) in AIR
            # a helicopter close enough to shoot at us comes first
            return d - (250 if air and d < 250 else 0)
        return min(live, key=score)

    def countermeasures(self, st):
        # Shells only miss when a flare is already up (000235D4): drop one
        # as soon as an enemy shell is close, not after it has hit.
        now = time.time()
        for o in st.all[30:]:
            if o.active and 'shell' in self.kind(o):
                d = math.hypot(wrapd(o.x - st.x), wrapd(o.y - st.y))
                if d < 90 and now - self.last_cm > 0.5 and st.flare > 0:
                    self.s.tap(K['FLARE'], 0.05)
                    self.last_cm = now
                    self.flares += 1
                    break
        if self.last_hull is not None and st.hull < self.last_hull:
            self.hits += 1
            now = time.time()
            if now - self.last_cm > 1.5:
                self.s.tap(K['FLARE'], 0.06); self.s.tap(K['CHAFF'], 0.06)
                self.last_cm = now
                self.note(f"hit: hull {self.last_hull}->{st.hull}, flare+chaff (flares so far {self.flares})")
            near = []
            for o in st.all:
                if o.active:
                    d = math.hypot(wrapd(o.x - st.x), wrapd(o.y - st.y))
                    if d < 60:
                        near.append(f"#{o.slot}:{self.kind(o).replace('object_state_','')}d{d:.0f}a{o.alt}")
            self.note(f"   alt={st.alt} near: " + " ".join(near))
        self.last_hull = st.hull

    def weapon(self, st, t, air):
        a = st.ammo
        if air:
            for page in (3, 0):
                if a[page] > 0:
                    return page
        else:
            for page in (5, 2, 1, 0):
                if a[page] > 0:
                    return page
        return None

    def cheat(self, row):
        """The shipped KYLE column (00026012): row 0 Fix Damage, 1 Reload."""
        s = self.s
        s.hold(set())
        s.tap(K['ESC'], 0.08); time.sleep(0.6)
        if not self.kyle:
            s.down(K['BS']); time.sleep(0.15)
            for c in (0x25, 0x15, 0x26, 0x12):      # K Y L E
                s.tap(c, 0.06); time.sleep(0.1)
            s.up(K['BS']); time.sleep(0.4)
            Pilot.kyle = True
        # The bar keeps its column and row between openings, so steer by
        # what it says rather than by a fixed count of presses.
        for _ in range(8):
            m = s.state()
            if m.menu_col == 4:
                break
            s.tap(K['RIGHT'], 0.06); time.sleep(0.25)
        for _ in range(4):
            m = s.state()
            if m.menu_row == row:
                break
            s.tap(K['DOWN'] if m.menu_row < row else K['UP'], 0.06); time.sleep(0.25)
        m = s.state()
        if m.menu_col != 4 or m.menu_row != row:
            self.note(f"cheat: bar at column {m.menu_col} row {m.menu_row}, not pressing")
            s.tap(K['ESC'], 0.08); time.sleep(0.6)
            return
        s.tap(K['RET'], 0.06); time.sleep(0.8)
        s.tap(K['BS'], 0.06); time.sleep(0.4)       # any key closes the box
        s.tap(K['ESC'], 0.08); time.sleep(0.6)
        st = s.state()
        if st and st.menu:
            s.tap(K['ESC'], 0.08); time.sleep(0.6)
        self.cheats[row] += 1
        self.note(f"cheat {'Fix Damage' if row == 0 else 'Reload'} (#{self.cheats[row]}): {s.state().summary()}")

    def notch_to(self, st, target):
        """Step the collective notch toward target with E / D (00001BA6)."""
        if st.notch < target:
            self.s.tap(K['E'], 0.05)
        elif st.notch > target:
            self.s.tap(K['D'], 0.05)

    def fire(self, st, t, air, dist):
        now = time.time()
        page = self.weapon(st, t, air)
        if page is None:
            return
        if page == 0 and dist > 70:
            return
        gap = 0.6 if page == 0 else 1.6
        if now - self.last_fire > gap:
            if st.page != page:
                self.s.tap([K['Z'], K['X'], K['C'], K['V'], K['B'], K['N']][page], 0.05)
            self.s.tap(K['SPACE'], 0.5 if page == 0 else 0.1)
            self.last_fire = now
            self.note(f"fire p{page} at #{t.slot} hp={t.health} d={dist:.0f} ammo={st.ammo} hull={st.hull}")

    def step(self, st):
        if self.allow_cheat and st.hull < 22:
            self.cheat(0)
            return 'repaired'
        ground_dry = st.ammo[1] == 0 and st.ammo[2] == 0 and st.ammo[5] == 0
        air_dry = st.ammo[3] == 0 and st.ammo[0] < 40
        if self.allow_cheat and time.time() - self.last_reload > 20 and (
                st.fuel < 2500 or ground_dry or air_dry):
            self.last_reload = time.time()
            self.cheat(1)
            return 'reloaded'
        self.countermeasures(st)
        live = [o for o in st.goals if o.active]
        if not live:
            self.s.hold(set())
            return 'done'
        air = [o for o in live if self.kind(o) in AIR]
        # any patrol helicopter is a threat, a mission goal or not
        hostile = [o for o in st.objs if o.active and self.kind(o) in AIR]
        threats = [o for o in hostile if bearing_err(st, o)[1] < 200]
        now = time.time()
        if threats and now > self.no_defend_until:
            if self.defend_since is None:
                self.defend_since = now
            if now - self.defend_since > 45 and now - self.last_fire > 45:
                # a stand-off nobody breaks: go after the goals for a while
                self.no_defend_until = now + 60
                self.defend_since = None
                self.note("defence stalled; hunting for 60 s")
            else:
                return self.defend(st, threats)
        else:
            self.defend_since = None
        if air and time.time() - self.t_start < self.wait_air:
            # the patrol is still up: let it come to us, sitting on the pad
            self.s.hold({K['KP2']} if st.fwd > 1_000_000 else set())
            self.notch_to(st, 0x00)
            return f"wait for the patrol ({len(air)} up)"
        return self.hunt(st, live)

    def defend(self, st, threats):
        """Sit on the ground facing the patrol; shoot whatever comes into view."""
        t = min(threats, key=lambda o: bearing_err(st, o)[1])
        e, dist = bearing_err(st, t)
        deg = math.degrees(e)
        landed = st.coll <= 6 and st.alt <= 2 * self.ground(st) + 7
        # a locked, visible helicopter: shoot it, wherever we are
        vis = [o for o in threats if o.targetable]
        if vis:
            v = min(vis, key=lambda o: bearing_err(st, o)[1])
            if st.lock != v.slot:
                self.s.tap(K['TAB'], 0.05)
            else:
                dv = bearing_err(st, v)[1]
                if dv < 180:
                    self.fire(st, v, True, dv)
        if abs(deg) > 30:
            # turn to face it: lift off, turn, then sit down again
            self.notch_to(st, 0x10)
            keys = {K['KP6'] if deg > 0 else K['KP4']}
            if st.fwd > 1_000_000:
                keys.add(K['KP2'])
            self.s.hold(keys)
            return f"turn to #{t.slot} e={deg:+.0f} d={dist:.0f}"
        self.s.hold({K['KP2']} if st.fwd > 1_000_000 else set())
        self.notch_to(st, 0x00)
        return f"hold vs #{t.slot} e={deg:+.0f} d={dist:.0f} landed={landed}"

    def ground(self, st):
        if self.hmap is None:
            return 0
        return self.hmap[((st.y >> 22) << 10) | (st.x >> 22)]

    def build_grid(self):
        """8x8-cell blocks the terrain follow cannot climb: byte(2h + 1) near
        the altitude byte's ceiling (h about 104-127; above 127 it wraps low)."""
        B = 128
        self.wall = bytearray(B * B)
        hm = self.hmap
        for by in range(B):
            for bx in range(B):
                worst = 0
                for y in range(by * 8, by * 8 + 8):
                    row = hm[y * 1024 + bx * 8: y * 1024 + bx * 8 + 8]
                    for h in row:
                        if 104 <= h < 128:
                            worst = 1; break
                    if worst:
                        break
                self.wall[by * B + bx] = worst

    def route(self, sx, sy, tx, ty):
        """A* over the 128x128 block grid (toroidal); returns block waypoints."""
        import heapq
        B = 128
        start = ((int(sx) >> 3) & 127, (int(sy) >> 3) & 127)
        goal = ((int(tx) >> 3) & 127, (int(ty) >> 3) & 127)
        def hdist(a):
            dx = min(abs(a[0] - goal[0]), B - abs(a[0] - goal[0]))
            dy = min(abs(a[1] - goal[1]), B - abs(a[1] - goal[1]))
            return max(dx, dy) + 0.41 * min(dx, dy)
        openq = [(hdist(start), 0, start)]
        came = {start: None}
        cost = {start: 0}
        n = 0
        while openq and n < 40000:
            n += 1
            _, g, cur = heapq.heappop(openq)
            if cur == goal:
                break
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    nb = ((cur[0] + dx) & 127, (cur[1] + dy) & 127)
                    if self.wall[nb[1] * B + nb[0]] and nb != goal:
                        continue
                    ng = g + (1.41 if dx and dy else 1)
                    if ng < cost.get(nb, 1e9):
                        cost[nb] = ng; came[nb] = cur
                        heapq.heappush(openq, (ng + hdist(nb), ng, nb))
        if goal not in came:
            return None
        path = []
        cur = goal
        while cur is not None:
            path.append(cur); cur = came[cur]
        return path[::-1]

    def waypoint(self, st, t):
        """Where to steer for t: the route's block a few steps ahead."""
        now = time.time()
        key = t.slot
        if self.path_for != key or now - self.path_at > 6:
            self.path = self.route(st.x / CELL, st.y / CELL, t.x / CELL, t.y / CELL)
            self.path_for = key; self.path_at = now
        if not self.path or len(self.path) < 5:
            return None
        here = ((st.x >> 25) & 127, (st.y >> 25) & 127)
        idx = 0
        for i, b in enumerate(self.path):
            if b == here:
                idx = i
        nxt = self.path[min(idx + 4, len(self.path) - 1)]
        return (nxt[0] * 8 + 4) * CELL, (nxt[1] * 8 + 4) * CELL

    def terrain_ahead(self, st, cells=80):
        """Highest map byte along the heading over the next `cells` cells."""
        if self.hmap is None:
            return 0
        a = st.angle / TWO32 * 2 * math.pi
        dx, dy = math.sin(a), -math.cos(a)
        x, y = st.x / CELL, st.y / CELL
        hmax = 0
        for i in range(0, cells, 2):
            cx = int(x + dx * i) & 1023
            cy = int(y + dy * i) & 1023
            hmax = max(hmax, self.hmap[(cy << 10) | cx])
        return hmax

    def clearance_notch(self, st, floor):
        """The notch whose clearance takes the ground ahead with a margin."""
        need = 2 * (self.terrain_ahead(st) - self.ground(st)) + 24
        return max(floor, min(0xE0, (need + 15) & ~15))

    def hunt(self, st, live):
        t = min(live, key=lambda o: bearing_err(st, o)[1])
        if self.target is None or self.target.slot != t.slot:
            self.note(f"hunt #{t.slot} {self.kind(t)} hp={t.health} at ({t.x>>22},{t.y>>22},{t.alt})")
        self.target = t
        e, dist = bearing_err(st, t)
        deg = math.degrees(e)
        if dist > 90 and self.hmap is not None:
            wp = self.waypoint(st, t)
            if wp is not None:
                class P: pass
                w = P(); w.x, w.y = int(wp[0]) & 0xFFFFFFFF, int(wp[1]) & 0xFFFFFFFF
                e = bearing_err(st, w)[0]
                deg = math.degrees(e)
        keys = set()
        if deg > 5:
            keys.add(K['KP6'])
        elif deg < -5:
            keys.add(K['KP4'])
        want = 0
        if abs(deg) < 25 and dist > 120:
            want = self.cruise
        elif abs(deg) < 15 and dist > 35 and st.lock != t.slot:
            want = 3_000_000            # not lockable yet: keep closing, slowly
        notch = self.clearance_notch(st, 0x40 if dist > 120 else 0x20)
        # ground ahead higher than we are: slow down until the climb catches up
        if st.alt < 2 * self.terrain_ahead(st, 30) + 12:
            want = min(want, 2_000_000)
        if st.fwd < want - 1_000_000:
            keys.add(K['KP8'])
        elif st.fwd > want + 1_000_000:
            keys.add(K['KP2'])
        self.s.hold(keys)
        self.notch_to(st, notch)
        if t.targetable and st.lock != t.slot:
            self.s.tap(K['TAB'], 0.05)
        elif st.lock == t.slot and abs(deg) < 12 and dist < 170:
            self.fire(st, t, False, dist)
        elif abs(deg) < 4 and dist < 60:
            # no lock to be had: rockets, then the gun, straight down the nose
            page = 1 if st.ammo[1] > 0 else (0 if st.ammo[0] > 0 else None)
            if page is not None and time.time() - self.last_fire > 0.8:
                if st.page != page:
                    self.s.tap([K['Z'], K['X']][page], 0.05)
                self.s.tap(K['SPACE'], 0.4 if page == 0 else 0.1)
                self.last_fire = time.time()
                self.note(f"fire p{page} unguided at #{t.slot} d={dist:.0f} tg={t.targetable}")
        return f"hunt #{t.slot} e={deg:+.0f} d={dist:.0f} lock={st.lock} tg={t.targetable}"


def to_mission(s, mission_down=0):
    """From power-on to the first flight frame of the mission `mission_down`
    rows below the list's opening row."""
    time.sleep(6); s.tap(K['SPACE']); time.sleep(2)
    for _ in range(4):
        s.tap(K['RET']); time.sleep(2)
    for _ in range(mission_down):
        s.tap(K['DOWN']); time.sleep(0.5)
    s.tap(K['RET']); time.sleep(2)     # briefing
    s.tap(K['RET']); time.sleep(8)     # accept, loading


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else 240
    s = Session(str(pathlib.Path(__file__).resolve().parents[2] / 'release/68060'), out)
    log = open(out / "pilot.log", "w")
    p = Pilot(s, log)
    try:
        to_mission(s)
        st = s.state(); p.note(st.summary())
        p.hmap = s.heightmap(); p.t_start = time.time()
        t0 = time.time(); lastp = 0; shot = 0
        while time.time() - t0 < limit:
            st = s.state()
            if st is None:
                p.note("no state"); break
            if not st.flying:
                p.note("left flight: " + st.summary()); break
            r = p.step(st)
            if time.time() - lastp > 3:
                p.note(f"{r} | {st.summary()}"); lastp = time.time()
            if time.time() - shot > 30:
                s.shot(f"f{int(time.time()-t0):04d}"); shot = time.time()
            if r == 'done':
                p.note(f"all goals destroyed; cheats used: fix={p.cheats[0]} reload={p.cheats[1]}")
                s.shot("won")
                s.chord(K['ALT'], K['A']); time.sleep(4)
                s.shot("debrief")
                p.note(s.state().summary())
                break
        s.shot("final")
        p.note(s.state().summary())
    finally:
        s.close()
