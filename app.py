 import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
from datetime import datetime
from io import BytesIO

# 1. ПОДКЛЮЧЕНИЕ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.auth = False
    st.session_state.role = None
    st.session_state.user_id = None

# --- АВТОРИЗАЦИЯ ---
if not st.session_state.auth:
    st.title("🚕 Вход в систему")
    c1, c2 = st.columns(2)
    l_in = c1.text_input("Логин")
    p_in = c2.text_input("Пароль", type="password")
    if st.button("ВОЙТИ", use_container_width=True):
        if l_in == "admin" and p_in == "mn123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        else:
            dr = supabase.table("drivers").select("*").eq("login", l_in).eq("password", p_in).execute()
            if dr.data:
                st.session_state.auth = True
                st.session_state.role = "driver"
                st.session_state.user_id = dr.data[0]['id']
                st.rerun()
            else:
                st.error("Ошибка входа")
else:
    # --- ДИСПЕТЧЕР ---
    if st.session_state.role == "admin":
        st.sidebar.title("🚀 ДИСПЕТЧЕР")
        menu = st.sidebar.radio("Меню", ["🆕 Новый рейс", "📜 Архив рейсов", "🚖 Водители", "Выход"])

        if menu == "🆕 Новый рейс":
            st.header("🚐 Управление заказами")
            e_id = st.query_params.get("edit_id")
            existing = None
            if e_id:
                res = supabase.table("trips").select("*").eq("id", e_id).execute()
                if res.data: existing = res.data[0]

            if 'p_list' not in st.session_state or (existing and not st.session_state.get('edit_on')):
                st.session_state.p_list = existing['passengers'] if existing else [{"name":"", "phone":""}]
                st.session_state.edit_on = True if existing else False

            for i, p in enumerate(st.session_state.p_list):
                cx, cy, cz = st.columns([2, 2, 0.5])
                st.session_state.p_list[i]["name"] = cx.text_input(f"Имя {i+1}", value=p["name"], key=f"n_{i}")
                st.session_state.p_list[i]["phone"] = cy.text_input(f"Тел {i+1}", value=p["phone"], key=f"p_{i}")
                if cz.button("❌", key=f"rm_{i}"):
                    st.session_state.p_list.pop(i)
                    st.rerun()
            
            if st.button("➕ Пассажир"):
                st.session_state.p_list.append({"name":"", "phone":""})
                st.rerun()

            route = st.text_area("📍 Маршрут", value=existing['route'] if existing else "")
            price = st.number_input("💰 Цена", value=existing['price'] if existing else 4000)
            
            d_res = supabase.table("drivers").select("*").execute()
            dr_map = {f"{d['name']} ({d['car']})": d['id'] for d in d_res.data}
            sel_dr = st.selectbox("🚖 Водитель", options=list(dr_map.keys()))

            if existing:
                if st.button("💾 СОХРАНИТЬ"):
                    supabase.table("trips").update({"route":route, "price":price, "driver_id":dr_map[sel_dr], "passengers":st.session_state.p_list}).eq("id", e_id).execute()
                    st.query_params.clear()
                    st.session_state.edit_on = False
                    st.rerun()
            else:
                if st.button("🚀 ОТПРАВИТЬ"):
                    supabase.table("trips").insert({"route":route, "price":price, "driver_id":dr_map[sel_dr], "passengers":st.session_state.p_list, "status":"Новый"}).execute()
                    st.session_state.p_list = [{"name":"", "phone":""}]
                    st.rerun()

            st.subheader("📡 В работе")
            act = supabase.table("trips").select("*, drivers(name)").eq("sta


tus", "Новый").execute()
            for t in act.data:
                ca, cb, cc = st.columns([4,1,1])
                ca.write(f"🚩 {t['route']} | 🚖 {t['drivers']['name']}")
                if cb.button("📝", key=f"ed_{t['id']}"):
                    st.query_params.edit_id = t['id']
                    st.rerun()
                if cc.button("🗑️", key=f"dl_{t['id']}"):
                    supabase.table("trips").delete().eq("id", t['id']).execute()
                    st.rerun()

        elif menu == "📜 Архив рейсов":
            st.header("📜 Архив поездок")
            res = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            if res.data:
                search = st.text_input("🔍 Поиск").lower()
                filt = [t for t in res.data if not search or search in json.dumps(t).lower()]
                st.metric("Общая выручка", f"{sum(i['price'] for i in filt)} ₽")
                
                if st.button("📊 СКАЧАТЬ ОТЧЕТ"):
                    output = BytesIO()
                    df_ex = pd.DataFrame(filt)
                    df_ex['Водитель'] = df_ex['drivers'].apply(lambda x: x['name'] if x else "Удален")
                    df_ex['Пассажиры'] = df_ex['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                    df_final = df_ex[['created_at', 'route', 'Водитель', 'Пассажиры', 'price']]
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False)
                    st.download_button(label="Скачать Excel", data=output.getvalue(), file_name="report.xlsx", mime="application/vnd.ms-excel")

                for t in filt:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']} | {t['price']}₽"):
                        st.write(f"🚖 Водитель: {t['drivers']['name'] if t['drivers'] else 'Удален'}")
                        for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")

        elif menu == "🚖 Водители":
            st.header("🚖 База водителей")
            with st.expander("➕ Добавить"):
                n = st.text_input("Имя")
                c = st.text_input("Авто")
                l = st.text_input("Логин")
                p = st.text_input("Пароль")
                if st.button("ОК"):
                    supabase.table("drivers").insert({"name":n, "car":c, "login":l, "password":p}).execute()
                    st.rerun()
            drvs = supabase.table("drivers").select("*").execute()
            for d in drvs.data:
                cd1, cd2 = st.columns([5, 1])
                cd1.write(f"👤 {d['name']} | {d['car']}")
                if cd2.button("❌", key=f"dr_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ВОДИТЕЛЬ ---
    else:
        st.sidebar.title("📱 МЕНЮ")
        dr_m = st.sidebar.radio("Переход", ["🆕 Заказы", "📜 Моя история", "Выход"])
        if dr_m == "🆕 Заказы":
            jobs = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Новый").execute()
            if jobs.data:
                for j in jobs.data:
                    with st.expander(f"🚩 {j['route']}", expanded=True):
                        st.write(f"💰 Оплата: {j['price']} ₽")
                        for p in j['passengers']:
                            cn, cb = st.columns([3,1])
                            cn.write(f"👤 {p['name']}\n{p['phone']}")
                            cb.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%;background:#25D366;color:white;border:none;padding:5px;border-radius:5px;">📞</button></a>', unsafe_allow_html=True)
                        if st.button("✅ ЗАВЕРШИТЬ", key=f"f_{j['id']}", use_container_width=True):
                            supabase.table("trips").update({"status": "Завершен"}).eq("id", j['id']).execute()


st.rerun()
            else: st.info("Нет активных заказов")
        elif dr_m == "📜 Моя история":
            my_res = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Завершен").execute()
            if my_res.data:
                st.metric("Заработок", f"{sum(i['price'] for i in my_res.data)} ₽")
                for t in my_res.data:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                        for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")

    if st.sidebar.button("🚪 Выход"):
        st.session_state.auth = False
        st.rerun()




