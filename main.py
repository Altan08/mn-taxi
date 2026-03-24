from nicegui import ui, app
import sqlite3
import pandas as pd
from io import BytesIO
import json
import os
from datetime import datetime

# --- 1. БАЗА ДАННЫХ ---
DB_PATH = "taxi.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS drivers 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, car TEXT, login TEXT, password TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, route TEXT, price INTEGER, 
                       driver_id INTEGER, status TEXT, passengers TEXT, created_at TEXT,
                       FOREIGN KEY(driver_id) REFERENCES drivers(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT UNIQUE, trips_count INTEGER DEFAULT 0)''')
    
    cursor.execute("PRAGMA table_info(clients)")
    if 'trips_count' not in [column[1] for column in cursor.fetchall()]:
        cursor.execute("ALTER TABLE clients ADD COLUMN trips_count INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

init_db()

def db_query(query, params=(), fetch=True):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        res = cursor.fetchall() if fetch else None
        conn.commit()
        conn.close()
        return [dict(row) for row in res] if fetch else None
    except Exception as e:
        ui.notify(f"Ошибка БД: {e}", color='negative')
        return [] if fetch else None

# --- КОМПОНЕНТ ПАССАЖИРОВ ---
class PassengerManager:
    def __init__(self, passengers=None):
        self.passengers = passengers if passengers else [{"name": "", "phone": ""}]
        self.container = ui.column().classes('w-full border p-2 rounded')
        self.draw()

    def add_passenger(self):
        self.passengers.append({"name": "", "phone": ""})
        self.draw()

    def check_client(self, phone, index):
        if len(phone) > 5:
            client = db_query("SELECT name, trips_count FROM clients WHERE phone=?", (phone,))
            if client:
                self.passengers[index]['name'] = client[0]['name']
                if client[0]['trips_count'] >= 5:
                    ui.notify(f"🎁 АКЦИЯ ДЛЯ {client[0]['name']}!", type='positive')
                self.draw()

    def draw(self):
        self.container.clear()
        with self.container:
            for i, p in enumerate(self.passengers):
                with ui.row().classes('w-full items-center q-gutter-sm'):
                    ui.input(label='Тел', value=p['phone'], on_change=lambda e, idx=i: [self.update(idx, 'phone', e.value), self.check_client(e.value, idx)]).classes('col')
                    ui.input(label='Имя', value=p['name'], on_change=lambda e, idx=i: self.update(idx, 'name', e.value)).classes('col')
            ui.button('➕ Пассажир', on_click=self.add_passenger).props('flat')

    def update(self, index, key, value):
        self.passengers[index][key] = value

    def get_json(self):
        return json.dumps(self.passengers, ensure_ascii=False)

# --- СТРАНИЦЫ ---

@ui.page('/')
def login_page():
    # ПРОВЕРКА: Если пользователь уже залогинен, перенаправляем сразу
    if app.storage.user.get('auth'):
        if app.storage.user.get('role') == 'admin':
            ui.navigate.to('/admin')
        else:
            ui.navigate.to('/driver')
        return

    with ui.card().classes('absolute-center w-80 p-6 shadow-2xl'):
        ui.label('🚕 NOMAD TECH').classes('text-h5 text-center text-primary font-bold q-mb-md')
        l = ui.input('Логин').classes('w-full')
        p = ui.input('Пароль', password=True).classes('w-full')
        
        def do_login():
            if l.value == "admin" and p.value == "mn123":
                app.storage.user.update({'auth': True, 'role': 'admin'})
                ui.navigate.to('/admin')
            else:
                user = db_query("SELECT * FROM drivers WHERE login=? AND password=?", (l.value, p.value))
                if user:
                    app.storage.user.update({'auth': True, 'role': 'driver', 'user_id': user[0]['id']})
                    ui.navigate.to('/driver')
                else:
                    ui.notify('Ошибка входа!', color='negative')
        
        ui.button('ВОЙТИ', on_click=do_login).classes('w-full q-mt-md')

@ui.page('/admin')
def admin_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'admin':
        ui.navigate.to('/')
        return
    
    def logout():
        app.storage.user.clear()
        ui.navigate.to('/')

    with ui.header().classes('bg-primary justify-between p-2'):
        ui.label('🚀 АДМИН ПАНЕЛЬ').classes('text-h6 text-white')
        ui.button(icon='logout', on_click=logout).props('flat color=white')

    with ui.tabs().classes('w-full bg-grey-2 text-primary') as tabs:
        t1, t2, t3, t4, t5 = ui.tab('🆕 Рейсы'), ui.tab('➕ Новый'), ui.tab('🚖 Водители'), ui.tab('📜 Архив'), ui.tab('👥 Клиенты')

    with ui.tab_panels(tabs, value=t1).classes('w-full'):
        with ui.tab_panel(t1):
            trips = db_query("SELECT trips.*, drivers.name as dname FROM trips LEFT JOIN drivers ON trips.driver_id = drivers.id WHERE status='Новый'")
            for t in trips:
                with ui.card().classes('w-full q-mb-sm border-l-4 border-primary'):
                    ui.label(t['route']).classes('text-bold')
                    ui.label(f"Цена: {t['price']}₽ | {t['dname']}")
                    ui.button('Удалить', on_click=lambda tid=t['id']: [db_query("DELETE FROM trips WHERE id=?", (tid,), False), ui.navigate.to('/admin')]).props('small flat color=red')

        with ui.tab_panel(t2):
            route = ui.textarea('📍 Маршрут').classes('w-full')
            price = ui.number('💰 Цена', value=4000).classes('w-full')
            drs = db_query("SELECT * FROM drivers")
            dr_select = ui.select({d['id']: d['name'] for d in drs}, label='Водитель').classes('w-full')
            pm = PassengerManager()
            
            def save_trip():
                if not route.value or not dr_select.value:
                    return ui.notify('Заполните данные!')
                for p in pm.passengers:
                    if p['phone']:
                        db_query("INSERT OR IGNORE INTO clients (name, phone, trips_count) VALUES (?, ?, 0)", (p['name'], p['phone']), False)
                db_query("INSERT INTO trips (route, price, driver_id, status, passengers, created_at) VALUES (?,?,?,?,?,?)",
                         (route.value, int(price.value), dr_select.value, "Новый", pm.get_json(), datetime.now().strftime("%d.%m.%Y %H:%M")), False)
                ui.notify('✅ Опубликовано!')
                ui.navigate.to('/admin')
            ui.button('🚀 ПУСК', on_click=save_trip).classes('w-full q-mt-md h-12')

        with ui.tab_panel(t3):
            with ui.expansion('➕ Добавить водителя').classes('w-full border rounded'):
                with ui.column().classes('p-4 w-full'):
                    n_in, c_in, l_in, p_in = ui.input('ФИО'), ui.input('Авто'), ui.input('Логин'), ui.input('Пароль')
                    def create_driver():
                        if not n_in.value or not l_in.value: return ui.notify('Заполните поля!')
                        db_query("INSERT INTO drivers (name, car, login, password) VALUES (?,?,?,?)", (n_in.value, c_in.value, l_in.value, p_in.value), False)
                        ui.navigate.to('/admin')
                    ui.button('СОХРАНИТЬ', on_click=create_driver).classes('w-full bg-primary text-white')

            for d in db_query("SELECT * FROM drivers"):
                with ui.card().classes('q-mb-xs p-2 w-full'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"👤 {d['name']} ({d['car']})")
                        ui.button(icon='delete', on_click=lambda did=d['id']: [db_query("DELETE FROM drivers WHERE id=?", (did,), False), ui.navigate.to('/admin')]).props('flat color=red')

        with ui.tab_panel(t5):
            for cl in db_query("SELECT * FROM clients ORDER BY trips_count DESC"):
                with ui.card().classes('q-mb-xs p-2 w-full'):
                    ui.label(f"👤 {cl['name']} — 📞 {cl['phone']} (Рейсов: {cl['trips_count']})")
                    if cl['trips_count'] >= 5: ui.badge('АКЦИЯ 50%', color='orange')

@ui.page('/driver')
def driver_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'driver':
        ui.navigate.to('/')
        return
    
    uid = app.storage.user.get('user_id')
    
    def logout():
        app.storage.user.clear()
        ui.navigate.to('/')

    with ui.header().classes('bg-green-7 justify-between p-2'):
        ui.label('📱 ВОДИТЕЛЬ').classes('text-h6')
        ui.button(icon='logout', on_click=logout).props('flat color=white')

    jobs = db_query("SELECT * FROM trips WHERE driver_id=? AND status='Новый'", (uid,))
    for j in jobs:
        with ui.card().classes('m-4 shadow-lg border-2 border-green'):
            ui.label(j['route']).classes('text-h6 font-bold')
            ps = json.loads(j['passengers'])
            for p in ps:
                with ui.row().classes('w-full justify-between p-2 bg-grey-1'):
                    ui.label(f"{p['name']}\n{p['phone']}")
                    ui.html(f'<a href="tel:{p["phone"]}"><button style="background:#25D366; color:white; border:none; border-radius:50%; width:45px; height:45px;">📞</button></a>')
            
            def complete_trip(jid=j['id'], passengers=ps):
                db_query("UPDATE trips SET status='Завершен' WHERE id=?", (jid,), False)
                for p in passengers:
                    if p['phone']:
                        current = db_query("SELECT trips_count FROM clients WHERE phone=?", (p['phone'],))
                        if current and current[0]['trips_count'] >= 5:
                            db_query("UPDATE clients SET trips_count = 0 WHERE phone=?", (p['phone'],), False)
                        else:
                            db_query("UPDATE clients SET trips_count = trips_count + 1 WHERE phone=?", (p['phone'],), False)
                ui.notify('Рейс завершен!')
                ui.navigate.to('/driver')

            ui.button('✅ ЗАВЕРШИТЬ', on_click=complete_trip).classes('bg-green text-white w-full h-12')

# --- ЗАПУСК (ОБЯЗАТЕЛЬНО С SECRET) ---
port = int(os.environ.get("PORT", 8080))
# Придумай свой длинный секретный ключ для storage_secret
ui.run(port=port, host='0.0.0.0', title="NOMAD TECH", storage_secret="MN_SECRET_KEY_12345")
