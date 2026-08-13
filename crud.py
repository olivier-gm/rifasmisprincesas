import sqlite3
import json
import time
from flask import request, render_template, redirect, url_for

DB_NAME = "rifa.db"
# --- Persistencia ---
def _ensure_flags_table():
    conn = sqlite3.connect('config.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feature_flags (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """)
    # Por defecto: 0 = acepta dólares (interruptor ON por defecto si así lo deseas)
    c.execute("INSERT OR IGNORE INTO feature_flags (key, value) VALUES ('acepta_dolares', 0)")
    conn.commit()
    conn.close()

def get_acepta_dolares() -> bool:
    """
    Retorna True si el interruptor debe estar ON (se aceptan dólares).
    BD: 0 = acepta, 1 = NO acepta  -> invertimos al retornar.
    """
    _ensure_flags_table()
    conn = sqlite3.connect('config.db')
    c = conn.cursor()
    c.execute("SELECT value FROM feature_flags WHERE key='acepta_dolares'")
    row = c.fetchone()
    conn.close()
    # 0 => acepta (True), 1 => no acepta (False)
    return (int(row[0]) == 0) if row else True  # por defecto True

def set_acepta_dolares(enabled: bool) -> None:
    """
    enabled True (ON) => guarda 0 (acepta)
    enabled False (OFF) => guarda 1 (NO acepta)
    """
    _ensure_flags_table()
    conn = sqlite3.connect('config.db')
    c = conn.cursor()
    value = 0 if enabled else 1
    c.execute("UPDATE feature_flags SET value=? WHERE key='acepta_dolares'", (value,))
    conn.commit()
    conn.close()

def execute_query(query, params=(), fetch=False, fetchone=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    if fetch:
        data = cursor.fetchall() if not fetchone else cursor.fetchone()
    else:
        conn.commit()
        data = None
    conn.close()
    return data

def obtener_datos_partida():
    # Conectar a la base de datos
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # Crear la consulta para obtener el dato específico
    cursor.execute("SELECT estatus, venta, recompensa, precio_de_ticket, precio_dolar, zelle, minima_ticket_regalo FROM venta WHERE id = 1")
    resultado = cursor.fetchone()
    conn.commit()

    #if resultado[0] == "Venta finalizada":

    #    cursor.execute("""DELETE FROM tickets_disponibles WHERE 1 = 1""")
    #    conn.commit()

    #    cursor.executemany("""
    #    INSERT OR IGNORE INTO tickets_disponibles (carton_disponible) VALUES (?);
    #    """, [(i,) for i in range(1, 1501)])
    #    conn.commit()

    conn.close()

    return resultado if resultado else None




def actualizar_partida(fecha_enunciado=None, recompensa=None, precio_carton=None, tipo_ticket=None, action=None, precio_dolares=None, zelle=None):
    import sqlite3

    # Conectar a la base de datos
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # Verificar si la tabla tiene al menos una fila
    cursor.execute("SELECT COUNT(*) FROM venta;")
    count = cursor.fetchone()[0]

    if count == 0:
        # Insertar una fila inicial con valores por defecto si no hay registros
        cursor.execute("""
            INSERT INTO venta (venta, recompensa, precio_de_ticket, minima_ticket_regalo, estatus)
            VALUES (?, ?, ?, ?, ?);
        """, ("", "", 0.0, "", "Venta finalizada"))
        conn.commit()

    # Construcción dinámica de los campos y valores para el comando UPDATE
    fields = []
    values = []

    if fecha_enunciado:
        fields.append("venta = ?")
        values.append(fecha_enunciado)

    if recompensa:
        fields.append("recompensa = ?")
        values.append(recompensa)

    if precio_carton:  # precio_carton puede ser 0, por eso se usa `is not None`
        fields.append("precio_de_ticket = ?")
        values.append(precio_carton)

    if precio_dolares:  # precio_carton puede ser 0, por eso se usa `is not None`
        fields.append("precio_dolar = ?")
        values.append(precio_dolares)

    if zelle:  # precio_carton puede ser 0, por eso se usa `is not None`
        fields.append("zelle = ?")
        values.append(zelle)

    if tipo_ticket:
        fields.append("minima_ticket_regalo = ?")
        values.append(tipo_ticket)

    if action:
        fields.append("estatus = ?")
        values.append(action)

    # Actualizar la fila solo si hay campos a modificar
    if fields:
        update_query = f"UPDATE venta SET {', '.join(fields)} WHERE id = 1;"
        cursor.execute(update_query, values)

    # Confirmar los cambios y cerrar conexión
    conn.commit()
    conn.close()




def venta(C=None, read=None, U=None, D=None):
    if C:
        query = """
        INSERT OR REPLACE INTO venta (id, venta, hora_de_partida, precio_de_ticket, estatus, mensaje)
        VALUES (1, ?, ?, ?, ?, ?);
        """
        execute_query(query, C)
    elif read:
        query = "SELECT * FROM venta WHERE id = 1;"
        return execute_query(query, fetch=True)
    elif U:
        query = """
        UPDATE venta
        SET venta = ?, hora_de_partida = ?, precio_de_ticket = ?, estatus = ?, mensaje = ?
        WHERE id = 1;
        """
        execute_query(query, U)
    elif D:
        query = "DELETE FROM venta WHERE id = 1;"
        execute_query(query)

def tickets_disponibles(C=None, read=None, U=None, D=None):
    if C:
        query = "SELECT carton FROM tickets_usados;"
        return execute_query(query, fetch=True)
    elif read:
        if read == "*":  # Si `read` es "*", obten todos los registros
            query = "SELECT carton_disponible FROM tickets_disponibles;"
            return execute_query(query, fetch=True)
        else:
            query = "SELECT * FROM tickets_disponibles WHERE carton_disponible = ?;"
            return execute_query(query, (read,), fetch=True)



def tickets_usados(C=None, read=None, U=None, D=None):
    if C:
        query = "INSERT INTO tickets_usados (carton, usuario) VALUES (?, ?);"
        execute_query(query, C)
    elif read:
        query = "SELECT * FROM tickets_usados WHERE carton = ?;"
        return execute_query(query, (read,), fetch=True)
    elif U:
        query = """
        UPDATE tickets_usados
        SET usuario = ?
        WHERE carton = ?;
        """
        execute_query(query, U)
    elif D:
        query = "DELETE FROM tickets_usados WHERE carton = ?;"
        execute_query(query, (D,))

def requeridos(C=None, read=None, U=None, D=None, table="requeridos"):
    if C:
        query = f"""
        INSERT INTO {table}
        (nombre_apellidos, cedula, telefono, referencia, tickets_vendidos, monto, fecha)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        execute_query(query, C)
    elif read:
        query = f"SELECT * FROM {table} WHERE cedula = ?;"
        return execute_query(query, (read,), fetch=True)
    elif U:
        query = f"""
        UPDATE {table}
        SET nombre_apellidos = ?, telefono = ?, referencia = ?,
            tickets_vendidos = ?, monto = ?, fecha = ?
        WHERE cedula = ?;
        """
        execute_query(query, U)
    elif D:
        query = f"DELETE FROM {table} WHERE cedula = ?;"
        execute_query(query, (D,))

def usuarios_aceptados(C=None, read=None, U=None, D=None):
    requeridos(C, read, U, D, table="usuarios_aceptados")

# Función para la tabla "tickets_usados"
def tickets_usados(C=None, read=None, U=None, D=None):
    if C:  # Insertar un nuevo cartón
        query = "INSERT OR IGNORE INTO tickets_usados (carton, usuario) VALUES (?, ?);"
        execute_query(query, C)
    elif read:  # Leer registros
        if read == "*":  # Leer todos los registros
            query = "SELECT carton FROM tickets_usados;"
            return execute_query(query, fetch=True)
        else:  # Leer un registro específico
            query = "SELECT * FROM tickets_usados WHERE carton = ?;"
            return execute_query(query, (read,), fetch=True)
    elif U:  # Actualizar un registro
        query = """
        UPDATE tickets_usados
        SET usuario = ?
        WHERE carton = ?;
        """
        execute_query(query, U)
    elif D:  # Eliminar un registro
        query = "DELETE FROM tickets_usados WHERE carton = ?;"
        execute_query(query, (D,))

def get_data2():
    import sqlite3

    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # >>> Cambiado: ahora solo trae requeridos aprobados <<<
    cursor.execute("""
        SELECT
            MIN(id) AS id,
            nombre_apellidos,
            cedula,
            telefono,
            referencia,
            GROUP_CONCAT(tickets_vendidos) AS cartones,
            SUM(monto) AS monto,
            fecha,
            estatus,
            link,
            SUM(
                (SELECT LENGTH(REPLACE(REPLACE(tickets_vendidos, '[', ''), ']', ''))
                        - LENGTH(REPLACE(REPLACE(tickets_vendidos, ',', ''), '[', '')) + 2)
            ) AS length
        FROM requeridos
        WHERE estatus IN ('aprobado', 'enviado')
        GROUP BY cedula
    """)

    rows = cursor.fetchall()
    conn.close()

    solicitudes = []
    for row in rows:
        solicitud = {
            "id": row[0],
            "nombre": row[1],
            "cedula": row[2],
            "telefono": row[3],
            "referencia": row[4],
            "cartones": row[5],
            "monto": row[6],
            "fecha": row[7],
            "estatus": row[8],
            "link": row[9],
            "length": row[10],
        }
        solicitudes.append(solicitud)

    return solicitudes

def get_data():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # Consulta todos los datos de la tabla
    cursor.execute("""
            SELECT *
            FROM requeridos
            WHERE id IN (
                SELECT MIN(id)
                FROM requeridos
                GROUP BY tickets_vendidos
            );
        """)
    rows = cursor.fetchall()
    conn.close()

    # Convertir los resultados en una lista de diccionarios
    solicitudes = []
    for row in rows:
        solicitud = {
            "id": row[0],
            "nombre": row[1],
            "cedula": row[2],
            "telefono": row[3],
            "referencia": row[4],
            "cartones": row[5],
            "monto": row[6],
            "fecha": row[7],
            "estatus": row[8],
            "link": row[9]
        }
        solicitudes.append(solicitud)

    return solicitudes

def get_enunciado3():
    conn = sqlite3.connect('rifa3.db')
    cursor = conn.cursor()

    cursor.execute("SELECT estatus FROM venta WHERE id = 1")
    estatus = cursor.fetchone()[0]
    conn.commit()

    if estatus == "Venta en curso":

        cursor.execute("SELECT venta FROM venta")
        data = cursor.fetchone()  # Recupera todos los datos de la tabla
        conn.close()

    else:

        data = ["No disponible"]

    return data[0] if data else None


def get_enunciado2():
    conn = sqlite3.connect('rifa2.db')
    cursor = conn.cursor()

    cursor.execute("SELECT estatus FROM venta WHERE id = 1")
    estatus = cursor.fetchone()[0]
    conn.commit()

    if estatus == "Venta en curso":

        cursor.execute("SELECT venta FROM venta")
        data = cursor.fetchone()  # Recupera todos los datos de la tabla
        conn.close()

    else:

        data = ["No disponible"]

    return data[0] if data else None



def get_enunciado():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    cursor.execute("SELECT estatus FROM venta WHERE id = 1")
    estatus = cursor.fetchone()[0]
    conn.commit()

    if estatus == "Venta en curso":

        cursor.execute("SELECT venta FROM venta")
        data = cursor.fetchone()  # Recupera todos los datos de la tabla
        conn.close()

    else:

        data = ["No disponible"]

    return data[0] if data else None



def get_premio3():
    conn = sqlite3.connect('rifa3.db')
    cursor = conn.cursor()
    cursor.execute("SELECT recompensa FROM venta")
    data = cursor.fetchone()  # Recupera todos los datos de la tabla
    conn.close()
    return data[0] if data else None


def get_premio2():
    conn = sqlite3.connect('rifa2.db')
    cursor = conn.cursor()
    cursor.execute("SELECT recompensa FROM venta")
    data = cursor.fetchone()  # Recupera todos los datos de la tabla
    conn.close()
    return data[0] if data else None


def get_premio():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT recompensa FROM venta")
    data = cursor.fetchone()  # Recupera todos los datos de la tabla
    conn.close()
    return data[0] if data else None

def get_precio():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT precio_de_ticket FROM venta")
    data = cursor.fetchone()  # Recupera todos los datos de la tabla
    conn.close()
    return data[0] if data else None




def insertar_comprador(nombre_apellido, cedula, telefono, referencia, tickets_vendidos, monto, fecha, referencia_ruta, link, tickets_vendidos_str, max_retries=3, delay=2):
    tickets_vendidos = [int(carton.strip()) for carton in ', '.join(map(str, tickets_vendidos_str)).split(",")]
    tickets_vendidos_text = json.dumps(tickets_vendidos)  # JSON format (recommended)

    # Intentar varias veces si falla
    attempt = 0
    while attempt < max_retries:
        try:
            # Conectar a la base de datos
            conn = sqlite3.connect('rifa.db')
            cursor = conn.cursor()

            # Iniciar la transacción explícitamente
            conn.execute("BEGIN TRANSACTION;")
            # Ejecutar el comando para eliminar los cartones de la tabla `tickets_disponibles`

            # Consultar si los cartones solicitados existen en la tabla 'tickets_disponibles'
            placeholders = ', '.join(['?'] * len(tickets_vendidos))
            query = f"SELECT carton_disponible FROM tickets_disponibles WHERE carton_disponible IN ({placeholders})"
            cursor.execute(query, tickets_vendidos)
            tickets_disponibles = [row[0] for row in cursor.fetchall()]
            cursor.execute(f"DELETE FROM tickets_disponibles WHERE carton_disponible IN ({placeholders});", tickets_vendidos)
            conn.commit()

            # Si la cantidad de cartones encontrados no coincide con la cantidad solicitada, significa que algunos cartones no están disponibles
            if len(tickets_disponibles) != len(tickets_vendidos):
                # Si no todos los cartones están disponibles, esperar y reintentar
                attempt += 1
                conn.execute("ROLLBACK;")
                conn.close()
                if attempt < max_retries:
                    print(f"Intento {attempt} fallido, reintentando...")
                    time.sleep(delay)  # Esperar un poco antes de reintentar
                    continue  # Volver a intentar la consulta
                else:
                    # Si se superan los intentos, retornar un mensaje
                    print("insercion invalida")
                    conn = sqlite3.connect('rifa.db')
                    cursor = conn.cursor()

            # Ejecutar el comando para eliminar los cartones de la tabla `tickets_disponibles`
            cursor.execute(f"DELETE FROM tickets_disponibles WHERE carton_disponible IN ({placeholders});", tickets_vendidos)
            conn.commit()

            # Si todos los cartones están disponibles, proceder con la inserción en la tabla 'requeridos'
            cursor.execute("""
                INSERT INTO requeridos (
                    nombre_apellidos,
                    cedula,
                    telefono,
                    referencia,
                    tickets_vendidos,
                    monto,
                    fecha,
                    link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (nombre_apellido, cedula, telefono, referencia_ruta, tickets_vendidos_text, monto, fecha, link))

            print('insercion exitosa')


            # Confirmar la inserción y eliminación
            conn.execute("COMMIT;")

            # Cerrar la conexión
            conn.close()
            break  # Si la operación fue exitosa, salir del bucle

        except sqlite3.OperationalError as e:
            # Si hay un error de base de datos, hacer rollback y esperar antes de reintentar
            conn.execute("ROLLBACK;")
            conn.close()
            print(f"Error al insertar comprador, reintentando: {e}")
            attempt += 1
            time.sleep(delay)  # Esperar un poco antes de reintentar

            # Si se superan los intentos, retornar un error o un mensaje
            print("No se pudo procesar la compra después de varios intentos, por favor intente más tarde.")




import sqlite3


def obtener_comprador_por_cedula3(cedula):
    """
    Recupera el nombre y los tickets vendidos de la base de datos usando la cédula.
    Si hay múltiples coincidencias, conserva el primer nombre encontrado y combina los tickets.
    Retorna un diccionario con los datos estructurados.
    """
    with sqlite3.connect("rifa3.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT nombre_apellidos, tickets_vendidos
        FROM requeridos
        WHERE cedula = ?''', (cedula,))
        resultados = cursor.fetchall()  # Obtener todas las coincidencias

    # Si no se encuentran datos, retorna None
    if not resultados:
        return None

    # Extraer el nombre de la primera coincidencia
    nombre_apellidos = resultados[0][0]

    # Acumular todos los tickets en una lista
    tickets_vendidos = []
    for _, tickets_str in resultados:
        try:
            tickets = eval(tickets_str)
            if not isinstance(tickets, list):
                raise ValueError("El campo tickets_vendidos no es una lista válida.")
            tickets_vendidos.extend(int(ticket) for ticket in tickets)
        except (SyntaxError, ValueError, TypeError):
            raise ValueError(f"Error al procesar tickets_vendidos: {tickets_str}")

    # Retornar los datos estructurados
    return {
        "nombre": nombre_apellidos,
        "tickets": tickets_vendidos
    }


def obtener_comprador_por_cedula2(cedula):
    """
    Recupera el nombre y los tickets vendidos de la base de datos usando la cédula.
    Si hay múltiples coincidencias, conserva el primer nombre encontrado y combina los tickets.
    Retorna un diccionario con los datos estructurados.
    """
    with sqlite3.connect("rifa2.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT nombre_apellidos, tickets_vendidos
        FROM requeridos
        WHERE cedula = ?''', (cedula,))
        resultados = cursor.fetchall()  # Obtener todas las coincidencias

    # Si no se encuentran datos, retorna None
    if not resultados:
        return None

    # Extraer el nombre de la primera coincidencia
    nombre_apellidos = resultados[0][0]

    # Acumular todos los tickets en una lista
    tickets_vendidos = []
    for _, tickets_str in resultados:
        try:
            tickets = eval(tickets_str)
            if not isinstance(tickets, list):
                raise ValueError("El campo tickets_vendidos no es una lista válida.")
            tickets_vendidos.extend(int(ticket) for ticket in tickets)
        except (SyntaxError, ValueError, TypeError):
            raise ValueError(f"Error al procesar tickets_vendidos: {tickets_str}")

    # Retornar los datos estructurados
    return {
        "nombre": nombre_apellidos,
        "tickets": tickets_vendidos
    }


def obtener_comprador_por_cedula(cedula):
    """
    Recupera el nombre y los tickets vendidos de la base de datos usando la cédula.
    Si hay múltiples coincidencias, conserva el primer nombre encontrado y combina los tickets.
    Retorna un diccionario con los datos estructurados.
    """
    with sqlite3.connect("rifa.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT nombre_apellidos, tickets_vendidos
        FROM requeridos
        WHERE cedula = ?''', (cedula,))
        resultados = cursor.fetchall()  # Obtener todas las coincidencias

    # Si no se encuentran datos, retorna None
    if not resultados:
        return None

    # Extraer el nombre de la primera coincidencia
    nombre_apellidos = resultados[0][0]

    # Acumular todos los tickets en una lista
    tickets_vendidos = []
    for _, tickets_str in resultados:
        try:
            tickets = eval(tickets_str)
            if not isinstance(tickets, list):
                raise ValueError("El campo tickets_vendidos no es una lista válida.")
            tickets_vendidos.extend(int(ticket) for ticket in tickets)
        except (SyntaxError, ValueError, TypeError):
            raise ValueError(f"Error al procesar tickets_vendidos: {tickets_str}")

    # Retornar los datos estructurados
    return {
        "nombre": nombre_apellidos,
        "tickets": tickets_vendidos
    }

from flask import request, render_template, redirect, url_for


# --- Persistencia de flags (crear/leer/actualizar) ---
def obtener_datos_historial():
    """
    Lee (y si es POST, actualiza) los flags que controlan mostrar/ocultar
    rifa2 y rifa3. Devuelve un dict con enteros 0/1.
    """
    conn = sqlite3.connect('config.db')
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feature_flags (
          key TEXT PRIMARY KEY,
          value INTEGER NOT NULL
        )
    """)
    # valores por defecto: todo visible
    defaults = [('mostrar_rifa2', 1), ('mostrar_rifa3', 1)]
    c.executemany("INSERT OR IGNORE INTO feature_flags (key,value) VALUES (?,?)", defaults)

    # Si venimos de un POST, guardamos
    if request.method == 'POST':
        r2 = 1 if request.form.get('rifa2') == 'on' else 0
        r3 = 1 if request.form.get('rifa3') == 'on' else 0
        c.execute("UPDATE feature_flags SET value=? WHERE key='mostrar_rifa2'", (r2,))
        c.execute("UPDATE feature_flags SET value=? WHERE key='mostrar_rifa3'", (r3,))
        conn.commit()

    # Leemos siempre para renderizar
    c.execute("SELECT key, value FROM feature_flags WHERE key IN ('mostrar_rifa2','mostrar_rifa3')")
    rows = dict(c.fetchall())
    conn.close()
    return {
        'mostrar_rifa2': int(rows.get('mostrar_rifa2', 1)),
        'mostrar_rifa3': int(rows.get('mostrar_rifa3', 1)),
    }


def get_tickets(cant_tickets):
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect('rifa.db')  # Cambia 'database_name.db' por el nombre de tu base de datos
        cursor = conn.cursor()

        # Consultar la cantidad total de columnas disponibles
        cursor.execute("SELECT COUNT(*) FROM tickets_disponibles")
        total_columns = cursor.fetchone()[0]

        # Validar que cant_tickets no supere el total de columnas disponibles
        if int(cant_tickets) > int(total_columns):
            cant_tickets = total_columns

        # Realizar la consulta para obtener los números en orden descendente
        query = f"SELECT carton_disponible FROM tickets_disponibles ORDER BY RANDOM() ASC LIMIT {cant_tickets}"
        cursor.execute(query)
        results = cursor.fetchall()

        # Convertir el resultado en una lista de números
        tickets = [row[0] for row in results]

        # Cerrar la conexión
        conn.close()

        return tickets

    except sqlite3.Error as e:
        print(f"Error en la base de datos: {e}")
        return []

# Ejemplo de uso
tickets_obtenidos = get_tickets(5)
print(tickets_obtenidos) #[50, 51, 52, 53, 54]

def get_porcentaje3(flag):
    conn = sqlite3.connect('rifa3.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(carton_disponible) FROM tickets_disponibles")
    cantidad = cursor.fetchone()[0]
    conn.close()
    if flag == False:
        return cantidad
    # Calcular el porcentaje
    total = 10000
    porcentaje = (cantidad / total) * 100
    return round(porcentaje, 2)


def get_porcentaje2(flag):
    conn = sqlite3.connect('rifa2.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(carton_disponible) FROM tickets_disponibles")
    cantidad = cursor.fetchone()[0]
    conn.close()
    if flag == False:
        return cantidad

    # Calcular el porcentaje
    total = 10000
    porcentaje = (cantidad / total) * 100
    return round(porcentaje, 2)



def get_porcentaje(flag):
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(carton_disponible) FROM tickets_disponibles")
    cantidad = cursor.fetchone()[0]
    conn.close()
    if flag == False:
        return cantidad

    # Calcular el porcentaje
    total = 10000
    porcentaje = (cantidad / total) * 100
    return round(porcentaje, 2)



def get_estatus():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT estatus FROM venta WHERE id = 1")
    estatus = cursor.fetchone()[0]
    conn.close()
    return estatus if estatus else None

def get_minima():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT minima_ticket_regalo FROM venta WHERE id = 1")
    modalidad = cursor.fetchone()[0]
    conn.close()
    return modalidad if modalidad else None

def vendidos(cartones):
    # Conectar a la base de datos
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # Convertir los valores del array en tuplas (executemany espera una lista de tuplas)
    cartones_tuplas = [(carton,) for carton in cartones]

    try:
        # Ejecutar el comando para insertar múltiples valores
        cursor.executemany("""
            INSERT INTO tickets_usados (carton) VALUES (?);
        """, cartones_tuplas)

        # Confirmar cambios
        conn.commit()
        print(f"Cartones insertados: {cartones}")
    except sqlite3.IntegrityError as e:
        print(f"Error al insertar cartones: {e}")
    finally:
        # Cerrar la conexión
        conn.close()

def get_dolar():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT precio_dolar FROM venta WHERE id = 1")
    dolar = cursor.fetchone()[0]
    conn.close()
    return dolar if dolar else None

def get_zelle():
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()
    cursor.execute("SELECT zelle FROM venta WHERE id = 1")
    zelle = cursor.fetchone()[0]
    conn.close()
    return zelle if zelle else None



def reintegrar_tickets(cartones):
    # Conectar a la base de datos
    conn = sqlite3.connect('rifa.db')
    cursor = conn.cursor()

    # Convertir los valores del array en tuplas (executemany espera una lista de tuplas)
    cartones_tuplas = [(carton,) for carton in cartones]

    try:
        # Ejecutar el comando para insertar múltiples valores
        cursor.executemany("""
        INSERT OR IGNORE INTO tickets_disponibles (carton_disponible) VALUES (?);
        """, cartones_tuplas)


        # Confirmar cambios
        conn.commit()
        print(f"Cartones reintegrados: {cartones}")
    except sqlite3.IntegrityError as e:
        print(f"Error al reintegrar cartones: {e}")
    finally:
        # Cerrar la conexión
        conn.close()
