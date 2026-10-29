"""Tests del semáforo de Rank Math. Ejecutar:  python3 -m unittest discover -s tests -v"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import seo_posts as sp  # noqa: E402

KW = "piscina de obra"
FILL = ("El proyecto se planifica con calma, se revisa el terreno y se acuerdan los plazos con la familia antes de empezar "
        "cualquier excavación, de modo que cada decisión técnica quede documentada y el resultado final sea duradero. ")


def filler(n_sentences: int) -> str:
    return (FILL * n_sentences).strip()


def good_post() -> dict:
    md = "\n\n".join([
        f"Una {KW} es una inversión a largo plazo para la casa y conviene conocer sus costes, plazos y mantenimiento antes de decidir. " + filler(2),
        "![Piscina de obra terminada en un jardín](jardin con piscina de obra al atardecer)",
        "## ¿Cuánto cuesta una piscina de obra?",
        # respuesta directa de ~50 palabras
        "El precio depende del tamaño, del acabado y del terreno, pero como orientación una vivienda media suele moverse entre "
        "un rango amplio que se concreta con una visita técnica. Pedir varios presupuestos detallados y comparar partidas permite "
        "entender qué incluye cada oferta y evitar sorpresas durante la obra.",
        filler(3),
        "## Qué tipos de piscina existen",
        filler(3),
        "- Hormigón proyectado con revestimiento\n- Acabado cerámico\n- Liner reforzado",
        "### Piscina de hormigón",
        filler(2) + " Consulta nuestras [piscinas de fibra](/piscinas-de-fibra/) si buscas una instalación más rápida.",
        "### Piscina con revestimiento",
        filler(2) + " También puedes ver el [proceso de construcción](/construccion/) paso a paso.",
        "## Cómo se mantiene una piscina de obra",
        filler(2),
        "El mantenimiento de piscinas exige constancia. Hay una guía de [mantenimiento](/mantenimiento/) con la rutina semanal.",
        "Conocer el precio piscina de cada oferta ayuda a decidir, y una piscina de obra bien cuidada mantiene su valor muchos años.",
        "Cada piscina de obra tiene su propio ritmo de limpieza, y la piscina de obra familiar suele necesitar menos productos si se cubre.",
        "Según el [Ministerio de Sanidad](https://www.sanidad.gob.es/), conviene controlar la calidad del agua.",
        "## Cuánto dura la construcción de una piscina de obra",
        filler(3),
        "## Preguntas frecuentes",
        "### ¿Se necesita licencia?",
        "Depende del municipio, así que lo mejor es consultarlo antes de empezar.",
        "### ¿Cuánto tarda la obra?",
        "Entre seis y diez semanas según el tamaño y la meteorología.",
        "### ¿Qué mantenimiento requiere?",
        "Revisar el pH y la limpieza cada semana y renovar el agua según el uso.",
    ])
    return {
        "titulo": "Piscina de obra: precio, tipos y mantenimiento en 2026",
        "slug": "piscina-de-obra-precio-tipos",
        "titulo_seo": "Piscina de obra: 5 claves de precio y mantenimiento",
        "meta_description": "Descubre cuánto cuesta una piscina de obra, qué tipos existen y cómo mantenerla. Pide tu presupuesto sin compromiso y compara opciones.",
        "keyword_principal": KW,
        "keywords_secundarias": ["precio piscina", "mantenimiento de piscinas"],
        "categoria": "Piscinas", "etiquetas": ["piscina de obra", "presupuesto"],
        "extracto": "Guía de costes, tipos y mantenimiento.",
        "schema": ["Article", "FAQPage"],
        "imagen_destacada_alt": "Piscina de obra con cascada",
        "tabla_contenidos": True,
        "contenido": md,
    }


def states(res):
    return {t["id"]: t["estado"] for t in res["tests"]}


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.post = good_post()
        self.base = "https://ejemplo.com"

    def run_post(self, post=None, **kw):
        return sp.validate_post(post or self.post, self.base, **kw)

    def test_good_post_is_green(self):
        res = self.run_post()
        bad = [(t["id"], t["estado"], t["detalle"]) for t in res["tests"] if t["estado"] in ("rojo", "naranja")]
        self.assertEqual(res["global"], "VERDE", bad)

    def test_keyword_missing_from_seo_title_is_red(self):
        p = copy.deepcopy(self.post); p["titulo_seo"] = "Guía de costes y mantenimiento"
        res = self.run_post(p)
        self.assertEqual(states(res)["kw_titulo_seo"], "rojo")
        self.assertEqual(res["global"], "ROJO")

    def test_title_and_meta_lengths(self):
        p = copy.deepcopy(self.post)
        p["titulo_seo"] = "Piscina de obra: " + "x" * 60
        p["meta_description"] = "Piscina de obra corta"
        s = states(self.run_post(p))
        self.assertEqual(s["titulo_seo_long"], "rojo")
        self.assertEqual(s["meta_long"], "rojo")

    def test_second_h1_in_content_is_red(self):
        p = copy.deepcopy(self.post); p["contenido"] = "# Otro título\n\n" + p["contenido"]
        self.assertEqual(states(self.run_post(p))["h1_unico"], "rojo")

    def test_heading_hierarchy(self):
        p = copy.deepcopy(self.post); p["contenido"] = "### Sección suelta\n\ntexto\n\n" + p["contenido"]
        self.assertEqual(states(self.run_post(p))["jerarquia"], "rojo")
        p["contenido"] = "## Uno\n\ntexto\n\n#### Salto\n\ntexto"
        self.assertEqual(states(self.run_post(p))["jerarquia"], "rojo")

    def test_short_content_is_red_and_density_is_checked(self):
        p = copy.deepcopy(self.post); p["contenido"] = f"## {KW}\n\n{KW} " * 10
        s = states(self.run_post(p))
        self.assertEqual(s["longitud"], "rojo")
        self.assertEqual(s["kw_densidad"], "rojo")

    def test_faq_schema_needs_visible_questions(self):
        p = copy.deepcopy(self.post)
        p["contenido"] = p["contenido"].split("## Preguntas frecuentes")[0]
        self.assertEqual(states(self.run_post(p))["schema_faq"], "rojo")
        p["schema"] = ["Article"]
        self.assertNotIn("schema_faq", states(self.run_post(p)))

    def test_missing_article_schema(self):
        p = copy.deepcopy(self.post); p["schema"] = ["FAQPage"]
        self.assertEqual(states(self.run_post(p))["schema_art"], "rojo")

    def test_links_split_internal_external(self):
        blocks = sp.parse_content("Mira [esto](/a/), [aquello](https://ejemplo.com/b/) y [fuera](https://otra.org/x).")
        internal, external = sp.split_links(sp.links_in(blocks), self.base)
        self.assertEqual(len(internal), 2)
        self.assertEqual([u for _, u in external], ["https://otra.org/x"])

    def test_no_external_links_is_red(self):
        p = copy.deepcopy(self.post)
        p["contenido"] = p["contenido"].replace("[Ministerio de Sanidad](https://www.sanidad.gob.es/)", "el Ministerio de Sanidad")
        self.assertEqual(states(self.run_post(p))["enl_ext"], "rojo")

    def test_direct_answer_snippet(self):
        p = copy.deepcopy(self.post)
        p["contenido"] = p["contenido"].replace("¿Cuánto cuesta una piscina de obra?", "Precio de una piscina de obra")
        p["contenido"] = p["contenido"].replace("¿Se necesita licencia?", "Licencia").replace("¿Cuánto tarda la obra?", "Plazo").replace("¿Qué mantenimiento requiere?", "Mantenimiento")
        self.assertEqual(states(self.run_post(p))["respuesta"], "naranja")

    def test_existing_keyword_is_flagged(self):
        res = self.run_post(existing=[{"title": "Piscina de obra: guía completa", "url": "https://ejemplo.com/piscina-de-obra-guia/"}])
        self.assertEqual(states(res)["kw_unica"], "naranja")

    def test_links_not_checked_by_default(self):
        self.assertEqual(states(self.run_post())["enl_activos"], "no_comprobado")

    def test_report_renders_fix_list(self):
        p = copy.deepcopy(self.post); p["titulo_seo"] = "Sin la clave"
        txt = sp.render_report(self.run_post(p))
        self.assertIn("Para corregir", txt)
        self.assertIn("🔴", txt)


class TestParse(unittest.TestCase):
    def test_blocks(self):
        md = "Intro con [enlace](/x/).\n\n## H2\n\n- a\n- b\n\n1. uno\n2. dos\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n![alt](idea)"
        kinds = [b["t"] for b in sp.parse_content(md)]
        self.assertEqual(kinds, ["p", "h2", "ul", "ol", "table", "img"])

    def test_table_rows_skip_separator(self):
        t = sp.parse_content("| A | B |\n|---|---|\n| 1 | 2 |")[0]
        self.assertEqual(t["rows"], [["A", "B"], ["1", "2"]])

    def test_url_ok(self):
        self.assertEqual(sp.url_ok(200), "ok")
        self.assertEqual(sp.url_ok(403), "bloquea")
        self.assertEqual(sp.url_ok(404), "roto")
        self.assertEqual(sp.url_ok(None), "roto")


class TestBrief(unittest.TestCase):
    def test_brief_issues(self):
        ok = {"keyword_principal": KW, "titulo_seo": "Piscina de obra: guía", "slug": "piscina-de-obra-guia",
              "meta_description": "Piscina de obra: " + "x" * 110}
        self.assertEqual(sp.brief_issues(ok), [])
        bad = dict(ok, titulo_seo="Guía de " + "x" * 70, slug="Piscina Obra")
        issues = " | ".join(sp.brief_issues(bad))
        self.assertIn("título SEO", issues)
        self.assertIn("slug", issues)


if __name__ == "__main__":
    unittest.main()
