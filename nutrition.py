"""
nutrition.py  ─  Rugby Performance OS  v4 (Franchise Edition)
=============================================================
All v3 features preserved. ACWR lives in data_manager.py;
this module provides display helpers for the ACWR widget.
"""

import math


# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

HARD_DAY_EVENTS   = {"Match Day", "Rugby Training"}
TDEE_HARD_BOOST   = 0.20
TDEE_BULK_SURPLUS = 400
PROTEIN_G_PER_KG  = 2.2
FAT_PCT_NORMAL    = 0.25
FAT_PCT_HARD_DAY  = 0.18


# ─────────────────────────────────────────────────────────────────────────────
#  BMR / TDEE
# ─────────────────────────────────────────────────────────────────────────────

def calculate_bmr(weight_kg, height_cm, age=25, sex="male"):
    base = (10*weight_kg)+(6.25*height_cm)-(5*age)
    return base+5 if sex=="male" else base-161


def calculate_tdee(bmr, activity_level):
    mults = {
        "sedentary":1.2,"lightly_active":1.375,
        "moderately_active":1.55,"very_active":1.725,"extra_active":1.9,
    }
    return bmr * mults.get(activity_level, 1.725)


# ─────────────────────────────────────────────────────────────────────────────
#  Epley 1RM
# ─────────────────────────────────────────────────────────────────────────────

def epley_1rm(weight_kg: float, reps: int) -> float:
    """1RM = weight × (1 + reps/30)  —  Epley (1985)"""
    if reps <= 0: return 0.0
    if reps == 1: return round(weight_kg, 1)
    return round(weight_kg*(1+reps/30), 1)


def compute_all_1rms(pr_df):
    import pandas as pd
    df    = pr_df.copy()
    lifts = [
        ("squat_kg","squat_reps","squat_1rm"),
        ("bench_kg","bench_reps","bench_1rm"),
        ("deadlift_kg","deadlift_reps","deadlift_1rm"),
        ("power_clean_kg","power_clean_reps","power_clean_1rm"),
    ]
    for kc, rc, oc in lifts:
        if kc in df.columns and rc in df.columns:
            df[oc] = df.apply(
                lambda row: epley_1rm(
                    float(row[kc]) if pd.notna(row[kc]) else 0,
                    int(row[rc])   if pd.notna(row[rc]) else 1,
                ), axis=1,
            )
        else:
            df[oc] = df.get(kc, 0)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Body Metrics Correlation Alert
# ─────────────────────────────────────────────────────────────────────────────

def check_fat_gain_alert(phys_df, pr_df) -> dict:
    """Weight↑ + 1RM↓ = potential fat gain. Returns alert dict."""
    import pandas as pd
    result = {"alert":False,"weight_delta":0.0,"strength_delta":0.0,"message":""}
    if len(phys_df)<2 or len(pr_df)<2: return result
    ps   = phys_df.sort_values("date")
    w_old,w_new = float(ps.iloc[-2]["weight_kg"]), float(ps.iloc[-1]["weight_kg"])
    w_d  = w_new-w_old
    pr1  = compute_all_1rms(pr_df.sort_values("date"))
    if "squat_1rm" not in pr1.columns: return result
    s_old,s_new = float(pr1.iloc[-2]["squat_1rm"]), float(pr1.iloc[-1]["squat_1rm"])
    s_d  = s_new-s_old
    result.update({"weight_delta":round(w_d,1),"strength_delta":round(s_d,1)})
    if w_d > 0.5 and s_d < -2.0:
        result["alert"] = True
        result["message"] = (
            f"⚠️ **Fat Gain Alert**: Weight +{w_d:.1f}kg but Squat 1RM {s_d:.1f}kg. "
            f"Reduce caloric surplus by 150–200 kcal and review training intensity."
        )
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Smart Bulking Targets  (Calendar Sync +20%)
# ─────────────────────────────────────────────────────────────────────────────

def bulking_targets(weight_kg, height_cm, activity_level="very_active",
                    today_events=None, age=25):
    bmr  = calculate_bmr(weight_kg, height_cm, age)
    tdee = calculate_tdee(bmr, activity_level)
    today_events = today_events or []
    is_hard      = any(ev in HARD_DAY_EVENTS for ev in today_events)
    adj_tdee     = tdee*(1+TDEE_HARD_BOOST) if is_hard else tdee
    base_cal     = adj_tdee + TDEE_BULK_SURPLUS
    fat_pct      = FAT_PCT_HARD_DAY if is_hard else FAT_PCT_NORMAL
    protein_g    = weight_kg*PROTEIN_G_PER_KG
    protein_kcal = protein_g*4
    fat_kcal     = base_cal*fat_pct;  fat_g = fat_kcal/9
    carb_kcal    = base_cal-protein_kcal-fat_kcal; carb_g = carb_kcal/4
    return {
        "bmr":round(bmr),"tdee":round(tdee),"adjusted_tdee":round(adj_tdee),
        "base_calories":round(base_cal),"bulking_calories":round(base_cal),
        "protein_g":round(protein_g),"fat_g":round(fat_g),"carb_g":round(carb_g),
        "protein_kcal":round(protein_kcal),"fat_kcal":round(fat_kcal),"carb_kcal":round(carb_kcal),
        "is_hard_day":is_hard,"tdee_boost_pct":TDEE_HARD_BOOST if is_hard else 0.0,
        "fat_pct":fat_pct,"today_events":today_events,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Radar Chart Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_radar_data(measures_df) -> dict:
    import pandas as pd
    REF = {"quad_cm":65.0,"arm_cm":42.0,"chest_cm":115.0}
    if measures_df.empty: return {}
    latest = measures_df.sort_values("date").iloc[-1]
    cats   = ["Quadriceps","Arm / Bicep","Chest"]
    vals   = []
    for k in ["quad_cm","arm_cm","chest_cm"]:
        v = float(latest[k]) if pd.notna(latest.get(k)) else 0
        vals.append(round(v/REF[k]*100, 1))
    return {
        "categories":cats, "values":vals,
        "reference":[100.0]*3,
        "raw":{"Quadriceps":float(latest.get("quad_cm",0)),
               "Arm":float(latest.get("arm_cm",0)),
               "Chest":float(latest.get("chest_cm",0))},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  ACWR Display Helper
# ─────────────────────────────────────────────────────────────────────────────

def acwr_zone_meta(zone: str, lang: str = "en") -> dict:
    """
    Return display metadata for an ACWR zone.
    Used by the UI to show the correct colour, label and advice.
    """
    meta = {
        "insufficient_data": {
            "color": "#5a6070",
            "label": {"es":"Sin datos suficientes","en":"Insufficient data"},
            "advice":{"es":"Necesitás al menos 4 semanas de agenda para calcular ACWR.",
                      "en":"You need at least 4 weeks of schedule data to compute ACWR."},
            "bar_pct": 0,
        },
        "undertraining": {
            "color": "#3498db",
            "label": {"es":"Bajo Entrenamiento","en":"Undertraining"},
            "advice":{"es":"Carga muy baja. Incrementá gradualmente el volumen.",
                      "en":"Load is very low. Gradually increase training volume."},
            "bar_pct": 20,
        },
        "safe": {
            "color": "#2ecc71",
            "label": {"es":"✅ Zona Segura","en":"✅ Safe Zone"},
            "advice":{"es":"Ratio óptimo. Mantené la progresión actual.",
                      "en":"Optimal ratio. Maintain current progression."},
            "bar_pct": 55,
        },
        "caution": {
            "color": "#f1c40f",
            "label": {"es":"⚠️ Precaución","en":"⚠️ Caution"},
            "advice":{"es":"Acercándote al límite. Monitoreá la fatiga de cerca.",
                      "en":"Approaching the limit. Monitor fatigue closely."},
            "bar_pct": 78,
        },
        "danger": {
            "color": "#e74c3c",
            "label": {"es":"🚨 RIESGO ALTO DE LESIÓN","en":"🚨 HIGH INJURY RISK"},
            "advice":{"es":"ACWR > 1.5. Reducí la carga esta semana inmediatamente.",
                      "en":"ACWR > 1.5. Reduce training load this week immediately."},
            "bar_pct": 100,
        },
    }
    m = meta.get(zone, meta["insufficient_data"])
    return {
        "color":   m["color"],
        "label":   m["label"].get(lang, m["label"]["en"]),
        "advice":  m["advice"].get(lang, m["advice"]["en"]),
        "bar_pct": m["bar_pct"],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Meal Timing Protocol
# ─────────────────────────────────────────────────────────────────────────────

def get_meal_timing_advice(lang: str = "en") -> list:
    meals_en = [
        {"window":"Wake-up (06:00)",       "rec":"30g whey protein + banana + espresso. Kick-start MPS."},
        {"window":"Breakfast (07:30)",     "rec":"Oats + 4 eggs + whole milk + berries. ~700 kcal."},
        {"window":"Pre-Training (11:00)",  "rec":"Rice + chicken breast + veg. Eat 2hrs before sessions."},
        {"window":"Intra-Training",        "rec":"500ml sports drink (40g fast carbs). Sustain glycogen."},
        {"window":"Post-Training (13:30)", "rec":"40g whey + 60g dextrose within 30min. Anabolic window."},
        {"window":"Lunch (14:30)",         "rec":"400g pasta + 200g lean beef + olive oil. Peak calorie meal."},
        {"window":"Snack (17:00)",         "rec":"250g Greek yogurt + 30g nuts + seasonal fruit."},
        {"window":"Dinner (19:30)",        "rec":"200g salmon or red meat + sweet potato + green veg."},
        {"window":"Pre-Bed (22:00)",       "rec":"40g casein + 2 tbsp peanut butter. Overnight MPS."},
    ]
    meals_es = [
        {"window":"Despertar (06:00)",     "rec":"30g proteína whey + banana + café. Activá la síntesis proteica."},
        {"window":"Desayuno (07:30)",      "rec":"Avena + 4 huevos + leche entera + berries. ~700 kcal."},
        {"window":"Pre-Entreno (11:00)",   "rec":"Arroz + pechuga de pollo + verduras. Comé 2hs antes."},
        {"window":"Intra-Entreno",         "rec":"500ml bebida isotónica (40g carbos rápidos). Glucógeno."},
        {"window":"Post-Entreno (13:30)",  "rec":"40g whey + 60g dextrosa en 30min. Ventana anabólica."},
        {"window":"Almuerzo (14:30)",      "rec":"400g pasta + 200g carne magra + aceite de oliva."},
        {"window":"Merienda (17:00)",      "rec":"250g yogur griego + 30g nueces + fruta de temporada."},
        {"window":"Cena (19:30)",          "rec":"200g salmón o carne roja + batata + verduras verdes."},
        {"window":"Pre-Cama (22:00)",      "rec":"40g caseína + 2 cdas mantequilla de maní. MPS nocturna."},
    ]
    return meals_es if lang == "es" else meals_en
