import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
from datetime import datetime
from io import BytesIO

# 1. НАСТРОЙКИ ПОДКЛЮЧЕНИЯ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO", layout="wide")

# Инициализация сессии
if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'role': None, 'user_id': None})

# --- БЛОК АВТОРИЗАЦИИ ---
if not st.session_state.auth:
    st.title("🚕 MN Transfer PRO")
    col1, col2 = st.columns(2)
    login_input = col1.text_input("Логин")
    pass_input = col2.text_input("Пароль", type="password")
    
    if st.button("ВОЙТИ", use_container_width=True):
        if login_input == "admin" and pass_input == "mn123":
            st.session_state.update({'auth': True, 'role': 'admin'})
            st.rerun()
        else:
            res = supabase.table("drivers").select("*").eq("login", login_input).eq("password", pass_input).execute()
            if res.data:
                st.session_state.update({'auth': True, 'role': 'driver', 'user_id': res.data[0]['id']})
                st.rerun()
            else:
                st.error("Неверный логин или пароль")

else:
    # --- ИНТЕРФЕЙС АДМИНИСТРАТОРА ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 ПАНЕЛЬ АДМИНА")
        menu = st.sidebar.radio("Навигация", ["🆕 Новый рейс", "📜 Архив", "🚖 Водители", "Выход"])

        if menu == "🆕 Новый рейс":
            st.header("Управление рейсами")
            
            # Логика редактирования
            edit_id = st.query_params.get("edit_id")
            if edit_id and 'edit_load' not in st.session_state:
                res = supabase.table("trips").select("*").eq("id", edit_id).execute()
                if res.data:
                    st.session_state.edit_load = res.data[0]
                    st.session_state.p_list = res.data[0]['passengers']
            
            if 'p_list' not in st.session_state:
                st.session_state.p_list = [{"name": "", "phone": ""}]

            # Список пассажиров
            st.subheader("Пассажиры")
            for i, p in enumerate(st.session_state.p_list):
                c1, c2, c3 = st.columns([2, 2, 0.5])
                st.session_state.p_list[i]["name"] = c1.text_input(f"Имя {i+1}", value=p["name"], key=f"p_n_{i}")
                st.session_state.p_list[i]["phone"] = c2.text_input(f"Телефон {i+1}", value=p["phone"], key=f"p_p_{i}")
                if c3.button("❌", key=f"del_{i}"):
                    st.session_state.p_list.pop(i)
                    st.rerun()
            
            if st.button("➕ Добавить пассажира"):
                st.session_state.p_list.append({"name": "", "phone": ""})
                st.rerun()

            st.divider()
            
            # Детали рейса
            curr = st.session_state.get('edit_load')
            route = st.text_area("📍 Маршрут", value=curr['route'] if curr else "")
            price = st.number_input("💰 Сумма (₽)", value=int(curr['price']) if curr else 4000)
            
            # Выбор водителя
            drv_res = supabase.table("drivers").select("*").execute()
            drv_dict = {f"{d['name']} ({d['car']})": d['id'] for d in drv_res.data}
            selected_drv = st.selectbox("🚖 Назначить водителя", options=list(drv_dict.keys()))

            if st.button("💾 СОХРАНИТЬ РЕЙС", use_container_width=True):
                trip_data = {
                    "route": route,
                    "price": price,
                    "driver_id": drv_dict[selected_drv],
                    "passengers": st.session_state.p_list,
                    "status": "Новый"
                }
                if edit_id:
                    supabase.table("trips").update(trip_data).eq("id", edit_id).execute()
                    st.query_params.clear()
                    if 'edit_load' in st.session_state: del st.session_state.edit_load
                else:
                    supabase.table("trips").insert(trip_data).execute()
                
                st.session_state.p_list = [{"name": "", "phone": ""}]
                st.success("Рейс успешно сохранен!")
                st.rerun()

            st.divider()
            st.subheader("📡 Текущие рейсы (в работе)")
            active = supabase.table("trips").select("*, drivers(name)").eq("status", "Новый").execute()
            for t in active.data:
                ca, cb, cc = st.columns([4, 1, 1])
                ca.write(f"🚩 **{t['route']}** | 🚖 {t['drivers']['name'] if t['drivers'] else '?'}")
                if cb.button("📝", key=f"ed_{t['id']}"):
                    st.query_params.edit_id = t['id']
                    if 'edit_load' in st.session_state: del st.session_state.edit_load
                    st.rerun()
                if cc.button("🗑️", key=f"rm_{t['id']}"):
                    supabase.table("trips").delete().eq("id", t['id']).execute()
                    st.rerun()

        elif menu == "📜 Архив":
            st.header("История поездок")
            res = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            if res.data:
                if st.button("📊 ЭКСПОРТ В EXCEL"):
                    output = BytesIO()
                    df = pd.DataFrame(res.data)
                    df['Водитель'] = df['drivers'].apply(lambda x: x['name'] if x else "Удален")
                    df['Пассажиры_текст'] = df['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                    df[['created_at', 'route', 'Водитель', 'Пассажиры_текст', 'price']].to_excel(output, index=False)
                    st.download_button("Скачать отчет", output.getvalue(), "otchet_mn.xlsx")
                
                for t in res.data:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                        st.write(f"Водитель: {t['drivers']['name'] if t['drivers'] else '?'}")
                        st.write(f"Сумма: {t['price']} ₽")
                        for p in t['passengers']:
                            st.write(f"👤 {p['name']} — {p['phone']}")

        elif menu == "🚖 Водители":
            st.header("База водителей")
            with st.expander("➕ Добавить нового водителя"):
                n = st.text_input("ФИО")
                c = st.text_input("Машина (Марка/Номер)")
                l = st.text_input("Логин для входа")
                p = st.text_input("Пароль")
                if st.button("Создать аккаунт"):
                    supabase.table("drivers").insert({"name": n, "car": c, "login": l, "password": p}).execute()
                    st.rerun()
            
            drivers = supabase.table("drivers").select("*").execute()
            for d in drivers.data:
                c1, c2 = st.columns([5, 1])
                c1.write(f"👤 {d['name']} — 🚗 {d['car']} (Логин: {d['login']})")
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
                        st.write(f"💰 Оплата: **{j['price']} ₽**")
                        st.write("---")
                        for p in j['passengers']:
                            col_n, col_b = st.columns([3, 1])
                            col_n.write(f"👤 {p['name']}\n📞 {p['phone']}")
                            # Кнопка звонка для мобильных
                            col_b.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%; height:40px; background-color:#25D366; color:white; border:none; border-radius:5px;">📞</button></a>', unsafe_allow_html=True)
                        
                        st.write("---")
                        if st.button("✅ ЗАВЕРШИТЬ РЕЙС", key=f"finish_{j['id']}", use_container_width=True):
                            supabase.table("trips").update({"status": "Завершен"}).eq("id", j['id']).execute()
                            st.success("Рейс завершен!")
                            st.rerun()
            else:
                st.info("На данный момент активных заказов нет")

        elif dr_menu == "📜 Моя история":
            hist = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Завершен").execute()
            st.metric("Общая выручка", f"{sum(t['price'] for t in hist.data)} ₽")
            for t in hist.data:
                with st.expander(f"{t['created_at'][:10]} — {t['route']}"):
                    st.write(f"Цена: {t['price']} ₽")
                    for p in t['passengers']:
                        st.write(f"👤 {p['name']} ({p['phone']})")

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
