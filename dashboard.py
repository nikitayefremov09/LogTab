"""
dashboard.py — Streamlit дашборд LogTab (Material Design Edition)
Запуск: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import csv
import os
import re
from analytics import load_data, get_route_stats, get_recent_entries, get_summary, get_route_transport_stats

# ============================================================
# ФУНКЦИЯ ПАРСИНГА (без изменений)
# ============================================================
def parse_whatsapp_text(text):
    data = {
        'from_city': '', 'to_city': '', 'volume_cbm': '', 'weight_ton': '',
        'transport': '', 'cargo': '', 'price_usd': '', 'price_kzt': ''
    }
    stop_words = {
        'нужна', 'нужен', 'ищу', 'требуется', 'срочно', 'груз', 'ставка',
        'растаможка', 'таможня', 'доставка', 'перевозка', 'машина',
        'фура', 'тент', 'реф', 'контейнер', 'площадка', 'трал', 'газель',
        'готов', 'загрузка', 'выгрузка', 'отправка', 'прибытие',
        'свободен', 'свободна', 'подача', 'адрес', 'контакт', 'телефон',
        'дозвол', 'дозвола', 'сопровождение', 'сопровождения',
        'без', 'есть', 'наличие', 'разрешение', 'разрешения',
        'оформление', 'оформления', 'выпуск', 'выпуска',
        'терминал', 'склад', 'свх', 'тлц', 'жд', 'авиа', 'авто',
        'оплата', 'нал', 'безнал', 'ндс', 'безндс',
        'предоплата', 'постоплата', 'аванс',
        'забор', 'погрузка', 'разгрузка',
        'менеджер', 'логист', 'экспедитор',
        'сегодня', 'завтра', 'срочно', 'вчера',
        'ватсап', 'whatsapp', 'wa',
        'кат', 'колейка', 'очередь', 'путевой', 'авансовый',
        'ликвидация', 'эцп', 'оур', 'оср', 'ип', 'бухгалтер',
        'рекомендация', 'консультация', 'ликбез', 'обучение',
        'акция', 'бонус', 'баланс', 'пополнение',
        'продажник', 'рекрутер', 'офис', 'аренда',
        'серый', 'санкционный',
    }
    forbidden_in_city = {'без', 'есть', 'нет', 'на', 'по', 'с', 'под', 'над', 'в'}

    route_patterns = [
        r'([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)\s*[→\-–]\s*([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)',
        r'из\s+([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)\s+в\s+([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)',
        r'([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)\s+([А-ЯЁ][а-яё-]+(?:\s+[А-ЯЁ][а-яё-]+)?)',
    ]
    for pat in route_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            city1_raw = match.group(1).strip()
            city2_raw = match.group(2).strip()
            city1_lower = city1_raw.lower()
            city2_lower = city2_raw.lower()
            c1_ok = (city1_lower not in stop_words and
                     not any(fw in city1_lower.split() for fw in forbidden_in_city) and len(city1_raw) >= 2)
            c2_ok = (city2_lower not in stop_words and
                     not any(fw in city2_lower.split() for fw in forbidden_in_city) and len(city2_raw) >= 2)
            if c1_ok and c2_ok:
                data['from_city'] = city1_raw.title()
                data['to_city'] = city2_raw.title()
                break

    vol_match = re.search(r'(\d{2,3})\s*(?:куб(?:ов)?|м3|m3)', text, re.IGNORECASE)
    if not vol_match and re.search(r'кубатурник', text, re.IGNORECASE):
        data['volume_cbm'] = 120
    elif vol_match:
        data['volume_cbm'] = int(vol_match.group(1))

    weight_match = re.search(r'(\d{1,2}(?:[.,]\d)?)\s*(?:т|тонн?|тн|тонник)', text, re.IGNORECASE)
    if weight_match:
        try:
            w = weight_match.group(1).replace(',', '.')
            data['weight_ton'] = float(w)
        except ValueError:
            pass

    transport_types = []
    if re.search(r'стандарт', text, re.IGNORECASE):
        transport_types.append('тент')
    if re.search(r'кубатурник|мега', text, re.IGNORECASE):
        transport_types.append('120м3')
    if re.search(r'будка|штора', text, re.IGNORECASE):
        transport_types.append('тент')
    if re.search(r'рефрижератор|термос', text, re.IGNORECASE):
        transport_types.append('реф')
    if re.search(r'площадка|трал', text, re.IGNORECASE):
        transport_types.append('площадка')
    if re.search(r'газель', text, re.IGNORECASE):
        transport_types.append('газель')
    if re.search(r'контейнер', text, re.IGNORECASE):
        transport_types.append('контейнер')
    if re.search(r'фура|тягач', text, re.IGNORECASE):
        if 'тент' not in transport_types and 'реф' not in transport_types and '120м3' not in transport_types:
            transport_types.append('фура')
    if 'тент' in transport_types and 'фура' in transport_types:
        transport_types.remove('фура')
    data['transport'] = ', '.join(transport_types) if transport_types else ''

    cargo = ''
    cargo_match = re.search(r'(?:груз|товар)[:\s]*([^.]+)', text, re.IGNORECASE)
    if cargo_match:
        cargo = cargo_match.group(1).strip()
    else:
        if re.search(r'хозка|базар', text, re.IGNORECASE):
            cargo = 'Хозтовары (ТНП)'
        elif re.search(r'стройка|стройматериалы', text, re.IGNORECASE):
            cargo = 'Стройматериалы'
        elif re.search(r'опасн|адр', text, re.IGNORECASE):
            cargo = 'Опасный груз (ADR)'
        elif re.search(r'серый|санкцион', text, re.IGNORECASE):
            cargo = 'Санкционный груз'
    if cargo and len(cargo) < 50 and cargo.lower() not in stop_words:
        data['cargo'] = cargo

    usd_match = re.search(r'(\d{3,5})\s*(?:\$|usd|долл|у\.е\.)', text, re.IGNORECASE)
    if usd_match:
        data['price_usd'] = int(usd_match.group(1))
    kzt_match = re.search(r'(\d{4,7})\s*(?:₸|kzt|тенге|тг)', text, re.IGNORECASE)
    if kzt_match:
        data['price_kzt'] = int(kzt_match.group(1))
    return data

def save_whatsapp_to_csv(data, raw_text, source="WhatsApp"):
    csv_file = "logistics_data.csv"
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'timestamp', 'chat', 'from_city', 'to_city',
                'volume_cbm', 'weight_ton', 'transport',
                'cargo', 'price_usd', 'price_kzt', 'raw_text'
            ])
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            source,
            data['from_city'],
            data['to_city'],
            data['volume_cbm'],
            data['weight_ton'],
            data['transport'],
            data['cargo'],
            data['price_usd'],
            data['price_kzt'],
            raw_text.replace('\n', ' ')
        ])

# ============================================================
# MATERIAL DESIGN CSS (ТЁМНАЯ ТЕМА)
# ============================================================
st.set_page_config(page_title="LogTab", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; font-family: 'Roboto', sans-serif; }
    [data-testid="metric-container"] {
        background: #1E1E1E; border-radius: 16px; padding: 20px 16px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2), 0 1px 2px rgba(0,0,0,0.3);
        transition: all 0.2s; border: none;
    }
    [data-testid="metric-container"]:hover {
        box-shadow: 0 8px 16px rgba(0,0,0,0.3), 0 2px 4px rgba(0,0,0,0.4);
        background: #252525;
    }
    .main-header {
        font-family: 'Roboto', sans-serif; font-weight: 500; font-size: 2.2rem;
        color: #90CAF9; text-align: left; padding: 24px 0 16px 0;
        margin-bottom: 8px; border-bottom: 2px solid #333333; letter-spacing: -0.5px;
    }
    .live-badge {
        display: inline-block; background: #4CAF50; color: white; font-weight: 500;
        padding: 4px 12px; border-radius: 24px; font-size: 0.8rem; margin-left: 16px;
        vertical-align: middle; box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
    }
    .stButton > button {
        background-color: #1976D2; color: white; border-radius: 24px; border: none;
        padding: 8px 24px; font-weight: 500; text-transform: uppercase;
        letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(25, 118, 210, 0.3);
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: #1565C0; box-shadow: 0 4px 8px rgba(25, 118, 210, 0.4);
        transform: translateY(-1px);
    }
    .stTextInput > div > div > input, .stSelectbox > div > div > div {
        background-color: #1E1E1E; border: 1px solid #424242; border-radius: 12px;
        color: #E0E0E0;
    }
    [data-testid="stSidebar"] { background-color: #1A1A1A; border-right: 1px solid #333333; }
    .dataframe { border-radius: 16px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    .js-plotly-plot { border-radius: 16px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
</style>
""", unsafe_allow_html=True)

# ============================================================
# ИНИЦИАЛИЗАЦИЯ SESSION STATE
# ============================================================
if 'selected_route' not in st.session_state:
    st.session_state.selected_route = "Все"
if 'selected_transport' not in st.session_state:
    st.session_state.selected_transport = "Все"

# ============================================================
# ИНТЕРФЕЙС (С СОХРАНЕНИЕМ СОСТОЯНИЯ В URL)
# ============================================================
query_params = st.query_params

default_hours = 24
default_currency = "usd"
default_detail = "Только маршруты"
default_auto_refresh = False

hours = int(query_params.get("hours", [default_hours])[0])
currency = query_params.get("currency", [default_currency])[0]
detail_level = query_params.get("detail", [default_detail])[0]
auto_refresh = query_params.get("refresh", [str(default_auto_refresh).lower()])[0] == "true"

with st.sidebar:
    st.markdown("### ⚙️ Фильтры")
    new_hours = st.selectbox(
        "Период данных",
        options=[1, 6, 12, 24, 48, 72],
        index=[1, 6, 12, 24, 48, 72].index(hours) if hours in [1, 6, 12, 24, 48, 72] else 3,
        format_func=lambda h: f"Последние {h}ч"
    )
    new_currency = st.radio(
        "Валюта",
        options=["usd", "kzt"],
        index=0 if currency == "usd" else 1,
        format_func=lambda c: "🇺🇸 USD ($)" if c == "usd" else "🇰🇿 KZT (₸)"
    )
    new_detail = st.radio(
        "Уровень детализации",
        options=["Только маршруты", "Маршруты + Транспорт"],
        index=0 if detail_level == "Только маршруты" else 1
    )
    new_auto_refresh = st.checkbox("Автообновление (30 сек)", value=auto_refresh)

    # При изменении любого фильтра (кроме auto_refresh) обновляем URL и перезагружаем
    if (new_hours != hours or new_currency != currency or new_detail != detail_level):
        st.query_params.update({
            "hours": new_hours,
            "currency": new_currency,
            "detail": new_detail,
            "refresh": str(new_auto_refresh).lower()
        })
        st.rerun()

    # Если изменился только auto_refresh — просто обновляем URL без перезагрузки
    if new_auto_refresh != auto_refresh:
        st.query_params["refresh"] = str(new_auto_refresh).lower()
        auto_refresh = new_auto_refresh

    st.divider()
    # Кнопка ручного обновления
    if st.button("🔄 Обновить данные", use_container_width=True):
        st.rerun()

    st.divider()
    st.markdown("### 📋 WhatsApp")
    whatsapp_text = st.text_area("Текст сообщения", height=150, key="wa_input", placeholder="Вставьте текст из WhatsApp...")
    if st.button("➕ Добавить в базу", use_container_width=True):
        if whatsapp_text.strip():
            parsed = parse_whatsapp_text(whatsapp_text)
            save_whatsapp_to_csv(parsed, whatsapp_text, source="WhatsApp")
            st.success(f"✅ Добавлено: {parsed['from_city']} → {parsed['to_city']}")
            st.rerun()
        else:
            st.warning("Вставь текст сообщения")
    st.divider()
    st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")

# Загрузка данных
df = load_data(hours=new_hours)

if new_detail == "Только маршруты":
    stats = get_route_stats(df, currency=new_currency)
else:
    stats = get_route_transport_stats(df, currency=new_currency)

summary = get_summary(df)

# Основной контент
st.markdown("""
<div class="main-header">
    🚛 LogTab
    <span class="live-badge">LIVE</span>
</div>
""", unsafe_allow_html=True)

# Метрики
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Всего предложений", summary["total_records"])
with col2:
    st.metric("🗺️ Маршрутов", summary["unique_routes"])
with col3:
    st.metric("💬 Чатов", summary["unique_chats"])
with col4:
    last = summary["last_update"]
    last_str = last.strftime("%H:%M") if pd.notna(last) else "—"
    st.metric("🕐 Последнее", last_str)

st.divider()
st.subheader("📊 Статистика по направлениям")

if stats.empty:
    st.info("📭 Данных пока нет.")
else:
    currency_symbol = "$" if new_currency == "usd" else "₸"
    rename_dict = {
        "route": "Маршрут",
        "count": "Кол-во",
        "mean": f"Среднее ({currency_symbol})",
        "median": f"Медиана ({currency_symbol})",
        "p75": f"75% ({currency_symbol})",
        "premium_rate": f"🔥 Премиум ({currency_symbol})",
        "min_price": f"Мин ({currency_symbol})",
        "max_price": f"Макс ({currency_symbol})",
    }
    if new_detail == "Маршруты + Транспорт" and "transport" in stats.columns:
        rename_dict["transport"] = "Транспорт"

    display_stats = stats.rename(columns=rename_dict)

    # Фильтры с сохранением в session_state
    if new_detail == "Только маршруты":
        all_routes = ["Все"] + list(stats["route"].unique())
        selected_route = st.selectbox(
            "Фильтр по маршруту",
            all_routes,
            index=all_routes.index(st.session_state.selected_route) if st.session_state.selected_route in all_routes else 0,
            key="route_select"
        )
        st.session_state.selected_route = selected_route
        if selected_route != "Все":
            display_stats = display_stats[display_stats["Маршрут"] == selected_route]
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_routes = ["Все"] + list(stats["route"].unique())
            selected_route = st.selectbox(
                "Фильтр по маршруту",
                all_routes,
                index=all_routes.index(st.session_state.selected_route) if st.session_state.selected_route in all_routes else 0,
                key="route_select_detail"
            )
            st.session_state.selected_route = selected_route
        with col_f2:
            all_transports = ["Все"] + list(stats["transport"].unique())
            selected_transport = st.selectbox(
                "Фильтр по транспорту",
                all_transports,
                index=all_transports.index(st.session_state.selected_transport) if st.session_state.selected_transport in all_transports else 0,
                key="transport_select"
            )
            st.session_state.selected_transport = selected_transport
        if selected_route != "Все":
            display_stats = display_stats[display_stats["Маршрут"] == selected_route]
        if selected_transport != "Все":
            display_stats = display_stats[display_stats["Транспорт"] == selected_transport]

    st.dataframe(
        display_stats,
        width='stretch',
        hide_index=True,
        column_config={
            f"🔥 Премиум ({currency_symbol})": st.column_config.NumberColumn(
                help="75-й процентиль + 10% — цена срочной подачи",
            )
        }
    )

    st.divider()
    st.subheader("📈 Визуализация")
    tab1, tab2 = st.tabs(["Сравнение ставок", "Распределение цен"])

    with tab1:
        top10 = stats.head(10)
        if new_detail == "Только маршруты":
            y_labels = top10["route"]
        else:
            y_labels = top10["route"] + " | " + top10["transport"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=f"Медиана ({currency_symbol})",
            y=y_labels,
            x=top10["median"],
            orientation="h",
            marker_color="#90CAF9",
        ))
        fig.add_trace(go.Bar(
            name=f"Премиум ({currency_symbol})",
            y=y_labels,
            x=top10["premium_rate"],
            orientation="h",
            marker_color="#FFB74D",
        ))
        fig.update_layout(
            barmode="group",
            plot_bgcolor="#121212",
            paper_bgcolor="#121212",
            font_color="#E0E0E0",
            height=400,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, width='stretch')

    with tab2:
        price_col = f"price_{new_currency}"
        df_with_route = df.dropna(subset=[price_col, "from_city", "to_city"]).copy()
        if not df_with_route.empty:
            df_with_route["route"] = df_with_route["from_city"] + " → " + df_with_route["to_city"]
            top_routes = df_with_route["route"].value_counts().head(8).index
            df_filtered = df_with_route[df_with_route["route"].isin(top_routes)]
            fig2 = px.box(
                df_filtered,
                x="route",
                y=price_col,
                color="route",
                labels={"route": "Маршрут", price_col: f"Ставка ({currency_symbol})"},
            )
            fig2.update_layout(
                plot_bgcolor="#121212",
                paper_bgcolor="#121212",
                font_color="#E0E0E0",
                showlegend=False,
                height=400,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig2, width='stretch')
        else:
            st.info("Недостаточно данных для box plot")

st.divider()
st.subheader("📡 Лента последних предложений")
recent = get_recent_entries(df, limit=20)
if recent.empty:
    st.info("Лента пуста")
else:
    currency_symbol = "$" if new_currency == "usd" else "₸"
    price_col = f"price_{new_currency}"
    
    display_cols = ["timestamp", "chat", "from_city", "to_city", "volume_cbm", "weight_ton", "transport", price_col]
    for col in display_cols:
        if col not in recent.columns:
            recent[col] = ""
    
    display_recent = recent[display_cols].fillna("—")
    display_recent = display_recent.rename(columns={
        "timestamp":  "Время",
        "chat":       "Чат",
        "from_city":  "Откуда",
        "to_city":    "Куда",
        "volume_cbm": "Куб (м³)",
        "weight_ton": "Вес (т)",
        "transport":  "Транспорт",
        price_col:    f"Ставка ({currency_symbol})",
    })
    st.dataframe(display_recent, width='stretch', hide_index=True)

# Автообновление через meta refresh
if new_auto_refresh:
    refresh_url = f"?hours={new_hours}&currency={new_currency}&detail={new_detail}&refresh=true"
    st.markdown(f'<meta http-equiv="refresh" content="30;url={refresh_url}">', unsafe_allow_html=True)
