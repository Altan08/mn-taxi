from nicegui import ui, app
from supabase import create_client, Client
import pandas as pd
from io import BytesIO
from geopy.geocoders import Nominatim
import folium
import json
import os

# --- 1. КОНФИГУРАЦИЯ И ПОДКЛЮЧЕНИЕ ---
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

# Глобальное состояние сессии
session = {'auth': False, 'role': None, 'user_id': None, 'passengers': []}

def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="mn_volga_nicegui_final")
        loc = geolocator.geocode(address, timeout=10)
        return [loc.latitude, loc.longitude] if loc else None
    except: return None

# --- ЗАГРУЗКА ДАННЫХ ДЛЯ ТАБЛИЦ ---
def load_drivers():
    try:
        res = supabase.table("drivers").select("*").execute()
        return res.data if res.data else []
    except: return []

def load_trips(status="Новый", driver_id=None):
    try:
        query = supabase.table("trips").select("*, drivers(name)")
        if driver_id:
            query = query.eq("driver_id", driver_id)
        res = query.eq("status", status).order("created_at", desc=True).execute()
        return res.data if res.data else []
    except: return []

# --- КОМПОНЕНТ ДИНАМИЧЕСКОГО СПИСКА ПАССАЖИРОВ ---
class PassengerManager:
    def __init__(self, passengers=[]):
        self.passengers = passengers if passengers else [{"name": "", "phone": ""}]
        self.container = ui.column().classes('w-full border p-2 rounded')
        self.draw()

    def add_passenger(self):
        self.passengers.append({"name": "", "phone": ""})
        self.draw()

    def remove_passenger(self, index):
        if len(self.passengers) > 1:
            self.passengers.pop(index)
            self.draw()

    def draw(self):
        self.container.clear()
        with self.container:
            ui.label('Список пассажиров').classes('text-lg q-mb-sm')
            for i, p in enumerate(self.passengers):
                with ui.row().classes('w-full items-center justify-between q-mb-xs'):
                    ui.input(label=f'Имя {i+1}', value=p['name'], 
                             on_change=lambda e, idx=i: self.update_data(idx, 'name', e.value)).classes('col-5')
                    ui.input(label=f'Тел {i+1}', value=p['phone'],
                             on_change=lambda e, idx=i: self.update_data(idx, 'phone', e.value)).classes('col-5')
                    if i > 0:
                        ui.button(icon='remove', on_click=lambda idx=i: self.remove_passenger(idx)).props('flat color=negative')
            ui.button('➕ Пассажир', on_click=self.add_passenger).classes('q-mt-sm')

    def update_data(self, index, key, value):
        self.passengers[index][key] = value

    def get_data(self):
        return self.passengers

# --- КОМПОНЕНТ КАРТЫ ВОЛГОГРАДА ---
class VolgogradMap:
    def __init__(self):
        self.map_container = ui.html().classes('w-full h-96 border rounded q-mt-md')
        self.draw()

    def draw(self):
        trips = load_trips(status="Новый")
        m = folium.Map(location=[48.7080, 44.5133], zoom_start=11)
        for t in trips:
            coords = get_coords(t['route'])
            if coords:
                folium.Marker(coords, popup=f"Рейс: {t['route']}\nОплата: {t['price']}₽").add_to(m)
        self.map_container.content = m._repr_html_()

# --- СТРАНИЦА ВХОДА ---
@ui.page('/')
def login_page():
    session.update({'auth': False, 'role': None, 'user_id': None})
    with ui.card().classes('absolute-center w-80 shadow-2xl p-4'):
        ui.label('🚕 MN Transfer PRO').classes('text-h5 text-center q-mb-md text-primary')
        l = ui.input('Логин').classes('w-full')
        p = ui.input('Пароль', password=True).classes('w-full')
        
        def do_login():
            if l.value == "admin" and p.value == "mn123":
                session.update({'auth': True, 'role': 'admin'})
                ui.navigate.to('/admin')
            else:
                try:
                    res = supabase.table("drivers").select("*").eq("login", l.value).eq("password", p.value).execute()
                    if res.data:
                        session.update({'auth': True, 'role': 'driver', 'user_id': res.data[0]['id']})
                        ui.navigate.to('/driver')
                    else:
                        ui.notify('Неверный логин или пароль!', color='negative')
                except Exception as e:
                    ui.notify(f'Ошибка сети: {e}', color='warning')

        ui.button('ВОЙТИ', on_click=do_login).classes('w-full q-mt-lg')

# --- ПАНЕЛЬ АДМИНИСТРАТОРА ---
@ui.page('/admin')
def admin_page():
    if not session['auth'] or session['role'] != 'admin': ui.navigate.to('/')
    
    with ui.header().classes('bg-primary items-center justify-between shadow-2'):
        ui.label('🚀 АДМИН-ПАНЕЛЬ | NOMAD TECH').classes('text-h6 text-white')
        ui.button(icon='logout', on_click=lambda: ui.navigate.to('/')).props('flat color=white')

    with ui.tabs().classes('w-full') as tabs:
        t1 = ui.tab('🆕 Рейсы в работе')
        t2 = ui.tab('➕ Создать рейс')
        t3 = ui.tab('🗺️ Карта Волгограда')
        t4 = ui.tab('📜 Архив и Excel')
        t5 = ui.tab('🚖 Водители')

    with ui.tab_panels(tabs, value=t1).classes('w-full p-4'):
        
        # --- ТАБ 1: РЕЙСЫ В РАБОТЕ ---
        with ui.tab_panel(t1):
            ui.label('Текущие активные заказы').classes('text-h6 q-mb-md')
            trips = load_trips(status="Новый")
            if not trips: ui.label('Нет активных рейсов').classes('text-subtitle1')
            
            for t in trips:
                with ui.card().classes('w-full q-mb-sm shadow-1 border'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"🚩 {t['route']}").classes('text-weight-bold')
                        ui.label(f"💰 {t['price']}₽").classes('text-h6 text-green')
                    ui.label(f"🚖 Водитель: {t['drivers']['name'] if t['drivers'] else '?'}")
                    
                    passengers = t['passengers'] if t['passengers'] else []
                    with ui.expansion(f"👤 Пассажиры ({len(passengers)})"):
                        for p in passengers:
                            ui.label(f"{p['name']} - {p['phone']}")

                    with ui.row().classes('w-full q-mt-sm justify-end'):
                        def delete_trip(tid=t['id']):
                            supabase.table("trips").delete().eq("id", tid).execute()
                            ui.notify(f'Рейс удален!')
                            ui.navigate.to('/admin') 

                        ui.button(icon='delete', on_click=delete_trip).props('flat color=negative')

        # --- ТАБ 2: СОЗДАНИЕ РЕЙСА ---
        with ui.tab_panel(t2):
            ui.label('Форма создания заказа').classes('text-h6 q-mb-md')
            route = ui.textarea('📍 Маршрут (укажите Волгоград...)').classes('w-full')
            price = ui.number('💰 Цена (₽)', value=4000).classes('w-full')
            
            drivers = load_drivers()
            dr_options = {d['id']: d['name'] for d in drivers}
            dr_select = ui.select(dr_options, label='🚖 Назначить водителя').classes('w-full')

            passenger_manager = PassengerManager()

            def save_trip():
                try:
                    if not route.value or not dr_select.value:
                        ui.notify('⚠️ Заполните маршрут и выберите водителя!', color='warning')
                        return
                    
                    payload = {
                        "route": str(route.value),
                        "price": int(price.value or 0),
                        "driver_id": dr_select.value,
                        "status": "Новый",
                        "passengers": passenger_manager.get_data()
                    }
                    supabase.table("trips").insert(payload).execute()
                    ui.notify('✅ Рейс успешно создан!', color='positive')
                    ui.navigate.to('/admin') 
                except Exception as e:
                    ui.notify(f'❌ Ошибка БД: {e}', color='negative')

            ui.button('💾 СОХРАНИТЬ И ОПУБЛИКОВАТЬ', on_click=save_trip).classes('w-full q-mt-lg')

        # --- ТАБ 3: КАРТА ---
        with ui.tab_panel(t3):
            ui.label('Геолокация активных заказов').classes('text-h6 q-mb-md')
            VolgogradMap()

        # --- ТАБ 4: АРХИВ + EXCEL ---
        with ui.tab_panel(t4):
            ui.label('История завершенных поездок').classes('text-h6 q-mb-md')
            
            def export_excel():
                data = load_trips(status="Завершен")
                if not data: ui.notify('Архив пуст'); return
                df = pd.DataFrame(data)
                df['Водитель'] = df['drivers'].apply(lambda x: x['name'] if x else "?")
                df['Пассажиры'] = df['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                output = BytesIO()
                df[['created_at','route','Водитель','Пассажиры','price']].to_excel(output, index=False)
                ui.download(output.getvalue(), 'archive.xlsx')
            
            ui.button('📊 СКАЧАТЬ EXCEL ОТЧЕТ', on_click=export_excel).classes('w-full q-mb-md')

            archived = load_trips(status="Завершен")
            for a in archived:
                with ui.expansion(f"{a['created_at'][:10]} | {a['route']}"):
                    ui.label(f"Цена: {a['price']} ₽")
                    ui.label(f"Пассажиры: {json.dumps(a['passengers'], ensure_ascii=False)}")

        # --- ТАБ 5: ВОДИТЕЛИ ---
        with ui.tab_panel(t5):
            ui.label('Управление персоналом').classes('text-h6 q-mb-md')
            
            with ui.expansion("➕ Зарегистрировать водителя"):
                n, c, l, p = ui.input("Имя"), ui.input("Авто"), ui.input("Логин"), ui.input("Пароль")
                def add_dr():
                    try:
                        if not n.value or not l.value or not p.value:
                            ui.notify('⚠️ Имя, логин и пароль обязательны!', color='warning')
                            return

                        payload = {
                            "name": n.value,
                            "car": c.value,
                            "login": l.value,
                            "password": p.value
                        }
                        supabase.table("drivers").insert(payload).execute()
                        ui.notify('✅ Водитель добавлен!', color='positive')
                        ui.navigate.to('/admin')
                    except Exception as e:
                        ui.notify(f'❌ Ошибка добавления: {e}', color='negative')
                
                ui.button("ОК", on_click=add_dr).classes('q-mt-md')

            d_list = load_drivers()
            for d in d_list:
                with ui.card().classes('w-full q-mb-xs shadow-1 border'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"👤 {d['name']} | {d['car']}")
                        ui.button(icon='delete', on_click=lambda did=d['id']: supabase.table("drivers").delete().eq("id", did).execute() or ui.navigate.to('/admin')).props('flat color=negative')

# --- КАБИНЕТ ВОДИТЕЛЯ ---
@ui.page('/driver')
def driver_page():
    if not session['auth'] or session['role'] != 'driver': ui.navigate.to('/')
    uid = session['user_id']
    
    with ui.header().classes('bg-green items-center justify-between shadow-2'):
        ui.label('📱 КАБИНЕТ ВОДИТЕЛЯ').classes('text-h6 text-white')
        ui.button(icon='logout', on_click=lambda: ui.navigate.to('/')).props('flat color=white')

    with ui.tabs().classes('w-full') as tabs:
        t1 = ui.tab('🆕 Мои заказы')
        t2 = ui.tab('📜 Моя история')

    with ui.tab_panels(tabs, value=t1).classes('w-full p-4'):
        
        with ui.tab_panel(t1):
            ui.label('Активные рейсы').classes('text-h6 q-mb-md')
            my_jobs = load_trips(status="Новый", driver_id=uid)
            if not my_jobs: ui.label('Пока нет новых заказов').classes('text-subtitle1')
            
            for j in my_jobs:
                with ui.card().classes('w-full q-mb-md shadow-2 border green-border'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(f"🚩 {j['route']}").classes('text-weight-bold text-lg')
                        ui.label(f"💰 {j['price']}₽").classes('text-h6 text-green')
                    ui.separator()
                    
                    passengers = j['passengers'] if j['passengers'] else []
                    for p in passengers:
                        with ui.row().classes('w-full items-center justify-between border-b p-1'):
                            ui.label(f"👤 {p['name']}\n📞 {p['phone']}")
                            ui.html(f'<a href="tel:{p["phone"]}"><button style="width:50px;height:50px;background:#25D366;color:white;border:none;padding:10px;border-radius:50%;cursor:pointer;font-size:20px;">📞</button></a>')

                    def finish_trip(jid=j['id']):
                        supabase.table("trips").update({"status": "Завершен"}).eq("id", jid).execute()
                        ui.notify('Рейс завершен, спасибо!', color='positive')
                        ui.navigate.to('/driver')

                    ui.button('✅ ЗАВЕРШИТЬ РЕЙС', on_click=finish_trip).classes('w-full q-mt-md bg-green text-white')

        with ui.tab_panel(t2):
            ui.label('Завершенные рейсы').classes('text-h6 q-mb-md')
            h = load_trips(status="Завершен", driver_id=uid)
            ui.metric("Выручка всего", f"{sum(i['price'] for i in h)} ₽")
            for t in h:
                with ui.expansion(f"{t['created_at'][:10]} | {t['route']}"):
                    ui.label(f"Оплата: {t['price']} ₽")

# --- ЗАПУСК ---
port = int(os.environ.get("PORT", 8080))
ui.run(port=port, host='0.0.0.0', title="NOMAD TECH", favicon="🚕")
