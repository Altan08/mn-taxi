import streamlit as st
from supabase import create_client, Client
import streamlit.components.v1 as components
from datetime import datetime

# Подключение к базе
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer System", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None
    st.session_state.user_id = None

# --- ВХОД В СИСТЕМУ ---
if not st.session_state.auth:
    st.title("🚕 Вход в систему")
    log_in = st.text_input("Логин")
    pwd_in = st.text_input("Пароль", type="password")
    if st.button("ВОЙТИ"):
        if log_in == "admin" and pwd_in == "mn123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        else:
            dr = supabase.table("drivers").select("*").eq("login", log_in).eq("password", pwd_in).execute()
            if dr.data:
                st.session_state.auth = True
                st.session_state.role = "driver"
                st.session_state.user_id = dr.data[0]['id']
                st.rerun()
            else:
                st.error("Неверные данные")
else:
    # --- ИНТЕРФЕЙС АДМИНА ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 ДИСПЕТЧЕР")
        menu = st.sidebar.radio("Меню", ["🆕 Новый рейс", "🚖 Водители", "Выход"])

        if menu == "🆕 Новый рейс":
            st.header("🚐 Создать заказ")
            route = st.text_area("Маршрут (например: Элиста - Волгоград)")
            price = st.number_input("Цена (₽)", value=4000)
            
            dr_res = supabase.table("drivers").select("*").execute()
            dr_opts = {f"{d['name']} ({d['car']})": d['id'] for d in dr_res.data}
            sel_dr = st.selectbox("Водитель", options=list(dr_opts.keys()))

            if st.button("ОТПРАВИТЬ ЗАКАЗ"):
                supabase.table("trips").insert({
                    "driver_id": dr_opts[sel_dr],
                    "route": route,
                    "price": price,
                    "status": "Новый"
                }).execute()
                st.success("Заказ отправлен!")

        elif menu == "🚖 Водители":
            st.header("Управление водителями")
            with st.expander("Добавить водителя"):
                n = st.text_input("Имя")
                c = st.text_input("Машина")
                l = st.text_input("Логин")
                p = st.text_input("Пароль")
                if st.button("Сохранить"):
                    supabase.table("drivers").insert({"name":n, "car":c, "login":l, "password":p}).execute()
                    st.rerun()
            
            res = supabase.table("drivers").select("*").execute()
            for d in res.data:
                col1, col2 = st.columns([4, 1])
                col1.write(f"👤 {d['name']} | {d['car']} (Логин: {d['login']})")
                if col2.button("❌", key=f"d_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ИНТЕРФЕЙС ВОДИТЕЛЯ ---
    else:
        st.title("📱 Мои заказы")
        my_trips = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).execute()
        if my_trips.data:
            for t in my_trips.data:
                with st.expander(f"🚩 Заказ №{t['id']}", expanded=True):
                    st.write(f"🗺️ **Путь:** {t['route']}")
                    st.write(f"💰 **Оплата:** {t['price']} ₽")
                    if st.button("✅ Завершить рейс", key=f"f_{t['id']}"):
                        supabase.table("trips").delete().eq("id", t['id']).execute()
                        st.rerun()
        else:
            st.info("Пока нет новых заказов.")

    if st.sidebar.button("Выйти"):
        st.session_state.auth = False
        st.rerun()
