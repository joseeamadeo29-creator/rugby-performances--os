"""
data_manager.py  ─  Rugby Performance OS  v4 (Franchise Edition)
=================================================================
DATA LAYER: Multi-athlete persistence, ACWR workload, robust I/O

New in v4:
  ✅ player_id on every record  (multi-athlete support)
  ✅ Squad CRUD  (add / list / delete / set active player)
  ✅ ACWR  (Acute:Chronic Workload Ratio — 7-day vs 28-day injury prevention)
  ✅ All v3 features preserved  (backups, sentiment, PDF, validation)

File layout:
  data/
    players.json          ← squad registry
    physical_log.csv      ← weight / height / bf%   (+ player_id column)
    gym_prs.csv           ← PR log                  (+ player_id column)
    match_journal.csv     ← journal entries          (+ player_id column)
    body_measures.csv     ← circumferences           (+ player_id column)
    schedule.json         ← shared calendar  (events linked to player_id)
    backups/              ← rotated CSV backups (max 3 per file)
"""

from __future__ import annotations
import json
import logging
import os
import re
import shutil
from datetime import datetime, date, timedelta

import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING,
                    format="[rugby_os] %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR      = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BACKUP_DIR    = os.path.join(DATA_DIR, "backups")
PLAYERS_FILE  = os.path.join(DATA_DIR, "players.json")
PHYSICAL_FILE = os.path.join(DATA_DIR, "physical_log.csv")
PRs_FILE      = os.path.join(DATA_DIR, "gym_prs.csv")
JOURNAL_FILE  = os.path.join(DATA_DIR, "match_journal.csv")
SCHEDULE_FILE = os.path.join(DATA_DIR, "schedule.json")
MEASURES_FILE = os.path.join(DATA_DIR, "body_measures.csv")

# ── Column schemas (include player_id as first data column) ───────────────────
_SCHEMAS: dict[str, list[str]] = {
    PHYSICAL_FILE: ["date", "player_id", "weight_kg", "height_cm", "body_fat_pct"],
    PRs_FILE: [
        "date", "player_id",
        "squat_kg",       "squat_reps",
        "bench_kg",       "bench_reps",
        "deadlift_kg",    "deadlift_reps",
        "power_clean_kg", "power_clean_reps",
    ],
    JOURNAL_FILE: [
        "timestamp", "player_id", "position",
        "performance_score", "notes", "sentiment",
    ],
    MEASURES_FILE: ["date", "player_id", "quad_cm", "arm_cm", "chest_cm"],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  BOOTSTRAP
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_data_dir() -> None:
    """Create /data and /data/backups, seed empty files. Idempotent."""
    try:
        os.makedirs(DATA_DIR,   exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

        for filepath, columns in _SCHEMAS.items():
            if not os.path.exists(filepath):
                pd.DataFrame(columns=columns).to_csv(filepath, index=False)

        if not os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, "w") as f:
                json.dump([], f)

        if not os.path.exists(PLAYERS_FILE):
            with open(PLAYERS_FILE, "w") as f:
                json.dump([], f)

    except Exception as exc:
        log.error(f"ensure_data_dir failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_read_csv(
    filepath:  str,
    date_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Safe CSV reader with schema migration and backup restore.
    Never raises — always returns a valid DataFrame.
    """
    columns = _SCHEMAS.get(filepath, [])
    empty   = pd.DataFrame(columns=columns)

    if not os.path.exists(filepath):
        return empty
    try:
        df = pd.read_csv(filepath)
        # Schema migration: add missing columns
        for col in columns:
            if col not in df.columns:
                df[col] = None
        if date_cols:
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception as exc:
        log.error(f"Could not read {filepath}: {exc}")
        restored = _try_restore_backup(filepath)
        return restored if restored is not None else empty


def _backup_csv(filepath: str) -> None:
    """Timestamped CSV backup, max 3 per file (FIFO rotation)."""
    if not os.path.exists(filepath):
        return
    try:
        base   = os.path.basename(filepath).replace(".csv", "")
        ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(filepath, os.path.join(BACKUP_DIR, f"{base}_{ts}.csv"))
        all_bk = sorted([
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith(base) and f.endswith(".csv")
        ])
        while len(all_bk) > 3:
            os.remove(os.path.join(BACKUP_DIR, all_bk.pop(0)))
    except Exception as exc:
        log.warning(f"Backup failed for {filepath}: {exc}")


def _try_restore_backup(filepath: str) -> pd.DataFrame | None:
    try:
        base = os.path.basename(filepath).replace(".csv", "")
        candidates = sorted([
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith(base) and f.endswith(".csv")
        ], reverse=True)
        if candidates:
            return pd.read_csv(os.path.join(BACKUP_DIR, candidates[0]))
    except Exception:
        pass
    return None


def _validate(label: str, val: float, lo: float, hi: float) -> bool:
    if lo <= val <= hi:
        return True
    log.warning(f"{label} out of range [{lo},{hi}]: {val}")
    return False


def _slug(name: str) -> str:
    """Convert player name to a filesystem-safe id slug."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())


# ═══════════════════════════════════════════════════════════════════════════════
#  SQUAD / PLAYER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_players() -> list[dict]:
    """Return list of player dicts from players.json."""
    try:
        if not os.path.exists(PLAYERS_FILE):
            return []
        with open(PLAYERS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.error(f"load_players: {exc}")
        return []


def save_player(
    name:     str,
    position: str,
    number:   int = 0,
    dob:      str = "",
) -> tuple[bool, str]:
    """
    Add a new player to the squad registry.
    Returns (success, player_id).
    Rejects duplicate names.
    """
    if not name.strip():
        return False, ""
    pid = _slug(name)
    players = load_players()
    if any(p["id"] == pid for p in players):
        return False, pid   # already exists

    players.append({
        "id":       pid,
        "name":     name.strip(),
        "position": position,
        "number":   int(number),
        "dob":      str(dob),
        "added":    str(date.today()),
    })
    try:
        with open(PLAYERS_FILE, "w") as f:
            json.dump(players, f, indent=2)
        return True, pid
    except Exception as exc:
        log.error(f"save_player: {exc}")
        return False, ""


def delete_player(player_id: str) -> bool:
    """Remove a player from the registry (does not delete their data rows)."""
    try:
        players = [p for p in load_players() if p["id"] != player_id]
        with open(PLAYERS_FILE, "w") as f:
            json.dump(players, f, indent=2)
        return True
    except Exception as exc:
        log.error(f"delete_player: {exc}")
        return False


def get_player_name(player_id: str) -> str:
    """Return display name for a player_id, or the id itself if not found."""
    for p in load_players():
        if p["id"] == player_id:
            return p["name"]
    return player_id


# ═══════════════════════════════════════════════════════════════════════════════
#  PHYSICAL / ANTHROPOMETRICS  (multi-athlete)
# ═══════════════════════════════════════════════════════════════════════════════

def save_physical_entry(
    weight_kg:    float,
    height_cm:    float,
    body_fat_pct: float,
    player_id:    str = "default",
) -> bool:
    if not _validate("weight_kg",    weight_kg,    30, 250): return False
    if not _validate("height_cm",    height_cm,   100, 230): return False
    if not _validate("body_fat_pct", body_fat_pct,   2,  60): return False

    entry = {
        "date":         datetime.now().strftime("%Y-%m-%d"),
        "player_id":    player_id,
        "weight_kg":    round(weight_kg, 1),
        "height_cm":    round(height_cm, 1),
        "body_fat_pct": round(body_fat_pct, 1),
    }
    try:
        _backup_csv(PHYSICAL_FILE)
        df = load_physical_log()
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        df.to_csv(PHYSICAL_FILE, index=False)
        return True
    except Exception as exc:
        log.error(f"save_physical_entry: {exc}")
        return False


def load_physical_log(player_id: str | None = None) -> pd.DataFrame:
    """Return anthropometrics, optionally filtered to one player."""
    df = _safe_read_csv(PHYSICAL_FILE, date_cols=["date"])
    if player_id and "player_id" in df.columns and not df.empty:
        df = df[df["player_id"] == player_id]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  BODY MEASURES  (multi-athlete)
# ═══════════════════════════════════════════════════════════════════════════════

def save_measures_entry(
    quad_cm:   float,
    arm_cm:    float,
    chest_cm:  float,
    player_id: str = "default",
) -> bool:
    if not _validate("quad_cm",  quad_cm,   30, 100): return False
    if not _validate("arm_cm",   arm_cm,    20,  60): return False
    if not _validate("chest_cm", chest_cm,  60, 160): return False

    entry = {
        "date":      datetime.now().strftime("%Y-%m-%d"),
        "player_id": player_id,
        "quad_cm":   round(quad_cm, 1),
        "arm_cm":    round(arm_cm, 1),
        "chest_cm":  round(chest_cm, 1),
    }
    try:
        _backup_csv(MEASURES_FILE)
        df = load_measures_log()
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        df.to_csv(MEASURES_FILE, index=False)
        return True
    except Exception as exc:
        log.error(f"save_measures_entry: {exc}")
        return False


def load_measures_log(player_id: str | None = None) -> pd.DataFrame:
    df = _safe_read_csv(MEASURES_FILE, date_cols=["date"])
    if player_id and "player_id" in df.columns and not df.empty:
        df = df[df["player_id"] == player_id]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  GYM PRs  (multi-athlete)
# ═══════════════════════════════════════════════════════════════════════════════

def save_pr_entry(
    squat: float,       squat_reps: int,
    bench: float,       bench_reps: int,
    deadlift: float,    deadlift_reps: int,
    power_clean: float, power_clean_reps: int,
    player_id: str = "default",
) -> bool:
    for label, val in [("squat", squat), ("bench", bench),
                       ("deadlift", deadlift), ("power_clean", power_clean)]:
        if not _validate(f"{label}_kg", val, 20, 600):
            return False
    entry = {
        "date":              datetime.now().strftime("%Y-%m-%d"),
        "player_id":         player_id,
        "squat_kg":          squat,       "squat_reps":        int(squat_reps),
        "bench_kg":          bench,       "bench_reps":        int(bench_reps),
        "deadlift_kg":       deadlift,    "deadlift_reps":     int(deadlift_reps),
        "power_clean_kg":    power_clean, "power_clean_reps":  int(power_clean_reps),
    }
    try:
        _backup_csv(PRs_FILE)
        df = load_pr_log()
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        df.to_csv(PRs_FILE, index=False)
        return True
    except Exception as exc:
        log.error(f"save_pr_entry: {exc}")
        return False


def load_pr_log(player_id: str | None = None) -> pd.DataFrame:
    df = _safe_read_csv(PRs_FILE, date_cols=["date"])
    if player_id and "player_id" in df.columns and not df.empty:
        df = df[df["player_id"] == player_id]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  MATCH JOURNAL  (multi-athlete + auto-sentiment)
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_sentiment(text: str) -> float:
    """TextBlob polarity, keyword-heuristic fallback."""
    try:
        from textblob import TextBlob
        return round(TextBlob(text).sentiment.polarity, 3)
    except ImportError:
        pass
    positive = {
        "great","good","excellent","strong","won","amazing","perfect","happy","proud",
        "solid","sharp","fast","confident","dominant","controlled","consistent","clinical",
    }
    negative = {
        "bad","poor","missed","tired","lost","injured","weak","frustrated","slow","awful",
        "sloppy","error","failed","nervous","dropped","penalty","confused","late","heavy",
    }
    words = set(text.lower().split())
    pos, neg = len(words & positive), len(words & negative)
    total = pos + neg
    return round((pos - neg) / total, 2) if total else 0.0


def save_journal_entry(
    position:  str,
    score:     int,
    notes:     str,
    player_id: str = "default",
) -> bool:
    if not _validate("score", score, 1, 10): return False
    if not notes.strip():                    return False

    entry = {
        "timestamp":         datetime.now().strftime("%Y-%m-%d %H:%M"),
        "player_id":         player_id,
        "position":          position,
        "performance_score": score,
        "notes":             notes,
        "sentiment":         _compute_sentiment(notes),
    }
    try:
        _backup_csv(JOURNAL_FILE)
        df = load_journal()
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        df.to_csv(JOURNAL_FILE, index=False)
        return True
    except Exception as exc:
        log.error(f"save_journal_entry: {exc}")
        return False


def load_journal(player_id: str | None = None) -> pd.DataFrame:
    df = _safe_read_csv(JOURNAL_FILE, date_cols=["timestamp"])
    if player_id and "player_id" in df.columns and not df.empty:
        df = df[df["player_id"] == player_id]
    return df


def check_burnout_alert(df: pd.DataFrame) -> bool:
    """True if last 3 entries all have sentiment < 0."""
    try:
        if len(df) < 3: return False
        recent = df.sort_values("timestamp").tail(3)
        sents  = pd.to_numeric(recent["sentiment"], errors="coerce").fillna(0)
        return bool((sents < 0).all())
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  ACWR  ─  Acute : Chronic Workload Ratio  (injury prevention)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_acwr(player_id: str = "default") -> dict:
    """
    Acute:Chronic Workload Ratio  (ACWR)  —  Industry Gold Standard

    Concept:
      • ACUTE load  = total sessions / training load in last  7 days
      • CHRONIC load = average weekly load over last 28 days
      • ACWR = acute / chronic

    Interpretation (Gabbett, 2016):
      ACWR < 0.8   → undertraining / deload — athlete is undertrained
      0.8–1.3      → safe training zone
      1.3–1.5      → caution zone — monitor closely
      > 1.5        → HIGH INJURY RISK — reduce load immediately

    Implementation:
      We use schedule event counts as a proxy for load units:
        Workout         → 1.0 load unit
        Rugby Training  → 1.5 load units  (higher intensity)
        Match Day       → 2.0 load units  (peak stress)
        Rest Day        → 0.0

    This is a simplified ACWR. Elite setups use GPS session RPE × duration.
    """
    EVENT_LOAD = {
        "Workout":        1.0,
        "Rugby Training": 1.5,
        "Match Day":      2.0,
        "Rest Day":       0.0,
    }

    today    = date.today()
    events   = load_schedule()

    # Filter events for this player (or all if schedule is shared)
    def event_load_for_day(d: date) -> float:
        ds = str(d)
        return sum(
            EVENT_LOAD.get(ev.get("type", ""), 0.0)
            for ev in events
            if ev.get("date") == ds
        )

    # Acute: sum of loads in last 7 days
    acute_total = sum(
        event_load_for_day(today - timedelta(days=i))
        for i in range(7)
    )

    # Chronic: average weekly load over 28 days
    chronic_weeks = []
    for week in range(4):
        week_load = sum(
            event_load_for_day(today - timedelta(days=week * 7 + i))
            for i in range(7)
        )
        chronic_weeks.append(week_load)
    chronic_avg = sum(chronic_weeks) / 4

    # ACWR calculation
    if chronic_avg < 0.1:
        acwr  = None   # not enough history
        zone  = "insufficient_data"
    else:
        acwr  = round(acute_total / chronic_avg, 2)
        if acwr < 0.8:    zone = "undertraining"
        elif acwr <= 1.3: zone = "safe"
        elif acwr <= 1.5: zone = "caution"
        else:             zone = "danger"

    return {
        "acwr":          acwr,
        "acute_load":    round(acute_total, 1),
        "chronic_avg":   round(chronic_avg, 2),
        "zone":          zone,
        "weekly_loads":  [round(w, 1) for w in chronic_weeks],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════

def load_schedule() -> list:
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.error(f"load_schedule: {exc}")
        return []


def save_event(date_str: str, event_type: str, details: str,
               player_id: str = "default") -> bool:
    if not date_str or not event_type: return False
    try:
        events = load_schedule()
        events.append({
            "id":        datetime.now().timestamp(),
            "date":      date_str,
            "type":      event_type,
            "details":   details,
            "player_id": player_id,
        })
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(events, f, indent=2)
        return True
    except Exception as exc:
        log.error(f"save_event: {exc}")
        return False


def delete_event(event_id: float) -> bool:
    try:
        events = [e for e in load_schedule() if e.get("id") != event_id]
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(events, f, indent=2)
        return True
    except Exception as exc:
        log.error(f"delete_event: {exc}")
        return False


def get_today_event_types(player_id: str | None = None) -> list[str]:
    today = str(date.today())
    evs   = load_schedule()
    if player_id:
        evs = [e for e in evs if e.get("player_id") == player_id
               or e.get("player_id") == "default"]
    return [ev["type"] for ev in evs if ev.get("date") == today]


# ═══════════════════════════════════════════════════════════════════════════════
#  PDF REPORT GENERATOR  (v3 preserved, updated for multi-athlete)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_pdf_report(
    phys_df:    pd.DataFrame,
    pr_df:      pd.DataFrame,
    jrnl_df:    pd.DataFrame,
    player_name: str = "Athlete",
) -> bytes | None:
    """Generate a professional FPDF2 performance report. Returns PDF bytes."""
    try:
        from fpdf import FPDF
    except ImportError:
        log.warning("fpdf2 not installed.")
        return None

    from modules.nutrition import compute_all_1rms

    class RugbyPDF(FPDF):
        def header(self):
            self.set_fill_color(14, 17, 23)
            self.rect(0, 0, 210, 297, "F")
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(46, 204, 113)
            self.cell(0, 12, "RUGBY PERFORMANCE OS", align="C",
                      new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 10)
            self.set_text_color(136, 136, 136)
            self.cell(0, 6, f"Player: {player_name}  ·  "
                             f"Generated {datetime.now().strftime('%d %b %Y %H:%M')}",
                      align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(46, 204, 113)
            self.set_line_width(0.4)
            self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
            self.ln(5)

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(60, 60, 60)
            self.cell(0, 10, f"Page {self.page_no()}  ─  Rugby Performance OS v4",
                      align="C")

        def section(self, title, color=(46, 204, 113)):
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*color)
            self.cell(0, 8, title.upper(), new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(*color)
            self.set_line_width(0.25)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(3)
            self.set_text_color(210, 210, 210)

        def row(self, label, value, delta="", pos=True):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(150, 150, 150)
            self.cell(70, 6, label)
            self.set_text_color(230, 230, 230)
            self.cell(50, 6, value)
            if delta:
                self.set_font("Helvetica", "", 9)
                self.set_text_color(46, 204, 113) if pos else self.set_text_color(232, 67, 67)
                self.cell(60, 6, delta)
            self.ln(6)

    pdf = RugbyPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_margins(10, 10, 10)

    # Physical
    pdf.section("Physical Status")
    if not phys_df.empty:
        last = phys_df.sort_values("date").iloc[-1]
        w    = float(last["weight_kg"])
        bf   = float(last.get("body_fat_pct", 0))
        pdf.row("Body Weight", f"{w:.1f} kg")
        pdf.row("Body Fat %",  f"{bf:.1f}%")
        pdf.row("Lean Mass",   f"{w*(1-bf/100):.1f} kg")
    else:
        pdf.set_font("Helvetica","I",9); pdf.cell(0,6,"No data.",new_x="LMARGIN",new_y="NEXT")
    pdf.ln(3)

    # PRs
    pdf.section("Strength — Best 1RM (Epley)", color=(201, 162, 39))
    if not pr_df.empty:
        pr1rm = compute_all_1rms(pr_df)
        for lift, col in [("Back Squat","squat_1rm"),("Bench Press","bench_1rm"),
                          ("Deadlift","deadlift_1rm"),("Power Clean","power_clean_1rm")]:
            if col in pr1rm.columns:
                best = pr1rm[col].max()
                pdf.row(lift, f"{best:.1f} kg" if best else "—")
    else:
        pdf.set_font("Helvetica","I",9); pdf.cell(0,6,"No data.",new_x="LMARGIN",new_y="NEXT")
    pdf.ln(3)

    # ACWR
    acwr_data = calculate_acwr()
    pdf.section("Workload — ACWR", color=(231, 76, 60))
    if acwr_data["acwr"] is not None:
        pdf.row("ACWR",         f"{acwr_data['acwr']:.2f}")
        pdf.row("Acute Load",   f"{acwr_data['acute_load']} units (7 days)")
        pdf.row("Chronic Avg",  f"{acwr_data['chronic_avg']} units/week")
        pdf.row("Zone",          acwr_data["zone"].upper())
    else:
        pdf.set_font("Helvetica","I",9)
        pdf.cell(0,6,"Insufficient schedule data for ACWR.",new_x="LMARGIN",new_y="NEXT")
    pdf.ln(3)

    # Journal
    pdf.section("Match Journal — Last 5 Entries", color=(52, 152, 219))
    if not jrnl_df.empty:
        for _, row in jrnl_df.sort_values("timestamp",ascending=False).head(5).iterrows():
            sc   = int(row.get("performance_score",0))
            sent = float(row.get("sentiment",0))
            sl   = "Positive" if sent>0 else "Negative" if sent<0 else "Neutral"
            pdf.set_font("Helvetica","B",9); pdf.set_text_color(180,180,180)
            pdf.cell(80,5,str(row.get("timestamp",""))); pdf.cell(40,5,f"{sc}/10")
            pdf.set_text_color(46,204,113) if sent>0 else pdf.set_text_color(232,67,67)
            pdf.cell(30,5,sl); pdf.ln(5)
            notes = str(row.get("notes","")).replace("\n"," ")[:100]+"..."
            pdf.set_font("Helvetica","I",8); pdf.set_text_color(100,100,100)
            pdf.multi_cell(0,4,notes); pdf.ln(1)
    else:
        pdf.set_font("Helvetica","I",9); pdf.cell(0,6,"No entries.",new_x="LMARGIN",new_y="NEXT")
    pdf.ln(3)

    # Recommendations
    pdf.section("Auto Recommendations", color=(241, 196, 15))
    recs = []
    if check_burnout_alert(jrnl_df):
        recs.append("BURNOUT RISK: 3+ negative-sentiment entries. Rest Day recommended.")
    if acwr_data.get("zone") == "danger":
        recs.append("INJURY RISK: ACWR > 1.5. Reduce training load this week.")
    elif acwr_data.get("zone") == "caution":
        recs.append("CAUTION: ACWR approaching 1.5. Monitor fatigue closely.")
    if not recs:
        recs.append("All metrics within optimal parameters. Continue executing the plan.")
    for r in recs:
        pdf.set_font("Helvetica","",9); pdf.set_text_color(200,200,200)
        pdf.multi_cell(0,6,r); pdf.ln(1)

    try:
        return bytes(pdf.output())
    except Exception as exc:
        log.error(f"PDF generation failed: {exc}")
        return None
