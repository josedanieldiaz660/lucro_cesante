"""Pruebas funcionales (auditoría 8.2). Ejecutar desde la raíz:  python -m unittest discover -s pruebas -v"""
import json, shutil, sys, tempfile, unittest
from pathlib import Path

import joblib
import pandas as pd
import sklearn

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import app as aplicacion  # noqa: E402

VALIDO = {"tipo_equipo": "Excavadora", "provincia": "Córdoba", "meses_inactividad": "36",
          "anio_fabricacion": "2015", "estado_motor": "Requiere_Reparacion"}


class PruebasApp(unittest.TestCase):
    def setUp(self):
        aplicacion.cargar_sistema()
        self.c = aplicacion.app.test_client()

    def post(self, **cambios):
        return self.c.post("/predecir_caso", data={**VALIDO, **cambios})

    def test_01_pagina_inicial(self):
        r = self.c.get("/"); self.assertEqual(r.status_code, 200); self.assertIn("demostración".encode(), r.data.lower())

    def test_02_caso_valido_dos_predicciones(self):
        r = self.post(); self.assertEqual(r.status_code, 200)
        self.assertIn("Pérdida estimada".encode(), r.data); self.assertIn("clasificador directo".encode(), r.data.lower())

    def test_03_cambiar_meses_cambia_resultado(self):
        a = self.post(meses_inactividad="6").data; b = self.post(meses_inactividad="100").data
        self.assertNotEqual(a, b)

    def test_04_valor_no_numerico(self):
        for campo in ("meses_inactividad", "anio_fabricacion"):
            for malo in ("abc", "", "nan", "inf", "-inf", "1e999"):
                r = self.post(**{campo: malo}); self.assertEqual(r.status_code, 400, (campo, malo))
                self.assertNotIn(b"Traceback", r.data)

    def test_05_meses_fuera_de_rango(self):
        for m in ("-1", "0", "0.5", "121", "999"):
            self.assertEqual(self.post(meses_inactividad=m).status_code, 400, m)
        for m in ("1", "120"):
            self.assertEqual(self.post(meses_inactividad=m).status_code, 200, m)

    def test_06_categoria_no_permitida(self):
        for campo in ("tipo_equipo", "provincia", "estado_motor"):
            self.assertEqual(self.post(**{campo: "Inventada"}).status_code, 400)
            self.assertEqual(self.post(**{campo: ""}).status_code, 400)

    def test_07_anio_fuera_de_rango_o_decimal(self):
        for a in ("1999", "2027", "2015.5"):
            self.assertEqual(self.post(anio_fabricacion=a).status_code, 400, a)
        for a in ("2000", "2026"):
            self.assertEqual(self.post(anio_fabricacion=a).status_code, 200, a)

    def test_08_campo_ausente(self):
        d = dict(VALIDO); d.pop("estado_motor")
        self.assertEqual(self.c.post("/predecir_caso", data=d).status_code, 400)

    def test_09_valores_conservados_tras_error(self):
        r = self.post(meses_inactividad="999")
        self.assertIn(b'value="999"', r.data); self.assertIn("Córdoba".encode(), r.data)

    def test_10_sin_modelos_no_entrena(self):
        with tempfile.TemporaryDirectory() as tmp:
            originales = (aplicacion.RUTA_REG, aplicacion.RUTA_CLF, aplicacion.RUTA_META)
            try:
                aplicacion.RUTA_REG = Path(tmp) / "no_existe_reg.joblib"
                aplicacion.cargar_sistema()
                self.assertFalse(aplicacion.SISTEMA["ok"]); self.assertIn("faltan", aplicacion.SISTEMA["error"])
                self.assertEqual(self.c.post("/predecir_caso", data=VALIDO).status_code, 503)
                self.assertEqual(self.c.get("/salud").status_code, 503)
                self.assertFalse(Path(aplicacion.RUTA_REG).exists())   # no se creó ningún modelo de respaldo
            finally:
                aplicacion.RUTA_REG, aplicacion.RUTA_CLF, aplicacion.RUTA_META = originales
                aplicacion.cargar_sistema()

    def test_11_version_incompatible(self):
        meta = dict(aplicacion.SISTEMA["meta"]); meta["versiones"] = {**meta["versiones"], "scikit-learn": "0.0.1"}
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "metadata.json"; ruta.write_text(json.dumps(meta), encoding="utf-8")
            original = aplicacion.RUTA_META; aplicacion.RUTA_META = ruta
            try:
                aplicacion.cargar_sistema(); self.assertFalse(aplicacion.SISTEMA["ok"])
                self.assertIn("scikit-learn", aplicacion.SISTEMA["error"])
            finally:
                aplicacion.RUTA_META = original; aplicacion.cargar_sistema()

    def test_12_coincide_con_artefactos_del_notebook(self):
        reg = joblib.load(aplicacion.RUTA_REG); clf = joblib.load(aplicacion.RUTA_CLF)
        meta = aplicacion.SISTEMA["meta"]; df = pd.DataFrame([{**VALIDO, "meses_inactividad": 36.0, "anio_fabricacion": 2015}])
        esperado = float(reg.predict(df)[0]); clase = int(clf.predict(df)[0])
        r = aplicacion.predecir({**VALIDO, "meses_inactividad": 36.0, "anio_fabricacion": 2015}, meta)
        self.assertAlmostEqual(r["pred_usd"], esperado); self.assertEqual(r["alerta_clasificador"], clase)
        self.assertEqual(r["alerta_regresion"], int(esperado >= meta["umbral_usd"]))

    def test_13_umbral_exacto_usa_mayor_o_igual(self):
        class Falso:  # regresor que devuelve exactamente el umbral
            def predict(self, X): return [100000.0]
        original = aplicacion.SISTEMA["reg"]; aplicacion.SISTEMA["reg"] = Falso()
        try:
            r = aplicacion.predecir({**VALIDO, "meses_inactividad": 36.0, "anio_fabricacion": 2015}, aplicacion.SISTEMA["meta"])
            self.assertEqual(r["alerta_regresion"], 1)
        finally:
            aplicacion.SISTEMA["reg"] = original

    def test_14_solicitud_demasiado_grande(self):
        self.assertEqual(self.c.post("/predecir_caso", data={**VALIDO, "tipo_equipo": "x" * 40000}).status_code, 413)

    def test_15_estatico_y_metodos(self):
        self.assertEqual(self.c.get("/estilos.css").status_code, 200)
        self.assertEqual(self.c.get("/predecir_caso").status_code, 302)

    # ---------------- Tablero de flota (visualización) ----------------
    def test_16_tablero_columnas_y_filas(self):
        r = self.c.get("/"); self.assertEqual(r.status_code, 200)
        for col in ("Dictamen y Viabilidad", "Lucro Cesante Estimado", "Costo Puesta Marcha", "Inactividad Proyectada"):
            self.assertIn(col.encode(), r.data)
        regs, aviso = aplicacion.construir_inventario(0, *aplicacion.parsear_filtros({}, aplicacion.SISTEMA["meta"])[1:])
        self.assertIsNone(aviso); self.assertEqual(len(regs), 100)
        self.assertEqual([x["id_maquina"] for x in regs[:3]], ["MOT-001", "ROD-002", "CAR-003"])

    def test_17_filtros_por_tipo_y_provincia(self):
        regs, _ = aplicacion.construir_inventario(0, ["Topadora"], ["Salta"])
        self.assertTrue(regs); self.assertTrue(all(x["tipo_equipo"] == "Topadora" and x["provincia"] == "Salta" for x in regs))
        self.assertEqual(aplicacion.construir_inventario(0, [], ["Salta"]), ([], None))   # nada seleccionado = sin filas

    def test_18_proyeccion_suma_meses_con_tope(self):
        base, _ = aplicacion.construir_inventario(0, ["Topadora"], ["Salta"])
        proy, _ = aplicacion.construir_inventario(10, ["Topadora"], ["Salta"])
        tope = aplicacion.SISTEMA["meta"]["rangos"]["meses_inactividad"][1]
        for a, b in zip(base, proy):
            self.assertEqual(b["meses_proyectados"], min(a["meses_base"] + 10, tope))
        grandes, _ = aplicacion.construir_inventario(10 ** 6, ["Topadora"], ["Salta"])
        self.assertTrue(all(x["meses_proyectados"] == tope for x in grandes))

    def test_19_parametros_invalidos_no_rompen(self):
        for q in ("meses_proyeccion=abc", "meses_proyeccion=99999", "meses_proyeccion=-5", "tipos=Inventada&provincias=Nada",
                  "meses_proyeccion=%00", "tipos=" + "x" * 3000):
            r = self.c.get("/?" + q); self.assertEqual(r.status_code, 200, q); self.assertNotIn(b"Traceback", r.data)

    def test_20_dictamen_urgente_usa_la_misma_regla_del_umbral(self):
        regs, _ = aplicacion.construir_inventario(0, *aplicacion.parsear_filtros({}, aplicacion.SISTEMA["meta"])[1:])
        umbral = aplicacion.SISTEMA["meta"]["umbral_usd"]
        self.assertTrue(any(x["color"] == "danger" for x in regs))
        self.assertTrue(all((x["lucro"] >= umbral) for x in regs if x["color"] == "danger"))
        self.assertTrue(all(x["color"] in ("dark", "danger", "warning", "success") for x in regs))

    def test_21_tablero_se_conserva_tras_predecir(self):
        r = self.post(); self.assertEqual(r.status_code, 200); self.assertIn(b"Dictamen y Viabilidad", r.data)
        r = self.post(meses_inactividad="abc"); self.assertEqual(r.status_code, 400); self.assertIn(b"Dictamen y Viabilidad", r.data)

    def test_22_sin_csv_el_tablero_avisa_y_la_prediccion_sigue(self):
        original = aplicacion.RUTA_CSV
        aplicacion.RUTA_CSV = RAIZ / "datos" / "no_existe.csv"
        try:
            r = self.c.get("/"); self.assertEqual(r.status_code, 200); self.assertIn("El tablero no está disponible".encode(), r.data)
            self.assertEqual(self.post().status_code, 200)
        finally:
            aplicacion.RUTA_CSV = original

    def test_23_escape_de_html(self):
        r = self.c.get("/?tipos=<script>alert(1)</script>"); self.assertNotIn(b"<script>alert(1)", r.data)

    def test_24_version_menor_distinta_carga_con_aviso(self):
        """Mismo scikit-learn mayor pero distinta menor (p. ej. 1.8.0 vs 1.9.0): el sistema funciona y avisa; no bloquea."""
        meta = dict(aplicacion.SISTEMA["meta"]); meta["versiones"] = {**meta["versiones"], "scikit-learn": "1.0.0"}
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "metadata.json"; ruta.write_text(json.dumps(meta), encoding="utf-8")
            original = aplicacion.RUTA_META; aplicacion.RUTA_META = ruta
            try:
                aplicacion.cargar_sistema()
                self.assertTrue(aplicacion.SISTEMA["ok"]); self.assertIn("Aviso de versión", aplicacion.SISTEMA["aviso"])
                r = self.c.get("/"); self.assertEqual(r.status_code, 200)
                self.assertIn("Aviso de versión".encode(), r.data); self.assertIn(b"Dictamen y Viabilidad", r.data)
                self.assertEqual(self.post().status_code, 200)
            finally:
                aplicacion.RUTA_META = original; aplicacion.cargar_sistema()
                entrenado = aplicacion.SISTEMA["meta"]["versiones"]["scikit-learn"]
                self.assertEqual(aplicacion.SISTEMA["aviso"] is None, entrenado == sklearn.__version__)

if __name__ == "__main__":
    unittest.main(verbosity=2)
