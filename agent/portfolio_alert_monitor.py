import sqlite3
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime
import time
import schedule
from openai import OpenAI
from config_utils import PROJECT_DIR, get_config_value

# ==========================================
# 1. 配置区
# ==========================================
WECHAT_APP_ID = get_config_value("WECHAT_APP_ID")
WECHAT_APP_SECRET = get_config_value("WECHAT_APP_SECRET")
WECHAT_USER_OPENID = get_config_value("WECHAT_USER_OPENID")
WECHAT_TEMPLATE_ID = get_config_value("WECHAT_TEMPLATE_ID")

DB_FILE = PROJECT_DIR / "invest_memory.db"

# ==========================================
# 2. 核心功能：微信原生官方接口
# ==========================================
def get_wechat_access_token():
    """获取微信官方调用凭证"""
    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        print("微信 App ID 或 App Secret 未配置，请检查 private_config.txt。")
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WECHAT_APP_ID}&secret={WECHAT_APP_SECRET}"
    try:
        res = requests.get(url).json()
        if "access_token" in res:
            return res["access_token"]
        else:
            print(f"获取 Token 失败: {res}")
            return None
    except Exception as e:
        print(f"请求 Token 出错: {e}")
        return None

def send_wechat_native_message(title, content):
    """使用微信官方模板消息接口发送推送"""
    if not WECHAT_USER_OPENID or not WECHAT_TEMPLATE_ID:
        print("微信 OpenID 或模板 ID 未配置，请检查 private_config.txt。")
        return

    token = get_wechat_access_token()
    if not token:
        return
        
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
    
    # 组装符合微信模板格式的数据
    payload = {
        "touser": WECHAT_USER_OPENID,
        "template_id": WECHAT_TEMPLATE_ID,
        "data": {
            "title": {
                "value": f"【{title}】\n", 
                "color": "#FF0000" if "警告" in title else "#173177" # 警告显示红色，正常显示蓝色
            },
            "content": {
                "value": content, 
                "color": "#333333"
            }
        }
    }
    
    try:
        res = requests.post(url, json=payload).json()
        if res.get("errcode") == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 微信原生推送发送成功！请查收手机。")
        else:
            print(f"微信推送失败，错误代码: {res}")
    except Exception as e:
        print(f"微信推送网络出错: {e}")

# ==========================================
# 3. 实时数据与 AI 大脑
# ==========================================
def get_usd_cny_rate():
    try:
        return yf.Ticker("CNY=X").fast_info.last_price
    except:
        return 7.20

def fetch_realtime_data(code):
    try:
        code_str = str(code).strip()
        if code_str.isalpha():
            ticker = yf.Ticker(code_str.upper())
            price_usd = ticker.fast_info.last_price
            return price_usd * get_usd_cny_rate(), f"{ticker.info.get('shortName', code_str.upper())}"
        else:
            code_lower = code_str.lower()
            if not (code_lower.startswith('sh') or code_lower.startswith('sz')):
                if code_lower.startswith(('6', '5', '9')): code_lower = 'sh' + code_lower
                elif code_lower.startswith(('0', '1', '3', '8')): code_lower = 'sz' + code_lower
            url = f"http://qt.gtimg.cn/q={code_lower}"
            res = requests.get(url, timeout=3)
            data = res.text.split('~')
            if len(data) > 3: return float(data[3]), data[1]
    except: pass
    return None, None

def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def check_portfolio_and_alert():
    """巡航核心逻辑：检查持仓并生成 AI 报告"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 哨兵启动：正在扫描全网行情...")
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM assets", conn)
    
    if df.empty:
        print("当前空仓，跳过监控。")
        return

    report_lines = []
    total_market_value = 0
    total_profit = 0
    needs_alert = False 
    
    for index, row in df.iterrows():
        real_price, name = fetch_realtime_data(row['code'])
        if real_price is None:
            continue
            
        cur_val = real_price * row['quantity']
        cost_val = row['cost_price'] * row['quantity']
        profit = cur_val - cost_val
        rate = (profit / cost_val * 100) if cost_val > 0 else 0
        
        total_market_value += cur_val
        total_profit += profit
        
        # 格式化，正数加 + 号
        rate_str = f"+{rate:.2f}%" if rate > 0 else f"{rate:.2f}%"
        report_lines.append(f"{name}: ￥{real_price:.2f} ({rate_str})")
        
        # 🚨 报警规则：如果单只股票亏损超过 5%，触发警报！
        if rate <= -5.0:
            needs_alert = True

    # 调用 AI 大脑
    ai_comment = "AI 大脑未配置 API Key，无法生成简评。"
    c = conn.cursor()
    c.execute("SELECT model_name, api_key, brand FROM ai_models WHERE api_key != '' LIMIT 1")
    ai_config = c.fetchone()
    
    if ai_config:
        model_name, api_key, brand = ai_config
        holdings_str = "\n".join(report_lines)
        prompt = f"""我是你的主人。这是我今天的持仓情况：
{holdings_str}
总市值: {total_market_value:.2f}元, 总浮动盈亏: {total_profit:.2f}元。
请用最简短、犀利的语言（不超过100字），告诉我今天的整体表现如何，需不需要注意什么风险？切忌废话。"""
        
        try:
            print(f"正在呼叫 {model_name} 进行深度分析...")
            if "Gemini" in brand:
                from google import genai
                client = genai.Client(api_key=api_key)
                ai_comment = client.models.generate_content(model=model_name, contents=[prompt]).text
            else:
                base_url = "https://api.deepseek.com" if "DeepSeek" in brand else "https://dashscope.aliyuncs.com/compatible-mode/v1"
                client = OpenAI(api_key=api_key, base_url=base_url)
                res = client.chat.completions.create(model=model_name, messages=[{"role": "user", "content": prompt}])
                ai_comment = res.choices[0].message.content
        except Exception as e:
            ai_comment = f"AI 分析失败: {e}"

    # 组装最终发到微信的排版
    status_title = "🚨 资产跌破警戒线警告！" if needs_alert else "📊 今日资产巡航报告"
    final_msg = f"总市值: ￥{total_market_value:,.2f}\n总盈亏: ￥{total_profit:,.2f}\n\n"
    final_msg += "【资产实时快照】\n" + "\n".join(report_lines) + "\n\n"
    final_msg += f"【🤖 AI {ai_config[0] if ai_config else ''} 简评】\n{ai_comment}"
    
    # 执行原生微信发送！
    send_wechat_native_message(status_title, final_msg)

# ==========================================
# 4. 定时任务调度器
# ==========================================
if __name__ == "__main__":
    print("🤖 AI 财富哨兵后台服务已启动！")
    
    # 【测试专用】为了让你立刻看到效果，一运行就先查一次并推送到微信！
    check_portfolio_and_alert() 
    
    # 设定每天 A 股收盘后自动巡航
    schedule.every().day.at("15:05").do(check_portfolio_and_alert)

    while True:
        schedule.run_pending()
        time.sleep(60)
