import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- ТВОИ ДАННЫЕ ИЗ SUPABASE ---
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP5OZzMPQaLocvBe6iFxAw_oOvO8Xpm"

supabase: Client = create_client(URL, KEY)

# --- ЛОГИКА ПРИЛОЖЕНИЯ ---
st.set_page_config(page_title="Трансфер МН", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'role': None, 'user_id': None})

if not st.session_state.auth:
    st.title("🚕 Трансфер МН: Вход")
    login = st.text_input("Логин")
    pwd = st.text_input("Пароль", type="password")
    if st.button("ВОЙТИ"):
        if login == "admin" and pwd == "mn123":
            st.session_state.update({'auth': True, 'role': 'admin'})
            st.rerun()
        else:
            res = supabase.table("drivers").select("*").eq("name", login).eq("password", pwd).execute()
            if res.data:
                st.session_state.update({'auth': True, 'role': 'driver', 'user_id': res.data[0]['id']})
                st.rerun()
            else: st.error("Ошибка входа")

elif st.session_state.role == "admin":
    menu = st.sidebar.radio("Меню", ["Новый заказ", "Архив", "Водители", "Выход"])
    if menu == "Выход": 
        st.session_state.auth = False
        st.rerun()
    
    if menu == "Новый заказ":
        st.subheader("Оформление поездки")
        phone = st.text_input("Телефон клиента")
        route = st.selectbox("Маршрут", ["Элиста - Волгоград", "Волгоград - Элиста"])
        addr = st.text_area("Адреса (Откуда -> Куда)")
        dr_list = supabase.table("drivers").select("*").execute().data
        dr_options = {f"{d['name']} ({d['car']})": d['id'] for d in dr_list}
        if dr_options:
            target = st.selectbox("Назначить водителя", list(dr_options.keys()))
            if st.button("ОТПРАВИТЬ ЗАКАЗ"):
                supabase.table("orders").insert({
                    "phone": phone, "route": route, "address": addr, 
                    "status": "новое", "driver_id": dr_options[target]
                }).execute()
                st.success("Заказ отправлен!")
        else: st.warning("Сначала добавьте водителей во вкладке Водители")

    elif menu == "Водители":
        st.subheader("Добавить водителя")
        n_log = st.text_input("Логин")
        n_pwd = st.text_input("Пароль")
        n_car = st.text_input("Машина")
        if st.button("Создать"):
            supabase.table("drivers").insert({"name": n_log, "password": n_pwd, "car": n_car}).execute()
            st.success("Водитель добавлен!")

else:
    st.title("📱 Мои заказы")
    my_orders = supabase.table("orders").select("*").eq("driver_id", st.session_state.user_id).neq("status", "выполнено").execute().data
    for o in my_orders:
        with st.expander(f"📍 Заказ №{o['id']}", expanded=True):
            st.write(f"📞 Тел: {o['phone']}")
            st.write(f"🏠 Адрес: {o['address']}")
            if st.button("ВЫПОЛНЕНО ✅", key=o['id']):
                supabase.table("orders").update({"status": "выполнено"}).eq("id", o['id']).execute()
                st.rerun()
    if st.button("Выход"): 
        st.session_state.auth = False
        st.rerun()
