import streamlit as st
from supabase import create_client, Client
from httpx import Timeout
import pandas as pd
from io import BytesIO
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim

# 1. ПОДКЛЮЧЕНИЕ К БАЗЕ С ТАЙМАУТОМ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"

@st.cache_resource
def get_supabase_client():
    return create_client(URL, KEY, options={"timeout": 20.0})

supabase = get_supabase_client()

st.set_page_config(page_title="MN Transfer PRO | NOMAD TECH", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.update({'auth': False, 'role': None, 'user_id': None})

def get_coords(address):
    try:
        geolocator = Nominatim(user_agent="mn_nomad_tech_final_check")
        location = geolocator.geocode(address)
        if location: return [location.latitude, location.longitude]
    except: return None
    return None

# --- АВТОРИЗАЦИЯ ---
if not st.session_state.auth:
    st.title("🚕 MN Transfer PRO")
    c1, c2 = st.columns(2)
    l_in = c1.text_input("Логин")
    p_in = c2.text_input("Пароль", type="password")
    
    if st.button("ВОЙТИ", use_container_width=True):
        if l_in == "admin" and p_in == "mn123":
            st.session_state.update({'auth': True, 'role': 'admin'})
            st.rerun()
        else:
            try:
                res = supabase.table("drivers").select("*").eq("login", l_in).eq("password", p_in).execute()
                if res.data:
                    st.session_state.update({'auth': True, 'role': 'driver', 'user_id': res.data[0]['id']})
                    st.rerun()
                else: st.error("Ошибка входа")
            except: st.error("Проблема с подключением к базе")

else:
    # --- АДМИН ПАНЕЛЬ ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 АДМИН")
        menu = st.sidebar.radio("Меню", ["🆕 Новый рейс", "🗺️ Карта", "📜 Архив", "🚖 Водители", "Выход"])

        if menu == "🆕 Новый рейс":
            st.header("Управление рейсами")
            e_id = st.query_params.get("edit_id")
            
            if e_id and 'ed_load' not in st.session_state:
                res = supabase.table("trips").select("*").eq("id", e_id).execute()
                if res.data:
                    st.session_state.ed_load = res.data[0]
                    st.session_state.p_list = res.data[0]['passengers']
            
            if 'p_list' not in st.session_state:
                st.session_state.p_list = [{"name":"","phone":""}]

            for i, p in enumerate(st.session_state.p_list):
                cx, cy, cz = st.columns([2, 2, 0.5])
                st.session_state.p_list[i]["name"] = cx.text_input(f"Имя {i+1}", value=p["name"], key=f"pn_{i}")
                st.session_state.p_list[i]["phone"] = cy.text_input(f"Тел {i+1}", value=p["phone"], key=f"pp_{i}")
                if cz.button("❌", key=f"rm_p_{i}"):
                    st.session_state.p_list.pop(i)
                    st.rerun()
            
            if st.button("➕ Пассажир"):
                st.session_state.p_list.append({"name":"","phone":""})
                st.rerun()

            ex = st.session_state.get('ed_load')
            rt = st.text_area("📍 Маршрут", value=ex['route'] if ex else "")
            pr = st.number_input("💰 Цена", value=int(ex['price']) if ex else 4000)
            
            dr_data = supabase.table("drivers").select("*").execute()
            dr_m = {f"{d['name']} ({d['car']})": d['id'] for d in dr_data.data}
            sl_d = st.selectbox("🚖 Водитель", options=list(dr_m.keys()))

            if st.button("💾 СОХРАНИТЬ", use_container_width=True):
                payload = {"route":rt, "price":pr, "driver_id":dr_m[sl_d], "passengers":st.session_state.p_list, "status":"Новый"}
                if e_id:
                    supabase.table("trips").update(payload).eq("id", e_id).execute()
                    st.query_params.clear()
                    if 'ed_load' in st.session_state: del st.session_state.ed_load
                else:
                    supabase.table("trips").insert(payload).execute()
                st.session_state.p_list = [{"name":"","phone":""}]
                st.rerun()

            st.subheader("📡 В работе")
            act = supabase.table("trips").select("*, drivers(name)").eq("status", "Новый").execute()
            for t in act.data:
                ca, cb, cc = st.columns([4, 1, 1])
                ca.write(f"🚩 {t['route']} | 🚖 {t['drivers']['name'] if t['drivers'] else '?'}")
                if cb.button("📝", key=f"ed_btn_{t['id']}"):
                    st.query_params.edit_id = t['id']
                    if 'ed_load' in st.session_state: del st.session_state.ed_load
                    st.rerun()
                if cc.button("🗑️", key=f"del_{t['id']}"):
                    supabase.table("trips").delete().eq("id", t['id']).execute()
                    st.rerun()

        elif menu == "🗺️ Карта":
            st.header("Карта заказов")
            active = supabase.table("trips").select("*").eq("status", "Новый").execute()
            m = folium.Map(location=[46.3078, 44.2558], zoom_start=7)
            for t in active.data:
                coords = get_coords(t['route'])
                if coords:
                    folium.Marker(coords, popup=f"{t['route']}").add_to(m)
            st_folium(m, width="100%", height=500)

        elif menu == "📜 Архив":
            res = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            if res.data:
                if st.button("📊 EXCEL"):
                    output = BytesIO()
                    df = pd.DataFrame(res.data)
                    df['Водитель'] = df['drivers'].apply(lambda x: x['name'] if x else "Удален")
                    df['Пассажиры'] = df['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                    df[['created_at','route','Водитель','Пассажиры','price']].to_excel(output, index=False)
                    st.download_button("Скачать", output.getvalue(), "otchet.xlsx")
                for t in res.data:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                        for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")

        elif menu == "🚖 Водители":
            with st.expander("➕ Добавить"):
                n, c, l, p = st.text_input("Имя"), st.text_input("Авто"), st.text_input("Логин"), st.text_input("Пароль")
                if st.button("ОК"):
                    supabase.table("drivers").insert({"name":n,"car":c,"login":l,"password":p}).execute()
                    st.rerun()
            for d in supabase.table("drivers").select("*").execute().data:
                c1, c2 = st.columns([5, 1])
                c1.write(f"👤 {d['name']} | {d['car']}")
                if c2.button("❌", key=f"dr_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ВОДИТЕЛЬ ---
    else:
        st.sidebar.title("📱 ВОДИТЕЛЬ")
        dr_o = st.sidebar.radio("Меню", ["🆕 Заказы", "📜 История", "Выход"])
        if dr_o == "🆕 Заказы":
            jobs = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Новый").execute()
            if jobs.data:
                for j in jobs.data:
                    with st.container(border=True):
                        st.subheader(f"🚩 {j['route']}")
                        st.write(f"💰 Оплата: {j['price']} ₽")
                        for p in j['passengers']:
                            cn, cb = st.columns([3, 1])
                            cn.write(f"👤 {p['name']}\n{p['phone']}")
                            cb.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%;background:#25D366;color:white;border:none;padding:10px;border-radius:5px;">📞</button></a>', unsafe_allow_html=True)
                        if st.button("✅ ЗАВЕРШИТЬ", key=f"fin_{j['id']}", use_container_width=True):
                            supabase.table("trips").update({"status":"Завершен"}).eq("id", j['id']).execute()
                            st.rerun()
        elif dr_o == "📜 История":
            h = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Завершен").execute()
            st.metric("Выручка", f"{sum(i['price'] for i in h.data)} ₽")
            for t in h.data:
                with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                    for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")

    if st.sidebar.button("🚪 Выйти"):
        st.session_state.auth = False
        st.rerun()
