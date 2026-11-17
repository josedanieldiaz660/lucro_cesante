from flask import Flask, render_template, request
import pandas as pd
import joblib
import os

app = Flask(__name__)

def cargar_modelos():
    path_reg = 'modelos/modelo_regresion_perdidas.joblib' if os.path.exists('modelos/modelo_regresion_perdidas.joblib') else 'modelo_regresion_perdidas.joblib'
    path_clf = 'modelos/modelo_clasificacion_perdidas.joblib' if os.path.exists('modelos/modelo_clasificacion_perdidas.joblib') else 'modelo_clasificacion_perdidas.joblib'
    
    try:
        reg = joblib.load(path_reg)
        clf = joblib.load(path_clf)
        return reg, clf, None
    except Exception as e:
        return None, None, f"Error al cargar los modelos serializados: {e}"

UMBRAL_CRITICO = 100000
HORAS_MENSUALES = 200

# Tarifas horarias de referencia para comparativa de costos
COSTO_OPERACION_HORA = {
    'Motoniveladora': 30,
    'Excavadora': 30,
    'Cargadora frontal': 25,
    'Rodillo compactador': 17,
    'Topadora': 52
}

COSTO_ALQUILER_HORA = {
    'Motoniveladora': 90,
    'Excavadora': 90,
    'Cargadora frontal': 55,
    'Rodillo compactador': 47,
    'Topadora': 140
}

COSTO_MANUAL_HORA = {
    'Motoniveladora': 1000,
    'Excavadora': 500,
    'Cargadora frontal': 500,
    'Rodillo compactador': 250,
    'Topadora': 1000
}

RENDIMIENTO_EQUIPO = {
    'Motoniveladora': {'rendimiento': '2.000 m²/h (Nivelación)', 'personas': '200 personas'},
    'Excavadora': {'rendimiento': '150 m³/h (Zanjeo/Remoción)', 'personas': '100 personas'},
    'Cargadora frontal': {'rendimiento': '200 m³/h (Carga de material)', 'personas': '100 personas'},
    'Rodillo compactador': {'rendimiento': '1.000 m²/h (Compactación)', 'personas': '50 personas (con pisón)'},
    'Topadora': {'rendimiento': '300 m³/h (Empuje/Desmonte)', 'personas': '200 personas'}
}

TIPOS_PERMITIDOS = ['Motoniveladora', 'Excavadora', 'Cargadora frontal', 'Rodillo compactador', 'Topadora']
PROVINCIAS_PERMITIDAS = ['Buenos Aires', 'Córdoba', 'Santa Fe', 'Mendoza', 'Salta']
ESTADOS_MOTOR_PERMITIDOS = ['Funcional', 'Requiere_Reparacion', 'Averia_Grave']

@app.route('/', methods=['GET', 'POST'])
def index():
    modelo_regresion, modelo_clasificacion, error_carga = cargar_modelos()

    # Valores seleccionados por defecto para el formulario
    form_state = {
        'modo_seleccion': 'individual',
        'tipo_individual': 'Excavadora',
        'provincia_individual': 'Buenos Aires',
        'tipos_equipo': ['Excavadora'],
        'provincias': ['Buenos Aires'],
        'meses': 36,
        'anio_fabricacion': 2015,
        'estado_motor': 'Requiere_Reparacion'
    }

    if request.method == 'POST':
        modo_seleccion = request.form.get('modo_seleccion', 'individual')
        form_state['modo_seleccion'] = modo_seleccion
        form_state['tipo_individual'] = request.form.get('tipo_individual', 'Excavadora')
        form_state['provincia_individual'] = request.form.get('provincia_individual', 'Buenos Aires')

        if error_carga:
            return render_template('index.html', resultados=None, error=error_carga, form_state=form_state)

        try:
            # 1. Recuperación según modo (Individual o Lote Múltiple) y Validación ESTRICTA (Auditoría: Punto 4)
            if modo_seleccion == 'multiple':
                tipos_equipo_raw = request.form.getlist('tipo_equipo')
                provincias_raw = request.form.getlist('provincia')
            else:
                ti = request.form.get('tipo_individual')
                pi = request.form.get('provincia_individual')
                tipos_equipo_raw = [ti] if ti else []
                provincias_raw = [pi] if pi else []

            form_state['tipos_equipo'] = tipos_equipo_raw
            form_state['provincias'] = provincias_raw
            
            if not tipos_equipo_raw or not provincias_raw:
                return render_template('index.html', resultados=None, error="Error: Debe seleccionar al menos un tipo de equipo y una provincia.", form_state=form_state)

            tipos_equipo = [t for t in tipos_equipo_raw if t in TIPOS_PERMITIDOS]
            if len(tipos_equipo) != len(tipos_equipo_raw):
                return render_template('index.html', resultados=None, error="Error: Se ha enviado un tipo de equipo no válido.", form_state=form_state)

            provincias = [p for p in provincias_raw if p in PROVINCIAS_PERMITIDAS]
            if len(provincias) != len(provincias_raw):
                return render_template('index.html', resultados=None, error="Error: Se ha enviado una provincia no válida.", form_state=form_state)

            # Validación de Meses de Inactividad (1 a 60 meses)
            try:
                meses_inactividad = int(request.form.get('meses', -1))
                form_state['meses'] = meses_inactividad
                if meses_inactividad < 1 or meses_inactividad > 60:
                    return render_template('index.html', resultados=None, error="Error: Los meses de inactividad deben estar entre 1 y 60.", form_state=form_state)
            except ValueError:
                return render_template('index.html', resultados=None, error="Error: Los meses de inactividad deben ser un valor numérico entero.", form_state=form_state)

            # Validación de Año de Fabricación (1990 a 2024)
            try:
                anio_fab = int(request.form.get('anio_fabricacion', -1))
                form_state['anio_fabricacion'] = anio_fab
                if anio_fab < 1990 or anio_fab > 2024:
                    return render_template('index.html', resultados=None, error="Error: El año de fabricación debe estar entre 1990 y 2024.", form_state=form_state)
            except ValueError:
                return render_template('index.html', resultados=None, error="Error: El año de fabricación debe ser un valor numérico entero.", form_state=form_state)

            # Validación de Estado del Motor
            estado_mot = request.form.get('estado_motor')
            form_state['estado_motor'] = estado_mot
            if estado_mot not in ESTADOS_MOTOR_PERMITIDOS:
                return render_template('index.html', resultados=None, error="Error: Debe seleccionar un estado del motor válido.", form_state=form_state)

            # 2. Construcción del lote/inventario a evaluar sin generación aleatoria
            inventario = []
            contador_id = 1
            for prov in provincias:
                for tipo in tipos_equipo:
                    codigo = f"{tipo[:3].upper()}-{prov[:3].upper()}-{contador_id:03d}"
                    inventario.append({
                        'id': codigo,
                        'tipo_equipo': tipo,
                        'provincia': prov,
                        'meses_inactividad': meses_inactividad,
                        'anio_fabricacion': anio_fab,
                        'estado_motor': estado_mot
                    })
                    contador_id += 1

            df_input = pd.DataFrame(inventario)

            # 3. Predicciones con los modelos de IA
            columnas_predictores = ['tipo_equipo', 'provincia', 'meses_inactividad', 'anio_fabricacion', 'estado_motor']
            predicciones_reg = modelo_regresion.predict(df_input[columnas_predictores])
            predicciones_clf = modelo_clasificacion.predict(df_input[columnas_predictores])

            detalle_filas = []
            total_estimado_ia = 0.0
            total_propio = 0.0
            total_alquiler = 0.0
            total_manual = 0.0
            total_horas = 0
            alertas_criticas = 0
            alertas_reg_criticas = 0
            alertas_clf_criticas = 0

            # 4. Procesamiento por equipo y comparación de alertas
            for i, row in df_input.iterrows():
                perdida_ia = float(predicciones_reg[i])
                es_critico_clf = int(predicciones_clf[i])
                es_critico_reg = 1 if perdida_ia >= UMBRAL_CRITICO else 0

                # Cálculo de comparativa financiera de costo de oportunidad
                horas = int(row['meses_inactividad'] * HORAS_MENSUALES)
                jornadas = int(horas / 8)
                costo_propio = float(horas * COSTO_OPERACION_HORA.get(row['tipo_equipo'], 0))
                costo_alq = float(horas * COSTO_ALQUILER_HORA.get(row['tipo_equipo'], 0))
                costo_man = float(horas * COSTO_MANUAL_HORA.get(row['tipo_equipo'], 0))
                info_eq = RENDIMIENTO_EQUIPO.get(row['tipo_equipo'], {'rendimiento': 'N/A', 'personas': 'N/A'})

                total_estimado_ia += perdida_ia
                total_propio += costo_propio
                total_alquiler += costo_alq
                total_manual += costo_man
                total_horas += horas

                if es_critico_clf == 1:
                    alertas_clf_criticas += 1
                if es_critico_reg == 1:
                    alertas_reg_criticas += 1

                critico_final = (es_critico_clf == 1 or es_critico_reg == 1)
                if critico_final:
                    alertas_criticas += 1

                if es_critico_clf == es_critico_reg:
                    coincidencia_texto = "Coinciden"
                elif es_critico_clf == 1 and es_critico_reg == 0:
                    coincidencia_texto = "Desacuerdo (Alerta: Clasificador)"
                else:
                    coincidencia_texto = "Desacuerdo (Alerta: Umbral)"

                detalle_filas.append({
                    'id': row['id'],
                    'tipo': row['tipo_equipo'],
                    'provincia': row['provincia'],
                    'anio_fabricacion': int(row['anio_fabricacion']),
                    'estado_motor': row['estado_motor'].replace('_', ' '),
                    'estado_motor_raw': row['estado_motor'],
                    'meses_inactividad': int(row['meses_inactividad']),
                    'horas': horas,
                    'jornadas': jornadas,
                    'rendimiento': info_eq['rendimiento'],
                    'personas': info_eq['personas'],
                    'costo_propio': costo_propio,
                    'costo_alquiler': costo_alq,
                    'costo_manual': costo_man,
                    'perdida_ia': perdida_ia,
                    'critico': critico_final,
                    'alerta_clf': "CRÍTICA" if es_critico_clf == 1 else "Normal",
                    'alerta_reg': "CRÍTICA" if es_critico_reg == 1 else "Normal",
                    'coincidencia': coincidencia_texto
                })

            resultados = {
                'filas': detalle_filas,
                'equipos_seleccionados': tipos_equipo,
                'provincias_seleccionadas': provincias,
                'meses_inactividad': meses_inactividad,
                'anio_fabricacion': anio_fab,
                'estado_motor_texto': estado_mot.replace('_', ' '),
                'total_estimado_ia': total_estimado_ia,
                'total_propio': total_propio,
                'total_alquiler': total_alquiler,
                'total_manual': total_manual,
                'total_horas': total_horas,
                'total_jornadas': int(total_horas / 8),
                'umbral_critico': UMBRAL_CRITICO,
                'umbral_lote': UMBRAL_CRITICO * len(detalle_filas),
                'cantidad': len(detalle_filas),
                'alertas_criticas': alertas_criticas,
                'alerta_clf_resumen': f"{alertas_clf_criticas} de {len(detalle_filas)} Críticos",
                'alerta_reg_resumen': f"{alertas_reg_criticas} de {len(detalle_filas)} Críticos",
                'nivel_alerta': 'CRÍTICO' if alertas_criticas > 0 else 'MODERADO',
                'color_alerta': '#ef4444' if alertas_criticas > 0 else '#f59e0b',
                'advertencia_metodologica': "Las predicciones y costos horarios comparativos son estimaciones basadas en supuestos fijos de mercado y peritaje documentados en el proyecto original. Funcionan como apoyo analítico y no reemplazan la pericia mecánica formal ni las decisiones de la autoridad judicial competente."
            }

            return render_template('index.html', resultados=resultados, error=None, form_state=form_state)

        except Exception as e:
            return render_template('index.html', resultados=None, error=f"Error técnico durante el procesamiento: {str(e)}", form_state=form_state)

    return render_template('index.html', resultados=None, error=error_carga, form_state=form_state)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
