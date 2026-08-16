import sqlite3
from config import RIFA_DB_PATH

# Crear conexión a la base de datos SQLite3
conn = sqlite3.connect(RIFA_DB_PATH)
cursor = conn.cursor()

# Tabla "venta" (solo permite una fila)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS venta (
    id INTEGER PRIMARY KEY CHECK (id = 1), -- Solo una fila, siempre tendrá id = 1
    venta TEXT,
    precio_de_ticket REAL,
    precio_dolar REAL,
    zelle TEXT,
    estatus TEXT,
    minima_ticket_regalo INTEGER,
    recompensa REAL
               );
""")

# Tabla "tickets_disponibles" (del 1 al 10.000)
cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets_disponibles (
    carton_disponible INTEGER PRIMARY KEY
);""")

# Insertar los cartones disponibles (1 al 10.000)
cursor.executemany("""
INSERT OR IGNORE INTO tickets_disponibles (carton_disponible) VALUES (?);
""", [(i,) for i in range(0, 10000)])

# Tabla "tickets_usados"
cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets_usados (
    carton INTEGER PRIMARY KEY);
""")

# Tabla "requeridos"
cursor.execute("""
CREATE TABLE IF NOT EXISTS requeridos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_apellidos TEXT NOT NULL,
    cedula TEXT NOT NULL,
    telefono TEXT NOT NULL,
    referencia TEXT NOT NULL,
    tickets_vendidos INTEGER NOT NULL,
    monto TEXT NOT NULL,
    fecha TEXT NOT NULL,
    estatus TEXT DEFAULT NULL,
    link TEXT
);
""")

# Insertar una fila inicial con valores por defecto si no hay registros
cursor.execute("""
            INSERT INTO venta (venta, recompensa, precio_de_ticket, minima_ticket_regalo, estatus) 
            VALUES (?, ?, ?, ?, ?);
        """, ("", "", 0.0, 0, "Venta finalizada"))
conn.commit()

# Confirmar los cambios y cerrar la conexión

conn.close()

print("Base de datos creada con éxito.")
