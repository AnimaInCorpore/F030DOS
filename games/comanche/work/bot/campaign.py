#!/usr/bin/env python3
"""Play the campaign mission by mission with the rule-based pilot."""
import sys, time, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hbot import Session, K
from pilot import Pilot

def wait_screen(s, sid, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = s.state()
        if st and st.screen and st.screen_id == sid:
            return st
        time.sleep(0.3)
    return s.state()

def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    missions = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    limit = float(sys.argv[3]) if len(sys.argv) > 3 else 1800
    s = Session(str(pathlib.Path(__file__).resolve().parents[2] / 'release/68060'), out)
    log = open(out / "campaign.log", "a")
    def note(m):
        print(m, flush=True); log.write(m + "\n"); log.flush()
    results = []
    try:
        time.sleep(6); s.tap(K['SPACE']); time.sleep(2)
        for n in range(missions):
            st = wait_screen(s, 0)
            note(f"main menu: sel={st.sel} count={st.count}")
            for _ in range(10):
                if st.sel == 0:
                    break
                s.tap(K['UP']); time.sleep(0.4); st = s.state()
            s.tap(K['RET']); time.sleep(2)               # Begin Mission
            st = s.state()
            if st.screen_id == 1:                         # campaign select
                s.tap(K['RET']); time.sleep(2)
            st = wait_screen(s, 2)
            if st.screen_id != 2:
                note(f"not on the mission list: screen {st.screen_id}"); s.shot(f"lost{n:02d}"); break
            time.sleep(1); st = s.state()
            note(f"mission list ink={st.ink!r} sel={st.sel} count={st.count}")
            s.shot(f"list{n:02d}")
            rows = [i for i, c in enumerate(st.ink[:st.count]) if c == 'g']
            if not rows:
                note("no green mission left"); break
            row = rows[0]
            while st.sel != row:
                s.tap(K['DOWN'] if st.sel < row else K['UP']); time.sleep(0.4)
                st = s.state()
            s.tap(K['RET']); time.sleep(2)               # briefing
            st = wait_screen(s, 7)
            s.shot(f"brief{n:02d}")
            s.tap(K['RET']); time.sleep(8)               # accept, load
            st = s.state()
            note(f"mission {row}: start {st.summary()}")
            p = Pilot(s, log)
            p.hmap = s.heightmap(); p.build_grid(); p.t_start = time.time()
            t0 = time.time(); lastp = 0; outcome = 'timeout'
            while time.time() - t0 < limit:
                st = s.state()
                if st is None:
                    outcome = 'no state'; break
                if not st.flying:
                    outcome = 'ended'; break
                r = p.step(st)
                if time.time() - lastp > 20:
                    note(f"  {r} | {st.summary()}"); lastp = time.time()
                if r == 'done':
                    outcome = 'won'
                    s.hold(set()); time.sleep(1)
                    s.chord(K['ALT'], K['A']); time.sleep(4)
                    break
            st = wait_screen(s, 5, 30)
            s.shot(f"debrief{n:02d}")
            res = dict(mission=row, outcome=outcome, fix=p.cheats[0], reload=p.cheats[1],
                       frames=st.iter, hull=st.hull, seconds=round(time.time() - t0))
            results.append(res)
            note(f"RESULT {res}")
            json.dump(results, open(out / "results.json", "w"), indent=1)
            s.tap(K['ESC']); time.sleep(3)
    finally:
        s.close()

if __name__ == "__main__":
    main()
