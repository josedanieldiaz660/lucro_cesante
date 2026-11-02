# TP Integrador de Aprendizaje Automático – Grupo 5
## Pérdida económica por maquinaria vial bajo custodia: regresión + alerta crítica

> **Datos SIMULADOS.** Las métricas valen dentro de la simulación y no prueban capacidad predictiva real.
> El umbral (USD 100.000) y los costos (FN = 5, FP = 1) son supuestos didácticos.

**Integrantes:** Maciel Fátima · Díaz José · Carrera Carla · Sarmiento Rodrigo
**Aplicación publicada:** _(completar URL de Vercel)_ · **Repositorio:** _(completar URL)_

### Qué hace
Dado un equipo (tipo, provincia, meses de inactividad, año de fabricación, estado del motor) estima la **pérdida económica en USD**
(regresión, KNN k=15) y emite una **alerta crítica** (≥ USD 100.000) de dos formas: regresión + umbral y clasificador directo (árbol prof=10).
La aplicación muestra ambas alertas, si coinciden y la cercanía al umbral, y un **tablero de flota** (hasta 100 equipos de `datos/dataset_maquinaria_preparado.csv`) con filtros por tipo y provincia, proyección de inactividad a futuro y dictamen visual. En el tablero solo el «Lucro Cesante Estimado» sale del modelo; valor de mercado, costo de puesta en marcha y dictamen son una simulación visual con valores de referencia supuestos.

### Estructura
```
app.py                     Aplicación Flask (solo carga modelos y hace predict)
templates/index.html       Interfaz
public/estilos.css         Estilos
notebooks/entrenamiento.ipynb   Datos → controles → entrenamiento → evaluación → guardado de modelos
datos/                     CSV crudo y preparado + README (diccionario y fórmula)
modelos/                   2 Pipelines .joblib + metadata.json
pruebas/                   24 pruebas funcionales + resultado_pruebas.txt
informe/                   informe_final.pdf (+ Entrega1_Grupo5.pdf)
presentacion/              presentacion_final.pptx
documentacion/             bitácora de decisiones y distribución de tareas
requirements.txt           Dependencias de la aplicación (Vercel)
requirements-notebook.txt  Dependencias para ejecutar el notebook
```

### Ejecutar localmente (Python 3.12)
```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-notebook.txt notebook
jupyter notebook notebooks/entrenamiento.ipynb          # Kernel > Restart & Run All (regenera datos/ y modelos/)
python app.py                                           # http://127.0.0.1:5001/
python -m unittest discover -s pruebas -v               # 24 pruebas
```
Si la versión de scikit-learn difiere solo en la menor (p. ej. 1.8.0 vs 1.9.0), la app **funciona y muestra un aviso** (tras una prueba de humo de los modelos); si difiere la versión mayor o los modelos no pasan la prueba, no los habilita. Para reproducir exactamente los resultados: `pip install -r requirements.txt` o reentrenar con el notebook.

### Despliegue (Vercel)
Subir el repositorio a GitHub → *Add New Project* en Vercel → importar. Vercel detecta Flask (`app.py`), `requirements.txt` y `.python-version`.
Verificar `https://<proyecto>.vercel.app/salud` y probar un caso desde otro dispositivo.

### Reproducibilidad
Semilla 42 · Python 3.12 · numpy 2.4.4 · pandas 3.0.2 · scikit-learn 1.8.0 · joblib 1.5.3 (ver `modelos/metadata.json`).
