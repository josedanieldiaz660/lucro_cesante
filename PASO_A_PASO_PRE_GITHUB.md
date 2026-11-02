# Paso a paso antes de subir a GitHub (Windows / PowerShell)

Objetivo: comprobar que **todo funciona, es reproducible y cumple la consigna** antes del primer `git push`.
Cada fase termina con un criterio de aprobación. No pasen a la siguiente si la anterior no aprobó.

---
## Fase 0 · Quedarse con una sola carpeta correcta
1. Hagan una copia de seguridad de su carpeta actual `lucro_cesante`.
2. Descompriman `lucro_cesante_final.zip` y copien su contenido **sobre** la carpeta del proyecto (reemplazar todo).
3. La carpeta `venv` no viene en el zip: si ya tienen una, déjenla (git la ignora).

✅ Aprobado si: existe `verificar_proyecto.py`, `PASO_A_PASO_PRE_GITHUB.md` y `pruebas/test_app.py` contiene `test_24`.

## Fase 1 · Entorno con las versiones exactas
```powershell
cd "D:\mis documentos\...\lucro_cesante"
python -m venv venv                          # solo si no existe
.\venv\Scripts\Activate.ps1                  # si lo bloquea: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m pip install --upgrade pip
pip install -r requirements-notebook.txt
pip install notebook ipykernel
python -m ipykernel install --user --name lucro_cesante --display-name "Python (lucro_cesante)"
pip list | findstr /i "scikit-learn pandas numpy flask joblib"
```
✅ Aprobado si: scikit-learn **1.8.0**, pandas **3.0.2**, numpy **2.4.4**, Flask **3.1.3**, joblib **1.5.3**.
> Si tenían scikit-learn 1.9.0, `pip install -r requirements-notebook.txt` lo baja a 1.8.0. Es lo que instalará Vercel.

## Fase 2 · Ejecutar el notebook desde cero (exigido por la consigna)
Su notebook guardado tenía un error (`No module named 'pandas'`): se ejecutó con un kernel que no era el del venv.
1. Abran `notebooks/entrenamiento.ipynb` en VS Code.
2. Arriba a la derecha: **Select Kernel → Python (lucro_cesante)** (o el intérprete `venv\Scripts\python.exe`).
3. **Restart** y luego **Run All**. Esperen a que termine sin errores y guarden (Ctrl+S).
4. Comparen con estos valores (semilla 42, deben coincidir):

| Resultado en test | Valor esperado |
|---|---|
| Regresor KNN k=15 | MAE ≈ 20.619 · RMSE ≈ 31.841 · R² ≈ 0,882 |
| Baseline regresión | MAE ≈ 71.057 |
| Clasificador directo (Árbol prof=10) | FP 24 · FN 23 · costo 139 |
| Regresión + umbral | FP 24 · FN 8 · costo 64 |

✅ Aprobado si: ninguna celda muestra error y los números coinciden. (Si su Python no es 3.12.3, solo cambia esa línea del informe: no los resultados.)

## Fase 3 · Pruebas funcionales automáticas
```powershell
python -m unittest discover -s pruebas -v
```
✅ Aprobado si: `Ran 24 tests … OK`.
Regeneren el registro de resultados (con codificación correcta):
```powershell
python -W ignore -m unittest discover -s pruebas -v *>&1 | Out-File -Encoding utf8 pruebas\resultado_pruebas.txt
```

## Fase 4 · Verificador automático del proyecto
```powershell
python verificar_proyecto.py
```
Revisa estructura de la consigna, requirements con versiones, coherencia modelos↔requirements, dataset (≥ 2000 filas, ≥ 5 predictores, regla ≥ umbral), notebook sin errores, seguridad de la app, pruebas, informe y pendientes.
✅ Aprobado si: **0 FAIL**. Los WARN 27 y 29 (campos «completar») se resuelven en la Fase 6.

## Fase 5 · Prueba manual de la aplicación local
```powershell
python app.py        # abrir http://127.0.0.1:5001/  (detener con Ctrl+C)
```
| # | Qué probar | Resultado esperado |
|---|---|---|
| 1 | Entrar a `/` | Sin banner rojo; se ve el tablero con la tabla (MOT-001, ROD-002, CAR-003…) |
| 2 | Marcar/desmarcar tipos y provincias → **Simular Proyección** | La tabla se filtra; con +12 meses cambian «Inactividad Proyectada» y los montos |
| 3 | Caso: Excavadora · Córdoba · 36 · 2015 · Requiere_Reparacion | Pérdida ≈ **$84.583,83**; NORMAL en ambos; coinciden; «cerca del umbral» |
| 4 | Caso: Topadora · Salta · 40 · 2018 · Averia_Grave | Pérdida ≈ **$189.322,58**; CRÍTICO en ambos; coinciden |
| 5 | Caso: Rodillo compactador · Buenos Aires · 5 · 2002 · Funcional | Pérdida ≈ **$13.954,23**; NORMAL en ambos |
| 6 | Meses = 999, o año = 2015,5, o campo vacío | Mensaje de error en rojo, sin traza técnica; la tabla sigue visible |
| 7 | `http://127.0.0.1:5001/salud` | `{"estado": "ok", …}` |
| 8 | Leer la pantalla | Aviso de datos simulados y bloque «Limitaciones» visibles |

✅ Aprobado si: las 8 filas se cumplen. Si ven un aviso amarillo de versión, vuelvan a la Fase 1.

## Fase 6 · Coherencia documental (lo que pide el profesor)
Completen lo que solo el grupo sabe y revisen que todo cuente lo mismo:
- [ ] `README.md`: URL del repositorio y de Vercel.
- [ ] `documentacion/bitacora_decisiones.md`: fechas y responsables reales.
- [ ] `documentacion/distribucion_tareas.md`: quién hizo cada parte (nombres reales).
- [ ] `informe/informe_final.pdf` y `presentacion/presentacion_final.pptx`: curso, fechas, URLs. *(Pásenme los datos y los regenero; el PDF no se edita a mano.)*
- [ ] Los números del informe y la presentación coinciden con la Fase 2.
- [ ] **Cada integrante** puede explicar: datos, validación, métricas, modelos, errores, aplicación y despliegue.

Vuelvan a correr `python verificar_proyecto.py`: **sin WARN 27 ni 29**.

## Fase 7 · Git y GitHub
```powershell
git init
git status                         # NO debe aparecer venv/ ni __pycache__/
git add .
git commit -m "Entrega final: notebook, modelos, app, informe y presentación"
git branch -M main
git remote add origin https://github.com/<usuario>/<repositorio>.git
git push -u origin main
```
- En GitHub: **Settings → Collaborators** → agreguen al docente.
- Etiquetas pedidas por la consigna (`entrega-1-propuesta`, `entrega-2-datos`, `entrega-3-regresion`, `entrega-4-clasificacion`, `entrega-5-final`): pónganlas **sobre el commit que realmente contiene cada entrega**. Si no hay commits de esas etapas, no los inventen: tagueen lo que exista y consulten al docente.
```powershell
git tag entrega-5-final
git push origin --tags
```
✅ Aprobado si: en GitHub se ven `app.py`, `modelos/`, `templates/`, `public/`, `notebooks/`, `datos/`, `informe/` y **no** se ve `venv/`.

## Fase 8 · Despliegue en Vercel
1. vercel.com → **Add New → Project** → importar el repositorio. Framework: detecta Flask (o «Other»).
2. Esperar el build y leer el log (errores de dependencias o tamaño aparecen ahí).
3. Abrir la URL `https://<proyecto>.vercel.app/`, luego `/salud` (debe decir `ok`).
4. Repetir los casos 3, 4 y 5 de la Fase 5 **desde el celular** (otra red/dispositivo).
5. Si el build falla por tamaño (> 250 MB) o por una dependencia: avísenme con el log y lo ajusto.

✅ Aprobado si: tablero visible, predicciones iguales a la Fase 5 y `/salud` en `ok`.

## Fase 9 · Cierre
1. Copien la URL de Vercel a `README.md`, informe y presentación (regenerados) → `git commit` → `git push`.
2. Muevan/creen la etiqueta final: `git tag -f entrega-5-final` y `git push -f origin entrega-5-final`.
3. Drive (según indique el docente): número y nombre del grupo, integrantes, informe PDF, presentación, enlace al repositorio, **etiqueta/commit** y enlace a Vercel.

---
## Correspondencia con las causas de devolución (consigna 8.1)
| Causa de devolución | Cómo se previene | Dónde se comprueba |
|---|---|---|
| No se puede ejecutar el notebook | Fase 2 con kernel del venv | `verificar_proyecto.py` #16–19 |
| Se usa el test para elegir el modelo | Selección por validación; test al final | Notebook (secciones 7–9) e informe §4 |
| Fuga de información | Objetivos e id fuera de las entradas | #13 |
| No se compara contra baselines | DummyRegressor / DummyClassifier | #18, informe §5 |
| Métricas sin interpretación | Texto por tabla; 8 respuestas | Informe §9, notebook |
| La app no usa los modelos presentados | Carga los `.joblib` y verifica versión | Pruebas 12 y 24, #6, #14 |
| Faltan integrantes en la defensa | Fase 6 | — |
| Se reproduce una solución externa | Análisis propio documentado | Bitácora |
