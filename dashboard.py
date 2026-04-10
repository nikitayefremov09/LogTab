"""
dashboard.py — Streamlit дашборд LogTab с ручным вводом из WhatsApp
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
# ФУНКЦИЯ ПАРСИНГА (улучшенная, идентична userbot.py)
# ============================================================
def parse_whatsapp_text(text):
    """Парсит текст сообщения и возвращает словарь с данными (улучшенная версия)"""
    data = {
        'from_city': '',
        'to_city': '',
        'volume_cbm': '',
        'weight_ton': '',
        'transport': '',
        'cargo': '',
        'price_usd': '',
        'price_kzt': ''
    }

    # Расширенный список стоп-слов
    stop_words = {
        # Базовые
        'нужна', 'нужен', 'ищу', 'требуется', 'срочно', 'груз', 'ставка',
        'растаможка', 'таможня', 'доставка', 'перевозка', 'машина',
        'фура', 'тент', 'реф', 'контейнер', 'площадка', 'трал', 'газель',
        'готов', 'загрузка', 'выгрузка', 'отправка', 'прибытие',
        'свободен', 'свободна', 'подача', 'адрес', 'контакт', 'телефон',
        # Из чатов
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
        # Новые из чата
        'кат', 'колейка', 'очередь', 'путевой', 'авансовый',
        'ликвидация', 'эцп', 'оур', 'оср', 'ип', 'бухгалтер',
        'рекомендация', 'консультация', 'ликбез', 'обучение',
        'акция', 'бонус', 'баланс', 'пополнение',
        'продажник', 'рекрутер', 'офис', 'аренда',
        'серый', 'санкционный',
    }

    # Запрещённые компоненты внутри города
    forbidden_in_city = {'без', 'есть', 'нет', 'на', 'по', 'с', 'под', 'над', 'в'}

    # 1. Маршрут
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
                     not any(fw in city1_lower.split() for fw in forbidden_in_city) and
                     len(city1_raw) >= 2)
            c2_ok = (city2_lower not in stop_words and
                     not any(fw in city2_lower.split() for fw in forbidden_in_city) and
                     len(city2_raw) >= 2)

            if c1_ok and c2_ok:
                data['from_city'] = city1_raw.title()
                data['to_city'] = city2_raw.title()
                break

    # 2. Объём (с поддержкой "120 кубов", "кубатурник")
    vol_match = re.search(r'(\d{2,3})\s*(?:куб(?:ов)?|м3|m3)', text, re.IGNORECASE)
    if not vol_match:
        # если явно сказано "кубатурник" – считаем 120м3
        if re.search(r'кубатурник', text, re.IGNORECASE):
            data['volume_cbm'] = 120
    if vol_match:
        data['volume_cbm'] = int(vol_match.group(1))

    # 3. Вес
    weight_match = re.search(r'(\d{1,2}(?:[.,]\d)?)\s*(?:т|тонн?|тн|тонник)', text, re.IGNORECASE)
    if weight_match:
        try:
            w = weight_match.group(1).replace(',', '.')
            data['weight_ton'] = float(w)
        except ValueError:
            pass

    # 4. Тип транспорта (с синонимами)
    transport_types = []
    # синонимы
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

    # дедупликация и чистка
    if 'тент' in transport_types and 'фура' in transport_types:
        transport_types.remove('фура')
    data['transport'] = ', '.join(transport_types) if transport_types else ''

    # 5. Груз (с ключевыми словами)
    cargo = ''
    # сначала ищем прямое указание "груз: ..."
    cargo_match = re.search(r'(?:груз|товар)[:\s]*([^.]+)', text, re.IGNORECASE)
    if cargo_match:
        cargo = cargo_match.group(1).strip()
    else:
        # ищем по ключевым словам
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

    # 6. Ставка USD
    usd_match = re.search(r'(\d{3,5})\s*(?:\$|usd|долл|у\.е\.)', text, re.IGNORECASE)
    if usd_match:
        data['price_usd'] = int(usd_match.group(1))

    # 7. Ставка KZT
    kzt_match = re.search(r'(\d{4,7})\s*(?:₸|kzt|тенге|тг)', text, re.IGNORECASE)
    if kzt_match:
        data['price_kzt'] = int(kzt_match.group(1))

    return data

def save_whatsapp_to_csv(data, raw_text, source="WhatsApp"):
    """Добавляет запись в CSV-файл"""
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
# ИНТЕРФЕЙС STREAMLIT
# ============================================================
st.set_page_config(
    page_title="LogTab",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS (без изменений)
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px;
    }
    .main-header {
        font-family: 'Courier New', monospace;
        font-size: 2.2rem;
        font-weight: 600;
        color: #58a6ff;
        text-align: center;
        border-bottom: 1px solid #30363d;
        padding-bottom: 12px;
        margin-bottom: 24px;
        letter-spacing: 2px;
    }
    .live-badge {
        display: inline-block;
        background: #238636;
        color: white;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .dataframe { font-size: 0.85rem !important; }
    .premium { color: #f78166; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# САЙДБАР
# ============================================================
with st.sidebar:
    st.header("⚙️ Фильтры")
    hours = st.selectbox(
        "Период данных",
        options=[1, 6, 12, 24, 48, 72],
        index=3,
        format_func=lambda h: f"Последние {h}ч"
    )
    currency = st.radio(
        "Валюта",
        options=["usd", "kzt"],
        format_func=lambda c: "🇺🇸 USD ($)" if c == "usd" else "🇰🇿 KZT (₸)"
    )

    detail_level = st.radio(
        "Уровень детализации",
        options=["Только маршруты", "Маршруты + Транспорт"],
        index=0,
        key="detail_level"
    )

    auto_refresh = st.checkbox("Автообновление (30 сек)", value=True)
    if auto_refresh:
        st.caption("Страница обновляется каждые 30 секунд")

    st.divider()
    st.header("📋 WhatsApp")
    st.caption("Вставь текст сообщения из WhatsApp и нажми «Добавить»")
    whatsapp_text = st.text_area("Текст сообщения", height=150, key="wa_input")
    if st.button("➕ Добавить в базу", use_container_width=True):
        if whatsapp_text.strip():
            parsed = parse_whatsapp_text(whatsapp_text)
            save_whatsapp_to_csv(parsed, whatsapp_text, source="WhatsApp")
            st.success(f"✅ Добавлено: {parsed['from_city']} → {parsed['to_city']}")
            st.rerun()  # Обновить дашборд
        else:
            st.warning("Вставь текст сообщения")

    st.divider()
    st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")

# ============================================================
# ОСНОВНАЯ ЧАСТЬ
# ============================================================
df = load_data(hours=hours)

if detail_level == "Только маршруты":
    stats = get_route_stats(df, currency=currency)
else:
    stats = get_route_transport_stats(df, currency=currency)

summary = get_summary(df)

st.markdown("""
<div class="main-header">
    🚛 LogTab &nbsp;
    <span class="live-badge">● LIVE</span>
</div>
""", unsafe_allow_html=True)

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
    st.info("📭 Данных пока нет. Запусти **userbot.py** или добавь сообщения вручную через боковую панель.")
else:
    currency_symbol = "$" if currency == "usd" else "₸"
    price_col = f"price_{currency}"

    rename_dict = {
        "route":        "Маршрут",
        "count":        "Кол-во",
        "mean":         f"Среднее ({currency_symbol})",
        "median":       f"Медиана ({currency_symbol})",
        "p75":          f"75% ({currency_symbol})",
        "premium_rate": f"🔥 Премиум ({currency_symbol})",
        "min_price":    f"Мин ({currency_symbol})",
        "max_price":    f"Макс ({currency_symbol})",
    }
    if detail_level == "Маршруты + Транспорт" and "transport" in stats.columns:
        rename_dict["transport"] = "Транспорт"

    display_stats = stats.rename(columns=rename_dict)

    if detail_level == "Только маршруты":
        all_routes = ["Все"] + list(stats["route"].unique())
        selected_route = st.selectbox("Фильтр по маршруту", all_routes)
        if selected_route != "Все":
            display_stats = display_stats[display_stats["Маршрут"] == selected_route]
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_routes = ["Все"] + list(stats["route"].unique())
            selected_route = st.selectbox("Фильтр по маршруту", all_routes, key="route_filter")
        with col_f2:
            all_transports = ["Все"] + list(stats["transport"].unique())
            selected_transport = st.selectbox("Фильтр по транспорту", all_transports, key="transport_filter")
        if selected_route != "Все":
            display_stats = display_stats[display_stats["Маршрут"] == selected_route]
        if selected_transport != "Все":
            display_stats = display_stats[display_stats["Транспорт"] == selected_transport]

    st.dataframe(
        display_stats,
        use_container_width=True,
        hide_index=True,
        column_config={
            f"🔥 Премиум ({currency_symbol})": st.column_config.NumberColumn(
                help="75-й процентиль + 10% — цена срочной подачи",
            )
        }
    )

    st.divider()
    st.subheader("📈 Визуализация")
    tab1, tab2 = st.tabs(["Сравнение ставок по маршрутам", "Распределение цен"])

    with tab1:
        top10 = stats.head(10)
        if detail_level == "Только маршруты":
            y_labels = top10["route"]
        else:
            y_labels = top10["route"] + " | " + top10["transport"]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=f"Медиана ({currency_symbol})",
            y=y_labels,
            x=top10["median"],
            orientation="h",
            marker_color="#58a6ff",
        ))
        fig.add_trace(go.Bar(
            name=f"Премиум ({currency_symbol})",
            y=y_labels,
            x=top10["premium_rate"],
            orientation="h",
            marker_color="#f78166",
        ))

        fig.update_layout(
            barmode="group",
            plot_bgcolor="#161b22",
            paper_bgcolor="#0d1117",
            font_color="#e6edf3",
            height=400,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        df_with_route = df.dropna(subset=[f"price_{currency}", "from_city", "to_city"]).copy()
        if not df_with_route.empty:
            df_with_route["route"] = df_with_route["from_city"] + " → " + df_with_route["to_city"]
            top_routes = df_with_route["route"].value_counts().head(8).index
            df_filtered = df_with_route[df_with_route["route"].isin(top_routes)]
            fig2 = px.box(
                df_filtered,
                x="route",
                y=f"price_{currency}",
                color="route",
                labels={"route": "Маршрут", f"price_{currency}": f"Ставка ({currency_symbol})"},
            )
            fig2.update_layout(
                plot_bgcolor="#161b22",
                paper_bgcolor="#0d1117",
                font_color="#e6edf3",
                showlegend=False,
                height=400,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Недостаточно данных для box plot")

st.divider()
st.subheader("📡 Лента последних предложений")
recent = get_recent_entries(df, limit=20)
if recent.empty:
    st.info("Лента пуста")
else:
    currency_symbol = "$" if currency == "usd" else "₸"
    price_col = f"price_{currency}"
    display_recent = recent[[
        "timestamp", "chat", "from_city", "to_city",
        "volume_cbm", "weight_ton", "transport", price_col
    ]].rename(columns={
        "timestamp":  "Время",
        "chat":       "Чат",
        "from_city":  "Откуда",
        "to_city":    "Куда",
        "volume_cbm": "Куб (м³)",
        "weight_ton": "Вес (т)",
        "transport":  "Транспорт",
        price_col:    f"Ставка ({currency_symbol})",
    })
    st.dataframe(display_recent, use_container_width=True, hide_index=True)

if auto_refresh:
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)