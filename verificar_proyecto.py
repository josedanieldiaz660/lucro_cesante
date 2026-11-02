"""Verificador previo a la entrega: contrasta el proyecto con la consigna y con lo trabajado.

Uso (desde la raíz del proyecto, con el entorno virtual activado):   python verificar_proyecto.py
Resultado: PASS (cumple) / WARN (pendiente o recomendable) / FAIL (hay que corregir). Termina con código 1 si hay FAIL.
"""
import json, re, subprocess, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
R = []   # (estado, bloque, detalle)


def ok(b, d): R.append(("PASS", b, d))
def warn(b, d): R.append(("WARN", b, d))
def fail(b, d): R.append(("FAIL", b, d))
def chk(cond, b, d_ok, d_mal, grave=True): (ok(b, d_ok) if cond else (fail if grave else warn)(b, d_mal))


def texto(p):
    try: return p.read_text(encoding="utf-8")
    except Exception: return ""


# 1. Estructura mínima de la consigna (6.1) y entrega final (7)
obligatorios = ["README.md", "requirements.txt", "app.py", "modelos", "templates/index.html", "public", "notebooks/entrenamiento.ipynb",
                "datos/README.md", "informe/informe_final.pdf"]
falt = [x for x in obligatorios if not (RAIZ / x).exists()]
chk(not falt, "1. Estructura (consigna 6.1)", "están todos los archivos de la estructura mínima", f"faltan: {falt}")
extras = ["presentacion/presentacion_final.pptx", "documentacion/bitacora_decisiones.md", "documentacion/distribucion_tareas.md",
          "datos/dataset_maquinaria_preparado.csv", "modelos/metadata.json", "modelos/modelo_regresion_perdidas.joblib",
          "modelos/modelo_clasificacion_perdidas.joblib", "pruebas/test_app.py", ".gitignore"]
falt = [x for x in extras if not (RAIZ / x).exists()]
chk(not falt, "2. Entrega final (consigna 7)", "presentación, bitácora, distribución, datos, modelos y pruebas presentes", f"faltan: {falt}")
chk(not (RAIZ / "venv").exists() and not (RAIZ / ".venv").exists(), "3. Sin entorno virtual en la carpeta",
    "no hay venv dentro del proyecto (o se ignora en git)", "hay una carpeta venv: no se sube a GitHub (debe estar en .gitignore)", grave=False)
gi = texto(RAIZ / ".gitignore"); chk("venv" in gi, "3b. .gitignore", "ignora venv/", "falta 'venv/' en .gitignore")
grandes = [str(p.relative_to(RAIZ)) for p in RAIZ.rglob("*") if p.is_file() and "venv" not in p.parts and "__pycache__" not in p.parts and p.stat().st_size > 50 * 2**20]
chk(not grandes, "3c. Tamaño de archivos", "ningún archivo supera 50 MB (límite práctico de GitHub: 100 MB)", f"archivos muy grandes: {grandes}")

# 2. requirements con versiones
req = {}
for l in texto(RAIZ / "requirements.txt").splitlines():
    l = l.split("#")[0].strip()
    if l and not l.startswith("-"):
        m = re.match(r"([A-Za-z0-9_.\-]+)==([\w.\-]+)$", l)
        if m: req[m.group(1).lower()] = m.group(2)
        else: fail("4. requirements.txt", f"línea sin versión fija '==': {l}")
for p in ("flask", "pandas", "numpy", "scikit-learn", "joblib"):
    if p not in req: fail("4. requirements.txt", f"falta {p}==<versión>")
if all(p in req for p in ("flask", "pandas", "numpy", "scikit-learn", "joblib")):
    ok("4. requirements.txt", "dependencias de la app con versión fija: " + ", ".join(f"{k}=={v}" for k, v in req.items()))
if any(p in req for p in ("matplotlib", "seaborn")):
    warn("4b. requirements.txt", "matplotlib/seaborn solo se usan en el notebook: moverlos a requirements-notebook.txt (aligera Vercel)")

# 3. metadata, modelos y consistencia de versiones
meta = None
try:
    meta = json.loads(texto(RAIZ / "modelos" / "metadata.json"))
    ok("5. metadata.json", f"umbral {meta['umbral_usd']:,} USD · regresor {meta['modelo_regresion']} · clasificador {meta['modelo_clasificacion']} · semilla {meta['semilla']}")
except Exception as e:
    fail("5. metadata.json", f"no se pudo leer: {e}")
if meta:
    vm = meta.get("versiones", {})
    for pkg, key in (("scikit-learn", "scikit-learn"), ("pandas", "pandas"), ("numpy", "numpy"), ("joblib", "joblib")):
        if pkg in req and vm.get(key) != req[pkg]:
            fail("6. Versiones", f"{pkg}: los modelos se entrenaron con {vm.get(key)} pero requirements.txt fija {req[pkg]} → reentrenar con el notebook o corregir requirements")
    if not any(r[1] == "6. Versiones" for r in R):
        ok("6. Versiones", "metadata.json coincide con requirements.txt (los modelos se pueden reproducir en Vercel)")
    try:
        import sklearn, pandas, numpy
        inst = {"scikit-learn": sklearn.__version__, "pandas": pandas.__version__, "numpy": numpy.__version__}
        dif = {k: (v, vm.get(k)) for k, v in inst.items() if vm.get(k) != v}
        chk(not dif, "6b. Entorno local", "las versiones instaladas son las de entrenamiento",
            f"entorno distinto al de entrenamiento (instalado, entrenamiento): {dif}. Ejecutar: pip install -r requirements.txt", grave=False)
    except ImportError as e:
        fail("6b. Entorno local", f"faltan librerías: {e}. Ejecutar: pip install -r requirements-notebook.txt")

# 4. Dataset (consigna 2 y 3.2)
try:
    import pandas as pd
    df = pd.read_csv(RAIZ / "datos" / "dataset_maquinaria_preparado.csv")
    pred = meta["predictores"] if meta else []
    chk(len(df) >= 2000, "7. Dataset ≥ 2000 registros", f"{len(df):,} registros", f"solo {len(df)} registros")
    chk(len(pred) >= 5 and all(c in df.columns for c in pred), "8. ≥ 5 predictores", f"{len(pred)} predictores: {', '.join(pred)}", "faltan predictores")
    chk(int(df.isna().sum().sum()) == 0, "9. Sin nulos en el dataset preparado", "0 valores nulos", "hay valores nulos")
    chk(not df.duplicated().any(), "10. Sin duplicados", "0 duplicados completos", "hay filas duplicadas", grave=False)
    if meta:
        coh = bool(((df["perdida_economica_usd"] >= meta["umbral_usd"]).astype(int) == df["perdida_critica"]).all())
        chk(coh, "11. Regla del umbral (≥)", f"perdida_critica coincide con 'pérdida ≥ {meta['umbral_usd']:,}' en todas las filas", "perdida_critica no coincide con la regla ≥ umbral")
        bal = df["perdida_critica"].mean()
        chk(0.2 < bal < 0.8, "12. Balance de clases", f"{bal:.1%} de casos críticos", f"clases muy desbalanceadas ({bal:.1%})", grave=False)
        ids = [c for c in pred if re.search(r"(^|_)(id|nombre|apellido|dni|cuil|mail|email|telefono|direccion|patente|perdida)($|_)", c, re.I)]
        chk(not ids, "13. Fuga / datos personales", "los predictores no incluyen identificadores ni objetivos", f"revisar predictores: {ids}")
except Exception as e:
    fail("7. Dataset", f"no se pudo analizar: {e}")

# 5. Modelos: cargan, predicen y son Pipelines
try:
    import joblib, warnings
    from sklearn.pipeline import Pipeline
    warnings.simplefilter("ignore")
    reg = joblib.load(RAIZ / "modelos" / "modelo_regresion_perdidas.joblib"); clf = joblib.load(RAIZ / "modelos" / "modelo_clasificacion_perdidas.joblib")
    chk(isinstance(reg, Pipeline) and isinstance(clf, Pipeline), "14. Pipelines guardados", "ambos modelos son Pipelines (preprocesamiento dentro)", "los modelos no son Pipelines")
    X = df[meta["predictores"]].head(200)
    p, c = reg.predict(X), clf.predict(X)
    chk(len(p) == 200 and set(c) <= {0, 1}, "15. Predicción", "los dos modelos predicen sobre datos reales del dataset", "las predicciones no tienen el formato esperado")
except Exception as e:
    fail("14. Modelos", f"no cargan/predicen: {e}")

# 6. Notebook ejecutado limpio y con lo exigido
try:
    nb = json.loads(texto(RAIZ / "notebooks" / "entrenamiento.ipynb"))
    cod = [c for c in nb["cells"] if c["cell_type"] == "code"]
    errores = [i for i, c in enumerate(cod) if any(o.get("output_type") == "error" for o in c.get("outputs", []))]
    sin_salida = [i for i, c in enumerate(cod) if not c.get("outputs")]
    chk(not errores, "16. Notebook sin errores guardados", "ninguna celda guardó un error", f"celdas de código con ERROR guardado: {errores} → ejecutar 'Run All' con el kernel del venv y guardar")
    chk(len(sin_salida) <= 1, "17. Notebook ejecutado completo", f"{len(cod) - len(sin_salida)}/{len(cod)} celdas con salida", f"{len(sin_salida)} celdas sin salida → ejecutar 'Run All' y guardar", grave=False)
    fuente = "\n".join("".join(c["source"]) for c in nb["cells"])
    req_nb = ["DummyRegressor", "DecisionTreeRegressor", "KNeighborsRegressor", "DummyClassifier", "DecisionTreeClassifier", "KNeighborsClassifier",
              "GaussianNB", "StandardScaler", "Pipeline", "random_state", "MAE", "RMSE", "confusion_matrix", "joblib.dump"]
    falt = [x for x in req_nb if x not in fuente]
    chk(not falt, "18. Contenido del notebook (consigna 3.3 / 3.4)", "modelos, métricas, Pipeline, semilla y guardado presentes", f"no aparece en el notebook: {falt}")
    chk("a completar" not in fuente.lower(), "19. Notebook sin pendientes", "no quedan textos 'a completar'", "quedan textos 'a completar' en el notebook")
except Exception as e:
    fail("16. Notebook", f"no se pudo leer: {e}")

# 7. Seguridad de la app (consigna 5.2)
app = texto(RAIZ / "app.py")
chk("request.files" not in app and "pickle.load" not in app, "20. App sin cargas de archivos ni pickle externos", "no acepta archivos ni deserializa datos externos", "la app acepta archivos o usa pickle")
chk("debug=True" not in app.replace(" ", ""), "21. App sin debug", "debug desactivado", "app.run con debug=True")
chk(not re.search(r"\.fit\(", app), "22. La app no entrena", "app.py no llama a .fit()", "app.py entrena modelos (prohibido por la consigna)")
chk("render_template(" in app and (RAIZ / "templates" / "index.html").exists(), "23. Usa templates/", "la app renderiza templates/index.html", "la app no usa templates/", grave=False)
sec = [str(p.relative_to(RAIZ)) for p in RAIZ.rglob("*") if p.is_file() and p.suffix in {".py", ".md", ".txt", ".json", ".html", ".env"} and "venv" not in p.parts
       and p.name != "verificar_proyecto.py" and re.search(r"(api[_-]?key|secret|password|passwd|token)\s*[=:]\s*['\"][^'\"]{6,}", texto(p), re.I)]
chk(not sec, "24. Sin credenciales en el repositorio", "no se detectaron claves ni contraseñas", f"posibles credenciales en: {sec}")

# 8. Pruebas funcionales
try:
    r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", "discover", "-s", "pruebas"], cwd=RAIZ, capture_output=True, text=True, timeout=300)
    salida = r.stderr + r.stdout
    n = re.search(r"Ran (\d+) tests?", salida)
    chk(r.returncode == 0, "25. Pruebas funcionales", f"{n.group(1) if n else '?'} pruebas aprobadas", "hay pruebas que fallan:\n" + salida[-700:])
    rp = texto(RAIZ / "pruebas" / "resultado_pruebas.txt"); nr = re.search(r"Ran (\d+) tests?", rp)
    chk(bool(n and nr and n.group(1) == nr.group(1)), "26. resultado_pruebas.txt actualizado", f"coincide con la ejecución ({nr.group(1) if nr else '?'} pruebas)",
        f"resultado_pruebas.txt dice {nr.group(1) if nr else 'nada'} pruebas y hoy hay {n.group(1) if n else '?'} → regenerarlo (ver paso a paso)", grave=False)
except Exception as e:
    fail("25. Pruebas funcionales", f"no se pudieron ejecutar: {e}")

# 9. Documentos y pendientes por completar
pend = {}
for rel in ["README.md", "documentacion/bitacora_decisiones.md", "documentacion/distribucion_tareas.md"]:
    n = len(re.findall(r"\(completar|_\(completar|\(asignar", texto(RAIZ / rel)))
    if n: pend[rel] = n
chk(not pend, "27. Campos por completar (md)", "no quedan campos pendientes", f"pendientes de completar por el grupo: {pend}", grave=False)
try:
    t = subprocess.run(["pdftotext", str(RAIZ / "informe" / "informe_final.pdf"), "-"], capture_output=True, text=True, timeout=60).stdout
    chk(len(t) > 3000, "28. Informe PDF con contenido", f"{len(t):,} caracteres de texto", "el informe parece vacío o corto")
    chk("(completar" not in t, "29. Informe sin campos pendientes", "no quedan '(completar...)'", "el informe aún tiene '(completar…)': curso, fechas y URLs (regenerar o editar el PDF)", grave=False)
    pr = [q for q in ("MAE", "Baseline", "umbral", "falso negativo", "Regresión + umbral", "Limitaciones") if q.lower() not in t.lower()]
    chk(not pr, "30. Informe con los temas pedidos", "baselines, MAE, umbral, FP/FN, integración y limitaciones presentes", f"faltan temas en el informe: {pr}")
except FileNotFoundError:
    warn("28. Informe PDF", "no se pudo leer el PDF (falta 'pdftotext'); revisar el informe a mano")
except Exception as e:
    warn("28. Informe PDF", f"no se pudo analizar: {e}")

# Resultado
orden = {"FAIL": 0, "WARN": 1, "PASS": 2}
ico = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}
print("\nVERIFICACIÓN DEL PROYECTO\n" + "=" * 70)
for e, b, d in R:
    print(f"{ico[e]} {e:<4} {b}\n        {d}")
n = {k: sum(1 for r in R if r[0] == k) for k in orden}
print("=" * 70 + f"\nRESUMEN: {n['PASS']} PASS · {n['WARN']} WARN · {n['FAIL']} FAIL")
print("→ " + ("LISTO PARA SUBIR (revisar los WARN pendientes del grupo)." if not n["FAIL"] else "CORREGIR los FAIL antes de subir al repositorio."))
sys.exit(1 if n["FAIL"] else 0)
