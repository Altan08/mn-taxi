import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
from datetime import datetime

# 1. ПОДКЛЮЧЕНИЕ К БАЗЕ
# Используем твои актуальные ключи Supabase
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO", layout="wide", initial_sidebar_state="expanded")

# Инициализация состояний сессии
if 'auth' not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None
    st.session_state.user_id = None
    st.session_state.user_name = ""

# --- БЛОК АВТОРИЗАЦИИ ---
if not st.session_state.auth:
    st.title("🚕 Система MN Transfer")
    st.subheader("Вход в рабочий кабинет")
    
    col_l, col_p = st.columns(2)
    login_input = col_l.text_input("Логин", placeholder="Введите логин")
    pwd_input = col_p.text_input("Пароль", type="password", placeholder="Введите пароль")
    
    if st.button("ВОЙТИ В СИСТЕМУ", use_container_width=True):
        if login_input == "admin" and pwd_input == "mn123":
            st.session_state.auth = True
            st.session_state.role = "admin"
            st.rerun()
        else:
            # Проверка водителя в базе
            driver_check = supabase.table("drivers").select("*").eq("login", login_input).eq("password", pwd_input).execute()
            if driver_check.data:
                user = driver_check.data[0]
                st.session_state.auth = True
                st.session_state.role = "driver"
                st.session_state.user_id = user['id']
                st.session_state.user_name = user['name']
                st.rerun()
            else:
                st.error("❌ Неверный логин или пароль. Проверьте данные.")

else:
    # --- ИНТЕРФЕЙС ДИСПЕТЧЕРА (АДМИН) ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 ПАНЕЛЬ УПРАВЛЕНИЯ")
        page = st.sidebar.radio("Меню", ["🆕 Новый рейс", "📜 Архив рейсов", "🚖 Водители", "Выход"])
        
        if page == "🆕 Новый рейс":
            st.header("🚐 Управление заказами")
            
            # Логика режима редактирования
            edit_id = st.query_params.get("edit_id")
            existing_trip = None
            if edit_id:
                res_edit = supabase.table("trips").select("*").eq("id", edit_id).execute()
                if res_edit.data:
                    existing_trip = res_edit.data[0]
                    st.warning(f"🔧 Режим редактирования заказа №{edit_id}")

            # 1. Блок пассажиров
            st.subheader("👥 Список пассажиров")
            if 'pass_list' not in st.session_state or (existing_trip and not st.session_state.get('edit_mode_active')):
                st.session_state.pass_list = existing_trip['passengers'] if existing_trip else [{"name": "", "phone": ""}]
                st.session_state.edit_mode_active = True if existing_trip else False

            for i, p in enumerate(st.session_state.pass_list):
                c1, c2, c3 = st.columns([2, 2, 0.5])
                st.session_state.pass_list[i]["name"] = c1.text_input(f"Имя пассажира {i+1}", value=p["name"], key=f"name_{i}")
                st.session_state.pass_list[i]["phone"] = c2.text_input(f"Телефон {i+1}", value=p["phone"], key=f"phone_{i}")
                if c3.button("🗑️", key=f"del_pass_{i}"):
                    st.session_state.pass_list.pop(i)
                    st.rerun()

            if st.button("➕ Добавить еще одного пассажира"):
                st.session_state.pass_list.append({"name": "", "phone": ""})
                st.rerun()

            st.divider()

            # 2. Детали рейса
            route = st.text_area("📍 Маршрут поездки", value=existing_trip['route'] if existing_trip else "Элиста - ")
            price = st.number_input("💰 Стоимость (₽)", value=existing_trip['price'] if existing_trip else 4000, step=100)
            
            drivers_res = supab


ase.table("drivers").select("*").execute()
            dr_map = {f"{d['name']} ({d['car']})": d['id'] for d in drivers_res.data}
            
            # Установка водителя по умолчанию при редактировании
            def_idx = 0
            if existing_trip:
                for idx, (label, d_id) in enumerate(dr_map.items()):
                    if d_id == existing_trip['driver_id']:
                        def_idx = idx
            
            selected_driver = st.selectbox("🚖 Выберите водителя", options=list(dr_map.keys()), index=def_idx)

            # Кнопки сохранения
            if existing_trip:
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", use_container_width=True):
                    supabase.table("trips").update({
                        "route": route, "price": price, 
                        "driver_id": dr_map[selected_driver],
                        "passengers": st.session_state.pass_list
                    }).eq("id", edit_id).execute()
                    st.query_params.clear()
                    st.session_state.edit_mode_active = False
                    st.success("✅ Заказ обновлен!")
                    st.rerun()
                if col_s2.button("Отменить редактирование", use_container_width=True):
                    st.query_params.clear()
                    st.session_state.edit_mode_active = False
                    st.rerun()
            else:
                if st.button("🚀 ОТПРАВИТЬ ЗАКАЗ ВОДИТЕЛЮ", use_container_width=True):
                    if route and any(ps['name'] for ps in st.session_state.pass_list):
                        supabase.table("trips").insert({
                            "route": route, "price": price, "status": "Новый",
                            "driver_id": dr_map[selected_driver],
                            "passengers": st.session_state.pass_list
                        }).execute()
                        st.session_state.pass_list = [{"name": "", "phone": ""}]
                        st.success("✅ Заказ успешно улетел в приложение водителю!")
                        st.rerun()
                    else: st.error("Заполните маршрут и хотя бы одного пассажира")

            st.divider()
            # 3. Список активных
            st.subheader("📡 Текущие рейсы (в работе)")
            active_trips = supabase.table("trips").select("*, drivers(name)").eq("status", "Новый").execute()
            if active_trips.data:
                for t in active_trips.data:
                    c_info, c_edit, c_del = st.columns([4, 1, 1])
                    c_info.write(f"🚩 **{t['route']}** | 🚖 {t['drivers']['name']} | 💰 {t['price']}₽")
                    if c_edit.button("📝 Изменить", key=f"ed_{t['id']}"):
                        st.query_params.edit_id = t['id']
                        st.rerun()
                    if c_del.button("❌ Удалить", key=f"dl_{t['id']}"):
                        supabase.table("trips").delete().eq("id", t['id']).execute()
                        st.rerun()
            else: st.info("Активных рейсов пока нет.")

        elif page == "📜 Архив рейсов":
            st.header("📜 Архив и поиск")
            query = st.text_input("🔍 Поиск пассажира (Имя или Телефон)").lower()
            
            arch_res = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            if arch_res.data:
                filtered = [t for t in arch_res.data if not query or query in json.dumps(t).lower()]
                
                if filtered:
                    st.metric("Выручка по найденным", f"{sum(i['price'] for i in filtered)} ₽")
                    for t in filtered:
                        with st.expander(f"📅 {t['created_at'][:10]} | {t['route']} | {t['price']} ₽"):
                            st.write(f"👤 **Водитель:** {t['drivers']['name'] if t['drivers'] else 'Удален'}")
                            st.write("**Пассажиры:**")


for p in t.get('passengers', []):
                                st.write(f"- {p['name']} (тел: {p['phone']})")
                else: st.warning("Ничего не найдено.")
            else: st.info("Архив пуст.")

        elif page == "🚖 Водители":
            st.header("🚖 Управление персоналом")
            with st.expander("➕ Зарегистрировать нового водителя"):
                n, c, l, p = st.columns(4)
                new_n = n.text_input("Имя")
                new_c = c.text_input("Машина")
                new_l = l.text_input("Логин")
                new_p = p.text_input("Пароль")
                if st.button("Создать аккаунт"):
                    supabase.table("drivers").insert({"name": new_n, "car": new_c, "login": new_l, "password": new_p}).execute()
                    st.rerun()
            
            all_dr = supabase.table("drivers").select("*").execute()
            for d in all_dr.data:
                col_d1, col_d2 = st.columns([5, 1])
                col_d1.write(f"👤 **{d['name']}** — {d['car']} (Логин: {d['login']})")
                if col_d2.button("Удалить", key=f"dr_del_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ИНТЕРФЕЙС ВОДИТЕЛЯ ---
    else:
        st.header(f"👋 Привет, {st.session_state.user_name}!")
        st.subheader("Твои текущие задачи:")
        
        my_jobs = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Новый").execute()
        
        if my_jobs.data:
            for t in my_jobs.data:
                with st.expander(f"🚩 ЗАКАЗ: {t['route']}", expanded=True):
                    st.info(f"💰 Оплата за рейс: **{t['price']} ₽**")
                    st.write("👥 **ПАССАЖИРЫ:**")
                    for p in t.get('passengers', []):
                        cn, cb = st.columns([3, 1])
                        cn.write(f"👤 {p['name']}\n📞 {p['phone']}")
                        cb.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%;background-color:#25D366;color:white;border:none;padding:8px;border-radius:5px;cursor:pointer;">📞 Позвонить</button></a>', unsafe_allow_html=True)
                    
                    st.divider()
                    if st.button("✅ ЗАВЕРШИТЬ РЕЙС", key=f"fin_{t['id']}", use_container_width=True):
                        supabase.table("trips").update({"status": "Завершен"}).eq("id", t['id']).execute()
                        st.balloons()
                        st.rerun()
        else:
            st.info("Новых заказов пока нет. Отдыхай!")

    if st.sidebar.button("🚪 Выйти из системы"):
        st.session_state.auth = False
        st.rerun()
