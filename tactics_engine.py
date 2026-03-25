"""
tactics_engine.py  ─  Rugby Performance OS  v4 (Franchise Edition)
====================================================================
THE BRAIN: Advanced Vision + Persistent Tracking + Spatial Heatmaps

New in v4:
  ✅ CentroidTracker   — lightweight persistent ID across frames
  ✅ generate_heatmap()— Plotly 2D density over pitch top-down view
  ✅ HeatmapStore      — session-level event coordinate accumulator
  ✅ All v3 classes preserved (RugbyEventDetector, TeamClusterer, etc.)

Tracking Logic:
  Uses Euclidean distance between frame-N centroids and frame-N+1 centroids.
  Each detection in frame N+1 is matched to the nearest detection in frame N
  within a MAX_DIST threshold. Unmatched detections get a new persistent ID.
  This is a simplified SORT-style tracker (no Kalman filter — fast & dependency-free).
"""

from __future__ import annotations
import io
import math
import collections
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Detection:
    track_id: int
    label:    str        # 'person' | 'sports ball'
    x:        float      # bbox centre-x (pixels)
    y:        float      # bbox centre-y (pixels)
    w:        float
    h:        float
    conf:     float
    team:     str = "unknown"


@dataclass
class FrameEvent:
    event:      str
    confidence: float
    frame_idx:  int
    location:   tuple    # (x, y) pixel epicentre
    details:    str = ""


# ═══════════════════════════════════════════════════════════════════════════════
#  CENTROID TRACKER  (persistent ID across frames)
# ═══════════════════════════════════════════════════════════════════════════════

class CentroidTracker:
    """
    Lightweight multi-object tracker using centroid-distance matching.

    Algorithm per frame:
      1. Compute centroid (cx, cy) for every new detection.
      2. If no previous objects → assign new IDs to all.
      3. Compute pairwise Euclidean distances between previous centroids
         and new centroids  (O(n²), fine for ≤30 players).
      4. Greedy match: sort pairs by distance ascending, assign matched pairs,
         skip if distance > MAX_DIST (object left frame or occlusion).
      5. Unmatched new detections → new persistent IDs.
      6. Objects unseen for > MAX_DISAPPEAR frames → deregistered.

    Why centroid distance works for rugby:
      Players move ~0.5–3 m per frame at standard zoom.
      At 40 px/m, MAX_DIST = 120 px covers up to 3 m displacement —
      sufficient for even fast sprint sequences at 25 fps with skip_n=3.
    """

    MAX_DIST      = 120   # pixels — max centroid distance to count as same player
    MAX_DISAPPEAR = 10    # frames before a track is dropped

    def __init__(self):
        self._next_id  = 0
        # track_id → (cx, cy)
        self._centroids: dict[int, tuple[float, float]] = {}
        # track_id → frames since last seen
        self._disappeared: dict[int, int] = {}

    def _new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def update(self, detections: list[Detection]) -> list[Detection]:
        """
        Assign persistent track_ids to the current frame's detections.
        Modifies detections in-place and returns them.
        """
        if not detections:
            # Mark all existing tracks as disappeared
            for tid in list(self._disappeared):
                self._disappeared[tid] += 1
                if self._disappeared[tid] > self.MAX_DISAPPEAR:
                    del self._centroids[tid]
                    del self._disappeared[tid]
            return detections

        # New centroids from this frame
        new_centroids = [(d.x, d.y) for d in detections]

        # First frame or no existing tracks
        if not self._centroids:
            for i, d in enumerate(detections):
                tid = self._new_id()
                d.track_id = tid
                self._centroids[tid]   = new_centroids[i]
                self._disappeared[tid] = 0
            return detections

        # Build cost matrix  (existing tracks × new detections)
        existing_ids  = list(self._centroids.keys())
        existing_cxcy = [self._centroids[tid] for tid in existing_ids]

        # distances[i][j] = dist(existing_ids[i], new_centroids[j])
        distances = [
            [math.dist(ec, nc) for nc in new_centroids]
            for ec in existing_cxcy
        ]

        # Greedy matching: sort (i, j, dist) ascending
        pairs = sorted(
            [(i, j, distances[i][j])
             for i in range(len(existing_ids))
             for j in range(len(new_centroids))],
            key=lambda x: x[2],
        )

        matched_existing = set()
        matched_new      = set()

        for i, j, dist in pairs:
            if i in matched_existing or j in matched_new:
                continue
            if dist > self.MAX_DIST:
                break   # sorted, so all remaining are farther

            tid = existing_ids[i]
            detections[j].track_id = tid
            self._centroids[tid]   = new_centroids[j]
            self._disappeared[tid] = 0
            matched_existing.add(i)
            matched_new.add(j)

        # Unmatched existing → increment disappeared counter
        for i, tid in enumerate(existing_ids):
            if i not in matched_existing:
                self._disappeared[tid] += 1
                if self._disappeared[tid] > self.MAX_DISAPPEAR:
                    del self._centroids[tid]
                    del self._disappeared[tid]

        # Unmatched new detections → assign fresh IDs
        for j, d in enumerate(detections):
            if j not in matched_new:
                tid = self._new_id()
                d.track_id = tid
                self._centroids[tid]   = new_centroids[j]
                self._disappeared[tid] = 0

        return detections


# ═══════════════════════════════════════════════════════════════════════════════
#  HEATMAP STORE  (accumulates event coordinates across frames)
# ═══════════════════════════════════════════════════════════════════════════════

class HeatmapStore:
    """
    Session-level store for event pixel coordinates.
    Converts pixel coords to normalised pitch coords (0–1) so heatmaps
    scale correctly regardless of video resolution.

    Usage:
        store = HeatmapStore()  # kept in st.session_state
        store.add(events, frame_w=1920, frame_h=1080)
        fig = store.build_plotly_heatmap(filter_event="Tackle")
    """

    def __init__(self):
        # List of dicts: {event, nx, ny}  (normalised 0–1)
        self._records: list[dict] = []

    def add(
        self,
        events:  list[FrameEvent],
        frame_w: int,
        frame_h: int,
    ) -> None:
        """Add event locations, normalised to [0,1] × [0,1]."""
        for ev in events:
            cx, cy = ev.location
            self._records.append({
                "event": ev.event,
                "nx":    cx / max(frame_w, 1),
                "ny":    cy / max(frame_h, 1),
            })

    def clear(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)

    def build_plotly_heatmap(
        self,
        filter_event: str = "All",
        lang:         str = "en",
    ):
        """
        Build a Plotly figure with a 2D density heatmap overlaid on a
        top-down rugby pitch schematic.

        Coordinate system:
          x-axis → touchline-to-touchline  (0 = left touch, 1 = right touch)
          y-axis → try-line-to-try-line    (0 = home try line, 1 = away try line)

        The pitch is drawn with Plotly shapes (rectangles + lines).
        Event density is rendered as a go.Histogram2dContour.
        """
        import plotly.graph_objects as go

        records = self._records
        if filter_event != "All":
            records = [r for r in records if r["event"] == filter_event]

        if not records:
            return None

        xs = [r["nx"] for r in records]
        ys = [r["ny"] for r in records]

        event_colors = {
            "Tackle":   "Reds",
            "Ruck":     "Greens",
            "Scrum":    "Oranges",
            "Line-out": "Blues",
            "All":      "Hot",
        }
        colorscale = event_colors.get(filter_event, "Hot")

        fig = go.Figure()

        # ── Pitch background ──────────────────────────────────────────────────
        # Main pitch rectangle
        fig.add_shape(type="rect", x0=0, y0=0, x1=1, y1=1,
                      fillcolor="#1a4a1a", line=dict(color="#ffffff", width=2))
        # Try zones (22m zones approximated as 15% of pitch length)
        for y0, y1 in [(0, 0.15), (0.85, 1)]:
            fig.add_shape(type="rect", x0=0, y0=y0, x1=1, y1=y1,
                          fillcolor="#153a15", line=dict(color="#ffffff", width=1))
        # Halfway line
        fig.add_shape(type="line", x0=0, y0=0.5, x1=1, y1=0.5,
                      line=dict(color="#ffffff", width=1.5))
        # 22m lines
        for y in [0.15, 0.85]:
            fig.add_shape(type="line", x0=0, y0=y, x1=1, y1=y,
                          line=dict(color="#aaffaa", width=1, dash="dash"))
        # Centre circle (approximated as ellipse)
        fig.add_shape(type="circle", x0=0.35, y0=0.44, x1=0.65, y1=0.56,
                      line=dict(color="#ffffff", width=1))

        # ── Density contour (heatmap) ─────────────────────────────────────────
        fig.add_trace(go.Histogram2dContour(
            x          = xs,
            y          = ys,
            colorscale = colorscale,
            opacity    = 0.75,
            showscale  = True,
            contours   = dict(showlines=False),
            colorbar   = dict(
                thickness = 12,
                len       = 0.6,
                title     = dict(text="Density", font=dict(size=10, color="#aaa")),
                tickfont  = dict(size=9, color="#aaa"),
            ),
            nbinsx = 12,
            nbinsy = 18,
        ))

        # Individual event scatter dots
        fig.add_trace(go.Scatter(
            x    = xs,
            y    = ys,
            mode = "markers",
            marker = dict(
                size  = 8,
                color = "rgba(255,255,255,0.6)",
                line  = dict(color="rgba(0,0,0,0.4)", width=1),
            ),
            name    = filter_event,
            hovertemplate = "x: %{x:.2f}<br>y: %{y:.2f}<extra></extra>",
        ))

        title_text = (
            f"Mapa de Calor — {filter_event}" if lang == "es"
            else f"Spatial Heatmap — {filter_event}"
        )

        fig.update_layout(
            title = dict(text=title_text, font=dict(color="#2ecc71", size=14)),
            template      = "plotly_dark",
            paper_bgcolor = "#0e1117",
            plot_bgcolor  = "#1a4a1a",
            height        = 480,
            margin        = dict(t=40, b=20, l=20, r=40),
            xaxis = dict(
                range=[0,1], showgrid=False, zeroline=False,
                showticklabels=False,
                title=dict(text="← Touchline | Touchline →",
                           font=dict(color="#888", size=10)),
            ),
            yaxis = dict(
                range=[0,1], showgrid=False, zeroline=False,
                showticklabels=False,
                title=dict(text="Try Line ↕ Try Line",
                           font=dict(color="#888", size=10)),
            ),
            showlegend = False,
        )

        return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  TEAM CLUSTERER  (K-Means jersey colour — unchanged from v3)
# ═══════════════════════════════════════════════════════════════════════════════

class TeamClusterer:
    """
    K-Means clustering on HSV hue histograms to auto-separate Home vs Away.
    See v3 docstring for full mathematical explanation.
    """
    def __init__(self, n_bins: int = 16):
        self.n_bins   = n_bins
        self._fitted  = False
        self._id_map: dict[int, str] = {}

    def _torso_crop(self, frame: np.ndarray, d: Detection) -> np.ndarray:
        h, w = frame.shape[:2]
        x1 = max(0, int(d.x - d.w/2)); x2 = min(w, int(d.x + d.w/2))
        y1 = max(0, int(d.y - d.h/2)); y2 = min(h, int(d.y + d.h/2))
        th = y2 - y1
        c  = frame[y1+int(th*.30):y1+int(th*.70), x1:x2]
        return c if c.size > 0 else frame[y1:y2, x1:x2]

    def _hist(self, crop: np.ndarray) -> np.ndarray:
        try:
            import cv2
            hsv  = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
            h    = cv2.calcHist([hsv],[0],None,[self.n_bins],[0,180]).flatten().astype(float)
            s    = h.sum()
            return h/s if s > 0 else h
        except Exception:
            return np.zeros(self.n_bins)

    def fit(self, frame: np.ndarray, dets: list[Detection]) -> None:
        from sklearn.cluster import KMeans
        persons = [d for d in dets if d.label == "person"]
        if len(persons) < 4: return
        hists = np.array([self._hist(self._torso_crop(frame, p)) for p in persons])
        km    = KMeans(n_clusters=2, n_init=10, random_state=42)
        km.fit(hists)
        self._fitted = True
        for p, lbl in zip(persons, km.labels_):
            self._id_map[p.track_id] = "home" if lbl == 0 else "away"

    def assign(self, dets: list[Detection]) -> list[Detection]:
        if not self._fitted: return dets
        for d in dets:
            d.team = self._id_map.get(d.track_id, "unknown")
        return dets


# ═══════════════════════════════════════════════════════════════════════════════
#  RUGBY EVENT DETECTOR  (spatial + temporal heuristics — v3 preserved)
# ═══════════════════════════════════════════════════════════════════════════════

class RugbyEventDetector:
    """
    Stateful frame-by-frame classifier.
    Mathematical logic documented in v3. Unchanged in v4.
    """
    TACKLE_DIST_PX    = 60
    TACKLE_SPEED_FALL = 0.50
    TACKLE_WINDOW     = 15
    RUCK_RADIUS_PX    = 80
    RUCK_MIN_PLAYERS  = 3
    RUCK_SUSTAIN      = 12
    SCRUM_CLUSTER_N   = 3
    SCRUM_FACING_TOL  = 0.35
    LINEOUT_ROW_N     = 3
    LINEOUT_Y_GAP_MIN = 30
    LINEOUT_Y_GAP_MAX = 140

    def __init__(self, fps=25, skip_n=3, pixels_per_meter=40.0):
        self.fps   = fps
        self.skip_n = skip_n
        self.px_per_m = pixels_per_meter
        self._history:      collections.deque = collections.deque(maxlen=60)
        self._ball_history: collections.deque = collections.deque(maxlen=60)
        self._ruck_frames = 0

    def update(self, dets: list[Detection], frame_idx: int) -> list[FrameEvent]:
        self._history.append(dets)
        ball = next((d for d in dets if d.label=="sports ball"), None)
        if ball: self._ball_history.append((frame_idx, ball.x, ball.y))
        persons = [d for d in dets if d.label=="person"]
        events  = []
        ev = self._check_ruck(persons, ball, frame_idx)
        if ev: events.append(ev)
        ev = self._check_tackle(persons, ball, frame_idx)
        if ev: events.append(ev)
        ev = self._check_scrum(persons, frame_idx)
        if ev: events.append(ev)
        ev = self._check_lineout(persons, frame_idx)
        if ev: events.append(ev)
        return events

    def _check_tackle(self, persons, ball, frame_idx):
        if len(persons) < 2: return None
        contact_pair, min_dist = None, float("inf")
        for i, pa in enumerate(persons):
            for pb in persons[i+1:]:
                if pa.team != "unknown" and pb.team != "unknown" and pa.team == pb.team:
                    continue
                d = math.dist((pa.x,pa.y),(pb.x,pb.y))
                if d < self.TACKLE_DIST_PX and d < min_dist:
                    min_dist, contact_pair = d, (pa,pb)
        if not contact_pair: return None
        if len(self._ball_history) < 4:
            conf = 0.45*(1-min_dist/self.TACKLE_DIST_PX)
            loc  = (int(contact_pair[0].x), int(contact_pair[0].y))
            return FrameEvent("Tackle", round(conf,2), frame_idx, loc,
                              f"Proximity {min_dist:.0f}px (no velocity data)")
        recent = list(self._ball_history)[-min(self.TACKLE_WINDOW, len(self._ball_history)):]
        _, x0,y0 = recent[0]; _, x1,y1 = recent[-1]
        n = len(recent)
        disp = math.dist((x0,y0),(x1,y1))
        t    = n*self.skip_n/self.fps
        vel  = (disp/self.px_per_m)/t if t>0 else 99.0
        if vel < self.TACKLE_SPEED_FALL:
            conf = min(0.95, 0.65+0.30*(1-min_dist/self.TACKLE_DIST_PX))
            loc  = (int((contact_pair[0].x+contact_pair[1].x)/2),
                    int((contact_pair[0].y+contact_pair[1].y)/2))
            return FrameEvent("Tackle", round(conf,2), frame_idx, loc,
                              f"Ball v={vel:.2f}m/s, prox={min_dist:.0f}px")
        return None

    def _check_ruck(self, persons, ball, frame_idx):
        bpos = None
        if ball: bpos = (ball.x, ball.y)
        elif self._ball_history: _, bx,by = self._ball_history[-1]; bpos=(bx,by)
        if not bpos: self._ruck_frames=0; return None
        nearby = [p for p in persons if math.dist((p.x,p.y),bpos)<self.RUCK_RADIUS_PX]
        if len(nearby) >= self.RUCK_MIN_PLAYERS:
            self._ruck_frames += 1
        else:
            self._ruck_frames = max(0, self._ruck_frames-1)
        if self._ruck_frames >= self.RUCK_SUSTAIN:
            conf = min(0.95, 0.70+0.05*(len(nearby)-self.RUCK_MIN_PLAYERS))
            return FrameEvent("Ruck", round(conf,2), frame_idx,
                              (int(bpos[0]),int(bpos[1])),
                              f"{len(nearby)} players in {self.RUCK_RADIUS_PX}px for {self._ruck_frames}f")
        return None

    def _check_scrum(self, persons, frame_idx):
        if len(persons) < 2*self.SCRUM_CLUSTER_N: return None
        sx = sorted(persons, key=lambda p:p.x)
        mid = len(sx)//2
        lg, rg = sx[:mid], sx[mid:]
        if len(lg)<self.SCRUM_CLUSTER_N or len(rg)<self.SCRUM_CLUSTER_N: return None
        cl = (np.mean([p.x for p in lg]), np.mean([p.y for p in lg]))
        cr = (np.mean([p.x for p in rg]), np.mean([p.y for p in rg]))
        xs = [p.x for p in persons]
        xsp = max(xs)-min(xs)
        ly_std = np.std([p.y for p in lg]); ry_std = np.std([p.y for p in rg])
        if (abs(cr[0]-cl[0])>0.25*xsp and abs(cr[1]-cl[1])<0.4*xsp
                and (ly_std+ry_std)/2 < 55):
            epi  = (int((cl[0]+cr[0])/2), int((cl[1]+cr[1])/2))
            conf = min(0.90, 0.60+0.10*(len(persons)/16))
            return FrameEvent("Scrum", round(conf,2), frame_idx, epi,
                              f"σ_y={(ly_std+ry_std)/2:.1f}px")
        return None

    def _check_lineout(self, persons, frame_idx):
        if len(persons)<2*self.LINEOUT_ROW_N: return None
        sp   = sorted(persons, key=lambda p:p.x)
        xs   = [p.x for p in sp]
        best_split, best_gap = None, 0
        for i in range(len(xs)-1):
            gap = xs[i+1]-xs[i]
            if self.LINEOUT_Y_GAP_MIN<gap<self.LINEOUT_Y_GAP_MAX and gap>best_gap:
                best_gap, best_split = gap, i+1
        if best_split is None: return None
        ra, rb = sp[:best_split], sp[best_split:]
        if len(ra)<self.LINEOUT_ROW_N or len(rb)<self.LINEOUT_ROW_N: return None
        ya_range = max(p.y for p in ra)-min(p.y for p in ra)
        yb_range = max(p.y for p in rb)-min(p.y for p in rb)
        ov = max(0, min(max(p.y for p in ra), max(p.y for p in rb))
                  - max(min(p.y for p in ra), min(p.y for p in rb)))
        if ov/(min(ya_range,yb_range)+1)>0.6:
            cx = int(np.mean([p.x for p in ra+rb]))
            cy = int(np.mean([p.y for p in ra+rb]))
            conf = min(0.88, 0.58+0.06*(len(ra)+len(rb)))
            return FrameEvent("Line-out", round(conf,2), frame_idx, (cx,cy),
                              f"Rows {len(ra)}+{len(rb)}, gap={best_gap:.0f}px")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  DRAWING & EXPORT UTILITIES  (v3 preserved)
# ═══════════════════════════════════════════════════════════════════════════════

TEAM_COLOURS = {
    "home":    (29,  185, 84),
    "away":    (46,  134, 222),
    "unknown": (180, 180, 180),
}


def draw_detections(frame: np.ndarray, dets: list[Detection],
                    events: list[FrameEvent]) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return frame
    out = frame.copy()
    for d in dets:
        x1,y1 = int(d.x-d.w/2),int(d.y-d.h/2)
        x2,y2 = int(d.x+d.w/2),int(d.y+d.h/2)
        if d.label == "sports ball":
            c = (201,162,39)
            cv2.circle(out,(int(d.x),int(d.y)),12,c,2)
            cv2.putText(out,"Ball",(x1,y1-5),cv2.FONT_HERSHEY_SIMPLEX,.42,c,1,cv2.LINE_AA)
        else:
            c = TEAM_COLOURS.get(d.team,(180,180,180))
            cv2.rectangle(out,(x1,y1),(x2,y2),c,2)
            tag = f"#{d.track_id} {d.team.upper()}"
            cv2.putText(out,tag,(x1,y1-5),cv2.FONT_HERSHEY_SIMPLEX,.40,c,1,cv2.LINE_AA)
    ev_clrs = {"Tackle":(232,67,67),"Ruck":(29,185,84),
               "Scrum":(201,162,39),"Line-out":(46,134,222)}
    for ev in events:
        ec = ev_clrs.get(ev.event,(255,255,255))
        cx,cy = ev.location
        cv2.circle(out,(cx,cy),30,ec,3)
        cv2.circle(out,(cx,cy),5,ec,-1)
        cv2.putText(out,f"{ev.event} {ev.confidence:.0%}",
                    (cx-40,cy-38),cv2.FONT_HERSHEY_SIMPLEX,.52,ec,2,cv2.LINE_AA)
    return out


def frame_skip_generator(cap, skip_n: int = 3):
    """Yield (frame_idx, frame_rgb) every Nth frame."""
    try:
        import cv2
    except ImportError:
        return
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        if idx % skip_n == 0:
            yield idx, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        idx += 1
    cap.release()


def export_annotated_frame(base_rgb: np.ndarray,
                           canvas_overlay_rgba: np.ndarray | None = None) -> bytes:
    """Composite YOLO frame + canvas drawing → PNG bytes."""
    from PIL import Image
    base = Image.fromarray(base_rgb.astype(np.uint8),"RGB").convert("RGBA")
    if canvas_overlay_rgba is not None:
        ov = Image.fromarray(canvas_overlay_rgba.astype(np.uint8),"RGBA")
        if ov.size != base.size:
            ov = ov.resize(base.size, Image.LANCZOS)
        base = Image.alpha_composite(base, ov)
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def run_yolo_on_frame(model, frame_rgb: np.ndarray) -> list[Detection]:
    """Run cached YOLO model, return Detection list for persons + ball."""
    dets: list[Detection] = []
    try:
        results = model(frame_rgb, verbose=False)[0]
        for i, box in enumerate(results.boxes):
            cls = int(box.cls[0])
            lbl = results.names[cls]
            if lbl not in ("person","sports ball"): continue
            x1,y1,x2,y2 = map(float, box.xyxy[0])
            w,h = x2-x1, y2-y1
            dets.append(Detection(
                track_id=i, label=lbl,
                x=x1+w/2, y=y1+h/2, w=w, h=h,
                conf=float(box.conf[0]),
            ))
    except Exception:
        pass
    return dets


# ═══════════════════════════════════════════════════════════════════════════════
#  TACTICAL KNOWLEDGE BASE  (v3 preserved — full ES titles added via i18n)
# ═══════════════════════════════════════════════════════════════════════════════

TACTICAL_ADVICE = {
    "Ruck": {
        "title":  "🔵 Ruck — Technical Checkpoints",
        "color":  "#1a9e5c",
        "checkpoints": [
            "**Body Position**: Hips low, spine parallel to ground — drive from legs, not back.",
            "**Leg Drive**: Short, explosive steps. Stay on your feet at all costs.",
            "**Bind**: Full-arm bind on jersey before engaging — no slaps.",
            "**Gate Entry**: Always arrive through the gate (behind hindmost foot of teammate).",
            "**Clear-Out Priority**: Target nearest threat first. Low entry wins collisions.",
            "**Jackaling Defence**: Get low and establish body-over-ball BEFORE ruck forms.",
            "**Breakdown Speed**: Ball must be available within 3 seconds or recycle.",
        ],
        "tip":    "💡 Watch the referee's eyes — they telegraph the penalty before whistling.",
        "drills": ["Jackle Bag Circuit (3×10)", "Chop Tackle → Clear-Out (2×5/side)", "Gate Entry Ladder (4×6)"],
    },
    "Scrum": {
        "title":  "⚫ Scrum — Technical Checkpoints",
        "color":  "#c9a227",
        "checkpoints": [
            "**Bind Sequence**: Crouch → Bind → Set. Never rush the set call.",
            "**Prop Mechanics**: Tight-head drives in and up. Loose-head drives straight.",
            "**Hooker Strike**: Strike on the 'S' of 'Set' — sharp and accurate.",
            "**Back-5 Push**: Lock shoulders connect to prop hips. Drive in unison.",
            "**No.8 Control**: Channel 1 vs Channel 3 — decide BEFORE ball comes back.",
            "**Scrum-half Positioning**: Stay behind scrum — movement before ball = penalty.",
            "**Reset Awareness**: If collapsing, release immediately to avoid yellow card.",
        ],
        "tip":    "💡 The dominant scrum wins 70% of subsequent plays.",
        "drills": ["Machine Scrum (5×3 reps)", "Live Engagement Sequence (3×5)", "Channel Decision Drill (4×3)"],
    },
    "Line-out": {
        "title":  "🟢 Line-out — Technical Checkpoints",
        "color":  "#2e86de",
        "checkpoints": [
            "**Lineout Caller**: Signals must be clear — use coded hand signals.",
            "**Jumper Timing**: Jump on thrower's release, not before.",
            "**Lifters**: Outside foot forward, low squat. Lift is leg-driven.",
            "**Throw Accuracy**: Aim for jumper's chest. Consistent 7-step routine.",
            "**Maul Binding**: Immediate and legal bind on jumper as they land.",
            "**Pod Structure**: Middle vs tail pods — disguise targets with dummy pods.",
            "**Peel Options**: If lineout is lost, defensive pods contest maul immediately.",
        ],
        "tip":    "💡 Study wind direction before match — significantly affects throw-in angle.",
        "drills": ["Throw Accuracy Wall Drill (50 reps)", "Two-Man Lift (3×8)", "Dummy Pod Movement (4×5)"],
    },
    "Kick": {
        "title":  "🟡 Kicking Game — Technical Checkpoints",
        "color":  "#e84393",
        "checkpoints": [
            "**Foot Strike Zone**: Contact ball at 2 o'clock position for spiral kick.",
            "**Follow-Through**: Kicking leg drives upward through ball — don't stop at contact.",
            "**Box Kick**: High, contestable, lands 15m behind backfield. Hang time > distance.",
            "**Chip & Chase**: Kick PAST the last defender — not over them.",
            "**Grubber**: Low trajectory, ball's point down at contact. Read the surface.",
            "**Up & Under**: Kick straight up — chasers must be onside at the kick.",
            "**Exit Strategy**: Know target zone BEFORE receiving in your own 22.",
        ],
        "tip":    "💡 Chase the kick with inside shoulder — prevents catcher from stepping inside.",
        "drills": ["20× Box Kick (contested)", "10× Grubber Target (precision)", "5× Up & Under + Chase"],
    },
    "Tackle": {
        "title":  "🔴 Tackle — Technical Checkpoints",
        "color":  "#e84343",
        "checkpoints": [
            "**Cheek-to-Cheek**: Plant cheek against ball-carrier's hip — never lead with crown.",
            "**Height**: Aim below ball-carrier's centre of gravity. Mid-thigh is ideal.",
            "**Wrap & Drive**: Wrap both arms. Drive legs through the contact point.",
            "**Shoulder Contact**: Lead shoulder makes first contact, arms wrap immediately after.",
            "**Jackal Position**: After tackle, immediate body-over-ball contest. Get low first.",
            "**Counter-Ruck Awareness**: If you're the tackler, roll away immediately.",
            "**Defensive Line Speed**: Re-set and advance BEFORE ball is played from ruck.",
        ],
        "tip":    "💡 Missed tackles cost ~2.3 points/game at elite level — technique is non-negotiable.",
        "drills": ["Bag Tackle Circuit (3×10)", "1v1 Tackle in Channel (4×5)", "Jackal Entry (2×8)"],
    },
    "Maul": {
        "title":  "🟠 Maul — Technical Checkpoints",
        "color":  "#e8a843",
        "checkpoints": [
            "**Ball Carrier**: Protect ball on inside hip. Never expose it outside.",
            "**First Bind**: Immediate, legal bind from behind — no side-entry.",
            "**Drive Direction**: Identify the weak shoulder of defending pod and target it.",
            "**Ball Movement**: Move ball through maul — static ball = penalty.",
            "**No.8 / Blindside**: Ready to peel wide if maul slows.",
            "**Defensive Maul**: Bind and drive in same direction — pull carrier down.",
            "**Scrum Option**: If maul stalls, call scrum early.",
        ],
        "tip":    "💡 A rolling maul gains ~6m per phase — commitment to carry is the key variable.",
        "drills": ["Rolling Maul (3×40m)", "3v2 Maul Contest (4×3)", "Peel Timing Drill (3×5)"],
    },
}


def get_advice(event: str) -> dict | None:
    return TACTICAL_ADVICE.get(event)


def list_events() -> list:
    return list(TACTICAL_ADVICE.keys())
