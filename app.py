"""Aplicación Flask del TP Integrador: carga los Pipelines entrenados en notebooks/entrenamiento.ipynb y ejecuta predict.

NO entrena modelos, NO genera datos, NO acepta archivos joblib/pickle externos y NO usa base de datos.
Las reglas (umbral, categorías, rangos) se leen de modelos/metadata.json, escrito por el notebook.
"""
import json
import math
import sys
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from flask import Flask, jsonify, redirect, render_template, request, url_for

def get_base_dir():
    """Ruta base correcta tanto en desarrollo/Vercel como empaquetado con PyInstaller (.exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
RUTA_REG = BASE_DIR / "modelos" / "modelo_regresion_perdidas.joblib"
RUTA_CLF = BASE_DIR / "modelos" / "modelo_clasificacion_perdidas.joblib"
RUTA_META = BASE_DIR / "modelos" / "metadata.json"
RUTA_CSV = BASE_DIR / "datos" / "dataset_maquinaria_preparado.csv"       # solo para el tablero de flota

# public/ se sirve en la raíz (/estilos.css); en Vercel lo entrega directamente el CDN.
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "public"),
            static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024      # los formularios son pequeños; no se aceptan cargas de archivos

SISTEMA = {"ok": False, "error": None, "aviso": None, "reg": None, "clf": None, "meta": None}


def cargar_sistema():
    """Carga los modelos y la metadata. Nunca entrena: si algo falta o no coincide, informa el error."""
    SISTEMA.update({"ok": False, "error": None, "aviso": None, "reg": None, "clf": None, "meta": None})
    faltan = [r.name for r in (RUTA_REG, RUTA_CLF, RUTA_META) if not r.is_file()]
    if faltan:
        SISTEMA["error"] = ("Error de configuración: faltan archivos en modelos/ (" + ", ".join(faltan) +
                            "). Ejecutar el notebook notebooks/entrenamiento.ipynb para generarlos.")
        return
    try:
        meta = json.loads(RUTA_META.read_text(encoding="utf-8"))
        v_entrenamiento = str(meta.get("versiones", {}).get("scikit-learn"))
        v_entorno = sklearn.__version__
        if v_entrenamiento.split(".")[0] != v_entorno.split(".")[0]:
            # otra versión MAYOR: los modelos guardados no son confiables
            SISTEMA["error"] = (f"Error de configuración: los modelos se entrenaron con scikit-learn {v_entrenamiento} "
                                f"y el entorno tiene {v_entorno} (versión mayor distinta). Reentrenar con el notebook o "
                                "igualar las versiones de requirements.txt.")
            return
        reg, clf = joblib.load(RUTA_REG), joblib.load(RUTA_CLF)
        humo = pd.DataFrame([{"tipo_equipo": meta["categorias"]["tipo_equipo"][0], "provincia": meta["categorias"]["provincia"][0],
                              "meses_inactividad": float(meta["rangos"]["meses_inactividad"][0]),
                              "anio_fabricacion": int(meta["rangos"]["anio_fabricacion"][1]),
                              "estado_motor": meta["categorias"]["estado_motor"][0]}], columns=meta["predictores"])
        reg.predict(humo); clf.predict(humo)          # prueba de humo: si falla, no se habilita el sistema
        if v_entrenamiento != v_entorno:
            SISTEMA["aviso"] = (f"Aviso de versión: los modelos se entrenaron con scikit-learn {v_entrenamiento} y este entorno "
                                f"tiene {v_entorno}. Las predicciones funcionan (prueba de humo superada); para reproducir "
                                "exactamente los resultados instalar las versiones de requirements.txt o reentrenar con el notebook.")
        SISTEMA["reg"], SISTEMA["clf"], SISTEMA["meta"] = reg, clf, meta
        SISTEMA["ok"] = True
    except Exception as e:  # noqa: BLE001 - se informa el motivo en pantalla
        SISTEMA["error"] = f"Error al cargar los modelos: {e}"


cargar_sistema()


class ErrorValidacion(ValueError):
    pass


def validar_caso(form, meta):
    """Valida los campos contra las categorías y rangos de la metadata (nunca confía en el navegador)."""
    cat, rangos = meta["categorias"], meta["rangos"]
    r_meses, r_anio = rangos["meses_inactividad"], rangos["anio_fabricacion"]
    errores = []

    tipo = (form.get("tipo_equipo") or "").strip()
    provincia = (form.get("provincia") or "").strip()
    estado = (form.get("estado_motor") or "").strip()
    if tipo not in cat["tipo_equipo"]:
        errores.append("Tipo de equipo no válido.")
    if provincia not in cat["provincia"]:
        errores.append("Provincia no válida.")
    if estado not in cat["estado_motor"]:
        errores.append("Estado del motor no válido.")

    meses = None
    try:
        meses = float(form.get("meses_inactividad", ""))
        if not math.isfinite(meses) or not r_meses[0] <= meses <= r_meses[1]:
            raise ValueError
    except ValueError:
        meses = None
        errores.append(f"Los meses de inactividad deben ser un número entre {r_meses[0]} y {r_meses[1]}.")

    anio = None
    try:
        anio_f = float(form.get("anio_fabricacion", ""))
        if not math.isfinite(anio_f) or not anio_f.is_integer():
            raise ValueError
        anio = int(anio_f)
        if not r_anio[0] <= anio <= r_anio[1]:
            raise ValueError
    except ValueError:
        anio = None
        errores.append(f"El año de fabricación debe ser un entero entre {r_anio[0]} y {r_anio[1]}.")

    if errores:
        raise ErrorValidacion(errores)
    return {"tipo_equipo": tipo, "provincia": provincia, "meses_inactividad": meses,
            "anio_fabricacion": anio, "estado_motor": estado}


def predecir(caso, meta):
    """Ejecuta los dos Pipelines y compara las dos alertas (regresión + umbral vs clasificador directo)."""
    umbral = meta["umbral_usd"]
    banda = meta["metricas_test"]["regresion"]["MAE (USD)"]          # un MAE de distancia al umbral
    df_caso = pd.DataFrame([caso], columns=meta["predictores"])
    pred_usd = float(SISTEMA["reg"].predict(df_caso)[0])
    clase = int(SISTEMA["clf"].predict(df_caso)[0])

    alerta_reg = int(pred_usd >= umbral)                              # regla única: >= umbral
    coincide = alerta_reg == clase
    distancia = pred_usd - umbral
    cerca = abs(distancia) <= banda

    if coincide and alerta_reg:
        interpretacion = "Ambos sistemas indican un caso CRÍTICO: conviene darle prioridad de revisión."
    elif coincide:
        interpretacion = "Ambos sistemas indican un caso NORMAL: no se espera una pérdida crítica."
    elif alerta_reg:
        interpretacion = ("Discrepancia: la regresión estima una pérdida igual o mayor al umbral, pero el clasificador "
                          "directo lo considera normal. Ante la duda se recomienda revisión manual (un falso negativo es "
                          "el error más costoso).")
    else:
        interpretacion = ("Discrepancia: el clasificador directo lo considera crítico, pero la regresión estima una pérdida "
                          "menor al umbral. Se recomienda revisión manual.")
    if cerca:
        interpretacion += (f" Además, la estimación está a menos de USD {banda:,.0f} (un MAE) del umbral: "
                           "un error pequeño del modelo podría cambiar la alerta.")
    if coincide:
        acuerdo = "COINCIDENCIA TOTAL: ambos sistemas concuerdan en la criticidad del caso."
    else:
        acuerdo = "DESACUERDO: los dos sistemas difieren. Se sugiere revisión manual."
    color = "warning" if (not coincide or cerca) else ("danger" if alerta_reg else "success")
    return {"pred_usd": pred_usd, "umbral": umbral, "alerta_regresion": alerta_reg, "alerta_clasificador": clase,
            "coincide": coincide, "distancia_umbral": distancia, "cerca_umbral": cerca, "banda": banda,
            "interpretacion": interpretacion, "acuerdo": acuerdo, "color_alerta": color}


# ---------------------------------------------------------------------------------------------------------
# TABLERO DE FLOTA (visualización). Solo la columna «Lucro cesante estimado» sale del modelo de regresión.
# El valor de mercado, el costo de puesta en marcha y el dictamen son una SIMULACIÓN VISUAL con valores de
# referencia supuestos (no forman parte de la evaluación del modelo).
# ---------------------------------------------------------------------------------------------------------
PRECIOS_NUEVAS = {"Motoniveladora": 250000, "Excavadora": 220000, "Retroexcavadora": 150000,
                  "Cargadora frontal": 180000, "Rodillo compactador": 120000, "Topadora": 300000}
MAX_FILAS_TABLERO = 100
ANIO_REFERENCIA = 2026


def calcular_puesta_en_marcha(costo_base, anios_parada, coeficiente_anual=0.15, exponente=1.35, coeficiente_maximo=4.0):
    """Costo de puesta en marcha que crece con los años de parada (con tope)."""
    if costo_base < 0 or anios_parada < 0:
        return 0.0
    coeficiente = min(coeficiente_maximo, 1 + coeficiente_anual * (anios_parada ** exponente))
    return round(costo_base * coeficiente, 2)


def evaluar_viabilidad(lucro, puesta_marcha, valor_mercado, precio_nueva, meses, umbral):
    """Dictamen visual del tablero. La urgencia usa la misma regla que el resto del proyecto: lucro >= umbral."""
    costo = calcular_puesta_en_marcha(puesta_marcha, meses / 12.0)
    if costo >= precio_nueva or costo >= valor_mercado:
        return "🛑 INVIABLE / CHATARRA: Supera valor comercial o 0km.", "dark", costo
    if lucro >= umbral:
        return f"🚨 URGENTE: Lucro cesante crítico (>= USD {umbral:,.0f}).", "danger", costo
    if costo >= valor_mercado * 0.75:
        return "⚠️ ATENCIÓN: Deterioro avanzado.", "warning", costo
    return "✅ OPERATIVA: Viable para puesta en marcha.", "success", costo


def parsear_filtros(args, meta):
    """Lee proyección y filtros del querystring; descarta valores no válidos. Sin parámetros = todo seleccionado."""
    todos_t, todas_p = meta["categorias"]["tipo_equipo"], meta["categorias"]["provincia"]
    r_max = meta["rangos"]["meses_inactividad"][1]
    try:
        proyeccion = max(0, min(int(args.get("meses_proyeccion", 0)), r_max))
    except (TypeError, ValueError):
        proyeccion = 0
    if not any(k in args for k in ("tipos", "provincias", "meses_proyeccion")):
        return proyeccion, list(todos_t), list(todas_p)
    return (proyeccion, [t for t in args.getlist("tipos") if t in todos_t],
            [p for p in args.getlist("provincias") if p in todas_p])


def construir_inventario(proyeccion, tipos_sel, prov_sel):
    """Devuelve (registros, aviso). Nunca rompe la página: si el CSV no está, informa y el resto sigue funcionando."""
    meta = SISTEMA["meta"]
    if not RUTA_CSV.is_file():
        return [], "El tablero no está disponible: no se encontró datos/dataset_maquinaria_preparado.csv."
    try:
        df = pd.read_csv(RUTA_CSV)
        cols = ["tipo_equipo", "provincia", "meses_inactividad", "anio_fabricacion", "estado_motor"]
        df = df[cols].copy()
        df["pos"] = range(1, len(df) + 1)                      # el ID no cambia al filtrar
        df = df[df["tipo_equipo"].isin(tipos_sel) & df["provincia"].isin(prov_sel)].head(MAX_FILAS_TABLERO)
        if df.empty:
            return [], None
        df["meses_total"] = (df["meses_inactividad"] + proyeccion).clip(upper=meta["rangos"]["meses_inactividad"][1])
        X = df[cols].copy()
        X["meses_inactividad"] = df["meses_total"]
        lucros = SISTEMA["reg"].predict(X[meta["predictores"]])
        registros = []
        for fila, lucro in zip(df.itertuples(), lucros):
            lucro = float(lucro)
            precio = PRECIOS_NUEVAS.get(fila.tipo_equipo, 200000)
            v_mercado = precio * (0.95 ** max(0, ANIO_REFERENCIA - fila.anio_fabricacion))
            base = {"Requiere_Reparacion": 15000, "Averia_Grave": 35000}.get(fila.estado_motor, 0)
            veredicto, color, costo = evaluar_viabilidad(lucro, base + fila.meses_total * 250, v_mercado, precio,
                                                         fila.meses_total, meta["umbral_usd"])
            registros.append({"id_maquina": f"{fila.tipo_equipo[:3].upper()}-{str(fila.pos).zfill(3)}",
                              "tipo_equipo": fila.tipo_equipo, "provincia": fila.provincia,
                              "meses_base": int(fila.meses_inactividad), "meses_proyectados": int(fila.meses_total),
                              "valor_mercado": v_mercado, "puesta_marcha": costo, "lucro": lucro,
                              "veredicto": veredicto, "color": color})
        return registros, None
    except Exception:  # noqa: BLE001
        app.logger.exception("Error al procesar el inventario")
        return [], "No se pudo procesar el inventario (ver registro del servidor)."


def contexto_base():
    meta = SISTEMA["meta"] or {
        "categorias": {"tipo_equipo": [], "provincia": [], "estado_motor": []},
        "rangos": {"meses_inactividad": [1, 120], "anio_fabricacion": [2000, 2026]},
        "umbral_usd": 100000, "costos_relativos": {"falso_negativo": 5, "falso_positivo": 1},
    }
    return {"sistema_ok": SISTEMA["ok"], "error_sistema": SISTEMA["error"], "aviso_version": SISTEMA["aviso"], "meta": meta,
            "valores": {"tipo_equipo": "", "provincia": "", "meses_inactividad": "12", "anio_fabricacion": "2015",
                        "estado_motor": ""},
            "errores": [], "resultado": None, "registros": [], "aviso_tablero": None,
            "meses_proyeccion": 0, "tipos_sel": [], "prov_sel": []}


def con_tablero(ctx, args):
    """Agrega al contexto los filtros y el inventario (si el sistema está operativo)."""
    if SISTEMA["ok"]:
        ctx["meses_proyeccion"], ctx["tipos_sel"], ctx["prov_sel"] = parsear_filtros(args, SISTEMA["meta"])
        ctx["registros"], ctx["aviso_tablero"] = construir_inventario(
            ctx["meses_proyeccion"], ctx["tipos_sel"], ctx["prov_sel"])
    return ctx


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", **con_tablero(contexto_base(), request.args))


@app.route("/predecir_caso", methods=["POST"])
def predecir_caso():
    ctx = contexto_base()
    if not SISTEMA["ok"]:
        return render_template("index.html", **ctx), 503
    ctx["valores"] = {k: (request.form.get(k) or "") for k in ctx["valores"]}
    estado = 200
    try:
        caso = validar_caso(request.form, SISTEMA["meta"])
        ctx["resultado"] = predecir(caso, SISTEMA["meta"])
    except ErrorValidacion as e:
        ctx["errores"], estado = e.args[0], 400
    except Exception:  # noqa: BLE001
        app.logger.exception("Error inesperado en la predicción")
        ctx["errores"], estado = ["Ocurrió un error inesperado durante la predicción."], 500
    con_tablero(ctx, request.form)            # el tablero se conserva con los filtros enviados (campos ocultos)
    return render_template("index.html", **ctx), estado


@app.route("/predecir_caso", methods=["GET"])
def predecir_caso_get():
    return redirect(url_for("index"))


@app.route("/salud", methods=["GET"])
def salud():
    if SISTEMA["ok"]:
        return jsonify({"estado": "ok", "scikit-learn": sklearn.__version__, "aviso": SISTEMA["aviso"],
                        "modelo_regresion": SISTEMA["meta"]["modelo_regresion"],
                        "modelo_clasificacion": SISTEMA["meta"]["modelo_clasificacion"]})
    return jsonify({"estado": "error", "detalle": SISTEMA["error"]}), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
