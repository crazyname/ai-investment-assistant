import streamlit as st
from ddgs import DDGS
import datetime
from config_utils import apply_proxy_from_config

# ==========================================
# 0. 网络代理设置 (解决一直转圈卡死的核心！)
# ==========================================
# 如需代理，请在 private_config.txt 或环境变量中设置 HTTP_PROXY / HTTPS_PROXY。
apply_proxy_from_config()

# ==========================================
# 1. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="私人 AI 投资助理", page_icon="📈", layout="wide")
st.title("📈 个人 AI 投资规划助理")
st.markdown("根据您的资产现状与今日互联网实时宏观资讯，自动生成投资规划。")

with st.sidebar:
    st.header("⚙️ 系统配置")
    api_key = st.text_input("🔑 输入 Gemini API Key", type="password")
    
    st.markdown("---")
    st.header("💼 资产现状")
    cash = st.number_input("可用现金 (人民币)", value=50000, step=1000)
    holdings = st.text_area("当前持仓", "示例：\n沪深300ETF 10000份")
    risk_level = st.selectbox("您的风险偏好", ["保守型", "稳健型", "激进型"])

# ==========================================
# 2. 核心逻辑执行区
# ==========================================
if st.button("🚀 开始生成今日投资规划", type="primary"):
    if not api_key:
        st.error("请先在左侧边栏输入您的 Gemini API Key！")
    else:
        # 使用官方最新的 SDK 导入方式
        from google import genai
        
        today_str = datetime.date.today().strftime("%Y年%m月%d日")
        
        # 步骤 A：获取新闻
        with st.spinner("正在全网搜索今日最新财经资讯..."):
            try:
                # 使用更新后的 ddgs 库
                results = DDGS().text(f"今日财经新闻 股市 宏观经济 {today_str}", max_results=5)
                news_context = "\n".join([f"- {n['title']}: {n['body']}" for n in results])
            except Exception as e:
                news_context = f"获取新闻失败: {e}"

        # 步骤 B：调用 Gemini
        with st.spinner("Gemini 正在深度分析您的资产与市场动态... (已配置代理)"):
            prompt = f"""
            今天是 {today_str}。请作为财富管理顾问，基于以下信息制定投资规划。
            【现状】现金: {cash}元 | 持仓: {holdings} | 偏好: {risk_level}
            【新闻】{news_context}
            请输出：1.宏观情绪总结 2.持仓风险评估 3.今日操作建议 4.风险提示。
            """
            
            try:
                # 初始化最新的 Client
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                   model='gemini-2.5-flash',
                    contents=prompt
                )

                st.success("规划生成完毕！")
                st.markdown("---")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"连接失败，请检查网络代理端口是否正确，或 API Key 是否有效。错误信息: {e}")
