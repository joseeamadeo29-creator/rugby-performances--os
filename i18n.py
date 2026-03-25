"""
i18n.py  ─  Rugby Performance OS  v4
======================================
Internacionalización / Internationalization

Uso / Usage:
    from modules.i18n import t, LANG
    st.markdown(t("dashboard_title"))

    El idioma se controla desde st.session_state["lang"]
    Language controlled from st.session_state["lang"]
    Values: "es" | "en"
"""

# ── Diccionario completo ES / EN ──────────────────────────────────────────────
_STRINGS: dict[str, dict[str, str]] = {

    # ── Sidebar ───────────────────────────────────────────────────────────────
    "app_subtitle":         {"es": "EDICIÓN PROFESIONAL v4",    "en": "PROFESSIONAL EDITION v4"},
    "nav_label":            {"es": "Navegación",                "en": "Navigation"},
    "nav_dashboard":        {"es": "🏠 Dashboard",              "en": "🏠 Dashboard"},
    "nav_squad":            {"es": "👥 Plantel",                "en": "👥 Squad"},
    "nav_tactics":          {"es": "🎬 Tácticas",              "en": "🎬 Tactics Lab"},
    "nav_physical":         {"es": "💪 Físico",                "en": "💪 Physical Hub"},
    "nav_journal":          {"es": "📓 Diario",                "en": "📓 Journal"},
    "nav_schedule":         {"es": "📅 Agenda",                "en": "📅 Schedule"},
    "live_kpis":            {"es": "KPIs en Vivo",             "en": "Live KPIs"},
    "weight_label":         {"es": "⚖️ Peso",                  "en": "⚖️ Weight"},
    "squat_1rm_label":      {"es": "🏋️ 1RM Squat",            "en": "🏋️ Squat 1RM"},
    "avg_perf_label":       {"es": "⭐ Rend. Promedio",        "en": "⭐ Avg Perf"},
    "lang_toggle":          {"es": "🌐 English",               "en": "🌐 Español"},
    "today_label":          {"es": "HOY",                      "en": "TODAY"},
    "select_player":        {"es": "Jugador Activo",           "en": "Active Player"},
    "add_player":           {"es": "+ Nuevo Jugador",          "en": "+ New Player"},

    # ── Dashboard ─────────────────────────────────────────────────────────────
    "dashboard_title":      {"es": "PANEL DE RENDIMIENTO",     "en": "PERFORMANCE DASHBOARD"},
    "dashboard_sub":        {"es": "KPIs en tiempo real · Alertas · Resumen semanal",
                             "en": "Real-time KPIs · Alerts · Weekly summary"},
    "burnout_title":        {"es": "🚨 Fatiga Mental Detectada","en": "🚨 Mental Fatigue Detected"},
    "burnout_body":         {"es": "3 entradas consecutivas con sentimiento negativo. "
                                   "Recomendación: Agendá un Día de Descanso Activo.",
                             "en": "3 consecutive journal entries with negative sentiment. "
                                   "Recommendation: Schedule an Active Rest Day."},
    "fat_gain_title":       {"es": "⚠️ Alerta de Composición Corporal",
                             "en": "⚠️ Body Composition Alert"},
    "kpi_body_weight":      {"es": "PESO CORPORAL",            "en": "BODY WEIGHT"},
    "kpi_squat_1rm":        {"es": "1RM SQUAT",                "en": "SQUAT 1RM"},
    "kpi_avg_perf":         {"es": "REND. PROMEDIO",           "en": "AVG PERFORMANCE"},
    "kpi_today":            {"es": "HOY",                      "en": "TODAY"},
    "epley_label":          {"es": "Fórmula Epley",            "en": "Epley formula"},
    "entries_label":        {"es": "entradas",                 "en": "entries"},
    "no_history":           {"es": "Sin historial",            "en": "No history"},
    "weight_trend":         {"es": "Evolución del Peso",       "en": "Body Weight Trend"},
    "perf_sentiment":       {"es": "Rendimiento & Sentimiento","en": "Performance & Sentiment"},
    "pdf_section":          {"es": "Informe Post-Partido",     "en": "Post-Match Report"},
    "pdf_button":           {"es": "📄 Generar Informe PDF",   "en": "📄 Generate PDF Report"},
    "pdf_download":         {"es": "⬇️ Descargar PDF",         "en": "⬇️ Download PDF"},
    "pdf_building":         {"es": "Generando PDF…",           "en": "Building PDF…"},
    "pdf_error":            {"es": "fpdf2 no instalado. Ejecutá: pip install fpdf2",
                             "en": "fpdf2 not installed. Run: pip install fpdf2"},
    "log_2_more":           {"es": "Registrá 2+ mediciones para ver la tendencia.",
                             "en": "Log 2+ measurements to see the trend."},
    "log_2_journal":        {"es": "Registrá 2+ entradas del diario.",
                             "en": "Log 2+ journal entries."},
    "acwr_section":         {"es": "Carga de Trabajo (ACWR)",  "en": "Workload (ACWR)"},
    "acwr_safe":            {"es": "✅ Zona Segura",           "en": "✅ Safe Zone"},
    "acwr_caution":         {"es": "⚠️ Zona de Precaución",   "en": "⚠️ Caution Zone"},
    "acwr_danger":          {"es": "🚨 RIESGO ALTO DE LESIÓN", "en": "🚨 HIGH INJURY RISK"},
    "acwr_no_data":         {"es": "Sin datos de agenda suficientes para ACWR.",
                             "en": "Not enough schedule data for ACWR."},

    # ── Squad Management ──────────────────────────────────────────────────────
    "squad_title":          {"es": "GESTIÓN DEL PLANTEL",      "en": "SQUAD MANAGEMENT"},
    "squad_sub":            {"es": "Agregá jugadores · Cambiá perfiles · Comparación",
                             "en": "Add players · Switch profiles · Compare"},
    "squad_add_section":    {"es": "Nuevo Jugador",            "en": "New Player"},
    "player_name":          {"es": "Nombre completo",          "en": "Full name"},
    "player_position":      {"es": "Posición",                 "en": "Position"},
    "player_number":        {"es": "Número de camiseta",       "en": "Jersey number"},
    "player_dob":           {"es": "Fecha de nacimiento",      "en": "Date of birth"},
    "player_save":          {"es": "💾 Guardar Jugador",       "en": "💾 Save Player"},
    "player_saved_ok":      {"es": "✅ Jugador guardado.",     "en": "✅ Player saved."},
    "player_exists":        {"es": "⚠️ Ya existe un jugador con ese nombre.",
                             "en": "⚠️ A player with that name already exists."},
    "squad_roster":         {"es": "Plantel Actual",           "en": "Current Roster"},
    "squad_comparison":     {"es": "Comparación de 1RM entre Jugadores",
                             "en": "Player 1RM Comparison"},
    "squad_no_pr":          {"es": "Sin datos de PR para comparar.",
                             "en": "No PR data to compare."},
    "squad_empty":          {"es": "Agregá jugadores para ver el plantel.",
                             "en": "Add players to see the roster."},
    "squad_delete":         {"es": "🗑️ Eliminar",             "en": "🗑️ Delete"},
    "squad_set_active":     {"es": "✅ Activar",               "en": "✅ Set Active"},

    # ── Tactics Lab ───────────────────────────────────────────────────────────
    "tactics_title":        {"es": "LABORATORIO TÁCTICO",      "en": "VIDEO TACTICS LAB"},
    "tactics_sub":          {"es": "YOLOv8 · Clustering · IA de Eventos · Heatmap · Telestrador",
                             "en": "YOLOv8 · Clustering · Event AI · Heatmap · Telestrator"},
    "video_input":          {"es": "Entrada de Video",         "en": "Video Input"},
    "upload_video":         {"es": "Subí el footage del partido (MP4 / MOV)",
                             "en": "Upload match footage (MP4 / MOV)"},
    "analysis_controls":    {"es": "Controles de Análisis",    "en": "Analysis Controls"},
    "frame_label":          {"es": "Frame #",                  "en": "Frame #"},
    "skip_label":           {"es": "Saltar",                   "en": "Skip"},
    "yolo_label":           {"es": "🤖 YOLO",                 "en": "🤖 YOLO"},
    "event_ai_label":       {"es": "🧠 IA de Eventos",        "en": "🧠 Event AI"},
    "team_cluster_label":   {"es": "👕 Clustering de Equipos", "en": "👕 Team Clustering"},
    "analyse_btn":          {"es": "📸 Analizar Frame",        "en": "📸 Analyse Frame"},
    "frame_skip_info":      {"es": "SALTO DE FRAMES",          "en": "FRAME SKIP"},
    "faster_processing":    {"es": "procesamiento más rápido", "en": "faster processing"},
    "eff_fps":              {"es": "fps efectivos",            "en": "effective fps"},
    "telestrator_title":    {"es": "Telestrador — Dibujá sobre el Frame",
                             "en": "Telestrator — Draw on Frame"},
    "draw_tool":            {"es": "Herramienta",              "en": "Tool"},
    "draw_color":           {"es": "Color",                    "en": "Colour"},
    "draw_width":           {"es": "Grosor",                   "en": "Width"},
    "export_btn":           {"es": "💾 Exportar Frame Anotado (PNG)",
                             "en": "💾 Export Annotated Frame (PNG)"},
    "download_png":         {"es": "⬇️ Descargar PNG",         "en": "⬇️ Download PNG"},
    "upload_prompt":        {"es": "Subí un video de partido para comenzar el análisis IA",
                             "en": "Upload match footage to begin AI analysis"},
    "manual_tag":           {"es": "Etiquetado Manual de Eventos",
                             "en": "Manual Event Tagging"},
    "tag_event":            {"es": "Etiquetar Evento",         "en": "Tag Event"},
    "tag_select":           {"es": "— Seleccioná —",           "en": "— Select —"},
    "checkpoints_title":    {"es": "📋 Checkpoints Técnicos",  "en": "📋 Technical Checkpoints"},
    "drills_title":         {"es": "🏋️ Ejercicios",           "en": "🏋️ Drills"},
    "select_event_prompt":  {"es": "Seleccioná una jugada para ver el consejo táctico",
                             "en": "Select a play event for tactical advice"},
    "ai_event_logic":       {"es": "Lógica IA de Eventos",     "en": "AI Event Logic"},
    "heatmap_title":        {"es": "Heatmap Espacial de Eventos",
                             "en": "Spatial Event Heatmap"},
    "heatmap_sub":          {"es": "Proyección de tackles y rucks sobre la cancha",
                             "en": "Tackles and rucks projected onto pitch"},
    "heatmap_no_data":      {"es": "Analizá frames con IA de Eventos para generar el heatmap.",
                             "en": "Analyse frames with Event AI to generate the heatmap."},
    "heatmap_event_filter": {"es": "Filtrar por evento",       "en": "Filter by event"},
    "heatmap_all":          {"es": "Todos",                    "en": "All"},
    "players_detected":     {"es": "jugadores detectados",     "en": "players detected"},
    "balls_detected":       {"es": "pelota(s) detectada(s)",   "en": "ball(s) detected"},
    "teams_detected":       {"es": "Equipos",                  "en": "Teams"},
    "no_events_frame":      {"es": "Sin eventos estructurados detectados en este frame.",
                             "en": "No structured events detected in this frame."},
    "tracking_id_label":    {"es": "ID de Seguimiento",        "en": "Tracking ID"},

    # ── Physical Hub ──────────────────────────────────────────────────────────
    "physical_title":       {"es": "MOTOR FÍSICO",             "en": "PHYSICAL POWER HUB"},
    "physical_sub":         {"es": "Motor 1RM · Composición · Medidas · Nutrición inteligente",
                             "en": "1RM Engine · Composition · Measures · Smart Nutrition"},
    "tab_log_data":         {"es": "📊 Registrar",             "en": "📊 Log Data"},
    "tab_1rm_charts":       {"es": "📈 Gráficos 1RM",         "en": "📈 1RM Charts"},
    "tab_measures":         {"es": "📏 Medidas",               "en": "📏 Measures"},
    "tab_nutrition":        {"es": "🥩 Nutrición",             "en": "🥩 Nutrition"},
    "anthropo_section":     {"es": "Antropometría",            "en": "Anthropometrics"},
    "weight_kg":            {"es": "Peso (kg)",                "en": "Weight (kg)"},
    "height_cm":            {"es": "Altura (cm)",              "en": "Height (cm)"},
    "body_fat_pct":         {"es": "% de Grasa Corporal",     "en": "Body Fat %"},
    "save_btn":             {"es": "💾 Guardar",               "en": "💾 Save"},
    "save_ok":              {"es": "✅ Guardado.",             "en": "✅ Saved."},
    "validation_fail":      {"es": "❌ Validación fallida",    "en": "❌ Validation failed"},
    "prs_section":          {"es": "PRs del Gimnasio + Reps → 1RM Epley",
                             "en": "Gym PRs + Reps → Epley 1RM"},
    "prs_caption":          {"es": "Ingresá peso Y reps — la fórmula Epley calcula tu 1RM.",
                             "en": "Enter weight AND reps — Epley formula computes your 1RM."},
    "reps_label":           {"es": "Reps",                    "en": "Reps"},
    "1rm_chart_title":      {"es": "Progresión Teórica de 1RM (Epley)",
                             "en": "Theoretical 1RM Progression (Epley)"},
    "epley_caption":        {"es": "1RM = peso × (1 + reps/30)  —  Epley (1985)",
                             "en": "1RM = weight × (1 + reps/30)  —  Epley (1985)"},
    "scatter_title":        {"es": "1RM Squat vs Peso Corporal",
                             "en": "Squat 1RM vs Body Weight"},
    "log_2_prs":            {"es": "Registrá 2+ sesiones de PRs para ver los gráficos.",
                             "en": "Log 2+ PR sessions to see charts."},
    "measures_section":     {"es": "Registro de Perímetros Musculares",
                             "en": "Muscle Circumference Log"},
    "quad_cm":              {"es": "🦵 Cuádriceps (cm)",       "en": "🦵 Quadriceps (cm)"},
    "arm_cm":               {"es": "💪 Brazo / Bícep (cm)",    "en": "💪 Arm / Bicep (cm)"},
    "chest_cm":             {"es": "🫀 Pecho (cm)",            "en": "🫀 Chest (cm)"},
    "measure_caption":      {"es": "Medí en el punto más ancho, brazos relajados.",
                             "en": "Measure at widest point, arms relaxed."},
    "radar_title":          {"es": "Radar — Benchmark de Élite",
                             "en": "Elite Benchmark Radar"},
    "radar_caption":        {"es": "% de los valores de referencia de rugby de élite.",
                             "en": "% of elite rugby athlete reference benchmarks."},
    "growth_title":         {"es": "Crecimiento en el Tiempo", "en": "Growth Over Time"},
    "log_measure":          {"es": "Registrá una medida para ver el radar.",
                             "en": "Log a measurement to see the radar chart."},
    "nutrition_smart":      {"es": "Calculadora Inteligente de Bulking (Calendar Sync)",
                             "en": "Smart Bulking Calculator (Calendar Sync)"},
    "cal_sync_active":      {"es": "📅 Calendar Sync Activo",  "en": "📅 Calendar Sync Active"},
    "tdee_boost":           {"es": "+20% TDEE aplicado",       "en": "+20% TDEE applied"},
    "carb_priority":        {"es": "modo prioridad carbohidratos activado",
                             "en": "carbohydrate priority mode engaged"},
    "daily_target":         {"es": "OBJETIVO DIARIO",          "en": "DAILY TARGET"},
    "meal_timing":          {"es": "Protocolo de Timing de Comidas",
                             "en": "Meal Timing Protocol"},
    "protein_label":        {"es": "🥩 Proteína",              "en": "🥩 Protein"},
    "carbs_label":          {"es": "🍚 Carbos",               "en": "🍚 Carbs"},
    "fat_label":            {"es": "🥑 Grasas",               "en": "🥑 Fat"},
    "activity_label":       {"es": "Nivel de Actividad",       "en": "Activity Level"},
    "act_moderate":         {"es": "Moderado (3-5 días)",      "en": "Moderate (3-5 days)"},
    "act_very":             {"es": "Muy Activo (6-7 días duros)","en": "Very Active (6-7 hard days)"},
    "act_extra":            {"es": "Extra Activo (2 sesiones/día)","en": "Extra Active (2× sessions)"},

    # ── Journal ───────────────────────────────────────────────────────────────
    "journal_title":        {"es": "DIARIO DE PARTIDO",        "en": "MATCH DAY JOURNAL"},
    "journal_sub":          {"es": "Análisis de sentimiento · Detección de burnout · Export PDF",
                             "en": "Sentiment analysis · Burnout detection · PDF export"},
    "post_match_entry":     {"es": "Entrada Post-Partido",     "en": "Post-Match Entry"},
    "position_played":      {"es": "Posición Jugada",          "en": "Position Played"},
    "performance_slider":   {"es": "Rendimiento (1–10)",       "en": "Performance (1–10)"},
    "notes_label":          {"es": "Notas (soporta Markdown)", "en": "Notes (Markdown supported)"},
    "notes_placeholder":    {"es": "## Fortalezas\n\n## Errores\n\n## Próximos Pasos",
                             "en": "## Strengths\n\n## Errors\n\n## Next Steps"},
    "save_entry_btn":       {"es": "💾 Guardar Entrada",       "en": "💾 Save Entry"},
    "entry_saved":          {"es": "✅ Guardado con análisis de sentimiento.",
                             "en": "✅ Saved with sentiment analysis."},
    "save_failed":          {"es": "❌ Error al guardar.",     "en": "❌ Save failed."},
    "add_notes_warn":       {"es": "Agregá notas antes de guardar.",
                             "en": "Add notes before saving."},
    "no_journal":           {"es": "Tu historial de partidos aparecerá aquí.",
                             "en": "Your match history appears here."},
    "sentiment_positive":   {"es": "🟢 Positivo",             "en": "🟢 Positive"},
    "sentiment_negative":   {"es": "🔴 Negativo",             "en": "🔴 Negative"},
    "sentiment_neutral":    {"es": "⚪ Neutral",              "en": "⚪ Neutral"},
    "polarity_label":       {"es": "Polaridad",               "en": "Polarity"},
    "active_rest_rec":      {"es": "Descanso Activo Recomendado",
                             "en": "Active Rest Recommended"},
    "active_rest_body":     {"es": "3 entradas negativas consecutivas. Agendá recuperación.",
                             "en": "3 consecutive negative entries. Schedule recovery."},

    # ── Schedule ──────────────────────────────────────────────────────────────
    "schedule_title":       {"es": "AGENDA DE ÉLITE",          "en": "ELITE SCHEDULE"},
    "schedule_sub":         {"es": "Calendario · Templates inteligentes · Planificación semanal",
                             "en": "Calendar · Smart templates · Weekly planning"},
    "add_event":            {"es": "Agregar Evento",           "en": "Add Event"},
    "event_date":           {"es": "Fecha",                    "en": "Date"},
    "event_type":           {"es": "Tipo",                     "en": "Type"},
    "event_template":       {"es": "Template",                 "en": "Template"},
    "event_details":        {"es": "Detalles",                 "en": "Details"},
    "add_event_btn":        {"es": "📅 Agregar Evento",        "en": "📅 Add Event"},
    "event_added":          {"es": "✅ Agregado.",             "en": "✅ Added."},
    "monthly_calendar":     {"es": "Vista Mensual",            "en": "Monthly Calendar"},
    "month_label":          {"es": "Mes",                      "en": "Month"},
    "year_label":           {"es": "Año",                      "en": "Year"},
    "all_events":           {"es": "Todos los Eventos",        "en": "All Events"},
    "no_events":            {"es": "Sin eventos agendados.",   "en": "No events scheduled."},
    "delete_btn":           {"es": "🗑️",                      "en": "🗑️"},
    "no_details":           {"es": "Sin detalles.",            "en": "No details."},

    # ── Event types ───────────────────────────────────────────────────────────
    "Workout":              {"es": "Gimnasio",                 "en": "Workout"},
    "Rugby Training":       {"es": "Entrenamiento Rugby",      "en": "Rugby Training"},
    "Match Day":            {"es": "Día de Partido",           "en": "Match Day"},
    "Rest Day":             {"es": "Día de Descanso",          "en": "Rest Day"},

    # ── Generic ───────────────────────────────────────────────────────────────
    "kg_unit":              {"es": " kg",                      "en": " kg"},
    "cm_unit":              {"es": " cm",                      "en": " cm"},
    "section_no_data":      {"es": "Sin datos aún.",           "en": "No data yet."},
    "prev_label":           {"es": "vs anterior",              "en": "vs prev"},
    "confidence":           {"es": "confianza",                "en": "confidence"},
}


def t(key: str) -> str:
    """
    Translate a key to the active language.
    Falls back to English if key not found, then to the key itself.

    Usage:
        import streamlit as st
        from modules.i18n import t
        st.markdown(t("dashboard_title"))
    """
    import streamlit as st
    lang = st.session_state.get("lang", "en")
    entry = _STRINGS.get(key)
    if entry is None:
        return key                          # unknown key → return raw
    return entry.get(lang, entry.get("en", key))


def get_lang() -> str:
    """Return the active language code: 'es' or 'en'."""
    import streamlit as st
    return st.session_state.get("lang", "en")
