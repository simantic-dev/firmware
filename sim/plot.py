"""Draws sim/screenshots/*.png from a finished run (sim/run.sh output in sim/out/). Needs matplotlib.
Only run data: CAN frames from can-frames.txt, console lines from uart.log. Nothing here is typed in.
usage: python3 sim/plot.py
"""
import importlib.util, os, re
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "screenshots")
os.makedirs(OUT, exist_ok=True)
FR = re.compile(r"^\[(\w+)\] \[([\d.]+)s\] \(\w+\) CAN (Tx|Rx) id=0x([0-9A-Fa-f]+) dlc=(\d+) data=(.*)$")
STATES = {0: "BOOT", 1: "LV_POWER", 2: "BUS_HEALTH", 3: "PRECHARGE", 4: "ENERGIZED", 5: "DRIVE", 10: "FAULT_BMS"}


def frames(scn):
    for line in open(os.path.join(HERE, "out", scn, "can-frames.txt"), errors="replace"):
        m = FR.match(line.strip())
        if m:
            yield m.group(1), float(m.group(2)), m.group(3), int(m.group(4), 16), bytes(int(b, 16) for b in m.group(6).split())


def s16(b, i):
    v = b[i] | (b[i + 1] << 8)
    return v - 65536 if v & 0x8000 else v


def bms_series():
    st, pv, tm = [], [], []
    for who, t, d, cid, b in frames("scenario"):
        if who != "bms" or d != "Tx":
            continue
        if cid == 5:
            st.append((t, b[0] & 0x1F))
        elif cid == 2:
            pv.append((t, s16(b, 0) / 10.0))
        elif cid == 3:
            tm.append((t, s16(b, 0) / 10.0, s16(b, 4) / 10.0))
    return st, pv, tm


def fig_bms(foot):
    st, pv, tm = bms_series()
    f, ax = plt.subplots(3, 1, figsize=(7.2, 5.6), sharex=True)
    ax[0].step([t for t, _ in st], [s for _, s in st], where="post", color="#1f77b4")
    used = sorted({s for _, s in st})
    ax[0].set_yticks(used); ax[0].set_yticklabels([STATES.get(s, str(s)) for s in used])
    ax[0].set_title("BMS state (CAN 0x5, sent by the BMS firmware)")
    ax[1].plot([t for t, _ in pv], [v for _, v in pv], color="#d62728")
    ax[1].set_ylabel("V"); ax[1].set_title("Pack voltage (0x2), from 10 ADBMS6830B peers' cell readings")
    ax[2].plot([t for t, *_ in tm], [a for _, a, _ in tm], label="average", color="#2ca02c")
    ax[2].plot([t for t, _, m in tm], [m for _, _, m in tm], label="hottest cell", color="#ff7f0e")
    ax[2].set_ylabel("deg C"); ax[2].set_xlabel("virtual time (s)"); ax[2].legend(loc="upper left"); ax[2].set_title("Pack temperature (0x3)")
    for a in ax:
        a.grid(alpha=.3)
    f.text(0.01, 0.005, foot, fontsize=7, color="#555")
    f.tight_layout(rect=(0, 0.02, 1, 1)); f.savefig(os.path.join(OUT, "bms-state.png"), dpi=100); plt.close(f)


def fig_cells(foot):
    txt = open(os.path.join(HERE, "out", "scenario", "uart.log"), errors="replace").read().splitlines()
    dumps, cur = [], None
    for ln in txt:
        if not ln.startswith("[bms]"):
            continue
        t = float(re.search(r"\[([\d.]+)s\]", ln).group(1))
        if "=== Cell Voltages" in ln:
            cur = (t, []); dumps.append(cur)
        m = re.search(r"\bC(\d\d): ([\d.]+)/", ln)
        if m and cur:
            cur[1].append(float(m.group(2)))
    f, ax = plt.subplots(figsize=(7.2, 3.6))
    for (t, v), c in zip(dumps, ["#1f77b4", "#ff7f0e", "#2ca02c"]):
        ax.plot(range(1, len(v) + 1), v, ".", ms=3, color=c, label=f"BMS|cells at {t:.2f} s ({len(v)} cells)")
    ax.set_xlabel("cell index (10 banks x 14)"); ax.set_ylabel("V")
    ax.set_title("Cell voltages the BMS console prints (read from the ADBMS peers over SPI1)")
    ax.legend(fontsize=7); ax.grid(alpha=.3)
    f.text(0.01, 0.005, foot, fontsize=7, color="#555")
    f.tight_layout(rect=(0, 0.03, 1, 1)); f.savefig(os.path.join(OUT, "cell-voltages.png"), dpi=100); plt.close(f)
    return dumps


def fig_can(foot):
    tx = defaultdict(list)
    for who, t, d, cid, b in frames("scenario"):
        if d == "Tx":
            tx[(who, cid)].append(t)
    keys = sorted(tx, key=lambda k: (k[0], k[1]))
    names = {"bms": "BMS", "pcu": "PCU", "lvpdb": "LVPDB (+DASH stand-in 0x10)", "front": "FRONT", "rear": "REAR", "dcu": "DCU"}
    colors = {"bms": "#d62728", "pcu": "#1f77b4", "lvpdb": "#2ca02c", "front": "#ff7f0e", "rear": "#9467bd", "dcu": "#8c564b"}
    f, ax = plt.subplots(figsize=(7.2, 5.2))
    for i, k in enumerate(keys):
        ax.plot(tx[k], [i] * len(tx[k]), "|", ms=7, color=colors[k[0]])
        ax.text(10.05, i, f"{len(tx[k])}", va="center", fontsize=6)
    ax.set_yticks(range(len(keys))); ax.set_yticklabels([f"{k[0]} 0x{k[1]:X}" for k in keys], fontsize=6)
    ax.set_xlim(0, 10.5); ax.set_xlabel("virtual time (s); count at right")
    ax.set_title("Every frame sent, one row per sender and CAN ID")
    ax.grid(alpha=.3, axis="x")
    f.text(0.01, 0.005, foot, fontsize=7, color="#555")
    f.tight_layout(rect=(0, 0.03, 1, 1)); f.savefig(os.path.join(OUT, "can-frames.png"), dpi=100); plt.close(f)


def fig_torque(foot):
    spec = importlib.util.spec_from_file_location("drive", os.path.join(HERE, "peers", "pcu-sn5-drive.py"))
    drive = importlib.util.module_from_spec(spec); spec.loader.exec_module(drive)
    ts, tq, en, bs = [], [], [], []
    for who, t, d, cid, b in frames("pcu"):
        if who == "pcu" and d == "Tx" and cid == 0xC0:
            q, e = drive.decode_torque(b); ts.append(t); tq.append(q); en.append(e)
        if d == "Tx" and cid == 5:
            bs.append((t, b[0] & 0x1F))
    f, ax = plt.subplots(2, 1, figsize=(7.2, 4.4), sharex=True)
    ax[0].step([t for t, _ in bs], [s for _, s in bs], where="post", color="#555")
    ax[0].set_yticks([4, 5]); ax[0].set_yticklabels(["ENERGIZED", "DRIVE"]); ax[0].set_title("bms_state the peer sends the PCU (0x5)")
    ax[1].plot(ts, tq, color="#1f77b4", label="torque command (Nm)")
    ax[1].plot(ts, [10 * int(bool(e)) for e in en], color="#d62728", lw=.8, label="inverter enable (x10)")
    ax[1].set_title("PCU torque command to the inverter (0xC0), pedal profile playing"); ax[1].set_xlabel("virtual time (s)"); ax[1].legend(fontsize=7)
    for a in ax:
        a.grid(alpha=.3)
    f.text(0.01, 0.005, foot, fontsize=7, color="#555")
    f.tight_layout(rect=(0, 0.03, 1, 1)); f.savefig(os.path.join(OUT, "pcu-torque.png"), dpi=100); plt.close(f)


def fig_console(foot, scn="scenario"):
    keep = []
    for ln in open(os.path.join(HERE, "out", scn, "uart.log"), errors="replace"):
        ln = ln.rstrip()
        if ln.startswith("[bms]") and re.search(r"BOOT -> LV_POWER|BMS Console Ready|BMS\|status|=== BMS Status|State: |Pack Voltage|Min Cell|Max Cell|Min Temp|Manual transition|-> BUS_HEALTH|Shutdown open|-> PRECHARGE|IVT current|FAULT ENTRY|BMS State: ", ln):
            keep.append(re.sub(r"^\[bms\] \[([\d.]+)s\] \([^)]*\) ?", lambda m: f"{float(m.group(1)):7.3f}s ", ln)
                        [:104])
    keep = keep[:30]
    f = plt.figure(figsize=(7.2, 0.19 * len(keep) + 0.7))
    f.text(0.01, 0.99, "BMS firmware console (USART2), typed by the console peer", fontsize=8, va="top", weight="bold")
    f.text(0.01, 0.94, "\n".join(keep), family="monospace", fontsize=6.2, va="top", linespacing=1.35)
    f.text(0.01, 0.005, foot, fontsize=7, color="#555")
    f.savefig(os.path.join(OUT, "console.png"), dpi=100); plt.close(f)


if __name__ == "__main__":
    foot = os.environ.get("FOOT", "")
    fig_bms(foot + " | scenario.yaml, 10 s"); fig_cells(foot + " | scenario.yaml, 10 s"); fig_can(foot + " | scenario.yaml, 10 s")
    fig_torque(foot + " | pcu.yaml, 10 s"); fig_console(foot + " | scenario.yaml, 10 s")
