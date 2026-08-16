from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory
from crud import set_acepta_dolares, get_acepta_dolares, obtener_datos_historial, obtener_comprador_por_cedula2, obtener_comprador_por_cedula3, get_enunciado2, get_enunciado3, get_porcentaje2, get_porcentaje3, get_premio2, get_premio3, obtener_comprador_por_cedula, get_tickets, get_porcentaje, tickets_disponibles,reintegrar_tickets,get_data, get_data2, actualizar_partida,obtener_datos_partida, get_enunciado, get_premio, insertar_comprador, get_estatus, get_precio, vendidos, get_minima, get_dolar, get_zelle
import os
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
from datetime import datetime
import random
import string
import time
import json
import shutil
from pathlib import Path
from config import (
    RIFA_DB_PATH,
    RIFA2_DB_PATH,
    RIFA3_DB_PATH,
    UPLOAD_DIR,
    IMG_DIR,
)



def generar_sufijo_aleatorio(length=6):
    # Genera un sufijo aleatorio de letras y números
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choices(caracteres, k=length))

# Decorador para proteger las rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):  # Verifica si el usuario está autenticado
            return redirect(url_for('admin_index'))  # Redirige al login si no está autenticado
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
UPLOAD_FOLDER = UPLOAD_DIR
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'supersecretkey'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/comprobantes/<path:filename>")
def serve_comprobante(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/img/<path:filename>")
def serve_img(filename):
    return send_from_directory(IMG_DIR, filename)


# ---------------------------------------------------------------------------
# CLI de desarrollo: insertar compras manuales con tickets definidos por el
# usuario, sin pasar por el proceso normal de compra.
# ---------------------------------------------------------------------------

def _parse_tickets_input(tickets_text):
    """Parsea una cadena tipo '1,2,3' o '1 2 3' a lista de enteros únicos."""
    if not tickets_text or not str(tickets_text).strip():
        raise ValueError("Debes indicar al menos un ticket.")

    raw = str(tickets_text).replace(';', ',').replace('|', ',').replace(' ', ',')
    values = [x.strip() for x in raw.split(',') if x.strip()]
    tickets = []
    for value in values:
        if not value.isdigit():
            raise ValueError(f"Ticket no numérico: {value}")
        ticket = int(value)
        if ticket < 0:
            raise ValueError(f"Ticket inválido: {ticket}")
        tickets.append(ticket)

    # Mantener orden y eliminar duplicados
    tickets_unicos = list(dict.fromkeys(tickets))
    return tickets_unicos


def _tickets_faltantes(tickets):
    """Devuelve tickets que NO están disponibles en rifa.db."""
    if not tickets:
        return []

    placeholders = ','.join(['?'] * len(tickets))
    with sqlite3.connect(RIFA_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT carton_disponible FROM tickets_disponibles WHERE carton_disponible IN ({placeholders})",
            tickets,
        )
        disponibles = {row[0] for row in cursor.fetchall()}

    return [ticket for ticket in tickets if ticket not in disponibles]


def _reservar_tickets_dev(tickets):
    """Reserva (elimina de disponibles) los tickets indicados dentro de una transacción."""
    if not tickets:
        raise ValueError("Debes enviar al menos un ticket.")

    placeholders = ','.join(['?'] * len(tickets))
    with sqlite3.connect(RIFA_DB_PATH) as conn:
        cursor = conn.cursor()
        conn.execute("BEGIN TRANSACTION;")
        cursor.execute(
            f"SELECT carton_disponible FROM tickets_disponibles WHERE carton_disponible IN ({placeholders})",
            tickets,
        )
        disponibles = [row[0] for row in cursor.fetchall()]
        if len(disponibles) != len(tickets):
            conn.execute("ROLLBACK;")
            faltantes = [ticket for ticket in tickets if ticket not in disponibles]
            raise ValueError(f"Estos tickets ya no están disponibles: {faltantes}")

        cursor.execute(
            f"DELETE FROM tickets_disponibles WHERE carton_disponible IN ({placeholders});",
            tickets,
        )
        conn.commit()


def insertar_compra_dev(
    nombre,
    cedula,
    telefono,
    tickets,
    monto=None,
    referencia="dev_manual",
    referencia_ruta="/comprobantes/dev_manual.jpg",
):
    """Inserta una compra directa para desarrollo, con tickets definidos manualmente.
    No requiere 'digitos'. El campo 'estatus' queda en NULL (como una compra normal).
    """
    if not tickets:
        raise ValueError("Debes enviar al menos un ticket.")

    _reservar_tickets_dev(tickets)

    link = f"/{cedula}"
    fecha = get_enunciado()

    if monto is None:
        precio = get_precio()
        try:
            monto = f"{float(precio) * len(tickets)}bs"
        except Exception:
            monto = "0bs"

    with sqlite3.connect(RIFA_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO requeridos (
                nombre_apellidos, cedula, telefono, referencia,
                tickets_vendidos, monto, fecha, link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                nombre,
                cedula,
                telefono,
                referencia,
                json.dumps(tickets),
                monto,
                fecha,
                link,
            ),
        )
        conn.commit()

    comprador = obtener_comprador_por_cedula(cedula)
    return bool(comprador)


def run_dev_cli():
    import argparse

    parser = argparse.ArgumentParser(description="Herramientas de desarrollo para rifas")
    subparsers = parser.add_subparsers(dest="command")

    insert_parser = subparsers.add_parser(
        "dev_insert",
        help="Inserta una compra directa en DB con tickets definidos manualmente",
    )
    insert_parser.add_argument("--nombre", required=True, help="Nombre y apellido")
    insert_parser.add_argument("--cedula", required=True, help="Cédula")
    insert_parser.add_argument("--telefono", required=True, help="Teléfono completo")
    insert_parser.add_argument(
        "--tickets",
        required=True,
        help="Lista manual de tickets, ej: 15,88,902 o '15 88 902'",
    )
    insert_parser.add_argument(
        "--monto",
        required=False,
        help="Monto textual a guardar, ej: 150bs o 150bs/2.5$ (opcional)",
    )
    insert_parser.add_argument(
        "--referencia",
        default="dev_manual",
        help="Nombre de referencia de comprobante",
    )
    insert_parser.add_argument(
        "--referencia-ruta",
        default="/comprobantes/dev_manual.jpg",
        help="Ruta pública de comprobante",
    )

    args = parser.parse_args()

    if args.command != "dev_insert":
        return False

    tickets = _parse_tickets_input(args.tickets)
    ok = insertar_compra_dev(
        nombre=args.nombre,
        cedula=args.cedula,
        telefono=args.telefono,
        tickets=tickets,
        monto=args.monto,
        referencia=args.referencia,
        referencia_ruta=args.referencia_ruta,
    )

    if ok:
        print(f"OK: compra insertada con tickets {tickets}")
    else:
        print(
            "WARN: no se encontró registro tras insertar. "
            "Verifica si los tickets ya estaban ocupados."
        )
    return True

# ---------------------------------------------------------------------------
# Fin de la sección CLI de desarrollo
# ---------------------------------------------------------------------------

@app.route('/', methods=["GET"])
def index():
    flags = obtener_datos_historial()  # solo lee en GET
    return render_template(
        'index.html', solicitudes = get_data2(),
        enunciado=get_enunciado(), enunciado2=get_enunciado2(), enunciado3=get_enunciado3(),
        premio=get_premio(), premio2=get_premio2(), premio3=get_premio3(),
        porcentaje=get_porcentaje(True), porcentaje2=get_porcentaje2(True), porcentaje3=get_porcentaje3(True),
        disponibilidad=get_porcentaje(False), disponibilidad2=get_porcentaje2(False), disponibilidad3=get_porcentaje3(False),
        mostrar_rifa2=bool(flags['mostrar_rifa2']),
        mostrar_rifa3=bool(flags['mostrar_rifa3'])
    )

@app.route("/toggle-acepta-dolares", methods=["POST"])
def toggle_acepta_dolares():
    # si está marcado vendrá "on"; si se apaga, no viene el campo
    set_acepta_dolares(request.form.get("acepta_dolares") == "on")
    # <!-- opcional: vuelve a la misma página -->
    next_url = request.form.get("next") or request.referrer or url_for("admin_partida")
    return redirect(next_url)

@app.route("/compra", methods=["POST", "GET"])
def pago():
    estatus = get_estatus()
    if estatus == "Venta finalizada":
        return redirect(url_for('index'))  # redirigir a un panel de administración
    # Si no es POST, solo se muestran los datos vacíos
    return render_template("comprar.html", cant_min=get_minima(),
                            precio=int(get_precio()),
                            zelle=get_zelle(), precio_dolares=get_dolar(),
                            porcentaje=get_porcentaje(True), disponibilidad = get_porcentaje(False),
    acepta_dolares=get_acepta_dolares())

@app.route("/verify", methods=["POST", "GET"])
def verificar():
    return render_template("verificar.html")

@app.route("/verify2", methods=["POST", "GET"])
def verificar2():
    return render_template("verificar2.html")

@app.route("/verify3", methods=["POST", "GET"])
def verificar3():
    return render_template("verificar3.html")


@app.route("/registrar_compra", methods=["POST", "GET"])
def registrar():
    if request.method == "POST":

        # Recuperar los datos del formulario
        nombre = request.form["nombre"]
        cedula = request.form["cedula"]
        nmr_te = request.form["telefono"]
        nmr_r = request.files["referencia"]
        if not nmr_te or nmr_te.strip() == "":
            return jsonify({"success": False, "message": "Por favor, completa el número de teléfono."}), 400

        # Validar y guardar el archivo de referencia si es necesario
        if nmr_r and allowed_file(nmr_r.filename):
            filename = secure_filename(nmr_r.filename)
            # Agregar un sufijo aleatorio al nombre del archivo
            nombre_archivo, extension = os.path.splitext(filename)
            sufijo = generar_sufijo_aleatorio()
            filename = f"{nombre_archivo}_{sufijo}{extension}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            nmr_r.save(filepath)

            referencia_ruta = os.path.join('/comprobantes', filename).replace("\\", "/")
            fecha = get_enunciado()

        # Recuperar los datos de la compra (los valores pasados en los campos ocultos)
        cant_tickets = request.form.get("quantity", "")
        if int(cant_tickets) == 0:
            return redirect(url_for('index'))
        tickets_seleccionados = get_tickets(cant_tickets)
        total_price = request.form.get("total_price", 0)
        total_price_2 = request.form.get("total_price_2", 0)


        link = f'/{cedula}'

        # Insertar los datos en la base de datos
        insertar_comprador(
            nombre, cedula, nmr_te, nmr_r.filename, tickets_seleccionados,
            f"{total_price}bs",
            fecha, referencia_ruta, link, tickets_seleccionados
        )

        return render_template('confirmacion.html')

    return redirect(url_for('index'))

@app.route("/admin/dashboard/partida/reiniciar" , methods = ["POST"])
@login_required  # Ruta protegida por login
def reiniciar():

    conn = sqlite3.connect(RIFA_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""DELETE FROM tickets_disponibles WHERE 1 = 1""")
    conn.commit()

    cursor.execute("""DELETE FROM requeridos WHERE 1 = 1""")
    conn.commit()

    cursor.executemany("""
    INSERT OR IGNORE INTO tickets_disponibles (carton_disponible) VALUES (?);
    """, [(i,) for i in range(0, 10000)])
    conn.commit()

    conn.close()

        # Eliminar todos los archivos en carpeta persistente de comprobantes
    folder_path = UPLOAD_DIR
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):  # Verificar si es un archivo
            os.remove(file_path)

    # Redirigir al panel de administración
    return redirect(url_for('admin_dashboard_partida'))


@app.route("/admin/dashboard/partida/desplazar", methods=["POST"])
@login_required
def desplazar():
    """
    Operaciones solicitadas:
    1) DBs:
       - Eliminar rifa3.db
       - Renombrar rifa2.db -> rifa3.db
       - Copiar rifa.db -> rifa2.db
       - Vaciar todas las tablas de rifa.db (mantener el esquema)
    2) Imágenes (en IMG_DIR):
       - Eliminar partida3.jpg
       - Renombrar partida2.jpg -> partida3.jpg
       - Mantener partida1.jpg (o partida.jpg si no existe la anterior) y sacar copia a partida2.jpg
    """
    # ---- Helpers ------------------------------------------------------------
    def safe_replace(src: Path, dst: Path):
        """Reemplaza dst con src (si existe), usando rename atómico cuando se pueda y move si no."""
        if not src.exists():
            return
        try:
            os.replace(src, dst)  # atómico en el mismo FS
        except OSError:
            shutil.move(str(src), str(dst))  # cross-device

    def delete_if_exists(p: Path):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            # Si no se puede borrar por locks, se ignora pero seguimos con el resto
            pass

    # Rutas de DB
    rifa = Path(RIFA_DB_PATH)
    rifa2 = Path(RIFA2_DB_PATH)
    rifa3 = Path(RIFA3_DB_PATH)

    # Rutas de imágenes
    img_dir = Path(IMG_DIR)
    partida1 = img_dir / "partida1.jpg"
    partida = img_dir / "partida.jpg"   # fallback por si el nombre fuese este
    partida2 = img_dir / "partida2.jpg"
    partida3 = img_dir / "partida3.jpg"

    # ------------------------------------------------------------------------
    # 1) ROTACIÓN DE BASES DE DATOS
    # ------------------------------------------------------------------------
    steps = {"db": [], "images": []}
    try:
        # 1.a) Eliminar rifa3.db
        delete_if_exists(rifa3)
        steps["db"].append("Eliminada rifa3.db (si existía)")

        # 1.b) Renombrar rifa2.db -> rifa3.db
        if rifa2.exists():
            safe_replace(rifa2, rifa3)
            steps["db"].append("Renombrada rifa2.db -> rifa3.db")
        else:
            steps["db"].append("No se encontró rifa2.db para renombrar")

        # 1.c) Copiar rifa.db -> rifa2.db (respaldo previo)
        if rifa.exists():
            shutil.copy2(rifa, rifa2)
            steps["db"].append("Copiada rifa.db -> rifa2.db")
        else:
            steps["db"].append("No se encontró rifa.db para copiar (no se pudo crear rifa2.db)")

        # 1.d) Vaciar tablas de rifa.db (manteniendo esquema)
        if rifa.exists():
            con = sqlite3.connect(RIFA_DB_PATH)
            try:
                con.execute("PRAGMA foreign_keys = OFF;")
                cur = con.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = [row[0] for row in cur.fetchall()]

                for t in tables:
                    cur.execute(f'DELETE FROM "{t}";')

                # Reiniciar autoincremento si existe
                try:
                    cur.execute("DELETE FROM sqlite_sequence;")
                except sqlite3.OperationalError:
                    pass  # puede no existir

                con.commit()
                # Opcional: compactar
                try:
                    con.execute("VACUUM;")
                except sqlite3.OperationalError:
                    pass

                steps["db"].append(f"Vaciadas {len(tables)} tablas en rifa.db")
            finally:
                cur.execute("""
            INSERT INTO venta (venta, recompensa, precio_de_ticket, precio_dolar, minima_ticket_regalo, estatus)
            VALUES (?, ?, ?, ?, ?, ?);
        """, ("", "", 0.0, 0.0, 0, "Venta finalizada"))
                con.commit()
                con.close()
        else:
            steps["db"].append("No se pudo vaciar rifa.db porque no existe")
    except Exception as e:
        return jsonify({"ok": False, "where": "db", "error": str(e), "steps": steps}), 500

    # ------------------------------------------------------------------------
    # 2) ROTACIÓN DE IMÁGENES
    # ------------------------------------------------------------------------
    try:
        # 2.a) Eliminar partida3.jpg
        delete_if_exists(partida3)
        steps["images"].append("Eliminada partida3.jpg (si existía)")

        # 2.b) Renombrar partida2.jpg -> partida3.jpg
        if partida2.exists():
            safe_replace(partida2, partida3)
            steps["images"].append("Renombrada partida2.jpg -> partida3.jpg")
        else:
            steps["images"].append("No se encontró partida2.jpg para renombrar")

        # 2.c) Mantener partida1.jpg (o partida.jpg como fallback) y copiar a partida2.jpg
        src_principal = partida1 if partida1.exists() else partida
        if src_principal and src_principal.exists():
            shutil.copy2(src_principal, partida2)
            steps["images"].append(f"Copiada {src_principal.name} -> partida2.jpg")
        else:
            steps["images"].append("No se encontró partida1.jpg ni partida.jpg para copiar a partida2.jpg")
    except Exception as e:
        return jsonify({"ok": False, "where": "images", "error": str(e), "steps": steps}), 500

    return redirect(url_for('admin_dashboard_partida'))

@app.route('/<cedula>')
def view_data(cedula):
    """
    Renderiza una plantilla HTML con el nombre y los tickets asociados a la cédula.
    """
    # Obtener datos del comprador desde la base de datos (implementar lógica en tu función)
    comprador = obtener_comprador_por_cedula(cedula)  # Ejemplo de función
    if not comprador:
        return redirect(url_for('verificar'))

    nombre = comprador["nombre"]
    tickets = comprador["tickets"]

    # Renderizar la plantilla con los datos
    return render_template('descargar_tickets.html', nombre=nombre, tickets=tickets)

@app.route('/2/<cedula>')
def view_data2(cedula):
    """
    Renderiza una plantilla HTML con el nombre y los tickets asociados a la cédula.
    """
    # Obtener datos del comprador desde la base de datos (implementar lógica en tu función)
    comprador = obtener_comprador_por_cedula2(cedula)  # Ejemplo de función
    if not comprador:
        return redirect(url_for('verificar2'))

    nombre = comprador["nombre"]
    tickets = comprador["tickets"]

    # Renderizar la plantilla con los datos
    return render_template('descargar_tickets2.html', nombre=nombre, tickets=tickets)

@app.route('/3/<cedula>')
def view_data3(cedula):
    """
    Renderiza una plantilla HTML con el nombre y los tickets asociados a la cédula.
    """
    # Obtener datos del comprador desde la base de datos (implementar lógica en tu función)
    comprador = obtener_comprador_por_cedula3(cedula)  # Ejemplo de función
    if not comprador:
        return redirect(url_for('verificar3'))

    nombre = comprador["nombre"]
    tickets = comprador["tickets"]

    # Renderizar la plantilla con los datos
    return render_template('descargar_tickets3.html', nombre=nombre, tickets=tickets)

@app.route('/comprobar_tickets')
def comprobar_tickets():
    tickets = request.args.get('orden', '')
    tickets_lista = tickets.split(',')

    # Puedes devolver una vista donde se muestran las imágenes de los cartones
    return render_template('comprobar_tickets.html', tickets=tickets_lista)

@app.route("/admin", methods=["GET", "POST"])
def admin_index():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "Admin92*":
            session['logged_in'] = True  # Establece que el usuario está autenticado
            return redirect(url_for('admin_dashboard'))  # redirigir a un panel de administración
        else:
            error_message = "Usuario o contraseña incorrectos"
            return render_template("login.html", error_message=error_message)

    return render_template("login.html")

@app.route("/admin/dashboard")
@login_required  # Ruta protegida por login

def admin_dashboard():
    return render_template("panel_admin.html")


@app.route("/admin/dashboard/partida" , methods = ["POST" , "GET"])
@login_required  # Ruta protegida por login

def admin_dashboard_partida():
    datos = obtener_datos_partida()

    if request.method == "POST":
        scnd_price = request.form.get("scnd_price")
        with sqlite3.connect(RIFA_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS scnd_price
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                precio INTEGER)''')
            conn.commit()
            cursor.execute('''SELECT precio FROM scnd_price LIMIT 1;''')
            if not scnd_price:
                scnd_price = cursor.fetchone()
            cursor.execute('''UPDATE scnd_price SET precio = ?''', (scnd_price,))
            conn.commit()

        UPLOAD_FOLDER_PARTIDA = IMG_DIR

        if "imagen" in request.files:
            file = request.files["imagen"]
            if file and allowed_file(file.filename):
                print("Archivo recibido correctamente.")  # Verifica si entra aquí
                os.makedirs(UPLOAD_FOLDER_PARTIDA, exist_ok=True)
                filename = secure_filename("partida.jpg")
                filepath = os.path.join(UPLOAD_FOLDER_PARTIDA, filename)
                file.save(filepath)
                print(f"Imagen guardada en: {filepath}")  # Verifica la ruta guardada
            else:
                print("Archivo no permitido.")
        else:
            print("No se recibió ningún archivo.")

        action = request.form.get("action")  #"reiniciar" o "detener"
        fecha_enunciado = request.form.get("fechaEnunciado")
        recompensa = request.form.get("recompensa")
        precio_carton = request.form.get("precioTicket")
        print(precio_carton)
        tipo_ticket = request.form.get("tipoTicket")
        precio_dolares = request.form.get("precioTicket$")
        zelle = request.form.get("zelle")
        actualizar_partida(fecha_enunciado, recompensa, precio_carton, tipo_ticket, action, precio_dolares, zelle)
        return redirect(url_for('admin_dashboard_partida'))  #redirigir a un panel de administración
    return render_template("admin_partida.html", datos=datos,
                           acepta_dolares=get_acepta_dolares())


@app.route("/admin/dashboard/historial" , methods = ["POST" , "GET"])
@login_required  # Ruta protegida por login

def admin_dashboard_historial():
    datos = obtener_datos_historial()
    return render_template("admin_historial.html", datos=datos)



@app.route("/admin/dashboard/solicitudes")
@login_required  # Ruta protegida por login
def admin_dashboard_solicitudes():
    solicitudes = get_data()  # Recupera los datos de la tabla
    return render_template("admin_solicitudes.html", solicitudes=solicitudes, json = json)

@app.route("/admin/dashboard/solicitudes/top")
@login_required  # Ruta protegida por login
def top():
    solicitudes = get_data2()
    return render_template("top.html", solicitudes = solicitudes)


@app.route("/admin/dashboard/solicitudes/aprobar/", methods=["POST"])
def aprobar():
    data = request.get_json() or {}
    solicitud_id = data.get("id")

    if not solicitud_id:
        return jsonify({"success": False, "message": "Falta el id de la solicitud"}), 400

    conn = sqlite3.connect(RIFA_DB_PATH)
    cursor = conn.cursor()

    try:
        # Solo cambiar estatus, NO tocar tickets
        cursor.execute("""UPDATE requeridos SET estatus = 'aprobado' WHERE id = ?""", (solicitud_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return jsonify({"success": False, "message": "Solicitud no encontrada"}), 404

        conn.commit()
        return jsonify({"success": True, "message": "Solicitud aprobada"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# (Opcional) Si el <form> llegara a disparar un GET, no hacer nada y volver
@app.route("/admin/dashboard/solicitudes/aprobar", methods=["GET"])
def aprobar_noop():
    return redirect(url_for('prueba'))

@app.route("/admin/dashboard/solicitudes/invalidate/", methods=["POST"])
def invalidate():
    data = request.get_json()
    solicitud_id = data.get("id")

    # Conectar a la base de datos
    conn = sqlite3.connect(RIFA_DB_PATH)
    cursor = conn.cursor()

    try:
        # Obtener los cartones asociados a la solicitud
        cursor.execute("""SELECT tickets_vendidos FROM requeridos WHERE id = ?""", (solicitud_id,))
        cartones_solicitados = cursor.fetchone()

        if not cartones_solicitados:
            return jsonify({"success": False, "message": "Solicitud no encontrada"}), 404

        # Extraer los cartones vendidos como texto
        cartones_texto = cartones_solicitados[0]  # Obtener el primer resultado
        if isinstance(cartones_texto, str):
            cartones = [int(carton.strip()) for carton in cartones_texto.strip('[]').split(',') if carton.strip().isdigit()]
        else:
            cartones = [int(cartones_texto)]


        # Reintegrar los cartones a la tabla de disponibles
        reintegrar_tickets(cartones)

        # Actualizar el estado de la solicitud como invalidada
        cursor.execute("""UPDATE requeridos SET estatus = "invalidado" WHERE id = ?""", (solicitud_id,))
        conn.commit()
        cursor.execute("""DELETE FROM requeridos WHERE id = ?""", (solicitud_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        conn.close()

    return redirect(url_for('prueba'))


@app.route("/admin/dashboard/solicitudes/invalidate/prueba", methods=["GET", "POST"])
def prueba():
    time.sleep(1)
    return redirect(url_for('admin_dashboard_solicitudes'))

@app.route("/admin/dashboard/solicitudes/message/", methods=["POST"])
def message():
    data = request.get_json()
    solicitud_id = data.get("id")

    # Conectar a la base de datos
    conn = sqlite3.connect(RIFA_DB_PATH)
    cursor = conn.cursor()

    # Verificar si la solicitud existe
    cursor.execute("""UPDATE requeridos SET estatus = "enviado" WHERE id = ?""", (solicitud_id,))
    conn.commit()

    # Extraer los cartones vendidos como texto
    cursor.execute("""SELECT tickets_vendidos FROM requeridos WHERE id = ?""", (solicitud_id,))
    cartones_vendidos = cursor.fetchone()[0]  # Obtener el primer resultado
    conn.close()

    # Limpieza y conversión del string a lista de enteros
    if isinstance(cartones_vendidos, str):
        # Eliminar caracteres no deseados y dividir el string
        cartones = [int(carton.strip()) for carton in cartones_vendidos.strip('[]').split(',') if carton.strip().isdigit()]
    else:
        # Si no es un string, manejarlo como un único valor
        cartones = [int(cartones_vendidos)]


    # Llamar a la función para insertar los cartones
    vendidos(cartones)

    return redirect(url_for('admin_dashboard_solicitudes'))  # redirigir a un panel de administración

import re

@app.route("/admin/dashboard/vendidos")
@login_required  # Ruta protegida por login
def mostrar_cartones():
    with sqlite3.connect(RIFA_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tickets_vendidos FROM requeridos;")
        cartones_tuplas = cursor.fetchall()
        conn.commit()
        cursor.execute("""
            SELECT monto
            FROM requeridos
            WHERE id IN (
                SELECT MIN(id)
                FROM requeridos
                GROUP BY tickets_vendidos
            );
        """)
        montos = cursor.fetchall()

        # Procesar los montos
        total_bs = 0
        total_dolar = 0

        for monto in montos:
            if monto and monto[0]:
                # Expresión regular para separar los montos antes de 'bs' y entre '/' y '$'
                match_bs = re.search(r'([\d.]+)bs', monto[0])
                match_dolar = re.search(r'/([\d.]+)\$', monto[0])

                if match_bs:
                    total_bs += float(match_bs.group(1))
                if match_dolar:
                    total_dolar += float(match_dolar.group(1))

        montos_totales = f"{total_bs}bs/{total_dolar}$"

        # Usar un conjunto para evitar duplicados
        cartones_set = set()
        for carton in cartones_tuplas:
            if carton[0]:  # Evitar errores con valores vacíos o nulos
                numeros = eval(carton[0]) if isinstance(carton[0], str) else carton[0]
                if isinstance(numeros, list):
                    cartones_set.update(numeros)
                else:
                    cartones_set.add(numeros)

        # Convertir el conjunto a lista para pasar a la plantilla
        tickets = list(cartones_set)

        return render_template("disponibles_no.html", tickets=tickets, montos_totales=montos_totales)



if __name__ == '__main__':
    import sys

    # Si hay subcomando CLI, se ejecuta y no levanta el servidor web.
    if len(sys.argv) > 1:
        try:
            handled = run_dev_cli()
            if handled:
                raise SystemExit(0)
        except ValueError as ex:
            print(f"ERROR: {ex}")
            raise SystemExit(1)

    app.run(debug=True)
