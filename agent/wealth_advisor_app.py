import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import requests 
import yfinance as yf  # 🚀 新增：雅虎财经，用于获取美股和实时汇率
from google import genai
from openai import OpenAI
import akshare as ak  # 🚀 新增：引入专业量化级数据源
from config_utils import PROJECT_DIR

# ==========================================
# 0. 基础配置与数据库初始化
# ==========================================
st.set_page_config(page_title="AI 智能财富管家 Pro Max", layout="wide", page_icon="💰")
DB_FILE = PROJECT_DIR / "invest_memory.db"

# 注入 CSS 黑科技：用户消息靠右对齐
st.markdown("""
<style>
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
    flex-direction: row-reverse;
}
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) div[data-testid="stChatMessageContent"] {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets
                 (code TEXT PRIMARY KEY, name TEXT, quantity REAL, cost_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (date TEXT PRIMARY KEY, total_value REAL, notes TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, role TEXT, content TEXT)''')
    
    try:
        c.execute("ALTER TABLE chats ADD COLUMN model_name TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass 
        
    c.execute('''CREATE TABLE IF NOT EXISTS ai_models
                 (brand TEXT, model_name TEXT PRIMARY KEY, api_key TEXT)''')
    
# 注入自愈补丁：永远确保核心模型存在，防手滑删空
    defaults = [("Google Gemini", "gemini-2.5-flash", ""), ("DeepSeek (深度求索)", "deepseek-chat", ""), ("阿里云 Qwen", "qwen-max", "")]
    c.executemany("INSERT OR IGNORE INTO ai_models (brand, model_name, api_key) VALUES (?, ?, ?)", defaults)
    
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('account_balance', '0.0')")
    default_prompt = """你是一个专业的金融投资顾问。
当前日期：{date}
【市场状态】{market_status}
【资金情况】可用现金：{cash} 元
【持仓与实时盈亏】（正数代表盈利，负数代表亏损）：
{holdings}

今日宏观资讯：
{news}

请根据以上信息，回答我的问题。作为长期投资者，我的核心配置是宽基ETF和高股息资产。请帮我把控宏观风险，过滤短期噪音。"""
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('system_prompt', ?)", (default_prompt,))
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 1. 资金管理辅助函数
# ==========================================
def get_balance():
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='account_balance'")
    row = c.fetchone()
    return float(row[0]) if row else 0.0

def update_balance(new_balance):
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('account_balance', ?)", (str(new_balance),))
    conn.commit()

# ==========================================
# 2. 🚀 全球实时行情获取模块 (中美双引擎)
# ==========================================
@st.cache_data(ttl=3600) # 缓存汇率 1 小时，避免频繁请求
def get_usd_cny_rate():
    """获取实时 美元/人民币 汇率"""
    try:
        return yf.Ticker("CNY=X").fast_info.last_price
    except:
        return 7.20 # 备用固定汇率

def fetch_realtime_data(code):
    try:
        code_str = str(code).strip()
        
        # 🚀 引擎 A：如果输入的是纯英文字母（如 SPY, QQQ, AAPL），走雅虎财经查美股
        if code_str.isalpha():
            ticker = yf.Ticker(code_str.upper())
            price_usd = ticker.fast_info.last_price
            
            # 获取实时汇率并将美元转换为人民币
            rate = get_usd_cny_rate()
            price_cny = price_usd * rate
            
            # 尝试获取公司名，获取不到就用代码代替
            name = ticker.info.get('shortName', code_str.upper())
            return price_cny, f"{name}(美股/￥计价)"
            
        # 🚀 引擎 B：如果输入的是数字，走腾讯财经查 A 股 / 国内 ETF
        else:
            code_lower = code_str.lower()
            if not (code_lower.startswith('sh') or code_lower.startswith('sz')):
                if code_lower.startswith(('6', '5', '9')):
                    code_lower = 'sh' + code_lower
                elif code_lower.startswith(('0', '1', '3', '8')):
                    code_lower = 'sz' + code_lower
                    
            url = f"http://qt.gtimg.cn/q={code_lower}"
            res = requests.get(url, timeout=3)
            data = res.text.split('~')
            if len(data) > 3:
                return float(data[3]), data[1]
                
    except Exception as e:
        pass
    return None, None

def get_holdings_df():
    df = pd.read_sql("SELECT * FROM assets", conn)
    if df.empty:
        return df
        
    current_prices, current_values, profits, profit_rates = [], [], [], []
    for index, row in df.iterrows():
        real_price, _ = fetch_realtime_data(row['code'])
        if real_price is None:
            real_price = row['cost_price']
            
        cur_val = real_price * row['quantity']
        cost_val = row['cost_price'] * row['quantity']
        profit = cur_val - cost_val
        rate = (profit / cost_val * 100) if cost_val > 0 else 0
        
        current_prices.append(round(real_price, 3))
        current_values.append(round(cur_val, 2))
        profits.append(round(profit, 2))
        profit_rates.append(f"{rate:.2f}%")
        
    df['最新价'] = current_prices
    df['当前市值'] = current_values
    df['浮动盈亏'] = profits
    df['盈亏比例'] = profit_rates
    return df.rename(columns={'code': '代码', 'name': '名称', 'quantity': '持有数量', 'cost_price': '持仓均价'})

# ==========================================
# 3. 核心交易逻辑
# ==========================================
def process_trade(code, name, trade_type, trade_qty, trade_price):
    c = conn.cursor()
    c.execute("SELECT quantity, cost_price FROM assets WHERE code=?", (code,))
    row = c.fetchone()
    current_balance = get_balance()
    transaction_amount = trade_qty * trade_price
    
    if trade_type == "买入/加仓":
        if current_balance < transaction_amount:
            return False, f"余额不足！需 {transaction_amount:,.2f} 元，余额仅 {current_balance:,.2f} 元。"
        if row:
            new_qty = row[0] + trade_qty
            new_avg_cost = ((row[0] * row[1]) + transaction_amount) / new_qty
            c.execute("UPDATE assets SET quantity=?, cost_price=? WHERE code=?", (new_qty, new_avg_cost, code))
        else:
            c.execute("INSERT INTO assets (code, name, quantity, cost_price) VALUES (?, ?, ?, ?)", (code, name, trade_qty, trade_price))
        update_balance(current_balance - transaction_amount)
                      
    elif trade_type == "卖出/减仓":
        if not row: return False, "未持有该资产"
        if trade_qty > row[0]: return False, "卖出数量不能超过持有数量！"
        if trade_qty == row[0]:
            c.execute("DELETE FROM assets WHERE code=?", (code,))
        else:
            c.execute("UPDATE assets SET quantity=? WHERE code=?", (row[0] - trade_qty, code))
        update_balance(current_balance + transaction_amount)
            
    elif trade_type == "强制覆盖修正":
        if trade_qty <= 0: c.execute("DELETE FROM assets WHERE code=?", (code,))
        else: c.execute("INSERT OR REPLACE INTO assets (code, name, quantity, cost_price) VALUES (?, ?, ?, ?)", (code, name, trade_qty, trade_price))
    
    conn.commit()
    return True, "交易记录成功！"

def get_chat_history(limit=50):
    c = conn.cursor()
    c.execute("SELECT timestamp, role, content, model_name FROM chats ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()[::-1]

def save_chat_message(role, content, model_name=None):
    c = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO chats (timestamp, role, content, model_name) VALUES (?, ?, ?, ?)", (ts, role, content, model_name))
    conn.commit()

# ==========================================
# 4. 网络搜索与超级 AI 路由调用
# ==========================================
@st.cache_data(ttl=300)
def get_finance_news():
    news_list = []
    
    # 🕵️‍♂️ 引擎 A：财联社 A股专属盘中异动（极速盯盘，但周末休市为空）
    try:
        df_a = ak.stock_zh_a_alerts_cls()
        if not df_a.empty:
            for _, row in df_a.head(3).iterrows():
                row_dict = row.to_dict() # 转换为字典，防止底层列名突变报错
                t = row_dict.get('时间', '最新')
                c = row_dict.get('内容', str(row_dict))
                news_list.append(f"🔴 [A股专线 | {t}] {c}")
    except Exception as e:
        pass # 沉默报错，交由备用引擎处理
        
    # 🌍 引擎 B：财联社 环球7x24小时电报（涵盖美股/外汇/宏观，全年无休）
    try:
        df_global = ak.stock_info_global_cls()
        if not df_global.empty:
            for _, row in df_global.head(4).iterrows():
                row_dict = row.to_dict()
                t = row_dict.get('发布时间', row_dict.get('时间', '最新'))
                title = row_dict.get('标题', '')
                c = row_dict.get('内容', str(row_dict))
                news_list.append(f"🔵 [全球宏观 | {t}] {title} - {c}")
    except Exception as e:
        pass

    # 🛡️ 终极防线：如果双路全部宕机，下达盲飞指令
    if not news_list:
        return "【系统警报】双路数据源均未获取到信息（可能遭遇网络防火墙或极端维护）。请AI调动历史知识库，主要依托多因子模型与资金管理纪律进行独立技术面推演。"
        
    return "\n".join(news_list)
@st.cache_data(ttl=86400) # 🚀 缓存一整天 (86400秒)，没必要每秒都去查日历，极大提升速度
def get_trading_calendar():
    import akshare as ak
    try:
        # 获取新浪财经的 A 股交易日历
        trade_df = ak.tool_trade_date_hist_sina()
        # 将日期列转换为 'YYYY-MM-DD' 格式的字符串列表
        trade_dates = [str(d.date()) if hasattr(d, 'date') else str(d) for d in trade_df['trade_date']]
        return trade_dates
    except Exception as e:
        return [] # 如果网络极度糟糕获取失败，返回空列表作为降级防御

def get_market_status():
    from datetime import datetime, timezone, timedelta
    
    # 强制锁定北京时间 (东八区)
    tz_beijing = timezone(timedelta(hours=8))
    now = datetime.now(tz_beijing)
    
    today_str = now.strftime('%Y-%m-%d')
    time_num = now.hour * 100 + now.minute
    
    # 星期几的中文显示
    weekday = now.weekday()
    weekday_str = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][weekday]
    current_time_str = f"{today_str} ({weekday_str}) {now.strftime('%H:%M')}"
    
    # 🚀 调取法定交易日历
    trade_dates = get_trading_calendar()
    
    # 🛡️ 核心风控：先判断今天是不是“法定交易日”
    if trade_dates and (today_str not in trade_dates):
        status = "🔴 休市（周末或法定节假日）。请复盘外围宏观局势，生成【下个交易日开盘交易计划】，切勿给出即刻买卖指令。"
    else:
        # 如果今天是法定交易日，再精细判断当前处在哪个交易阶段
        if time_num < 915:
            status = "🟡 盘前休市（请生成【今日开盘交易计划】，提示集合竞价挂单策略）"
        elif (915 <= time_num < 930):
            status = "🟡 集合竞价中（请提示是否需要参与早盘竞价抢筹/逃顶）"
        elif (930 <= time_num <= 1130) or (1300 <= time_num < 1500):
            status = "🟢 盘中交易（市场正在交易，可直接给出即时买卖挂单指令）"
        else:
            status = "🔴 盘后休市（请复盘今日行情，并生成【明日交易计划】，切勿给出即刻指令）"
            
    return current_time_str, status
        
    return current_time_str, status

def call_ai(user_input, api_key, ai_brand, selected_model):
    if not api_key: return f"⚠️ 请先在左侧输入并保存您的 {selected_model} API Key！"
    
    df = get_holdings_df()
    holdings_str = df.to_markdown(index=False) if not df.empty else "暂无持仓"
    
    with st.spinner("⚡ 正在接通主力专线，拉取财联社 7x24 小时实时电报..."):
        news_context = get_finance_news()
            
    # 🚀 1. 新增：调用刚才写的函数，获取精准时间与A股开盘状态
    current_time_str, market_status = get_market_status()
    
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='system_prompt'")
    template = c.fetchone()[0]
    
    # 🚀 2. 修改：把提取到的时间和状态，注射到提示词占位符里
    final_prompt = template.format(
        date=current_time_str, 
        market_status=market_status, # 👈 就是这里！把状态塞进去
        cash=f"{get_balance():,.2f}", 
        holdings=holdings_str, 
        news=news_context
    )

    c.execute("SELECT role, content FROM chats ORDER BY id DESC LIMIT 6")
    recent_history = c.fetchall()[::-1]
    
    try:
        if "Gemini" in ai_brand:
            client = genai.Client(api_key=api_key)
            history_str = "\n".join([f"{'User' if r=='user' else 'Assistant'}: {cont}" for r, cont in recent_history])
            full_context = final_prompt + "\n\n【近期对话历史】\n" + (history_str if history_str else "无")
            response = client.models.generate_content(model=selected_model, contents=[full_context, user_input])
            return response.text
            
        elif "DeepSeek" in ai_brand or "Qwen" in ai_brand:
            messages = [{"role": "system", "content": final_prompt}]
            for role, cont in recent_history:
                messages.append({"role": role, "content": cont})
            messages.append({"role": "user", "content": user_input})
            
            base_url = "https://api.deepseek.com" if "DeepSeek" in ai_brand else "https://dashscope.aliyuncs.com/compatible-mode/v1"
            client = OpenAI(api_key=api_key, base_url=base_url)
            res = client.chat.completions.create(model=selected_model, messages=messages)
            return res.choices[0].message.content

    except Exception as e:
        return f"🚨 调用 {selected_model} 发生错误: {e}"
# ==========================================
# 5. Streamlit UI 界面布局
# ==========================================
with st.sidebar:
    st.title("⚙️ 控制台 (现实环境)")
    
    st.subheader("🤖 AI 引擎库")
    brands_df = pd.read_sql("SELECT DISTINCT brand FROM ai_models", conn)
    brands = brands_df['brand'].tolist() if not brands_df.empty else ["Google Gemini"]
    ai_brand = st.selectbox("1. 供货商", brands)
    models_df = pd.read_sql("SELECT model_name, api_key FROM ai_models WHERE brand=?", conn, params=(ai_brand,))
    model_options = models_df['model_name'].tolist() if not models_df.empty else []
    
    if model_options:
        selected_model = st.selectbox("2. 选定模型", model_options)
        saved_key_series = models_df[models_df['model_name'] == selected_model]['api_key'].values
        saved_key = saved_key_series[0] if len(saved_key_series) > 0 and saved_key_series[0] else ""
        
        api_key_input = st.text_input("3. 专属 API Key", value=saved_key, type="password")
        if api_key_input != saved_key:
            if st.button("💾 记忆 Key"):
                c = conn.cursor()
                c.execute("UPDATE ai_models SET api_key=? WHERE model_name=?", (api_key_input, selected_model))
                conn.commit()
                st.rerun()
    else: 
        selected_model, api_key_input = None, ""

    # ================= 🚀 新增：更强大的自定义模型扩展面板 =================
    with st.expander("🛠️ 增减自定义模型"):
        known_brands = [
            "Google Gemini", "DeepSeek (深度求索)", "阿里云 Qwen", 
            "OpenAI (ChatGPT)", "Anthropic (Claude)", "月之暗面 (Kimi)", 
            "智谱 AI (GLM)", "➕ 自定义新公司..."
        ]
        
        col_m1, col_m2 = st.columns(2)
        new_m_brand_sel = col_m1.selectbox("1. 选择所属公司", known_brands)
        
        if new_m_brand_sel == "➕ 自定义新公司...":
            new_m_brand = col_m1.text_input("✍️ 输入新公司名称")
        else:
            new_m_brand = new_m_brand_sel
            
        new_m_name = col_m2.text_input("2. 模型机器码 (如 gpt-4o)")
        
        if st.button("➕ 添加至库"):
            if new_m_brand and new_m_name:
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO ai_models (brand, model_name, api_key) VALUES (?, ?, '')", (new_m_brand, new_m_name.strip()))
                    conn.commit()
                    st.success(f"成功录入 {new_m_brand} 的新模型！")
                    st.rerun()
                except sqlite3.IntegrityError: 
                    st.error("⚠️ 该模型已存在，请勿重复添加！")
            else:
                st.warning("请填写完整公司和模型机器码！")
                
        st.divider()
        del_m_name = st.selectbox("选择要删除的模型", model_options if model_options else ["无"])
        if st.button("➖ 从库中彻底删除") and del_m_name != "无":
            c = conn.cursor()
            c.execute("DELETE FROM ai_models WHERE model_name=?", (del_m_name,))
            conn.commit()
            st.rerun()
    # ======================================================================
            
   # ================= 🚀 新增：AI 大脑人设与提示词修改器 =================
    st.divider()
    st.subheader("🧠 AI 核心设定")
    with st.expander("📝 修改系统提示词 (Prompt)", expanded=False):
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key='system_prompt'")
        current_prompt = c.fetchone()[0]
        
        st.caption("你可以使用 {date}, {cash}, {holdings}, {news} 作为动态占位符。")
        new_prompt = st.text_area("自定义 AI 的角色与行为：", value=current_prompt, height=250)
        
        if st.button("💾 保存并覆盖提示词"):
            c.execute("UPDATE settings SET value=? WHERE key='system_prompt'", (new_prompt,))
            conn.commit()
            st.success("✅ 提示词已更新！下一次提问即刻生效。")
            st.rerun()
    # ======================================================================
            
  
    st.divider()
    st.subheader("💳 资金台")
    current_balance = get_balance()
    st.metric("可用资金余额", f"¥ {current_balance:,.2f}")
    with st.expander("💸 充值/提现"):
        cash_amount = st.number_input("金额", min_value=0.0, step=1000.0)
        cash_action = st.radio("操作", ["充值", "提现"], horizontal=True)
        if st.button("确认"):
            if cash_action == "充值": update_balance(current_balance + cash_amount)
            else: 
                if current_balance >= cash_amount: update_balance(current_balance - cash_amount)
                else: st.error("余额不足！")
            st.rerun()
            
    st.divider()
    st.subheader("💰 交易台")
    with st.expander("⚖️ 录入流水", expanded=True):
        with st.form("trade_form"):
            st.caption("提示：美股请输入全英文字母代码(如 QQQ)")
            trade_type = st.radio("操作", ["买入/加仓", "卖出/减仓", "强制覆盖修正"], horizontal=True)
            col1, col2 = st.columns(2)
            input_code = col1.text_input("代码 (A股数字/美股字母)")
            input_name = col2.text_input("名称 (留空自动查)")
            
            input_qty = col1.number_input("数量", min_value=0.0, step=10.0)
            input_cost = col2.number_input("单价 (请输入人民币单价)", min_value=0.0, step=0.01)
            
            if st.form_submit_button("执行"):
                if input_code and input_qty > 0:
                    _, fetched_name = fetch_realtime_data(input_code)
                    final_name = input_name if input_name else fetched_name
                    if not final_name and trade_type != "卖出/减仓": st.error("查无此名，请手填")
                    else:
                        success, msg = process_trade(input_code, final_name, trade_type, input_qty, input_cost)
                        if success: st.rerun()
                        else: st.error(msg)
                else: st.error("请输入代码和数量！")

st.title("📈 个人智能财富中心 Pro Max")

tab1, tab2, tab3 = st.tabs(["💬 投资顾问对话", "📊 我的实时资产", "🗂️ 聊天记录管理"])

with tab1:
    st.caption(f"当前选定驱动引擎：**{selected_model}**。已掌握您的资金流与盈亏，支持跨模型记忆共享。")
    chat_container = st.container(height=550)
    
    with chat_container:
        history_msgs = get_chat_history(limit=50)
        current_date = None
        for ts, role, content, saved_model_name in history_msgs:
            if ts:
                msg_date = ts.split(" ")[0]
                if msg_date != current_date:
                    st.markdown(f"<div style='text-align: center; color: #aaa; font-size: 0.8rem; margin: 15px 0;'>📅 {msg_date}</div>", unsafe_allow_html=True)
                    current_date = msg_date
            
            with st.chat_message(role):
                if role == "assistant" and saved_model_name:
                    badge_html = f"""
                    <div style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 14px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        🚀 引擎驱动: {saved_model_name}
                    </div>
                    """
                    st.markdown(badge_html, unsafe_allow_html=True)
                st.markdown(content)
                
    if user_input := st.chat_input(f"正在向 {selected_model} 提问..."):
        save_chat_message("user", user_input)
        
        with chat_container:
            today_date = datetime.now().strftime("%Y-%m-%d")
            if today_date != current_date:
                st.markdown(f"<div style='text-align: center; color: #aaa; font-size: 0.8rem; margin: 15px 0;'>📅 {today_date}</div>", unsafe_allow_html=True)
            with st.chat_message("user"):
                st.markdown(user_input)
                
            with st.chat_message("assistant"):
                badge_html = f"""
                <div style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 14px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    🚀 引擎驱动: {selected_model}
                </div>
                """
                st.markdown(badge_html, unsafe_allow_html=True)
                
                message_placeholder = st.empty()
                with st.spinner(f"{selected_model} 思考中..."):
                    full_response = call_ai(user_input, api_key_input, ai_brand, selected_model)
                message_placeholder.markdown(full_response)
                
            save_chat_message("assistant", full_response, model_name=selected_model)

with tab2:
    st.subheader("资金流水与持仓快照 (全局人民币计价)")
    holdings_df = get_holdings_df()
    
    current_cash = get_balance()
    total_market_value = holdings_df['当前市值'].sum() if not holdings_df.empty else 0
    total_assets = current_cash + total_market_value
    total_profit = holdings_df['浮动盈亏'].sum() if not holdings_df.empty else 0
    
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("🏦 账户总资产", f"¥ {total_assets:,.2f}")
    col_b.metric("💳 可用现金", f"¥ {current_cash:,.2f}")
    col_c.metric("💰 股票总市值", f"¥ {total_market_value:,.2f}", delta=f"总盈亏: {total_profit:,.2f}", delta_color="normal")
    
    st.divider()
    if not holdings_df.empty:
        def highlight_profit(val):
            try:
                num = float(str(val).replace('%', ''))
                return f"color: {'red' if num > 0 else 'green' if num < 0 else 'black'}"
            except: return ''
                
        st.dataframe(holdings_df.style.map(highlight_profit, subset=['浮动盈亏', '盈亏比例']), hide_index=True, width="stretch")

        with st.expander("➖ 强制清仓 (不影响现金)"):
            del_code = st.selectbox("选择删除代码", holdings_df['代码'].tolist())
            if st.button("确认删除"):
                c = conn.cursor()
                c.execute("DELETE FROM assets WHERE code=?", (del_code,))
                conn.commit()
                st.rerun()
with tab3:
    st.subheader("🔍 智能检索与记忆管理系统")
    st.caption("在这里，你可以像管理邮件一样管理 AI 的大脑记忆。支持日历筛选、全文搜索和精准遗忘。")
    
    # === 上半部分：检索控制台 ===
    col_search1, col_search2 = st.columns(2)
    
    # 1. 日历系统 (流式 UI，勾选后才显示日历)
    filter_by_date = col_search1.checkbox("📅 启用日历筛选", value=False)
    if filter_by_date:
        selected_date = col_search1.date_input("选择要回顾的日期")
    else:
        selected_date = None
        
    # 2. 关键词搜索引擎
    search_kw = col_search2.text_input("🔑 关键词搜索", placeholder="输入你记得的聊天片段 (如: 苹果公司)")
    
    # 动态构建 SQL 语句进行精准打击
    query = "SELECT id as '记录ID', timestamp as '时间', role as '发言者', model_name as '模型', content as '内容' FROM chats WHERE 1=1"
    params = []
    
    if filter_by_date and selected_date:
        # 利用 SQL 的 LIKE 实现日历匹配
        query += " AND timestamp LIKE ?"
        params.append(f"{selected_date.strftime('%Y-%m-%d')}%")
        
    if search_kw:
        # 利用 SQL 的 LIKE 实现全文模糊匹配
        query += " AND content LIKE ?"
        params.append(f"%{search_kw}%")
        
    query += " ORDER BY id DESC"  # 永远把最新的放在最上面
    
    # 执行查询并用 Pandas 优雅地展示出来
    df_search = pd.read_sql(query, conn, params=params)
    
    # 美化显示：替换英文角色为中文
    if not df_search.empty:
        df_search['发言者'] = df_search['发言者'].replace({'user': '👤 我', 'assistant': '🤖 AI'})
        
    st.dataframe(df_search, use_container_width=True, hide_index=True)
    
    # === 下半部分：精准删除系统 ===
    st.divider()
    st.subheader("🗑️ 记忆清理站")
    
    if df_search.empty:
        st.info("当前筛选条件下没有找到任何聊天记录。")
    else:
        with st.expander("🚨 展开删除面板 (危险操作)"):
            st.warning("被删除的记忆将无法恢复，AI 会彻底忘记这段对话。")
            # 自动把搜索结果里的 ID 提取出来做成下拉菜单，防止手滑输错
            del_target = st.selectbox("选择要永久删除的【记录ID】", df_search['记录ID'].tolist())
            
            if st.button("💥 永久删除选中记录"):
                c = conn.cursor()
                c.execute("DELETE FROM chats WHERE id=?", (int(del_target),))
                conn.commit()
                st.success(f"成功！记录ID [ {del_target} ] 已被彻底抹除。")
                st.rerun() # 刷新页面，让删除立刻生效
