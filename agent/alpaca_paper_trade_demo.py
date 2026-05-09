from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from config_utils import get_config_value

# ==========================================
# 1. 读取 Alpaca 模拟盘 API 密钥
# ==========================================
API_KEY = get_config_value("ALPACA_API_KEY")
SECRET_KEY = get_config_value("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    raise SystemExit("请先在 private_config.txt 或环境变量中配置 ALPACA_API_KEY 和 ALPACA_SECRET_KEY。")

# 初始化交易客户端 (paper=True 代表这是绝对安全的模拟盘！)
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

# ==========================================
# 2. 查一下我们有多少钱
# ==========================================
account = trading_client.get_account()
print(f"💰 当前模拟账户购买力: ${account.buying_power}")

# ==========================================
# 3. 激动人心的时刻：用代码下单！
# ==========================================
print("🚀 准备向纳斯达克发送订单：买入 1 股 标普500 ETF (SPY)...")

# 构建一个市价单 (Market Order)
market_order_data = MarketOrderRequest(
                    symbol="SPY",           # 股票代码
                    qty=1,                  # 数量：1股
                    side=OrderSide.BUY,     # 动作：买入
                    time_in_force=TimeInForce.GTC # 订单有效期：一直有效直到成交
                )

try:
    # 提交订单！
    market_order = trading_client.submit_order(order_data=market_order_data)
    print(f"✅ 订单提交成功！订单状态: {market_order.status}")
    print(f"📊 登录 Alpaca 网页后台，去看看你的持仓吧！")
except Exception as e:
    print(f"❌ 订单提交失败，原因: {e}")
