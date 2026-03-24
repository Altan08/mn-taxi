from nicegui import ui, app
import sqlite3
import pandas as pd
from io import BytesIO
import json
import os
from datetime import datetime

# --- 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite) ---
DB_PATH = "taxi.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Таблица водителей
    cursor.execute('''CREATE TABLE IF NOT EXISTS drivers 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, car TEXT, login TEXT, password TEXT)''')
    # Таблица рейсов
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, route TEXT, price INTEGER, 
                       driver_id INTEGER, status TEXT, passengers TEXT, created_at TEXT,
                       FOREIGN KEY(driver_id) REFERENCES drivers(id))''')
    # НОВАЯ ТАБЛИЦА КЛИЕНТОВ
    cursor.execute('''CREATE TABLE IF NOT EXISTS clients 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT UNIQUE)''')
    conn.commit()
    conn.close()

init_db()

# --- Вспомогательные функции ---
def db_query(query, params=(), fetch=True):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return [dict(row) for row in res] if fetch else None

# Глобальное состояние сессии
session = {'auth': False, 'role': None, 'user_id': None}

# --- КОМПОНЕНТ ПАССАЖИРОВ С АВТОПОДСТАНОВКОЙ ---
class PassengerManager:
    def __init__(self, passengers=None):
        self.passengers = passengers if passengers else [{"name": "", "phone": ""}]
        self.container = ui.column().classes('w-full border p-2 rounded')
        self.draw()

    def add_passenger(self):
        self.passengers.append({"name": "", "phone": ""})
        self.draw()

    def check_client(self, phone, index):
        # Если в базе есть клиент с таким телефоном, подставляем имя
        client = db_query("SELECT name FROM clients WHERE phone=?", (phone,))
        if client:
            self.passengers[index]['name'] = client[0]['name']
            ui.notify(f"Найдено в базе: {client[0]['name']}")
            self.draw()

    def draw(self):
        self.container.clear()
        with self.container:
            ui.label('Список пассажиров').classes('text-lg font-bold')
            for i, p in enumerate(self.passengers):
                with ui.row().classes('w-full items-center q-gutter-sm'):
                    # Поле телефона (триггер для поиска)
                    ui.input(label='Телефон', value=p['phone'], 
                             on_change=lambda e, idx=i: [self.update(idx, 'phone', e.value), self.check_client(e.value, idx)]).classes('col')
                    # Поле имени
                    ui.input(label='Имя', value=p['name'], 
                             on_change=lambda e, idx=i: self.update(idx, 'name', e.value)).classes('col')
            ui.button('➕ Добавить пассажира', on_click=self.add_passenger).props('flat color=primary')

    def update(self, index, key, value):
        self.passengers[index][key] = value

    def get_json(self):
        return json.dumps(self.passengers, ensure_ascii=False)

# --- СТРАНИЦЫ ---
@ui.page('/')
def login_page():
    with ui.card().classes('absolute-center w-80 p-6 shadow-2xl'):
        ui.label('🚕 NOMAD TECH').classes('text-h5 text-center text-primary font-bold q-mb-md')
        l = ui.input('Логин').classes('w-full')
        p = ui.input('Пароль', password=True).classes('w-full')
        ui.button('ВОЙТИ', on_click=lambda: do_login()).classes('w-full q-mt-md')
        
        def do_login():
            if l.value == "admin" and p.value == "mn123":
                session.update({'auth': True, 'role': 'admin'})
                ui.navigate.to('/admin')
            else:
                user = db_query("SELECT * FROM drivers WHERE login=? AND password=?", (l.value, p.value))
                if user:
                    session.update({'auth': True, 'role': 'driver', 'user_id': user[0]['id']})
                    ui.navigate.to('/driver')
                else:
                    ui.notify('Ошибка входа!', color='negative')

@ui.page('/admin')
def admin_page():
    if not session['auth'] or session['role'] != 'admin': ui.navigate.to('/')
    
    with ui.header().classes('bg-primary justify-between p-2'):
        ui.label('🚀 ПАНЕЛЬ УПРАВЛЕНИЯ').classes('text-h6 text-white')
        ui.button(icon='logout', on_click=lambda: ui.navigate.to('/')).props('flat color=white')

    with ui.tabs().classes('w-full bg-grey-2 text-primary') as tabs:
        t1, t2, t3, t4, t5 = ui.tab('🆕 Рейсы'), ui.tab('➕ Новый'), ui.tab('🚖 Водители'), ui.tab('📜 Архив'), ui.tab('👥 Клиенты')

    with ui.tab_panels(tabs, value=t1).classes('w-full'):
        
        with ui.tab_panel(t1):
            trips = db_query("SELECT trips.*, drivers.name as dname FROM trips LEFT JOIN drivers ON trips.driver_id = drivers.id WHERE status='Новый'")
            for t in trips:
                with ui.card().classes('w-full q-mb-sm border-l-4 border-primary'):
                    with ui.row().classes('w-full justify-between'):
                        ui.label(t['route']).classes('text-bold')
                        ui.label(f"{t['price']}₽").classes('text-green text-bold')
                    ui.label(f"Водитель: {t['dname']}")
                    ui.button('Удалить', on_click=lambda tid=t['id']: [db_query("DELETE FROM trips WHERE id=?", (tid,), False), ui.navigate.to('/admin')]).props('small flat color=red')

        with ui.tab_panel(t2):
            route = ui.textarea('📍 Маршрут').classes('w-full')
            price = ui.number('💰 Цена рейса', value=4000).classes('w-full')
            drs = db_query("SELECT * FROM drivers")
            dr_select = ui.select({d['id']: d['name'] for d in drs}, label='🚖 Назначить водителя').classes('w-full')
            pm = PassengerManager()
            
            def save():
                if not route.value or not dr_select.value:
                    return ui.notify('Заполните маршрут и водителя!', color='warning')
                
                # Сохраняем/обновляем клиентов в справочнике
                passengers_list = pm.passengers
                for p in passengers_list:
                    if p['phone'] and p['name']:
                        db_query("INSERT OR REPLACE INTO clients (name, phone) VALUES (?, ?)", (p['name'], p['phone']), False)

                db_query("INSERT INTO trips (route, price, driver_id, status, passengers, created_at) VALUES (?,?,?,?,?,?)",
                         (route.value, price.value, dr_select.value, "Новый", pm.get_json(), datetime.now().strftime("%d.%m.%Y %H:%M")), False)
                ui.notify('✅ Рейс создан и клиенты сохранены!')
                ui.navigate.to('/admin')
            
            ui.button('🚀 ОПУБЛИКОВАТЬ РЕЙС', on_click=save).classes('w-full q-mt-md h-12 text-lg')

        with ui.tab_panel(t3):
            with ui.expansion('Добавить нового водителя'):
                with ui.card().classes('p-4'):
                    n, c, l, p = ui.input('ФИО'), ui.input('Авто'), ui.input('Логин'), ui.input('Пароль')
                    ui.button('Добавить', on_click=lambda: [db_query("INSERT INTO drivers (name, car, login, password) VALUES (?,?,?,?)", (n.value, c.value, l.value, p.value), False), ui.navigate.to('/admin')]).classes('w-full')
            
            ui.label('Список водителей:').classes('text-h6 q-mt-md')
            for d in db_query("SELECT * FROM drivers"):
                with ui.card().classes('q-mb-xs p-2'):
                    ui.label(f"👤 {d['name']} — {d['car']}")

        with ui.tab_panel(t4):
            if ui.button('📊 СКАЧАТЬ ОТЧЕТ EXCEL').classes('w-full q-mb-md'):
                df = pd.read_sql("SELECT * FROM trips WHERE status='Завершен'", sqlite3.connect(DB_PATH))
                output = BytesIO()
                df.to_excel(output)
                ui.download(output.getvalue(), 'history.xlsx')
            
            archived = db_query("SELECT * FROM trips WHERE status='Завершен' ORDER BY id DESC")
            for a in archived:
                with ui.expansion(f"{a['created_at']} | {a['route']}"):
                    ui.label(f"Цена: {a['price']}₽")
                    ui.label(f"Пассажиры: {a['passengers']}")

        # НОВАЯ ВКЛАДКА КЛИЕНТОВ
        with ui.tab_panel(t5):
            ui.label('База постоянных клиентов').classes('text-h6 q-mb-md')
            clients = db_query("SELECT * FROM clients ORDER BY name ASC")
            for c in clients:
                with ui.card().classes('q-mb-xs p-2'):
                    ui.label(f"👤 {c['name']} — 📞 {c['phone']}")

@ui.page('/driver')
def driver_page():
    if not session['auth'] or session['role'] != 'driver': ui.navigate.to('/')
    uid = session['user_id']
    
    with ui.header().classes('bg-green-7 justify-between p-2'):
        ui.label('📱 КАБИНЕТ ВОДИТЕЛЯ').classes('text-h6')
        ui.button(icon='logout', on_click=lambda: ui.navigate.to('/')).props('flat color=white')

    jobs = db_query("SELECT * FROM trips WHERE driver_id=? AND status='Новый'", (uid,))
    if not jobs: ui.label('🚀 Новых заказов пока нет. Отдыхайте!').classes('p-4 text-center w-full')
    for j in jobs:
        with ui.card().classes('m-4 shadow-lg border-2 border-green'):
            ui.label(j['route']).classes('text-h6 font-bold')
            ui.separator()
            ps = json.loads(j['passengers'])
            for p in ps:
                with ui.row().classes('w-full items-center justify-between p-2 bg-grey-1'):
                    ui.label(f"{p['name']}\n{p['phone']}").classes('whitespace-pre')
                    ui.html(f'<a href="tel:{p["phone"]}"><button style="background:#25D366; color:white; border:none; border-radius:50%; width:45px; height:45px; font-size:20px;">📞</button></a>')
            
            ui.button('✅ ЗАВЕРШИТЬ РЕЙС', on_click=lambda jid=j['id']: [db_query("UPDATE trips SET status='Завершен' WHERE id=?", (jid,), False), ui.notify('Рейс завершен!'), ui.navigate.to('/driver')]).classes('bg-green text-white w-full h-12')

# --- ЗАПУСК ---
port = int(os.environ.get("PORT", 8080))
ui.run(port=port, host='0.0.0.0', title="NOMAD TECH")
