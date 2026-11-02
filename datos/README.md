# Datos (SIMULADOS)

## Fuente y origen
No existe una fuente externa: el dataset lo **genera el grupo** con el código de la sección 2 de `notebooks/entrenamiento.ipynb` (semilla 42). Los valores de referencia de cada tipo de equipo, los factores de estado y provincia, la depreciación y la tasa mensual son **supuestos didácticos** (no valores de mercado verificados). Para reproducirlo basta con ejecutar el notebook.

Generados por `notebooks/entrenamiento.ipynb` con semilla 42. No provienen de registros reales; no contienen datos personales.

## Archivos
| Archivo | Contenido |
|---|---|
| `dataset_maquinaria_crudo.csv` | 2.520 filas. Incluye 51 faltantes en `meses_inactividad`, 10 valores imposibles (-3 y 999) y 20 duplicados exactos, agregados a propósito para practicar la limpieza |
| `dataset_maquinaria_preparado.csv` | 2.440 filas, sin nulos, sin duplicados, dentro de rango |

## Qué representa cada fila
Un equipo de maquinaria vial inspeccionado al ingresar a custodia.

## Diccionario de variables
| Variable | Tipo | Rol | Descripción / rango |
|---|---|---|---|
| `id_registro` | texto | Identificador (descartada) | EQ-0001 … sin valor predictivo |
| `tipo_equipo` | categórica | Predictor | Motoniveladora, Excavadora, Retroexcavadora, Cargadora frontal, Rodillo compactador, Topadora |
| `provincia` | categórica | Predictor | Buenos Aires, Córdoba, Santa Fe, Mendoza, Salta |
| `meses_inactividad` | numérica | Predictor | Meses de inactividad al momento de la consulta, 1 a 120 |
| `anio_fabricacion` | entera | Predictor | 2000 a 2026 |
| `estado_motor` | categórica | Predictor | Funcional, Requiere_Reparacion, Averia_Grave (resultado de la inspección inicial) |
| `perdida_economica_usd` | numérica | Objetivo de regresión | Pérdida económica simulada en USD (≥ 0) |
| `perdida_critica` | binaria | Objetivo de clasificación | 1 si `perdida_economica_usd >= 100000`, si no 0 |

## Fórmula de simulación (supuestos didácticos)
```
antiguedad   = 2026 - anio_fabricacion
valor_actual = valor_ref[tipo] * 0.96 ** antiguedad
perdida      = valor_actual * 0.012 * meses * mult_estado * mult_provincia * Lognormal(0, 0.10) + Normal(0, 5000)   (mínimo 0)
```
`valor_ref` (USD): Motoniveladora 250.000 · Excavadora 220.000 · Retroexcavadora 150.000 · Cargadora frontal 180.000 ·
Rodillo compactador 120.000 · Topadora 300.000. `mult_estado`: 1,00 / 1,25 / 1,50. `mult_provincia`: BA 1,00 · Cba 0,95 ·
SF 0,95 · Mza 1,05 · Salta 1,10. Todos son **supuestos**, no valores de mercado verificados.

## Variables descartadas
`id_registro` (identificador sin valor predictivo) y los dos objetivos (`perdida_economica_usd`, `perdida_critica`), que no pueden ser predictores porque serían fuga de información.

## Limpieza (resumen)
Se eliminan 20 duplicados, 10 filas con `meses_inactividad` imposible y 50 con faltante (decisión: no imputar, para no
inventar la variable más importante ni filtrar información de test). El detalle se imprime en el notebook (sección 3).

## Limitaciones
Las relaciones entre variables son las de la fórmula: no se pueden interpretar como relaciones reales.
