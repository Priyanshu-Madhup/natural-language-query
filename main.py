import streamlit as st
import sqlite3
import google.generativeai as genai
import json
import re

# Configure Gemini API
genai.configure(api_key="")#please enter your api key for gemini
generation_config = {"temperature": 0.9, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
model = genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)

# List of sensitive tables
SENSITIVE_TABLES = ["products", "users", "payments", "transactions", "salaries", "bank_accounts"]

# Allowed SQL Commands (Only Retrieval)
ALLOWED_COMMANDS = ["SELECT", "DISPLAY"]

# Function to check if query involves a sensitive table
def is_sensitive_query(sql_query):
    pattern = r"\b(" + "|".join(SENSITIVE_TABLES) + r")\b"
    return bool(re.search(pattern, sql_query, re.IGNORECASE))

# Function to check if query contains only allowed commands
def is_allowed_query(sql_query):
    first_word = sql_query.strip().split()[0].upper()
    return first_word in ALLOWED_COMMANDS

# Function to send query to Gemini and get SQL query
def query_gemini(nl_query, table_structure):
    response = model.generate_content([
        f"Read the following table structure and generate the required SQL query for the given natural language prompt. Table structure: {table_structure}. (Don't format the text, just write it as it is) Prompt: {nl_query}"
    ])
    return response.text.strip()

# Function to create tables and insert data from JSON
def create_tables_and_insert_data(json_data, conn):
    cursor = conn.cursor()
    for table_name, rows in json_data.items():
        if not rows:
            continue
        columns = rows[0].keys()
        column_definitions = ", ".join([f"{col} TEXT" for col in columns])
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_definitions})"
        cursor.execute(create_table_query)
        
        # Check if the table already contains data
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        if cursor.fetchone()[0] == 0:
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])
            insert_query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
            for row in rows:
                cursor.execute(insert_query, tuple(row.values()))
    
    conn.commit()

# Streamlit UI
st.set_page_config(page_title="AI Agent SQL", page_icon="🤖", layout="centered")

st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Natural Language AI-Powered SQL Query Generator</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 16px;'>Upload a JSON file, generate SQL queries, and execute them effortlessly!</p>", unsafe_allow_html=True)
st.divider()

# Step 1: Input database name
st.subheader("🔹 Step 1: Enter Database Name")
db_name = st.text_input("Enter the database name (without .db extension):", key="db_name")

if db_name:
    db_path = f"{db_name}.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    st.success(f"✅ Database '{db_name}' created successfully.")

    # Step 2: Upload JSON file
    st.subheader("📂 Step 2: Upload JSON File")
    uploaded_file = st.file_uploader("Upload a JSON file containing the table data", type="json")

    if uploaded_file:
        json_data = json.load(uploaded_file)
        create_tables_and_insert_data(json_data, conn)
        st.success("✅ Tables created and data inserted successfully!")

        # Display table schema
        with st.expander("📊 View Database Schema"):
            st.write("Below is the table structure of your uploaded data:")
            for table_name in json_data.keys():
                st.subheader(f"📌 {table_name}")
                schema = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
                st.table([{ "Column Name": col[1], "Type": col[2] } for col in schema])

        # Step 3: Natural Language Query Input
        st.subheader("💬 Step 3: Ask Your SQL Query")
        query = st.text_input("Enter your natural language query:", key="query")

        if query:
            table_structure = json.dumps(json_data, indent=4)
            gemini_response = query_gemini(query, table_structure)

            # Check if the query is allowed
            if not is_allowed_query(gemini_response):
                st.error("❌ Access Denied: Only **SELECT** and **DISPLAY** queries are allowed!")
            # Check for sensitive data access
            elif is_sensitive_query(gemini_response):
                st.warning("⚠️ Access Denied: This query involves a **sensitive table** and cannot be executed.")
            else:
                st.info(f"**📝 Generated SQL Query:** `{gemini_response}`")

                # Execute SQL Query
                try:
                    cursor.execute(gemini_response)
                    results = cursor.fetchall()
                    
                    if results:
                        st.subheader("📊 Query Results")
                        results_list = [dict(zip([column[0] for column in cursor.description], row)) for row in results]
                        st.json(results_list)

                        # Step 4: Download Query Results
                        results_json = json.dumps(results_list, indent=4)
                        st.download_button("📥 Download Results as JSON", data=results_json, file_name="query_results.json", mime="application/json")

                    else:
                        st.warning("⚠️ No results found for the given query.")

                except sqlite3.Error as e:
                    st.error(f"❌ Failed to execute query: {e}")

    conn.close()
