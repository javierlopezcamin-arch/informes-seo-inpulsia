#!/usr/bin/env python3
"""
Analizador de datos SEO
Interpreta datos de GA4 y Search Console, genera narrativas en español
"""

from typing import Dict
from datetime import datetime
from utils import MESES, pct_delta

AI_TIMEOUT_MS = 90_000


class SEOAnalyzer:
    """Analiza datos SEO y genera narrativas profesionales"""

    def __init__(self, ga4_data: Dict, sc_data: Dict,
                 ga4_prev: Dict = None, sc_prev: Dict = None,
                 ads_data: Dict = None, ads_prev: Dict = None, insights: Dict = None):
        self.ga4 = ga4_data
        self.insights = insights or {}
        self.sc = sc_data
        self.ga4_prev = ga4_prev or {}
        self.sc_prev = sc_prev or {}
        self.ads = ads_data or {}
        self.ads_prev = ads_prev or {}
        self.month = ga4_data.get('month', sc_data.get('month', 1))
        self.year = ga4_data.get('year', sc_data.get('year', 2026))
        self.month_name = MESES.get(self.month, 'mes')

    # ── Tráfico ──────────────────────────────────────────────
    def analyze_traffic(self) -> Dict:
        metrics = self.ga4.get('metrics', {})
        prev = self.ga4_prev.get('metrics', {})
        users = metrics.get('total_users', 0)
        sessions = metrics.get('sessions', 0)
        dur = metrics.get('avg_session_duration', 0)
        bounce = metrics.get('bounce_rate', 0)
        pvs = metrics.get('pageviews', 0)

        narrative = (
            f"En el mes de {self.month_name} el volumen de tráfico total del sitio web "
            f"se sitúa en los {users} usuarios con {sessions} sesiones. "
        )
        if dur > 30:
            narrative += f"El tiempo de interacción medio aumenta hasta los {dur:.0f} segundos, lo que indica un tráfico más cualificado. "
        else:
            narrative += f"El tiempo de interacción medio se sitúa en {dur:.0f} segundos. "
        if bounce > 50:
            narrative += "La tasa de rebote es elevada, sugiriendo oportunidades de mejora en la experiencia de usuario."

        return {
            'users': users, 'sessions': sessions, 'avg_duration': dur,
            'bounce_rate': bounce, 'pageviews': pvs, 'narrative': narrative,
            'd_users': pct_delta(users, prev.get('total_users', 0)),
            'd_sessions': pct_delta(sessions, prev.get('sessions', 0)),
            'd_pageviews': pct_delta(pvs, prev.get('pageviews', 0)),
        }

    # ── Search Console ───────────────────────────────────────
    def analyze_search_console(self) -> Dict:
        summary = self.sc.get('summary', {})
        prev = self.sc_prev.get('summary', {})
        imp = summary.get('impressions', 0)
        clicks = summary.get('clicks', 0)
        ctr = summary.get('ctr', 0)
        pos = summary.get('position', 0)

        narrative = (
            f"Durante {self.month_name}, el sitio ha recibido un total de "
            f"{imp:,} impresiones en Google y {clicks} clics, "
            f"lo que nos da un CTR del {ctr:.2f}%. "
        )
        if pos < 5:
            narrative += f"La posición media es excelente ({pos:.1f}), ubicándonos en el Top 5."
        elif pos < 10:
            narrative += f"La posición media de {pos:.1f} nos sitúa dentro del Top-10."
        else:
            narrative += f"La posición media es {pos:.1f}, sugiriendo oportunidades de mejora."

        return {
            'impressions': imp, 'clicks': clicks, 'ctr': ctr,
            'position': pos, 'narrative': narrative,
            'd_impressions': pct_delta(imp, prev.get('impressions', 0)),
            'd_clicks': pct_delta(clicks, prev.get('clicks', 0)),
            'd_ctr': pct_delta(ctr, prev.get('ctr', 0)),
        }

    # ── Keywords ─────────────────────────────────────────────
    def analyze_keywords(self) -> Dict:
        keywords = self.sc.get('top_keywords', [])
        if not keywords:
            return {'top_keywords': [], 'narrative': "No hay datos suficientes de keywords."}

        top3 = keywords[:3]
        high_pos = sum(1 for kw in keywords if kw['position'] < 10)
        narrative = (
            "Los keywords con mejor rendimiento son: "
            + ", ".join(f"'{kw['query']}' (pos. {kw['position']})" for kw in top3)
            + f". Contamos con {high_pos} keywords en la primera página."
        )

        return {'top_keywords': keywords, 'top_3': top3, 'narrative': narrative}

    # ── Páginas ──────────────────────────────────────────────
    def analyze_pages(self) -> Dict:
        return {
            'top_pages_sc': self.sc.get('top_pages', []),
            'top_pages_ga4': self.ga4.get('top_pages', []),
        }

    # ── Resumen ejecutivo (#5) ──────────────────────────────
    def generate_executive_summary(self) -> str:
        import os
        if os.getenv("IA_ENABLED", "true").lower() == "false":
            return ""
        key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not key:
            return ""
        try:
            from google import genai
        except ImportError:
            return ""

        t = self.analyze_traffic()
        sc = self.analyze_search_console()

        prompt = (
            "Eres un consultor SEO senior. Genera un resumen ejecutivo de EXACTAMENTE 3 frases "
            "cortas (máximo 50 palabras en total), en español, tono siempre positivo y constructivo. "
            "Destaca logros, oportunidades y avances. Nunca uses palabras negativas. "
            "Cada frase en una línea separada, sin numeración ni viñetas.\n\n"
            f"Usuarios: {t['users']} ({t.get('d_users','—')}), Sesiones: {t['sessions']}\n"
            f"Impresiones: {sc['impressions']} ({sc.get('d_impressions','—')}), Clics: {sc['clicks']}\n"
            f"CTR: {sc['ctr']:.2f}%, Posición media: {sc['position']:.1f}"
        )
        try:
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            from utils import gemini_bump
            gemini_bump()
            return resp.text.strip()
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                from utils import gemini_mark_exhausted
                gemini_mark_exhausted()
            print(f"  ⚠️  IA resumen ejecutivo: {e}")
            return ""

    # ── Conclusiones ─────────────────────────────────────────
    def generate_conclusions(self) -> str:
        """Conclusiones con IA (Gemini → Claude → genéricas)."""
        import os
        if os.getenv("IA_ENABLED", "true").lower() == "false":
            print("  ℹ️  IA: desactivada (IA_ENABLED=false)")
            return self._fallback_conclusions()

        ai = self._gemini_conclusions() or self._claude_conclusions()
        return ai if ai else self._fallback_conclusions()

    def _build_prompt(self) -> str:
        t = self.analyze_traffic()
        sc = self.analyze_search_console()
        kw = self.analyze_keywords()
        top_kw = ", ".join(f"{k['query']} (pos {k['position']})" for k in kw.get('top_keywords', [])[:5])

        datos = (
            f"Mes: {self.month_name} {self.year}\n"
            f"Usuarios: {t['users']} ({t.get('d_users', '—')} vs mes anterior)\n"
            f"Sesiones: {t['sessions']} ({t.get('d_sessions', '—')})\n"
            f"Tasa de rebote: {t['bounce_rate']:.1f}%\n"
            f"Impresiones: {sc['impressions']} ({sc.get('d_impressions', '—')})\n"
            f"Clics: {sc['clicks']} ({sc.get('d_clicks', '—')})\n"
            f"CTR: {sc['ctr']:.2f}% ({sc.get('d_ctr', '—')})\n"
            f"Posición media: {sc['position']:.1f}\n"
            f"Top keywords: {top_kw or 'sin datos'}"
        )
        return (
            "Eres un consultor SEO senior. A partir de estos datos mensuales de un cliente, "
            "redacta unas conclusiones profesionales en español (máximo 180 palabras): "
            "1) un párrafo breve interpretando la evolución del mes, y "
            "2) una lista de 4 próximos pasos accionables y específicos para este cliente. "
            "No inventes datos. Usa un tono profesional y directo.\n\n"
            f"DATOS:\n{datos}"
        )

    def _gemini_conclusions(self) -> str:
        import os
        key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not key:
            return ""
        try:
            from google import genai
        except ImportError:
            print("  ⚠️  IA: módulo 'google-genai' no instalado (pip install google-genai)")
            return ""
        print(f"  🤖 IA: generando conclusiones con Gemini (clave {key[:12]}…)")
        try:
            client = genai.Client(api_key=key, http_options={"timeout": AI_TIMEOUT_MS})
            resp = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=self._build_prompt(),
            )
            result = resp.text.strip()
            from utils import gemini_bump
            gemini_bump()
            print("  ✅ IA: conclusiones generadas con Gemini")
            return result
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                from utils import gemini_mark_exhausted
                gemini_mark_exhausted()
            print(f"  ⚠️  IA: error Gemini — {type(e).__name__}: {e}")
            return ""

    def _claude_conclusions(self) -> str:
        import os
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return ""
        try:
            import anthropic
        except ImportError:
            return ""
        print(f"  🤖 IA: fallback a Claude (clave {key[:12]}…)")
        try:
            client = anthropic.Anthropic(timeout=AI_TIMEOUT_MS / 1000)
            resp = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1024,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content": self._build_prompt()}],
            )
            result = "".join(b.text for b in resp.content if b.type == "text").strip()
            print("  ✅ IA: conclusiones generadas con Claude")
            return result
        except Exception as e:
            print(f"  ⚠️  IA: error Claude — {type(e).__name__}: {e}")
            return ""

    def _fallback_conclusions(self) -> str:
        t = self.analyze_traffic()
        sc = self.analyze_search_console()

        lines = [f"{self.month_name.capitalize()} ha sido un mes con el siguiente desempeño SEO:\n"]

        lines.append(f"{'✓' if t['users'] > 50 else '•'} Tráfico web: {t['users']} usuarios, {t['sessions']} sesiones.")
        lines.append(f"{'✓' if sc['position'] < 10 else '•'} Posición media en búsqueda: {sc['position']:.1f}.")
        lines.append(f"{'✓' if sc['ctr'] > 2 else '•'} CTR: {sc['ctr']:.2f}%.")

        lines.append("\n📌 Próximos pasos:")
        lines.append("• Continuar creando contenido de calidad")
        lines.append("• Optimizar páginas en posiciones 11-20")
        lines.append("• Mejorar CTR con títulos y descripciones más atractivas")
        lines.append("• Analizar palabras clave con potencial")

        return "\n".join(lines)

    def analyze_traffic_channels(self) -> Dict:
        channels = self.ga4.get('traffic_channels', [])
        if not channels:
            return {'channels': [], 'narrative': "No hay datos suficientes de canales de adquisición."}
        
        main_channel = channels[0]
        narrative = (
            f"El canal principal de adquisición de tráfico es {main_channel['channel']}, "
            f"que representa el {main_channel['percentage']}% del total con {main_channel['sessions']:,} sesiones."
        )
        
        if len(channels) > 1:
            sec_channel = channels[1]
            narrative += f" En segundo lugar se sitúa {sec_channel['channel']} con un {sec_channel['percentage']}%."
            
        return {
            'channels': channels,
            'narrative': narrative
        }

    def analyze_devices(self) -> Dict:
        devices = self.ga4.get('devices', {})
        if not devices:
            return {'devices': {}, 'narrative': "No hay datos suficientes de dispositivos."}
            
        total = sum(devices.values()) or 1
        dev_pct = {k: round(v / total * 100, 1) for k, v in devices.items()}
        
        dominant_device = max(devices, key=devices.get)
        dominant_pct = dev_pct[dominant_device]
        
        narrative = (
            f"El dispositivo más utilizado para acceder a la web es {dominant_device} ({dominant_pct}%), "
            f"lo que destaca la importancia de una buena experiencia de usuario en este formato."
        )
        return {
            'devices': devices,
            'percentages': dev_pct,
            'narrative': narrative
        }

    def analyze_daily_trends(self) -> Dict:
        daily = self.sc.get('daily_performance', [])
        if not daily:
            return {'daily': [], 'narrative': "No hay datos suficientes de rendimiento diario."}
            
        max_clicks_day = max(daily, key=lambda x: x['clicks'])
        
        # Formatear la fecha para que sea más legible (ej. YYYY-MM-DD -> DD/MM/YYYY)
        d_str = max_clicks_day['date']
        try:
            d_obj = datetime.strptime(d_str, "%Y-%m-%d")
            d_formatted = d_obj.strftime("%d/%m/%Y")
        except Exception:
            d_formatted = d_str

        narrative = (
            f"El día con mayor volumen de clics orgánicos fue el {d_formatted} "
            f"con {max_clicks_day['clicks']} clics y {max_clicks_day['impressions']:,} impresiones."
        )
        return {
            'daily': daily,
            'narrative': narrative
        }

    def analyze_mom(self) -> Dict:
        """Comparativa visual MoM: métricas actuales vs anteriores."""
        m = self.ga4.get('metrics', {})
        mp = self.ga4_prev.get('metrics', {})
        s = self.sc.get('summary', {})
        sp = self.sc_prev.get('summary', {})

        metrics = []
        for label, curr, prev in [
            ("Usuarios", m.get('total_users', 0), mp.get('total_users', 0)),
            ("Sesiones", m.get('sessions', 0), mp.get('sessions', 0)),
            ("Impresiones", s.get('impressions', 0), sp.get('impressions', 0)),
            ("Clics", s.get('clicks', 0), sp.get('clicks', 0)),
        ]:
            if curr or prev:
                metrics.append({"label": label, "current": curr, "previous": prev})

        if not metrics:
            return {'metrics': [], 'narrative': ''}

        narrative = "Comparativa de las principales métricas respecto al mes anterior."
        return {'metrics': metrics, 'narrative': narrative}

    # ── Keywords ganadas / perdidas (#5) ────────────────────
    def analyze_keyword_movements(self) -> Dict:
        curr_kws = {k['query']: k for k in self.sc.get('top_keywords', [])}
        prev_kws = {k['query']: k for k in self.sc_prev.get('top_keywords', [])}
        if not curr_kws or not prev_kws:
            return {'gained': [], 'lost': [], 'new': []}

        movements = []
        for q, c in curr_kws.items():
            if q in prev_kws:
                delta = prev_kws[q]['position'] - c['position']
                movements.append({
                    'query': q, 'position': round(c['position'], 1),
                    'prev_position': round(prev_kws[q]['position'], 1),
                    'delta': round(delta, 1), 'clicks': c.get('clicks', 0),
                })

        gained = sorted([m for m in movements if m['delta'] > 0], key=lambda x: -x['delta'])[:6]
        lost = sorted([m for m in movements if m['delta'] < 0], key=lambda x: x['delta'])[:6]
        new_kws = [{'query': q, 'position': round(c['position'], 1), 'clicks': c.get('clicks', 0)}
                   for q, c in curr_kws.items() if q not in prev_kws][:5]

        return {'gained': gained, 'lost': lost, 'new': new_kws}

    # ── Oportunidades página 2 (#6) ──────────────────────────
    def analyze_opportunities(self) -> Dict:
        kws = self.sc.get('top_keywords', [])
        opps = [k for k in kws if 10 < k['position'] <= 20]
        opps.sort(key=lambda x: -x.get('impressions', 0))
        opps = opps[:8]
        items = [{
            'query': k['query'],
            'position': round(k['position'], 1),
            'impressions': k.get('impressions', 0),
            'gap': round(k['position'] - 10, 1),
        } for k in opps]
        n = len(items)
        narrative = f"{n} keywords en posiciones 11-20: a un empujón del Top 10." if n else ""
        return {'opportunities': items, 'narrative': narrative}

    # ── Insights IA por sección (#9) ──────────────────────────
    def generate_section_insights(self) -> Dict:
        import os, json as _json
        if os.getenv("IA_ENABLED", "true").lower() == "false":
            return {}
        key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not key:
            return {}
        try:
            from google import genai
        except ImportError:
            return {}

        t = self.analyze_traffic()
        sc = self.analyze_search_console()
        kw = self.analyze_keywords()

        prompt = (
            "Eres un consultor SEO senior. A partir de estos datos, genera exactamente 4 notas "
            "de UNA frase corta cada una (máximo 20 palabras), en español. "
            "IMPORTANTE: el tono debe ser siempre positivo y constructivo. Destaca logros, "
            "oportunidades y avances. Nunca uses palabras negativas. "
            "Responde SOLO con JSON válido, sin markdown:\n"
            '{"traffic":"...","search":"...","keywords":"...","technical":"..."}\n\n'
            f"Usuarios: {t['users']} ({t.get('d_users','—')}), Sesiones: {t['sessions']} ({t.get('d_sessions','—')})\n"
            f"Impresiones: {sc['impressions']} ({sc.get('d_impressions','—')}), Clics: {sc['clicks']}, CTR: {sc['ctr']:.2f}%\n"
            f"Posición media: {sc['position']:.1f}\n"
            f"Top keywords: {', '.join(k['query'] for k in kw.get('top_keywords',[])[:5]) or 'sin datos'}"
        )
        try:
            client = genai.Client(api_key=key, http_options={"timeout": AI_TIMEOUT_MS})
            resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            from utils import gemini_bump
            gemini_bump()
            text = resp.text.strip()
            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return _json.loads(text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                from utils import gemini_mark_exhausted
                gemini_mark_exhausted()
            print(f"  ⚠️  IA insights: {e}")
            return {}

    # ── Google Ads (opcional) ────────────────────────────────
    def analyze_ads(self) -> Dict:
        a, p = self.ads, self.ads_prev
        if not a or not a.get('impressions'):
            return {}
        cur = a.get('currency', '€')
        cost, clicks, imps = a.get('cost', 0), a.get('clicks', 0), a.get('impressions', 0)
        conv = a.get('conversions', 0)
        # El informe es para el cliente: sin conversiones reales no se muestran ni se mencionan
        # (el diagnóstico va en el archivo interno de propuestas).
        show_conv = a.get('conversion_state', 'ok' if conv > 0 else 'sin_datos') == 'ok' and conv > 0

        def money(v):
            return f"{v:,.0f} {cur}" if v >= 100 else f"{v:,.2f} {cur}"

        narrative = (
            f"En {self.month_name} se invirtieron {money(cost)} en Google Ads, con {imps:,} impresiones "
            f"y {clicks:,} clics (CTR {a.get('ctr', 0):.2f}%, CPC medio {a.get('avg_cpc', 0):.2f} {cur}). "
        )
        if show_conv:
            cpa = cost / conv
            narrative += f"Se registraron {conv:,.0f} conversiones, a {money(cpa)} por conversión."
            if a.get('conv_value'):
                narrative += f" El valor de conversión asciende a {money(a['conv_value'])} (ROAS {a['conv_value'] / cost:.1f}x)." if cost else ""

        d_clicks = pct_delta(clicks, p.get('clicks', 0)) if p else ""
        d_imps = pct_delta(imps, p.get('impressions', 0)) if p else ""
        d_conv = pct_delta(conv, p.get('conversions', 0)) if show_conv and p and p.get('conversions') else ""
        d_cpc = pct_delta(a.get('avg_cpc', 0), p.get('avg_cpc', 0)) if p and p.get('avg_cpc') else ""

        insight = ""
        if p and p.get('cost'):
            insight = (f"La inversión pasa de {money(p['cost'])} a {money(cost)} "
                       f"({pct_delta(cost, p['cost'])}) respecto al mes anterior.")
        elif show_conv:
            insight = f"Las campañas generan conversiones a {money(cost / conv)} cada una."

        return {
            'currency': cur, 'cost': cost, 'cost_label': money(cost),
            'impressions': imps, 'clicks': clicks, 'conversions': conv,
            'show_conversions': show_conv,
            'cpa_label': money(cost / conv) if show_conv else "",
            'ctr': a.get('ctr', 0), 'avg_cpc': a.get('avg_cpc', 0),
            'd_impressions': d_imps, 'd_clicks': d_clicks, 'd_conversions': d_conv, 'd_cpc': d_cpc,
            'campaigns': a.get('campaigns', []),
            'conversions_by_action': a.get('conversions_by_action', []) if show_conv else [],
            'narrative': narrative, 'insight': insight,
        }

    # ── Bundle IA: una sola llamada para todo ────────────────
    @staticmethod
    def _parse_json(text: str) -> Dict:
        import json as _json
        txt = (text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = _json.loads(txt)
        if not isinstance(data, dict):
            raise ValueError("la IA no devolvió un objeto JSON")
        return data

    def _bundle_gemini(self, prompt: str) -> Dict:
        import os
        from utils import gemini_usage, GEMINI_DAILY_LIMIT, gemini_bump, gemini_mark_exhausted
        key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not key:
            return {}
        if gemini_usage() >= GEMINI_DAILY_LIMIT:
            print("  ℹ️  IA: cuota diaria de Gemini agotada")
            return {}
        try:
            from google import genai
        except ImportError:
            return {}
        try:
            client = genai.Client(api_key=key, http_options={"timeout": AI_TIMEOUT_MS})
            resp = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            gemini_bump()
            return self._parse_json(resp.text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                gemini_mark_exhausted()
            print(f"  ⚠️  IA Gemini: {type(e).__name__}: {str(e)[:160]}")
            return {}

    def _bundle_claude(self, prompt: str) -> Dict:
        import os
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            return {}
        try:
            import anthropic
        except ImportError:
            return {}
        model = os.getenv("CLAUDE_FALLBACK_MODEL", "claude-haiku-4-5-20251001").strip()
        print(f"  🤖 IA: respaldo con Claude ({model})")
        try:
            client = anthropic.Anthropic(api_key=key, timeout=AI_TIMEOUT_MS / 1000)
            resp = client.messages.create(model=model, max_tokens=2000,
                                          messages=[{"role": "user", "content": prompt}])
            return self._parse_json("".join(b.text for b in resp.content if b.type == "text"))
        except Exception as e:
            print(f"  ⚠️  IA Claude: {type(e).__name__}: {str(e)[:160]}")
            return {}

    def generate_ai_bundle(self, level: str = "analitico") -> Dict:
        """Una única llamada de IA que devuelve resumen, conclusiones, notas,
        recomendaciones y anomalías. Gemini primero; si no hay cuota o falla, Claude Haiku."""
        import os
        if os.getenv("IA_ENABLED", "true").lower() == "false":
            return {}
        if not (os.getenv("GOOGLE_GEMINI_API_KEY", "").strip() or os.getenv("ANTHROPIC_API_KEY", "").strip()):
            return {}

        t = self.analyze_traffic()
        sc = self.analyze_search_console()
        kw = self.analyze_keywords()
        moves = self.analyze_keyword_movements()
        opps = self.analyze_opportunities()
        top_kw = ", ".join(k['query'] for k in kw.get('top_keywords', [])[:6]) or "sin datos"
        gained = ", ".join(f"{m['query']} ({m['delta']:+.0f})" for m in moves.get('gained', [])[:4]) or "—"
        lost = ", ".join(f"{m['query']} ({m['delta']:+.0f})" for m in moves.get('lost', [])[:4]) or "—"
        _opp = opps.get('opportunities', []) if isinstance(opps, dict) else opps
        opp_list = ", ".join(o['query'] for o in (_opp or [])[:5]) or "—"

        tono = ("Tono SIEMPRE positivo y constructivo, frases breves; no uses palabras negativas."
                if level == "positivo" else
                "Interpreta los datos: correlaciones, causas y tendencias. Constructivo pero realista; "
                "señala con tacto lo que necesita atención.")

        prompt = (
            "Eres un consultor SEO senior. Analiza estos datos mensuales y responde SOLO con JSON "
            "válido (sin markdown), con esta estructura exacta:\n"
            '{"executive_summary":["f1","f2","f3"],'
            '"conclusions":"párrafo breve seguido de 4 viñetas separadas por saltos de línea",'
            '"insights":{"traffic":"...","search":"...","keywords":"...","technical":"..."},'
            '"recommendations":["r1","r2","r3","r4"],"anomalies":["a1","a2"]}\n'
            f"{tono} No inventes datos. Español.\n"
            "executive_summary: 3 frases. insights: 1 frase por sección (máx 20 palabras). "
            "recommendations: 4 acciones concretas y priorizadas para este cliente. "
            "anomalies: hasta 3 cambios relevantes (subidas o caídas fuertes); usa [] si no hay.\n\n"
            f"DATOS:\nMes: {self.month_name} {self.year}\n"
            f"Usuarios: {t['users']} ({t.get('d_users', '—')}), Sesiones: {t['sessions']} ({t.get('d_sessions', '—')}), Rebote: {t['bounce_rate']:.1f}%\n"
            f"Impresiones: {sc['impressions']} ({sc.get('d_impressions', '—')}), Clics: {sc['clicks']} ({sc.get('d_clicks', '—')}), CTR: {sc['ctr']:.2f}%, Posición: {sc['position']:.1f}\n"
            f"Top keywords: {top_kw}\nSuben: {gained}\nBajan: {lost}\nOportunidades pág.2: {opp_list}"
            f"{self._insights_prompt()}"
        )
        print(f"  🤖 IA: análisis (nivel {level}, 1 llamada)")
        data = self._bundle_gemini(prompt) or self._bundle_claude(prompt)
        if data:
            print("  ✅ IA: análisis completo generado")
        else:
            print("  ⚠️  IA: sin respuesta; se usará texto genérico")
        return data

    def _insights_prompt(self) -> str:
        """Líneas extra para la IA con las señales cruzadas (contenido que cae y tráfico desde IA)."""
        lines = []
        dec = (self.insights.get('decay') or {}).get('pages', [])
        if dec:
            lines.append("Páginas que pierden clics (3 meses vs 3 anteriores): " + ", ".join(
                f"{p['page'].split('://')[-1][-60:]} ({p['pct']}%)" for p in dec[:4]))
        ai = self.insights.get('ai') or {}
        if ai.get('sessions'):
            lines.append(f"Visitas desde asistentes de IA: {ai['sessions']} (mes anterior: {ai.get('prev_sessions', '—')})")
        return ("\n" + "\n".join(lines)) if lines else ""

    # ── Análisis completo ────────────────────────────────────
    def get_full_analysis(self, historical: list = None, notes_level: str = "analitico") -> Dict:
        bundle = self.generate_ai_bundle(notes_level)
        exec_summary = "\n".join(bundle.get('executive_summary', [])) if bundle.get('executive_summary') else ""
        return {
            'month': self.month,
            'year': self.year,
            'month_name': self.month_name,
            'traffic': self.analyze_traffic(),
            'search_console': self.analyze_search_console(),
            'keywords': self.analyze_keywords(),
            'pages': self.analyze_pages(),
            'traffic_channels': self.analyze_traffic_channels(),
            'devices': self.analyze_devices(),
            'daily_trends': self.analyze_daily_trends(),
            'daily_users': self.ga4.get('daily_users', []),
            'top_countries': self.ga4.get('top_countries', []),
            'devices_sc': self.sc.get('devices', []),
            'mom': self.analyze_mom(),
            'keyword_movements': self.analyze_keyword_movements(),
            'opportunities': self.analyze_opportunities(),
            'insights': bundle.get('insights', {}) or {},
            'executive_summary': exec_summary,
            'recommendations': bundle.get('recommendations', []) or [],
            'anomalies': bundle.get('anomalies', []) or [],
            'historical': historical or [],
            'ads': self.analyze_ads(),
            'seo_insights': self.insights,
            'conclusions': bundle.get('conclusions') or self._fallback_conclusions(),
        }


def analyze_seo_data(ga4_data: Dict, sc_data: Dict,
                     ga4_prev: Dict = None, sc_prev: Dict = None,
                     historical: list = None, notes_level: str = "analitico",
                     ads_data: Dict = None, ads_prev: Dict = None, insights: Dict = None) -> Dict:
    return SEOAnalyzer(ga4_data, sc_data, ga4_prev, sc_prev, ads_data, ads_prev,
                       insights).get_full_analysis(historical, notes_level)
