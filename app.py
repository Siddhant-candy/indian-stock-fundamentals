
import streamlit as st
import pandas as pd
from openscreener import Stock
import yfinance as yf
import subprocess
import sys
import math

from io import BytesIO

buffer = BytesIO()


@st.cache_resource
def install_chromium():
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Chromium installation failed: {result.stderr}"
        )



st.set_page_config(
    page_title="Indian Stock Fundamentals",
    page_icon="📈",
    layout="wide"
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(ellipse at 88% 0%, rgba(20, 125, 116, 0.08), transparent 36%),
            #f4f7fa;
        color: #18364e;
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        max-width: 1380px;
        padding-top: 2.4rem;
        padding-bottom: 3rem;
    }

    .hero {
        padding: 1.8rem 2rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 18px;
        color: white;
        background: linear-gradient(115deg, #142d43, #1b4a5a 72%, #176b66);
        box-shadow: 0 12px 30px rgba(24, 54, 78, 0.14);
    }

    .hero-kicker {
        margin: 0 0 0.45rem 0;
        color: #a8d8cd;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .hero h1 {
        margin: 0;
        color: white;
        font-size: 2rem;
        line-height: 1.2;
    }

    .hero p {
        margin: 0.55rem 0 0 0;
        color: #d6e4e8;
        font-size: 1rem;
    }

    [data-testid="stTextArea"] textarea {
        border: 1px solid #d5dee5;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.92);
        color: #18364e !important;
        -webkit-text-fill-color: #18364e;
        caret-color: #147d74;
    }

    [data-testid="stTextArea"] textarea::placeholder {
        color: #6b7d89;
        -webkit-text-fill-color: #6b7d89;
    }

    [data-testid="stTextArea"] [data-testid="stWidgetLabel"] {
        color: #18364e !important;
    }

    [data-testid="stTextArea"] textarea:focus {
        border-color: #16877b;
        box-shadow: 0 0 0 1px #16877b;
    }

    .stButton button, .stDownloadButton button {
        min-height: 2.75rem;
        border-radius: 9px;
        font-weight: 650;
    }

    .stButton button[kind="primary"] {
        border: 0;
        color: white;
        background: #147d74;
    }

    .stButton button[kind="primary"]:hover {
        border: 0;
        color: white;
        background: #10665f;
    }

    [data-testid="stTable"] {
        overflow: auto;
        border: 1px solid #dce4e9;
        border-radius: 12px;
        background: white;
        box-shadow: 0 6px 18px rgba(24, 54, 78, 0.07);
    }

    [data-testid="stTable"] table {
        border-collapse: collapse;
    }

    [data-testid="stTable"] tbody td {
        color: #18364e !important;
        background: #ffffff;
        white-space: nowrap;
    }

    [data-testid="stTable"] thead tr th {
        color: #18364e;
        background: #eaf1f4;
        font-weight: 700;
    }

    [data-testid="stTable"] tbody tr:nth-child(even) {
        background: #f7fafb;
    }

    [data-testid="stTable"] tbody tr:nth-child(even) td {
        background: #f7fafb;
    }

    [data-testid="stMarkdownContainer"] h2 {
        color: #18364e;
    }

    [data-testid="stAlert"] {
        color: #18364e;
        border-radius: 10px;
    }

    .stDownloadButton button {
        border: 1px solid #d5dee5;
        color: #18364e;
        background: white;
    }
    </style>

    <section class="hero">
        <p class="hero-kicker">Market research dashboard</p>
        <h1>Indian Stock Fundamentals</h1>
        <p>Compare company fundamentals and price trends for NSE-listed stocks.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

symbols_input = st.text_area(
    "Enter NSE symbols (one per line)",
    value="TCS\nINFY\nHDFCBANK"
)

def get_industry_pe(peers_data):
    """Read the peer-group median P/E row from openscreener's peers response."""
    if not isinstance(peers_data, dict):
        return None
    companies = peers_data.get("companies", [])
    if not isinstance(companies, list):
        companies = []

    for company in companies:
        name = str(company.get("company", "")).lower()
        if name.startswith("median:"):
            return company.get("p_e")

    # Use the package's median object if it contains a P/E.
    median = peers_data.get("median")
    if isinstance(median, dict):
        return median.get("p_e")

    return None

def calculate_rsi(closes, period=14):
    """Wilder RSI."""
    changes = closes.diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()
    avg_loss = losses.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()

    relative_strength = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + relative_strength))

    # No losses means RSI is 100; no gains and no losses means neutral.
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)

    return rsi.iloc[-1] if not rsi.empty else None


def get_price_metrics(symbol):
    """Return available Yahoo Finance metrics; missing metrics stay empty."""
    symbol = symbol.upper()
    yahoo_symbol = f"{symbol}.NS"
    metrics = {"RSI (14)": None, "4 DMA": None, "11 DMA": None,
               "18 DMA": None, "50 DMA": None, "200 DMA": None,
               "52W High": None, "52W Low": None, "All-time High": None}
    try:
        history = yf.Ticker(yahoo_symbol).history(
            period="max", interval="1d", auto_adjust=True,
        )
        if history is None or history.empty or "Close" not in history:
            return metrics

        closes = history["Close"].dropna()
        if not closes.empty:
            metrics["RSI (14)"] = calculate_rsi(closes)
            for period, label in ((4, "4 DMA"), (11, "11 DMA"),
                                  (18, "18 DMA"), (50, "50 DMA"),
                                  (200, "200 DMA")):
                if len(closes) >= period:
                    metrics[label] = closes.tail(period).mean()

        if "High" in history:
            highs = history["High"].dropna()
            if len(highs) >= 252:
                metrics["52W High"] = highs.tail(252).max()
            if not highs.empty:
                metrics["All-time High"] = highs.max()
        if "Low" in history:
            lows = history["Low"].dropna()
            if len(lows) >= 252:
                metrics["52W Low"] = lows.tail(252).min()
    except Exception:
        # Price data is optional; preserve other sources for this ticker.
        pass
    return metrics


def display_value(value):
    """Use a readable marker for missing or non-finite values."""
    if value is None:
        return "NA"
    try:
        if pd.isna(value):
            return "NA"
        if isinstance(value, (int, float)) and not math.isfinite(value):
            return "NA"
    except (TypeError, ValueError):
        pass
    return value

if st.button("Fetch fundamentals", type="primary"):

    symbols = list(dict.fromkeys(
        s.strip().upper()
        for s in symbols_input.splitlines()
        if s.strip()
    ))

    results = []

    if not symbols:
        st.warning("Please enter at least one stock symbol.")
    else:
        with st.spinner("Preparing Chromium browser..."):
            try:
                install_chromium()
            except Exception as e:
                st.warning(f"Chromium setup failed; Screener data may be unavailable: {e}")

        progress = st.progress(0)

        for i, symbol in enumerate(symbols):
            try:
                with st.spinner(f"Fetching {symbol}..."):
                    row = {"Symbol": symbol, "Name": None, "CMP Rs.": None,
                           "Mar Cap Rs.Cr.": None, "P/E": None,
                           "Industry P/E": None, **get_price_metrics(symbol)}

                    try:
                        stock = Stock(symbol)
                        data = stock.summary() or {}
                        if not isinstance(data, dict):
                            data = {}
                        ratios = data.get("ratios") or {}
                        if not isinstance(ratios, dict):
                            ratios = {}
                        row.update({
                            "Symbol": data.get("nse_symbol") or symbol,
                            "Name": data.get("company_name"),
                            "CMP Rs.": ratios.get("current_price"),
                            "Mar Cap Rs.Cr.": ratios.get("market_cap"),
                            "P/E": ratios.get("stock_p_e"),
                        })
                        try:
                            row["Industry P/E"] = get_industry_pe(stock.peers())
                        except Exception:
                            pass
                    except Exception:
                        # Screener can fail for individual symbols; keep the row.
                        pass

                    results.append({key: display_value(value) for key, value in row.items()})

            except Exception as e:
                st.warning(f"Some data for {symbol} could not be fetched: {e}. Missing fields are shown as NA.")

            progress.progress((i + 1) / len(symbols))

        if results:
            df = pd.DataFrame(results)

            st.success(f"Successfully fetched {len(results)} stocks.")

            st.subheader("Fundamentals")
            st.table(df)

            st.download_button(
                label="Download CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name="stock_fundamentals.csv",
                mime="text/csv"
            )
            df.to_excel(buffer, index=False, engine="openpyxl")

            st.download_button(
                label="Download Excel",
                data=buffer.getvalue(),
                file_name="stock_fundamentals.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.error("No stock data was fetched.")

