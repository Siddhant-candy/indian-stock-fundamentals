
import streamlit as st
import pandas as pd
from openscreener import Stock
import subprocess
import sys



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

st.title("📈 Indian Stock Fundamentals")
st.write("Fetch stock fundamentals from Screener.in.")

symbols_input = st.text_area(
    "Enter NSE symbols (one per line)",
    value="TCS\nINFY\nHDFCBANK"
)

if st.button("Fetch fundamentals", type="primary"):

    symbols = [
        s.strip().upper()
        for s in symbols_input.splitlines()
        if s.strip()
    ]

    results = []

    if not symbols:
        st.warning("Please enter at least one stock symbol.")
    else:
        with st.spinner("Preparing Chromium browser..."):
            install_chromium()

        progress = st.progress(0)

        for i, symbol in enumerate(symbols):

            try:
                with st.spinner(f"Fetching {symbol}..."):
                    stock = Stock(symbol)
                    data = stock.summary()
                    ratios = data.get("ratios", {})

                    row = {
                        "Symbol": data.get("nse_symbol", symbol),
                        "Name": data.get("company_name"),
                        "CMP Rs.": ratios.get("current_price"),
                        "Mar Cap Rs.Cr.": ratios.get("market_cap"),
                        "Div Yld %": ratios.get("dividend_yield"),
                        "P/E": ratios.get("stock_p_e"),
                        "ROE %": ratios.get("roe_percent"),
                        "ROCE %": ratios.get("roce_percent"),
                    }

                    results.append(row)

            except Exception as e:
                st.warning(f"Could not fetch {symbol}: {e}")

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
        else:
            st.error("No stock data was fetched.")

