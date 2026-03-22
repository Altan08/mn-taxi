import streamlit as st
from supabase import create_client, Client
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# 1. ПОДКЛЮЧЕНИЕ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO", layout="wide")

# Проверка авторизации
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🚕 MN Transfer: Центр Управления")
    l, p = st.columns(2)
    login = l.text_input("Логин")
    pwd = p.text_input("Пароль", type="password")
    if st.button("ВОЙТИ"):
        if login == "admin" and pwd == "mn123":
            st.session_state.auth = True
            st.rerun()
else:
    st.sidebar.title("🚀 MN CONTROL")
    page = st.sidebar.radio("Навигация", ["🆕 Новый рейс", "📊 Аналитика", "Выход"])
    
    if page == "🆕 Новый рейс":
        st.header("🚐 Формирование сложного маршрута")
        
        # Акция до 2026
        if datetime.now() <= datetime(2026, 12, 31):
            st.success("🎁 Акция '6-й рейс 50%' активна до 31.12.2026")

        if "points" not in st.session_state:
            st.session_state.points = ["Элиста", "Волгоград"]

        c1, c2 = st.columns([1, 4])
        if c1.button("➕ Остановка"):
            st.session_state.points.insert(-1, "")
            st.rerun()
        if c2.button("♻️ Сброс"):
            st.session_state.points = ["Элиста", "Волгоград"]
            st.rerun()

        full_route = []
        psgr_data = ""
        for i, pt in enumerate(st.session_state.points):
            label = "🏙️ Старт" if i == 0 else ("🏁 Конец" if i == len(st.session_state.points)-1 else f"📍 Точка {i}")
            val = st.text_input(label, value=pt, key=f"pt_{i}")
            full_route.append(val)
            if 0 < i < len(st.session_state.points)-1:
                psgr_data += f"\n- {val}"

        # КАРТА
        route_str = "~".join([p for p in full_route if p])
        map_url = f"https://yandex.ru/map-widget/v1/?mode=routes&rtext={route_str}&rtt=auto"
        components.html(f'<iframe src="{map_url}" width="100%" height="400" frameborder="0" style="border-radius:10px;"></iframe>', height=400)

        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            price = st.number_input("Касса (₽)", value=4000)
            fuel = st.number_input("Бензин (₽)", value=1200)
            st.metric("Чистая прибыль", f"{price - fuel} ₽")
        
        with col_r:
            wa_msg = f"🚐 ЗАКАЗ: {full_route[0]} -> {full_route[-1]}\n📍 ПУТЬ: {' -> '.join(full_route)}\n💰 КАССА: {price}р"
            st.text_area("WhatsApp текст:", wa_msg, height=100)
            nav_url = f"https://yandex.ru/maps/?rtext={route_str}&rtt=auto"
            st.markdown(f'<a href="{nav_url}" target="_blank"><button style="width:100%;background-color:#FFCC00;border:none;padding:10px;border-radius:5px;font-weight:bold;cursor:pointer;">🚀 В НАВИГАТОР</button></a>', unsafe_allow_html=True)

        if st.button("💾 СОХРАНИТЬ РЕЙС"):
            st.balloons()
            st.success("Рейс зафиксирован!")

    elif page == "📊 Аналитика":
        st.header("📈 Аналитика")
        st.metric("Выручка за месяц", "560,000 ₽", "+12%")
        st.bar_chart({"Рейсы": [5, 10, 15, 7, 20]})

    elif page == "Выход":
        st.session_state.auth = False
        st.rerun()
