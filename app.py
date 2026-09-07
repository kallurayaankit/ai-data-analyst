import streamlit as st
import pandas as pd
import plotly.express as px
from nl2sql import nl_to_sql, get_usage_stats

st.set_page_config(page_title="AI Data Analyst", layout="wide")
st.title("📊 AI Data Analyst")
st.markdown("Ask a question about your business data. The system will generate SQL, execute it, and visualize the results.")

question = st.text_input("Your question:", placeholder="e.g., Show revenue by country for the last 3 months")

if st.button("Run") and question:
    with st.spinner("Thinking..."):
        try:
            result = nl_to_sql(question)
            st.subheader("Generated SQL")
            st.code(result["sql"], language="sql")
            st.subheader("Results")
            df = pd.DataFrame(result["results"]["rows"], columns=result["results"]["columns"])
            st.dataframe(df)

            # Try to create a chart if data is suitable
            try:
                if len(df) > 0:
                    # Assume first column is label, second is numeric for simple bar chart
                    if len(df.columns) >= 2:
                        col1, col2 = df.columns[0], df.columns[1]
                        if pd.api.types.is_numeric_dtype(df[col2]):
                            fig = px.bar(df, x=col1, y=col2, title="Chart")
                            st.plotly_chart(fig)
            except Exception:
                pass

            st.subheader("Explanation")
            st.write(result["explanation"])
        except Exception as e:
            st.error(f"Error: {e}")

st.sidebar.subheader("Usage Stats")
stats = get_usage_stats()
st.sidebar.write(f"Total tokens: {stats['total_tokens']}")
st.sidebar.write(f"Estimated cost: ${stats['total_cost']}")