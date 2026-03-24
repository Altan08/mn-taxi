from nicegui import ui, app
import sqlite3
import pandas as pd
from io import BytesIO
import json
import os
from datetime import datetime

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ ---
DB_DIR = "/data" if os.path.exists("/data") else "./data"
if not os.path.exists(DB_DIR): os.makedirs(DB_DIR)
DB_PATH = os.path.join(DB_DIR, "taxi.db")

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
    if 'trips_count' not in [col[1] for col in cursor.fetchall()]:
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
        return []

# --- КОМПОНЕНТ ПАССАЖИРОВ ---
class PassengerManager:
    def __init__(self, passengers=None):
        self.passengers = passengers if passengers else [{"name": "", "phone": ""}]
        self.container = ui.column().classes('w-full border p-2 rounded bg-white')
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
                    ui.notify(f"🎁 АКЦИЯ: Скидка 50% для {client[0]['name']}!", type='positive')
                self.draw()

    def draw(self):
        self.container.clear()
        with self.container:
            for i, p in enumerate(self.passengers):
                with ui.row().classes('w-full items-center no-wrap q-gutter-xs q-mb-xs'):
                    ui.input(label='Тел', value=p['phone'], on_change=lambda e, idx=i: [self.update(idx, 'phone', e.value), self.check_client(e.value, idx)]).classes('col-5')
                    ui.input(label='Имя', value=p['name'], on_change=lambda e, idx=i: self.update(idx, 'name', e.value)).classes('col-7')
            ui.button('➕ Пассажир', on_click=self.add_passenger).props('flat dense color=primary')

    def update(self, idx, key, val): self.passengers[idx][key] = val
    def get_json(self): return json.dumps(self.passengers, ensure_ascii=False)

# --- СТРАНИЦЫ ---

@ui.page('/')
def login_page():
    if app.storage.user.get('auth'):
        ui.navigate.to('/admin' if app.storage.user.get('role') == 'admin' else '/driver')
        return

    with ui.card().classes('absolute-center w-80 p-6 shadow-2xl'):
        ui.label('MN Transfer').classes('text-h4 text-center text-primary font-bold q-mb-md')
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
                else: ui.notify('Ошибка входа!', color='negative')
        ui.button('ВОЙТИ', on_click=do_login).classes('w-full q-mt-md h-12')

@ui.page('/admin')
def admin_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'admin':
        ui.navigate.to('/'); return

    with ui.header().classes('bg-primary justify-between p-2'):
        ui.label('MN Transfer | Admin').classes('text-h6')
        ui.button(icon='logout', on_click=lambda: [app.storage.user.clear(), ui.navigate.to('/')]).props('flat color=white')

    with ui.tabs().classes('w-full bg-grey-2') as tabs:
        t1, t2, t3, t4, t5, t6 = ui.tab('🆕 Рейсы'), ui.tab('➕ Новый'), ui.tab('🚖 Водители'), ui.tab('📜 Архив'), ui.tab('👥 Клиенты'), ui.tab('📊 Стат')

    with ui.tab_panels(tabs, value=t1).classes('w-full'):
        # --- ТЕКУЩИЕ РЕЙСЫ ---
        with ui.tab_panel(t1):
            trips = db_query("SELECT trips.*, drivers.name as dname FROM trips LEFT JOIN drivers ON trips.driver_id = drivers.id WHERE status='Новый'")
            for t in trips:
                with ui.card().classes('w-full q-mb-sm border-l-4 border-primary'):
                    ui.label(t['route']).classes('text-bold')
                    ui.label(f"Цена: {t['price']}₽ | {t['dname']}")
                    with ui.row():
                        ui.button(icon='delete', on_click=lambda tid=t['id']: [db_query("DELETE FROM trips WHERE id=?", (tid,), False), ui.navigate.to('/admin')]).props('flat color=red')
                        ui.button(icon='map', on_click=lambda r=t['route']: ui.open(f'https://yandex.ru/maps/?text={r}')).props('flat color=blue')

        # --- СОЗДАНИЕ ---
        with ui.tab_panel(t2):
            route = ui.textarea('📍 Маршрут').classes('w-full')
            price = ui.number('💰 Цена', value=4000).classes('w-full')
            drs = db_query("SELECT * FROM drivers")
            dr_select = ui.select({d['id']: d['name'] for d in drs}, label='Водитель').classes('w-full')
            pm = PassengerManager()
            def save():
                if not route.value or not dr_select.value: return ui.notify('Заполните поля!')
                for p in pm.passengers:
                    if p['phone']: db_query("INSERT OR IGNORE INTO clients (name, phone, trips_count) VALUES (?, ?, 0)", (p['name'], p['phone']), False)
                db_query("INSERT INTO trips (route, price, driver_id, status, passengers, created_at) VALUES (?,?,?,?,?,?)",
                         (route.value, int(price.value), dr_select.value, "Новый", pm.get_json(), datetime.now().strftime("%d.%m.%Y %H:%M")), False)
                ui.notify('✅ Рейс создан!'); ui.navigate.to('/admin')
            ui.button('🚀 ОПУБЛИКОВАТЬ', on_click=save).classes('w-full h-12 q-mt-md')

        # --- АРХИВ + EXCEL ---
        with ui.tab_panel(t4):
            def export_to_excel():
                data = db_query('''SELECT trips.id, trips.created_at as Дата, trips.route as Маршрут, 
                                          trips.price as Цена, drivers.name as Водитель, trips.passengers as Пассажиры
                                   FROM trips 
                                   LEFT JOIN drivers ON trips.driver_id = drivers.id 
                                   WHERE status="Завершен" ORDER BY trips.id DESC''')
                if not data: return ui.notify('Архив пуст!', color='warning')
                
                df = pd.DataFrame(data)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Архив рейсов')
                
                ui.download(output.getvalue(), 'MN_Transfer_Archive.xlsx')
            
            ui.button('📊 СКАЧАТЬ ВЕСЬ АРХИВ (EXCEL)', icon='download', on_click=export_to_excel).classes('w-full bg-green text-white q-mb-md h-12')
            
            for a in db_query("SELECT trips.*, drivers.name as dname FROM trips LEFT JOIN drivers ON trips.driver_id = drivers.id WHERE status='Завершен' ORDER BY id DESC"):
                with ui.expansion(f"{a['created_at']} | {a['route'][:30]}..."):
                    ui.label(f"Полный маршрут: {a['route']}")
                    ui.label(f"Цена: {a['price']}₽ | Водитель: {a['dname']}")
                    ui.label(f"Пассажиры: {a['passengers']}")

        # --- ВОДИТЕЛИ ---
        with ui.tab_panel(t3):
            with ui.expansion('➕ Добавить водителя').classes('w-full border rounded'):
                with ui.column().classes('p-4 w-full'):
                    n, c, l, p = ui.input('ФИО'), ui.input('Авто'), ui.input('Логин'), ui.input('Пароль')
                    ui.button('СОХРАНИТЬ', on_click=lambda: [db_query("INSERT INTO drivers (name, car, login, password) VALUES (?,?,?,?)", (n.value, c.value, l.value, p.value), False), ui.navigate.to('/admin')]).classes('w-full')
            for d in db_query("SELECT * FROM drivers"):
                with ui.card().classes('q-mb-xs p-2 w-full'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"👤 {d['name']} ({d['car']})")
                        ui.button(icon='delete', on_click=lambda did=d['id']: [db_query("DELETE FROM drivers WHERE id=?", (did,), False), ui.navigate.to('/admin')]).props('flat color=red')

        # --- КЛИЕНТЫ ---
        with ui.tab_panel(t5):
            for cl in db_query("SELECT * FROM clients ORDER BY trips_count DESC"):
                with ui.card().classes('q-mb-xs p-2 w-full'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f"👤 {cl['name']} ({cl['phone']})")
                        ui.badge(f"Поездок: {cl['trips_count']}", color='orange' if cl['trips_count'] >= 5 else 'grey')
                        ui.button(icon='delete', on_click=lambda cid=cl['id']: [db_query("DELETE FROM clients WHERE id=?", (cid,), False), ui.navigate.to('/admin')]).props('flat color=red small')

        # --- СТАТИСТИКА ---
        with ui.tab_panel(t6):
            stats = db_query('''SELECT drivers.name, SUM(trips.price) as total, COUNT(trips.id) as count 
                                FROM trips JOIN drivers ON trips.driver_id = drivers.id 
                                WHERE status="Завершен" GROUP BY drivers.id''')
            for s in stats:
                with ui.card().classes('q-mb-sm p-3 w-full'):
                    ui.label(f"🚖 {s['name']}").classes('text-bold text-lg')
                    ui.label(f"Итого: {s['total']} ₽ | Рейсов: {s['count']}")

@ui.page('/driver')
def driver_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'driver':
        ui.navigate.to('/'); return
    uid = app.storage.user.get('user_id')
    
    with ui.header().classes('bg-green-7 justify-between p-2'):
        ui.label('MN Transfer | Водитель')
        ui.button(icon='logout', on_click=lambda: [app.storage.user.clear(), ui.navigate.to('/')]).props('flat color=white')

    jobs = db_query("SELECT * FROM trips WHERE driver_id=? AND status='Новый'", (uid,))
    if not jobs: ui.label('Свободных заказов нет').classes('p-10 text-center w-full text-grey')
    for j in jobs:
        with ui.card().classes('m-4 shadow-lg border-2 border-green'):
            ui.label(j['route']).classes('text-h6 font-bold')
            ui.button('Карта', icon='map', on_click=lambda r=j['route']: ui.open(f'https://yandex.ru/maps/?text={r}')).classes('w-full q-mb-md')
            
            ps = json.loads(j['passengers'])
            for p in ps:
                with ui.row().classes('w-full justify-between p-2 bg-grey-1 items-center rounded q-mb-xs'):
                    ui.label(f"{p['name']}\n{p['phone']}").classes('whitespace-pre')
                    ui.html(f'<a href="tel:{p["phone"]}"><button style="background:#25D366; color:white; border:none; border-radius:50%; width:40px; height:40px;">📞</button></a>')
            
            def complete(jid=j['id'], passengers=ps):
                db_query("UPDATE trips SET status='Завершен' WHERE id=?", (jid,), False)
                for p in passengers:
                    if p['phone']:
                        curr = db_query("SELECT trips_count FROM clients WHERE phone=?", (p['phone'],))
                        new_count = 0 if curr and curr[0]['trips_count'] >= 5 else (curr[0]['trips_count'] + 1 if curr else 1)
                        db_query("UPDATE clients SET trips_count = ? WHERE phone=?", (new_count, p['phone']), False)
                ui.notify('✅ Рейс завершен!'); ui.navigate.to('/driver')

            ui.button('ЗАВЕРШИТЬ РЕЙС', on_click=complete).classes('bg-green text-white w-full h-14 q-mt-md')

# Запуск
ui.run(port=int(os.environ.get("PORT", 8080)), host='0.0.0.0', title="MN Transfer", storage_secret="MN_TRANSFER_SECURE_KEY_777")
