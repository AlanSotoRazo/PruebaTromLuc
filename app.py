from flask import Flask, render_template, request, redirect, session, url_for, jsonify, flash, send_file
import mysql.connector
import cv2
import numpy as np
import face_recognition
import base64
import json
import os
from datetime import datetime, date
from pathlib import Path
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'


db_config = {
    "host": "crossover.proxy.rlwy.net",
    "user": "root",
    "password": "ctXmVXKaEgqbrgJcPgxmZFOnjSpAIOSs",
    "database": "railway",
    "port": 47507
}


def get_db_connection():
    conn = mysql.connector.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        port=db_config["port"]
    )
    conn.set_charset_collation('utf8mb4')
    return conn


# Crear carpetas si no existen
Path("fotos/entrada").mkdir(parents=True, exist_ok=True)
Path("fotos/salida").mkdir(parents=True, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == 'admin1':
            return redirect(url_for('registro'))
        elif password == 'admin2':
            return redirect(url_for('asistencia_html'))
        else:
            return render_template('index.html', error="❌ Contraseña incorrecta.")
    return render_template('index.html')


# ---------------- REGISTRO Y  ----------------
@app.route('/registro')
def registro():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_tipo, tipo_usuario FROM tipo_usuario")
    tipos = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('registro.html', tipos=tipos)


# ---------------- REGISTRAR PERSONA  ----------------
@app.route('/registrar', methods=['POST'])
def registrar():
    nombre = request.form['nombre']
    apellido_paterno = request.form['apellido_paterno']
    apellido_materno = request.form['apellido_materno']
    id_tipo = request.form['tipo_usuario']
    foto_base64 = request.form['foto']

    if ',' in foto_base64:
        foto_base64 = foto_base64.split(',')[1]
    imagen_bytes = base64.b64decode(foto_base64)
    nparr = np.frombuffer(imagen_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    rostros = face_recognition.face_encodings(rgb_img)
    if len(rostros) == 0:
        flash("❌ No se detectó rostro.", "error")
        return redirect(url_for('registro'))

    vector_rostro = json.dumps(rostros[0].tolist())

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
         INSERT INTO emp_activos (vectores_rostro, nombre, apellido_pa, apellido_ma, id_tipo)
         VALUES (%s, %s, %s, %s, %s)
         ''', (vector_rostro, nombre, apellido_paterno, apellido_materno, id_tipo))
        conn.commit()
        cursor.close()
        conn.close()
        flash("✅ Usuario registrado correctamente", "success")
    except Exception as e:
        flash(f"❌ Error al guardar: {e}", "error")

    return redirect(url_for('registro'))

@app.route('/asistencia')
def asistencia_html():
    return render_template('asistencia.html')

# ---------------- ASISTENCIA  Y PARA EDITAR LATITUD LONGITUD----------------
@app.route('/registrar_asistencia', methods=['POST'])
def registrar_asistencia():
    try:
        data = request.get_json()
        foto_base64 = data['foto']
        latitud = data.get('latitud')
        longitud = data.get('longitud')

        if ',' in foto_base64:
            foto_base64 = foto_base64.split(',')[1]
        imagen_bytes = base64.b64decode(foto_base64)
        nparr = np.frombuffer(imagen_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rostros = face_recognition.face_encodings(rgb)

        if len(rostros) == 0:
            return jsonify({'status': 'fail', 'message': '❌ No se detectó rostro'})

        vector_nuevo = rostros[0]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_emp, vectores_rostro, nombre, apellido_pa FROM emp_activos")
        usuarios = cursor.fetchall()

        matches = []
        for codigo, vector_json, nombre, apellido in usuarios:
            vector_bd = np.array(json.loads(vector_json))
            distancia = face_recognition.face_distance([vector_bd], vector_nuevo)[0]
            if distancia < 0.5:
                matches.append((codigo, nombre, apellido, distancia))

        if not matches:
            cursor.close()
            conn.close()
            return jsonify({'status': 'fail', 'message': '❌ Rostro no reconocido'})

        matches.sort(key=lambda x: x[3])
        codigo_emp, nombre, apellido, _ = matches[0]
        hoy = date.today()
        hora_actual = datetime.now().time()

        cursor.execute("SELECT id_asistencia FROM asistencia WHERE fecha = %s AND codigo_emp = %s", (hoy, codigo_emp))
        registro = cursor.fetchone()

        nombre_archivo = f"{nombre}_{apellido}_{hoy.strftime('%Y%m%d')}.jpg"

        # ---------------- AQUI SE PONEN CONVERTIDAS LA LATITUD Y LONGITUD DE MAZDA y editas el mensaje----------------
        lat_min = 20.6123
        lat_max = 20.6133
        lon_min = -101.2385
        lon_max = -101.2375

        ubicacion = "Ubicación fuera de la zona de trabajo"
        if lat_min <= float(latitud) <= lat_max and lon_min <= float(longitud) <= lon_max:
            ubicacion = "Ubicación en Mazda"

        if registro:
            carpeta = "fotos/salida"
            ruta = os.path.join(carpeta, nombre_archivo)
            cv2.imwrite(ruta, img)

            cursor.execute("UPDATE asistencia SET hora_salida = %s, ubicacion = %s WHERE id_asistencia = %s", (hora_actual, ubicacion, registro[0]))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'ok', 'message': f'🕒 Salida registrada de {nombre}'})
        else:
            carpeta = "fotos/entrada"
            ruta = os.path.join(carpeta, nombre_archivo)
            cv2.imwrite(ruta, img)

            cursor.execute("""
                INSERT INTO asistencia (codigo_emp, vector, fecha, hora_entrada, latitud, longitud, ubicacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (codigo_emp, json.dumps(vector_nuevo.tolist()), hoy, hora_actual, latitud, longitud, ubicacion))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'status': 'ok', 'message': f'🕐 Entrada registrada de {nombre}'})

    except Exception as e:
        return jsonify({'status': 'fail', 'message': f'❌ Error: {str(e)}'})



# ---------------- REGISTROS CON FILTRO 7-8-2025----------------
@app.route('/registros')
def mostrar_registros():
    fecha = request.args.get('fecha')

    conn = get_db_connection()
    cursor = conn.cursor()

    if fecha:
        cursor.execute("""
            SELECT e.codigo_emp, e.nombre, e.apellido_pa, e.apellido_ma, 
                   a.ubicacion, a.vector, a.fecha, a.hora_entrada, a.hora_salida
            FROM asistencia a
            JOIN emp_activos e ON a.codigo_emp = e.codigo_emp
            WHERE a.fecha = %s
            ORDER BY a.fecha DESC, a.hora_entrada ASC
        """, (fecha,))
    else:
        cursor.execute("""
            SELECT e.codigo_emp, e.nombre, e.apellido_pa, e.apellido_ma, 
                   a.ubicacion, a.vector, a.fecha, a.hora_entrada, a.hora_salida
            FROM asistencia a
            JOIN emp_activos e ON a.codigo_emp = e.codigo_emp
            ORDER BY a.fecha DESC, a.hora_entrada ASC
        """)

    registros = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('registros.html', registros=registros)

# ---------------- REGRESAR / DESCARGAR ----------------
@app.route('/regresar')
def regresar_registros():
    return render_template('registro.html')


# ---------------- PARTE DE EXCEL, SE DEBE MODIFICAR PARA LOS FILTROS ----------------
@app.route('/descargar_excel')
def descargar_excel():
    try:
        fecha = request.args.get('fecha')  # Obtener la fecha del filtro

        # Crear conexión
        conn = get_db_connection()
        cursor = conn.cursor()

        # Consulta base
        query = '''
            SELECT 
                e.codigo_emp, 
                e.nombre, 
                e.apellido_pa, 
                e.apellido_ma, 
                a.ubicacion, 
                a.fecha, 
                a.hora_entrada, 
                a.hora_salida
            FROM emp_activos e
            JOIN asistencia a ON e.codigo_emp = a.codigo_emp
        '''
        params = ()

        # Si hay filtro de fecha, agregar condición
        if fecha:
            query += " WHERE a.fecha = %s"
            params = (fecha,)

        cursor.execute(query, params)
        registros = cursor.fetchall()

        # Cerrar conexión temporalmente
        cursor.close()
        conn.close()

        # Crear DataFrame
        columnas = [
            'Código Empleado',
            'Nombre',
            'Apellido Paterno',
            'Apellido Materno',
            'Ubicación',
            'Fecha',
            'Hora Entrada',
            'Hora Salida'
        ]
        df = pd.DataFrame(registros, columns=columnas)

        def format_timedelta(td):
            if pd.isnull(td):
                return ''
            total_seconds = int(td.total_seconds())
            horas = total_seconds // 3600
            minutos = (total_seconds % 3600) // 60
            segundos = total_seconds % 60
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"

        df['Hora Entrada'] = df['Hora Entrada'].apply(format_timedelta)
        df['Hora Salida'] = df['Hora Salida'].apply(format_timedelta)

        # Generar Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Asistencia')
        output.seek(0)

        return send_file(
            output,
            download_name='registros_asistencia.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        return f"❌ Error al generar Excel: {str(e)}"



    # ---------------- CERRAR SESIÓN DE TODOS LADOS  ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    pass  # o simplemente comenta toda esta sección
    # app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))





