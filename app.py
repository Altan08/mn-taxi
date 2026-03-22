import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
from datetime import datetime
from io import BytesIO
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim

# 1. ПОДКЛЮЧЕНИЕ К БАЗЕ SUPABASE
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO | NOMAD TECH", layout="wide")

# Инициализация состояний сессии
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'role': None, 'user_id': None})

# Функция для получения координат адреса (Геокодинг)
def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="nomad_tech_app")
        location = geolocator.geocode(address)
        if location:
            return [location.latitude, location.longitude]
    except:
        return None
    return None

# --- БЛОК АВТОРИЗАЦИИ ---
if not st.session_state.auth:
    st.title("🚕 MN Transfer PRO")
    st.subheader("Система управления трансферами")
    col1, col2 = st.columns(2)
    l_in = col1.text_input("Логин")
    p_in = col2.text_input("Пароль", type="password")
    
    if st.button("ВОЙТИ В СИСТЕМУ", use_container_width=True):
        if l_in == "admin" and p_in == "mn123":
            st.session_state.update({'auth': True, 'role': 'admin'})
            st.rerun()
        else:
            dr_res = supabase.table("drivers").select("*").eq("login", l_in).eq("password", p_in).execute()
            if dr_res.data:
                st.session_state.update({'auth': True, 'role': 'driver', 'user_id': dr_res.data[0]['id']})
                st.rerun()
            else:
                st.error("Ошибка: Неверные данные для входа")

else:
    # --- ИНТЕРФЕЙС АДМИНИСТРАТОРА ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 АДМИНИСТРАТОР")
        menu = st.sidebar.radio("Навигация", ["🆕 Новый рейс", "🗺️ Карта заказов", "📜 Архив рейсов", "🚖 База водителей", "Выход"])

        if menu == "🆕 Новый рейс":
            st.header("Управление рейсами")
            
            # Логика загрузки данных при редактировании
            e_id = st.query_params.get("edit_id")
            if e_id and 'ed_load' not in st.session_state:
                res = supabase.table("trips").select("*").eq("id", e_id).execute()
                if res.data:
                    st.session_state.ed_load = res.data[0]
                    st.session_state.p_list = res.data[0]['passengers']
            
            if 'p_list' not in st.session_state:
                st.session_state.p_list = [{"name": "", "phone": ""}]

            st.subheader("Данные пассажиров")
            for i, p in enumerate(st.session_state.p_list):
                c1, c2, c3 = st.columns([2, 2, 0.5])
                st.session_state.p_list[i]["name"] = c1.text_input(f"Имя {i+1}", value=p["name"], key=f"pname_{i}")
                st.session_state.p_list[i]["phone"] = c2.text_input(f"Телефон {i+1}", value=p["phone"], key=f"pphone_{i}")
                if c3.button("❌", key=f"remove_{i}"):
                    st.session_state.p_list.pop(i)
                    st.rerun()
            
            if st.button("➕ Добавить пассажира"):
                st.session_state.p_list.append({"name": "", "phone": ""})
                st.rerun()

            st.divider()
            
            # Детали рейса
            ex = st.session_state.get('ed_load')
            route = st.text_area("📍 Маршрут (например: Элиста, ул. Ленина 1)", value=ex['route'] if ex else "")
            price = st.number_input("💰 Стоимость рейса (₽)", value=int(ex['price']) if ex else 4000)
            
            # Список водителей из БД
            drivers_data = supabase.table("drivers").select("*").execute()
            drv_dict = {f"{d['name']} ({d['car']})": d['id'] for d in drivers_data.data}
            selected_drv = st.selectbox("🚖 Назначить водителя", options=list(drv_dict.keys()))

            if st.button("💾 СОХРАНИТЬ ДАННЫЕ", use_container_width=True):
                trip_payload = {
                    "route": route, 
                    "price": price, 
                    "driver_id": drv_dict[selected_drv], 
                    "passengers": st.session_state.p_list, 
                    "status": "Новый"
                }
                if e_id:
                    supabase.table("trips").update(trip_payload).eq("id", e_id).execute()
                    st.query_params.clear()
                    if 'ed_load' in st.session_state: del st.session_state.ed_load
                else:
                    supabase.table("trips").insert(trip_payload).execute()
                
                st.session_state.p_list = [{"name": "", "phone": ""}]
                st.success("Рейс обновлен/создан!")
                st.rerun()

            st.divider()
            st.subheader("📡 Активные рейсы")
            active_trips = supabase.table("trips").select("*, drivers(name)").eq("status", "Новый").execute()
            for t in active_trips.data:
                ca, cb, cc = st.columns([4, 1, 1])
                ca.write(f"🚩 **{t['route']}** | 🚖 {t['drivers']['name'] if t['drivers'] else 'Не назначен'}")
                if cb.button("📝", key=f"edit_btn_{t['id']}"):
                    st.query_params.edit_id = t['id']
                    if 'ed_load' in st.session_state: del st.session_state.ed_load
                    st.rerun()
                if cc.button("🗑️", key=f"del_btn_{t['id']}"):
                    supabase.table("trips").delete().eq("id", t['id']).execute()
                    st.rerun()

        elif menu == "🗺️ Карта заказов":
            st.header("География активных заказов")
            active = supabase.table("trips").select("*").eq("status", "Новый").execute()
            # Центрируем карту на Элисте
            m = folium.Map(location=[46.3078, 44.2558], zoom_start=7)
            for t in active.data:
                coords = get_coords(t['route'])
                if coords:
                    folium.Marker(
                        coords, 
                        popup=f"Рейс: {t['route']}\nЦена: {t['price']}₽",
                        icon=folium.Icon(color="blue", icon="car", prefix="fa")
                    ).add_to(m)
            st_folium(m, width="100%", height=600)

        elif menu == "📜 Архив рейсов":
            st.header("История завершенных поездок")
            archive = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            if archive.data:
                if st.button("📊 ЭКСПОРТ В EXCEL"):
                    output = BytesIO()
                    df = pd.DataFrame(archive.data)
                    df['Водитель'] = df['drivers'].apply(lambda x: x['name'] if x else "N/A")
                    df['Список пассажиров'] = df['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                    df[['created_at', 'route', 'Водитель', 'Список пассажиров', 'price']].to_excel(output, index=False)
                    st.download_button("Скачать отчет .xlsx", output.getvalue(), "otchet_mn_transfer.xlsx")
                
                for t in archive.data:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                        st.write(f"**Сумма:** {t['price']} ₽")
                        for p in t['passengers']:
                            st.write(f"👤 {p['name']} — 📞 {p['phone']}")

        elif menu == "🚖 База водителей":
            st.header("Управление персоналом")
            with st.expander("➕ Зарегистрировать нового водителя"):
                n = st.text_input("ФИО водителя")
                c = st.text_input("Автомобиль (Марка/Госномер)")
                l = st.text_input("Логин")
                p = st.text_input("Пароль")
                if st.button("Добавить в базу"):
                    supabase.table("drivers").insert({"name": n, "car": c, "login": l, "password": p}).execute()
                    st.rerun()
            
            drivers = supabase.table("drivers").select("*").execute()
            for d in drivers.data:
                c1, c2 = st.columns([5, 1])
                c1.write(f"👤 **{d['name']}** | 🚗 {d['car']} (Логин: {d['login']})")
                if c2.button("❌", key=f"dr_del_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ИНТЕРФЕЙС ВОДИТЕЛЯ ---
    else:
        st.sidebar.title("📱 КАБИНЕТ ВОДИТЕЛЯ")
        dr_menu = st.sidebar.radio("Меню", ["🆕 Мои заказы", "📜 Моя история", "Выход"])
        
        if dr_menu == "🆕 Мои заказы":
            jobs = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Новый").execute()
            if jobs.data:
                for j in jobs.data:
                    with st.container(border=True):
                        st.subheader(f"🚩 {j['route']}")
                        st.write(f"💰 Сумма к получению: **{j['price']} ₽**")
                        st.divider()
                        for p in j['passengers']:
                            cn, cb = st.columns([3, 1])
                            cn.write(f"👤 {p['name']}\n📞 {p['phone']}")
                            # Кнопка звонка
                            cb.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%;background-color:#25D366;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;">📞 Звонок</button></a>', unsafe_allow_html=True)
                        
                        st.divider()
                        if st.button("✅ ЗАВЕРШИТЬ РЕЙС", key=f"f_job_{j['id']}", use_container_width=True):
                            supabase.table("trips").update({"status": "Завершен"}).eq("id", j['id']).execute()
                            st.rerun()
            else:
                st.info("У вас нет активных заказов на данный момент.")

        elif dr_menu == "📜 Моя история":
            h = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Завершен").execute()
            st.metric("Заработано всего", f"{sum(i['price'] for i in h.data)} ₽")
            for t in h.data:
                with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                    st.write(f"Оплата: {t['price']} ₽")
                    for p in t['passengers']:
                        st.write(f"👤 {p['name']} ({p['phone']})")

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
