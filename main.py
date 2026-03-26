from nicegui import ui, app
import sqlite3
import pandas as pd
from io import BytesIO
import json
import os
from datetime import datetime
import urllib.parse

# --- 1. НАСТРОЙКА БАЗЫ ДАННЫХ ---
DB_DIR = "/data" if os.path.exists("/data") else "./data"
if not os.path.exists(DB_DIR): 
    os.makedirs(DB_DIR)
DB_PATH = os.path.join(DB_DIR, "taxi.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица администраторов (для кастомного логина и пароля)
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_users 
                      (id INTEGER PRIMARY KEY, login TEXT, password TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO admin_users (id, login, password) VALUES (1, 'admin', 'mn123')")
    
    # Таблица водителей
    cursor.execute('''CREATE TABLE IF NOT EXISTS drivers 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, car TEXT, login TEXT, password TEXT)''')
    
    # Таблица рейсов (driver_id теперь может быть пустым/0)
    cursor.execute('''CREATE TABLE IF NOT EXISTS trips 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, route TEXT, price INTEGER, 
                       driver_id INTEGER DEFAULT 0, status TEXT, passengers TEXT, created_at TEXT)''')
    
    # Таблица клиентов
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
        print(f"Ошибка БД: {e}")
        ui.notify(f"Ошибка базы данных: {e}", color='negative')
        return [] if fetch else None

# Функция для генерации маршрута в Яндекс.Картах со всеми точками
def open_combined_map(route_text, passengers_json):
    try:
        ps = json.loads(passengers_json)
        # Собираем все точки. Сначала основной маршрут
        addresses = [route_text]
        # Затем адреса пассажиров
        for p in ps:
            if "name" in p and len(p['name']) > 2:
                addresses.append(p['name'])
        
        # Кодируем каждый адрес отдельно и соединяем через тильду (формат Яндекса)
        encoded_addresses = [urllib.parse.quote(a.strip()) for a in addresses if a.strip()]
        query = "~".join(encoded_addresses)
        
        url = f"https://yandex.ru/maps/?mode=routes&rtext={query}"
        ui.open(url)
    except Exception as e:
        print(e)
        ui.notify('Ошибка при формировании карты', color='negative')

# --- КОМПОНЕНТ УПРАВЛЕНИЯ ПАССАЖИРАМИ ---
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
                    ui.input(label='Телефон', value=p['phone'], 
                             on_change=lambda e, idx=i: [self.update(idx, 'phone', e.value), self.check_client(e.value, idx)]).classes('col-5')
                    ui.input(label='Имя / Адрес', value=p['name'], 
                             on_change=lambda e, idx=i: self.update(idx, 'name', e.value)).classes('col-7')
            ui.button('➕ Добавить пассажира', on_click=self.add_passenger).props('flat dense color=primary')

    def update(self, idx, key, val): 
        self.passengers[idx][key] = val
    
    def get_json(self): 
        return json.dumps(self.passengers, ensure_ascii=False)

# --- СТРАНИЦЫ ПРИЛОЖЕНИЯ ---

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
            admin_data = db_query("SELECT login, password FROM admin_users WHERE id=1")
            
            if admin_data and l.value == admin_data[0]['login'] and p.value == admin_data[0]['password']:
                app.storage.user.update({'auth': True, 'role': 'admin'})
                ui.navigate.to('/admin')
            else:
                user = db_query("SELECT * FROM drivers WHERE login=? AND password=?", (l.value, p.value))
                if user:
                    app.storage.user.update({'auth': True, 'role': 'driver', 'user_id': user[0]['id']})
                    ui.navigate.to('/driver')
                else: 
                    ui.notify('Неверный логин или пароль!', color='negative')
        
        ui.button('ВОЙТИ', on_click=do_login).classes('w-full q-mt-md h-12')

@ui.page('/admin')
def admin_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'admin':
        ui.navigate.to('/'); return

    with ui.header().classes('bg-primary justify-between p-2 items-center'):
        ui.label('MN Transfer | Админ-панель').classes('text-h6')
        ui.button(icon='logout', on_click=lambda e: [app.storage.user.clear(), ui.navigate.to('/')]).props('flat color=white')

    with ui.tabs().classes('w-full bg-grey-2') as tabs:
        t1 = ui.tab('🆕 Рейсы')
        t2 = ui.tab('➕ Новый')
        t3 = ui.tab('🚖 Водители')
        t4 = ui.tab('📜 Архив')
        t5 = ui.tab('👥 Клиенты')
        t6 = ui.tab('📊 Стат')
        t7 = ui.tab('⚙️ Настройки')

    with ui.tab_panels(tabs, value=t1).classes('w-full'):
        
        # --- ВКЛАДКА 1: АКТИВНЫЕ РЕЙСЫ (УПРАВЛЕНИЕ И ЗАВЕРШЕНИЕ) ---
        with ui.tab_panel(t1):
            trips = db_query("SELECT trips.*, IFNULL(drivers.name, 'Не назначен') as dname FROM trips LEFT JOIN drivers ON trips.driver_id = drivers.id WHERE status='Новый' ORDER BY trips.id DESC")
            drs_list = db_query("SELECT id, name FROM drivers")
            dr_options = {0: "Не назначен"}
            if drs_list:
                for d in drs_list:
                    dr_options[d['id']] = d['name']
            
            if not trips:
                ui.label('Нет активных рейсов').classes('text-h6 text-grey text-center w-full q-mt-md')

            def assign_driver(trip_id, new_driver_id):
                db_query("UPDATE trips SET driver_id=? WHERE id=?", (new_driver_id, trip_id), False)
                ui.notify('Водитель назначен', type='info')
                
            def complete_trip(trip_id, passengers_json):
                # Функция завершения перенесена сюда (для диспетчера)
                db_query("UPDATE trips SET status='Завершен' WHERE id=?", (trip_id,), False)
                
                passengers = json.loads(passengers_json)
                for p in passengers:
                    if p['phone']:
                        curr = db_query("SELECT trips_count FROM clients WHERE phone=?", (p['phone'],))
                        if curr:
                            new_c = 0 if curr[0]['trips_count'] >= 5 else curr[0]['trips_count'] + 1
                            db_query("UPDATE clients SET trips_count=?, name=? WHERE phone=?", (new_c, p['name'], p['phone']), False)
                        else:
                            db_query("INSERT INTO clients (name, phone, trips_count) VALUES (?, ?, 1)", (p['name'], p['phone']), False)
                ui.notify('✅ Рейс успешно завершен!', type='positive')
                ui.navigate.to('/admin')

            def open_edit_dialog(trip):
                with ui.dialog() as dialog, ui.card().classes('w-full max-w-md'):
                    ui.label('Редактирование рейса').classes('text-h6 font-bold q-mb-md')
                    edit_date = ui.input('Дата и время', value=trip['created_at']).classes('w-full')
                    edit_route = ui.textarea('Маршрут', value=trip['route']).classes('w-full')
                    edit_price = ui.number('Цена (₽)', value=trip['price']).classes('w-full')
                    
                    ui.label('Пассажиры').classes('text-bold q-mt-md')
                    pm_edit = PassengerManager(passengers=json.loads(trip['passengers']))
                    
                    def save_edits():
                        db_query('''UPDATE trips SET route=?, price=?, passengers=?, created_at=? WHERE id=?''', 
                                 (edit_route.value, int(edit_price.value), pm_edit.get_json(), edit_date.value, trip['id']), False)
                        ui.notify('Рейс обновлен', type='positive')
                        dialog.close()
                        ui.navigate.to('/admin')
                    
                    with ui.row().classes('w-full justify-end q-mt-md'):
                        ui.button('Отмена', on_click=dialog.close).props('flat')
                        ui.button('Сохранить', on_click=save_edits).props('color=primary')
                dialog.open()

            for t in trips:
                with ui.card().classes('w-full q-mb-sm border-l-4 border-primary'):
                    with ui.row().classes('w-full justify-between items-start no-wrap'):
                        with ui.column().classes('col'):
                            ui.label(f"📅 {t['created_at']}").classes('text-caption text-grey-7')
                            ui.label(t['route']).classes('text-bold text-lg')
                            ui.label(f"💰 {t['price']}₽")
                            
                            # Выбор водителя прямо в карточке
                            ui.select(dr_options, label='🚖 Водитель', value=t['driver_id'] if t['driver_id'] else 0,
                                      on_change=lambda e, tid=t['id']: assign_driver(tid, e.value)).classes('w-64 q-mt-xs q-mb-xs')
                            
                            ps_data = json.loads(t['passengers'])
                            for p in ps_data:
                                if p['name'] or p['phone']:
                                    ui.label(f"👤 {p['name']} ({p['phone']})").classes('text-sm text-grey-8')
                        
                        with ui.column().classes('items-center q-gutter-sm'):
                            ui.button('ЗАВЕРШИТЬ', on_click=lambda e, tid=t['id'], pss=t['passengers']: complete_trip(tid, pss)).classes('bg-green text-white w-full')
                            with ui.row():
                                ui.button(icon='map', on_click=lambda e, tr=t: open_combined_map(tr['route'], tr['passengers'])).props('flat color=blue').tooltip('Открыть карту')
                                ui.button(icon='edit', on_click=lambda e, tr=t: open_edit_dialog(tr)).props('flat color=primary').tooltip('Редактировать')
                                ui.button(icon='delete', on_click=lambda e, tid=t['id']: [db_query("DELETE FROM trips WHERE id=?", (tid,), False), ui.navigate.to('/admin')]).props('flat color=red').tooltip('Удалить')

        # --- ВКЛАДКА 2: СОЗДАНИЕ РЕЙСА (БЕЗ ВОДИТЕЛЯ) ---
        with ui.tab_panel(t2):
            ui.label('Создать новый рейс').classes('text-h6 q-mb-md')
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
            new_trip_date = ui.input('Дата и время', value=current_time).classes('w-full')
            new_route = ui.textarea('📍 Маршрут (Откуда - Куда)').classes('w-full')
            new_price = ui.number('💰 Цена (₽)', value=4000).classes('w-full')
            
            ui.label('Пассажиры и промежуточные точки:').classes('q-mt-md text-bold')
            new_pm = PassengerManager()
            
            def create_trip():
                if not new_route.value:
                    return ui.notify('Заполните маршрут!', color='warning')
                
                # driver_id передаем как 0 (Не назначен)
                db_query("INSERT INTO trips (route, price, driver_id, status, passengers, created_at) VALUES (?,?,?,?,?,?)",
                         (new_route.value, int(new_price.value), 0, "Новый", new_pm.get_json(), new_trip_date.value), False)
                ui.notify('✅ Рейс успешно создан! Назначьте водителя во вкладке "Рейсы"', type='positive')
                ui.navigate.to('/admin')
            
            ui.button('🚀 ОПУБЛИКОВАТЬ РЕЙС', on_click=create_trip).classes('w-full h-14 q-mt-lg bg-primary text-white text-lg')

        # --- ВКЛАДКА 3: УПРАВЛЕНИЕ ВОДИТЕЛЯМИ ---
        with ui.tab_panel(t3):
            with ui.expansion('➕ Добавить нового водителя').classes('w-full border rounded'):
                with ui.column().classes('p-4 w-full'):
                    dn = ui.input('ФИО')
                    dc = ui.input('Автомобиль (Марка, Номер)')
                    dl = ui.input('Логин')
                    dp = ui.input('Пароль')
                    def add_dr():
                        if dn.value and dl.value:
                            db_query("INSERT INTO drivers (name, car, login, password) VALUES (?,?,?,?)", (dn.value, dc.value, dl.value, dp.value), False)
                            ui.notify('Водитель добавлен')
                            ui.navigate.to('/admin')
                    ui.button('СОХРАНИТЬ', on_click=add_dr).classes('w-full q-mt-sm')

            ui.label('Список водителей:').classes('q-mt-md text-bold')
            for d in db_query("SELECT * FROM drivers"):
                with ui.card().classes('w-full q-mb-xs p-2'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f"{d['name']} | {d['car']} (Логин: {d['login']})")
                        ui.button(icon='delete', on_click=lambda e, did=d['id']: [db_query("DELETE FROM drivers WHERE id=?", (did,), False), ui.navigate.to('/admin')]).props('flat color=red')

        # --- ВКЛАДКА 4: АРХИВ ---
        with ui.tab_panel(t4):
            def export():
                data = db_query("SELECT created_at as Дата, route as Маршрут, price as Цена FROM trips WHERE status='Завершен' ORDER BY id DESC")
                if not data: return ui.notify('Архив пуст')
                df = pd.DataFrame(data)
                out = BytesIO()
                with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                ui.download(out.getvalue(), 'Archive.xlsx')
            
            ui.button('📊 СКАЧАТЬ АРХИВ (EXCEL)', icon='download', on_click=export).classes('w-full bg-green text-white h-12 q-mb-md')
            
            for a in db_query("SELECT * FROM trips WHERE status='Завершен' ORDER BY id DESC"):
                with ui.expansion(f"{a['created_at']} | {a['route'][:30]}..."):
                    ui.label(f"Полный маршрут: {a['route']}")
                    ui.label(f"Цена: {a['price']}₽")

        # --- ВКЛАДКА 5: БАЗА КЛИЕНТОВ ---
        with ui.tab_panel(t5):
            for cl in db_query("SELECT * FROM clients ORDER BY trips_count DESC"):
                with ui.card().classes('w-full q-mb-xs p-2'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f"👤 {cl['name']} ({cl['phone']})")
                        ui.badge(f"Поездок: {cl['trips_count']}", color='orange' if cl['trips_count'] >= 5 else 'grey')

        # --- ВКЛАДКА 6: СТАТИСТИКА ---
        with ui.tab_panel(t6):
            stats = db_query('''SELECT drivers.name, SUM(trips.price) as total 
                                FROM trips JOIN drivers ON trips.driver_id = drivers.id 
                                WHERE status="Завершен" GROUP BY drivers.id''')
            if not stats:
                ui.label('Нет завершенных рейсов').classes('text-grey')
            for s in stats:
                ui.label(f"🚖 {s['name']}: {s['total']} ₽").classes('text-h6 border-b w-full p-2')
                
        # --- ВКЛАДКА 7: НАСТРОЙКИ (СМЕНА ЛОГИНА/ПАРОЛЯ) ---
        with ui.tab_panel(t7):
            ui.label('Смена доступов Администратора').classes('text-h6 q-mb-md')
            ui.label('Внимание: Если вы забудете эти данные, потребуется вмешательство разработчика.').classes('text-red text-sm q-mb-md')
            
            admin_data = db_query("SELECT login, password FROM admin_users WHERE id=1")[0]
            
            new_login = ui.input('Новый логин', value=admin_data['login']).classes('w-full q-mb-sm')
            new_pass = ui.input('Новый пароль', value=admin_data['password']).classes('w-full q-mb-sm')
            
            def change_admin_creds():
                if new_login.value and new_pass.value:
                    db_query("UPDATE admin_users SET login=?, password=? WHERE id=1", (new_login.value, new_pass.value), False)
                    ui.notify('✅ Логин и пароль успешно изменены!', type='positive')
                else:
                    ui.notify('Заполните оба поля!', color='negative')
                    
            ui.button('СОХРАНИТЬ ДОСТУПЫ', on_click=change_admin_creds).classes('w-full bg-primary text-white')

@ui.page('/driver')
def driver_page():
    if not app.storage.user.get('auth') or app.storage.user.get('role') != 'driver':
        ui.navigate.to('/'); return
    
    uid = app.storage.user.get('user_id')
    driver_info = db_query("SELECT name FROM drivers WHERE id=?", (uid,))[0]
    
    with ui.header().classes('bg-green-7 justify-between p-2 items-center'):
        ui.label(f"Водитель: {driver_info['name']}").classes('text-h6')
        ui.button(icon='logout', on_click=lambda e: [app.storage.user.clear(), ui.navigate.to('/')]).props('flat color=white')

    jobs = db_query("SELECT * FROM trips WHERE driver_id=? AND status='Новый'", (uid,))
    
    if not jobs:
        ui.label('Сейчас у вас нет назначенных рейсов').classes('absolute-center text-grey text-h6 text-center')

    for j in jobs:
        with ui.card().classes('m-4 shadow-lg border-2 border-green w-full'):
            ui.label(f"📅 {j['created_at']}").classes('text-grey-7 text-sm')
            ui.label(j['route']).classes('text-h6 font-bold q-mb-md')
            
            ps = json.loads(j['passengers'])
            ui.label('Пассажиры:').classes('text-sm text-grey q-mb-xs')
            for p in ps:
                with ui.row().classes('w-full justify-between p-2 bg-grey-1 items-center rounded q-mb-xs border'):
                    ui.label(f"{p['name']}\n{p['phone']}").classes('whitespace-pre font-bold text-base')
                    if p['phone']:
                        ui.html(f'<a href="tel:{p["phone"]}"><button style="background:#25D366;color:white;border:none;border-radius:50%;width:45px;height:45px;font-size:20px;cursor:pointer;">📞</button></a>')

# Запуск
ui.run(port=int(os.environ.get("PORT", 8080)), host='0.0.0.0', title="MN Transfer", storage_secret="MN_TRANSFER_PRO_KEY_999")
