import streamlit as st
from supabase import create_client, Client
import pandas as pd
import json
from io import BytesIO

# 1. ПОДКЛЮЧЕНИЕ
URL = "https://hixvwbjybjhyefbsojmm.supabase.co"
KEY = "sb_publishable_dP50ZzMPQaLocvBe6iFxAw_oOvO8Xpm"
supabase: Client = create_client(URL, KEY)

st.set_page_config(page_title="MN Transfer PRO", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.auth, st.session_state.role, st.session_state.user_id = False, None, None

# --- АВТОРИЗАЦИЯ ---
if not st.session_state.auth:
    st.title("🚕 Вход в систему")
    col_l, col_p = st.columns(2)
    l_in = col_l.text_input("Логин")
    p_in = col_p.text_input("Пароль", type="password")
    if st.button("ВОЙТИ", use_container_width=True):
        if l_in == "admin" and p_in == "mn123":
            st.session_state.auth, st.session_state.role = True, "admin"
            st.rerun()
        else:
            dr = supabase.table("drivers").select("*").eq("login", l_in).eq("password", p_in).execute()
            if dr.data:
                st.session_state.auth, st.session_state.role, st.session_state.user_id = True, "driver", dr.data[0]['id']
                st.rerun()
            else: st.error("Ошибка входа")
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

            for i, p in enumerate(st.session_state.passengers_list if 'passengers_list' in st.session_state else st.session_state.p_list):
                c1, c2, c3 = st.columns([2, 2, 0.5])
                st.session_state.p_list[i]["name"] = c1.text_input(f"Имя {i+1}", value=p["name"], key=f"n_{i}")
                st.session_state.p_list[i]["phone"] = c2.text_input(f"Тел {i+1}", value=p["phone"], key=f"p_{i}")
                if c3.button("❌", key=f"rm_{i}"):
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
            act = supabase.table("trips").select("*, drivers(name)").eq


("status", "Новый").execute()
            for t in act.data:
                c1, c2, c3 = st.columns([4,1,1])
                c1.write(f"🚩 {t['route']} | 🚖 {t['drivers']['name']}")
                if c2.button("📝", key=f"ed_{t['id']}"):
                    st.query_params.edit_id = t['id']
                    st.rerun()
                if c3.button("🗑️", key=f"dl_{t['id']}"):
                    supabase.table("trips").delete().eq("id", t['id']).execute()
                    st.rerun()

        elif menu == "📜 Архив рейсов":
            st.header("📜 Архив поездок")
            res = supabase.table("trips").select("*, drivers(name)").eq("status", "Завершен").execute()
            
            if res.data:
                search = st.text_input("🔍 Поиск").lower()
                filt = [t for t in res.data if not search or search in json.dumps(t).lower()]
                
                st.metric("Общая выручка", f"{sum(i['price'] for i in filt)} ₽")

                # Кнопка Excel
                if st.button("📊 СКАЧАТЬ ОТЧЕТ В EXCEL"):
                    output = BytesIO()
                    df_excel = pd.DataFrame(filt)
                    df_excel['Водитель'] = df_excel['drivers'].apply(lambda x: x['name'] if x else "Удален")
                    df_excel['Пассажиры'] = df_excel['passengers'].apply(lambda x: ", ".join([f"{p['name']} ({p['phone']})" for p in x]))
                    df_final = df_excel[['created_at', 'route', 'Водитель', 'Пассажиры', 'price']]
                    df_final.columns = ['Дата', 'Маршрут', 'Водитель', 'Пассажиры', 'Сумма (₽)']
                    
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Архив_MN_Transfer')
                    
                    st.download_button(label="Нажмите для загрузки файла", data=output.getvalue(), file_name=f"report_{datetime.now().strftime('%d_%m')}.xlsx", mime="application/vnd.ms-excel")

                for t in filt:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']} | {t['price']}₽"):
                        st.write(f"🚖 Водитель: {t['drivers']['name'] if t['drivers'] else 'Удален'}")
                        for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")
            else: st.info("Архив пуст.")

        elif menu == "🚖 Водители":
            st.header("🚖 Водители")
            with st.expander("➕ Добавить"):
                n, c, l, p = st.text_input("Имя"), st.text_input("Авто"), st.text_input("Логин"), st.text_input("Пароль")
                if st.button("ОК"):
                    supabase.table("drivers").insert({"name":n, "car":c, "login":l, "password":p}).execute()
                    st.rerun()
            drvs = supabase.table("drivers").select("*").execute()
            for d in drvs.data:
                col1, col2 = st.columns([5, 1])
                col1.write(f"👤 {d['name']} | {d['car']}")
                if col2.button("❌", key=f"dr_{d['id']}"):
                    supabase.table("drivers").delete().eq("id", d['id']).execute()
                    st.rerun()

    # --- ВОДИТЕЛЬ ---
    else:
        st.sidebar.title("📱 МЕНЮ")
        dr_menu = st.sidebar.radio("Переход", ["🆕 Заказы", "📜 Моя история", "Выход"])
        if dr_menu == "🆕 Заказы":
            jobs = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Новый").execute()
            if jobs.data:
                for j in jobs.data:
                    with st.expander(f"🚩 {j['route']}", expanded=True):
                        st.write(f"💰 Оплата: {j['price']} ₽")
                        for p in j['passengers']:
                            c_n, c_b = st.columns([3,1])
                            c_n.write(f"👤 {p['name']}\n{p['phone']}")
                            c_b.markdown(f'<a href="tel:{p["phone"]}"><button style="width:100%;background:#25D366;color:white;border:none;p


adding:5px;border-radius:5px;">📞</button></a>', unsafe_allow_html=True)
                        if st.button("✅ ЗАВЕРШИТЬ", key=f"f_{j['id']}", use_container_width=True):
                            supabase.table("trips").update({"status": "Завершен"}).eq("id", j['id']).execute()
                            st.rerun()
            else: st.info("Нет активных заказов")
        elif dr_menu == "📜 Моя история":
            my_res = supabase.table("trips").select("*").eq("driver_id", st.session_state.user_id).eq("status", "Завершен").execute()
            if my_res.data:
                st.metric("Мой заработок", f"{sum(i['price'] for i in my_res.data)} ₽")
                for t in my_res.data:
                    with st.expander(f"{t['created_at'][:10]} | {t['route']}"):
                        for p in t['passengers']: st.write(f"👤 {p['name']} - {p['phone']}")

    if st.sidebar.button("Выход"):
        st.session_state.auth = False
        st.rerun()
