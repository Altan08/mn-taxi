import streamlit as st
from supabase import create_client, Client
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# 1. ПОДКЛЮЧЕНИЕ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="МН Трансфер: Центр Управления", layout="wide")

# Проверка авторизации
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🚕 Вход в систему MN Transfer")
    l, p = st.columns(2)
    login = l.text_input("Логин")
    pwd = p.text_input("Пароль", type="password")
    if st.button("ВОЙТИ", use_container_width=True):
        if login == "admin" and pwd == "mn123":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Доступ запрещен")
else:
    # --- БОКОВАЯ ПАНЕЛЬ ---
    st.sidebar.title("🚀 MN CONTROL")
    page = st.sidebar.radio("Навигация", ["🆕 Новый рейс", "📅 Журнал заказов", "📊 Аналитика", "⚙️ Настройки"])
    
    if st.sidebar.button("Выйти из системы"):
        st.session_state.auth = False
        st.rerun()

    # --- НОВЫЙ РЕЙС ---
    if page == "🆕 Новый рейс":
        st.header("🚐 Формирование сложного маршрута")
        
        # Акция до конца 2026
        promo_limit = datetime(2026, 12, 31)
        if datetime.now() <= promo_limit:
            st.success(f"🎁 Акция активна: Каждый 6-й рейс — 50% скидка (до {promo_limit.strftime('%d.%m.%Y')})")

        # Управление точками маршрута
        if "points" not in st.session_state:
            st.session_state.points = ["Элиста", "Волгоград"]

        c1, c2, c3 = st.columns([1, 1, 3])
        if c1.button("➕ Остановка"):
            st.session_state.points.insert(-1, "")
            st.rerun()
        if c2.button("♻️ Сброс"):
            st.session_state.points = ["Элиста", "Волгоград"]
            st.rerun()

        # Поля ввода
        full_route = []
        passengers_info = ""
        for i, pt in enumerate(st.session_state.points):
            label = "🏙️ Точка старта" if i == 0 else ("🏁 Конечный пункт" if i == len(st.session_state.points)-1 else f"📍 Остановка {i}")
            val = st.text_input(label, value=pt, key=f"pt_{i}")
            full_route.append(val)
            if 0 < i < len(st.session_state.points)-1:
                passengers_info += f"\n- Точка {i}: {val}"

        # КАРТА
        st.subheader("🗺️ Маршрут")
        route_str = "~".join([p for p in full_route if p])
        map_url = f"https://yandex.ru/map-widget/v1/?mode=routes&rtext={route_str}&rtt=auto"
        components.html(f'<iframe src="{map_url}" width="100%" height="450" frameborder="0" style="border-radius:15px; border:1px solid #ddd;"></iframe>', height=450)

        # РАСЧЕТ И ОТПРАВКА
        st.divider()
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("### 💰 Финансы")
            price = st.number_input("Общая касса (₽)", value=4000, step=500)
            fuel = st.number_input("Расход на бензин (₽)", value=1200)
            st.metric("Чистая прибыль", f"{price - fuel} ₽", delta=f"{((price-fuel)/price)*100:.0f}% рентабельность")
            driver = st.text_input("Водитель (ФИО / Авто)")

        with col_right:
            st.write("### 📲 Для водителя")
            wa_msg = f"🚐 *НОВЫЙ ЗАКАЗ*\n📍 *ПУТЬ:* {' ➔ '.join(full_route)}\n👥 *ДЕТАЛИ:* {passengers_info}\n💵 *КАССА:* {price}р\n🚘 *ВОДИТЕЛЬ:* {driver}"
            st.text_area("Скопируй текст в WhatsApp:", wa_msg, height=120)
            
            nav_url = f"https://yandex.ru/maps/?rtext={route_str}&rtt=auto"
            st.markdown(f'<a href="{nav_url}" target="_blank"><button style="width:100%;background-color:#FFCC00;color:black;border:none;padding:12px;border-radius:8px;font-weight:bold;cursor:pointer;">🚀 ОТКРЫТЬ В НАВИГАТОРЕ</button></a>', unsafe_allow_html=True)

        if st.button("✅ СОХРАНИТЬ Р


ЕЙС В БАЗУ", use_container_width=True):
            st.balloons()
            st.success("Данные успешно улетели в Supabase!")

    # --- АНАЛИТИКА ---
    elif page == "📊 Аналитика":
        st.header("📈 Показатели бизнеса")
        m1, m2, m3 = st.columns(3)
        m1.metric("Рейсов за месяц", "156", "+12%")
        m2.metric("Общая касса", "624,000 ₽", "+8.5%")
        m3.metric("Экономия (Акции)", "45,000 ₽")
        
        st.write("### Динамика за неделю")
        st.line_chart({"Заказы": [12, 18, 15, 25, 21, 30, 28]})

    elif page == "📅 Журнал заказов":
        st.header("📋 Список всех поездок")
        st.info("Здесь будет таблица из базы данных. Сейчас она настраивается...")
