import streamlit as st
import pandas as pd
import sqlite3
import requests
import hashlib
import json
import os

# ----------------- CONFIG -----------------
st.set_page_config(
    page_title="AutoSQL AI – Natural Language to SQL Converter",
    layout="centered",
    page_icon="🧠"
)

# Constants
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:latest"
USER_FILE = "users.json"

# Custom CSS for enhanced design
st.markdown("""
    <style>
    html, body {
        background-color: #f0f2f6;
        font-family: 'Segoe UI', sans-serif;
    }
    .reportview-container .main .block-container {
        background-color: #ffffff;
        padding: 2rem 3rem;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        margin-top: 30px;
    }
    h1, h4 {
        font-weight: 700;
    }
    h1 {
        font-size: 2.5rem;
        color: #222831;
    }
    h4 {
        color: #393e46;
    }
    .stButton > button {
        background-color: #007bff;
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
    }
    .stDownloadButton > button {
        background-color: #28a745;
        color: white;
    }
    .stTextInput>div>input {
        padding: 0.6rem;
        border-radius: 6px;
        border: 1px solid #ccc;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------- Functions -----------------
def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(users, username, password):
    return username in users and users[username] == hash_password(password)

def register_user(users, username, password):
    if username in users:
        return False
    users[username] = hash_password(password)
    save_users(users)
    return True

def generate_sql_query(columns, question):
    prompt = f"""
You are an expert SQL assistant. Convert user questions into accurate, executable SQL queries using the given table schema.

### Table schema:
Table: user_data
Columns:
{columns}

### Examples:
-- Example 1:
Question: What is the average salary of employees older than 30?
SQL: SELECT AVG(salary) FROM user_data WHERE age > 30;

-- Example 2:
Question: List all distinct departments sorted by name.
SQL: SELECT DISTINCT department FROM user_data ORDER BY department;

-- Example 3:
Question: How many employees are in the IT department and earn more than 70000?
SQL: SELECT COUNT(*) FROM user_data WHERE department = 'IT' AND salary > 70000;

-- Example 4:
Question: Which employees joined in the last 2 years?
SQL: SELECT * FROM user_data WHERE join_date >= DATE('now', '-2 years');

-- Example 5:
Question: Show the top 5 highest paid employees.
SQL: SELECT * FROM user_data ORDER BY salary DESC LIMIT 5;

-- Now your turn:

Question: {question}
SQL:
""".strip()

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()
        result = response.json()["response"]
        return result.strip()
    except Exception as e:
        return f"❌ Error: {e}"

def extract_sql_only(text):
    sql_lines = []
    capture = False
    for line in text.splitlines():
        if line.strip().upper().startswith("SELECT") or line.strip().upper().startswith("WITH"):
            capture = True
        if capture:
            if line.strip().endswith(";"):
                sql_lines.append(line.strip().rstrip(";"))
                break
            sql_lines.append(line.strip())
    return " ".join(sql_lines)

# ----------------- Main Interface -----------------
st.markdown("""
    <h1 style='text-align: center;'>🧠 AutoSQL AI</h1>
    <h4 style='text-align: center;'>Convert natural language into SQL using LLaMA AI</h4>
    <hr>
""", unsafe_allow_html=True)

# User session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

users = load_users()

# ----------------- Auth -----------------
if not st.session_state.logged_in:
    with st.expander("🔐 Login / Register"):
        auth_mode = st.radio("Choose an option", ["Login", "Register"])

        if auth_mode == "Login":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                if check_password(users, username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(f"Welcome {username}!")
                    st.rerun()
                else:
                    st.error("Incorrect username or password")

        else:
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            if st.button("Register"):
                if register_user(users, new_username, new_password):
                    st.success("Registration successful. Please log in.")
                else:
                    st.error("Username already exists.")

else:
    st.sidebar.success(f"👋 Logged in as {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    uploaded_file = st.file_uploader("📂 Upload your CSV or Excel file", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.subheader("📊 Data Preview")
            st.dataframe(df.head())

            conn = sqlite3.connect(":memory:")
            df.to_sql("user_data", conn, index=False, if_exists="replace")

            columns = ", ".join(df.columns)
            question = st.text_input("❓ What do you want to know from this data?")

            if st.button("💬 Ask AI"):
                with st.spinner("Generating SQL query with LLaMA..."):
                    full_response = generate_sql_query(columns, question)
                    sql = extract_sql_only(full_response)

                st.subheader("🧠 Generated SQL")
                st.code(sql, language="sql")

                try:
                    result_df = pd.read_sql_query(sql, conn)
                    st.subheader("📈 Query Result")
                    st.dataframe(result_df)
                    st.download_button("⬇️ Download Result as CSV", result_df.to_csv(index=False), "result.csv")
                except Exception as e:
                    st.error(f"❌ Could not execute SQL: {e}")

        except Exception as e:
            st.error(f"Error reading file: {e}")