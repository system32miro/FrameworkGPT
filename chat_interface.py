from __future__ import annotations
from typing import List, Dict, Any
import streamlit as st
from dotenv import load_dotenv
from rag_engine import RAGEngine
import time

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Interactive Documentation",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
FRAMEWORKS = {
    'crawl4ai': {
        'name': 'Crawl4AI',
        'description': 'Asynchronous web crawling framework',
        'docs_url': 'https://docs.crawl4ai.com',
        'color': '#4287f5',
        'emoji': '🕸️'
    },
    'pydantic': {
        'name': 'Pydantic AI',
        'description': 'Data validation framework for AI',
        'docs_url': 'https://ai.pydantic.dev',
        'color': '#9c42f5',
        'emoji': '🔍'
    },
    'agno': {
        'name': 'Agno',
        'description': 'Web development framework',
        'docs_url': 'https://docs.agno.com',
        'color': '#42f5ad',
        'emoji': '🌐'
    }
}

def initialize_session_state():
    """Initialize session variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'selected_framework' not in st.session_state:
        st.session_state.selected_framework = 'crawl4ai'
    if 'rag_engine' not in st.session_state:
        st.session_state.rag_engine = RAGEngine()
    if 'theme_color' not in st.session_state:
        st.session_state.theme_color = FRAMEWORKS['crawl4ai']['color']

def set_custom_theme():
    """Set custom theme based on selected framework"""
    framework = st.session_state.selected_framework
    st.session_state.theme_color = FRAMEWORKS[framework]['color']
    
    # Define CSS variables for the current theme
    st.markdown(f"""
    <style>
        :root {{
            --primary-color: {st.session_state.theme_color};
            --primary-light: {st.session_state.theme_color}22;
            --primary-medium: {st.session_state.theme_color}44;
        }}
        
        .stApp {{
            background-color: #0e1117;
            color: #ffffff;
        }}
        
        .sidebar .sidebar-content {{
            background-color: #1a1c24;
        }}
        
        .stButton>button {{
            background-color: var(--primary-color);
            color: white;
            border-radius: 20px;
            border: none;
            padding: 0.5rem 1rem;
            transition: all 0.3s ease;
        }}
        
        .stButton>button:hover {{
            background-color: var(--primary-medium);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .stSelectbox [data-baseweb=select] {{
            border-radius: 20px;
            border: 2px solid var(--primary-color);
        }}
        
        div[data-testid="stChatInput"] {{
            border-radius: 20px;
            border: 2px solid var(--primary-color);
            padding: 0.5rem;
        }}
        
        div[data-testid="stChatInput"]:focus-within {{
            border: 2px solid var(--primary-color);
            box-shadow: 0 0 10px var(--primary-light);
        }}
        
        div[data-testid="stChatMessage"] {{
            border-radius: 15px;
            padding: 1rem;
            margin-bottom: 1rem;
            animation: fadeIn 0.5s ease-in-out;
        }}
        
        div[data-testid="stChatMessage"].user {{
            background-color: var(--primary-medium);
            border-top-right-radius: 0;
        }}
        
        div[data-testid="stChatMessage"].assistant {{
            background-color: #2d2d39;
            border-top-left-radius: 0;
        }}
        
        @keyframes fadeIn {{
            0% {{ opacity: 0; transform: translateY(10px); }}
            100% {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .framework-card {{
            background-color: #1a1c24;
            border-left: 4px solid var(--primary-color);
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            transition: all 0.3s ease;
        }}
        
        .framework-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }}
        
        .sources-expander {{
            background-color: transparent !important;
            border: 1px solid var(--primary-color) !important;
            border-radius: 10px !important;
            margin-top: 0.5rem;
        }}
        
        a {{
            color: var(--primary-color) !important;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        h1, h2, h3 {{
            color: #ffffff;
        }}
        
        .title-container {{
            text-align: center;
            margin-bottom: 2rem;
            padding: 1rem;
            background: linear-gradient(90deg, #0e1117, var(--primary-medium), #0e1117);
            border-radius: 10px;
        }}
    </style>
    """, unsafe_allow_html=True)

def create_sidebar():
    """Create sidebar with framework selection and information"""
    with st.sidebar:
        st.title("📚 Interactive Documentation")
        
        # Framework selection
        st.markdown("### Select a framework:")
        for key, framework in FRAMEWORKS.items():
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button(framework['emoji'], key=f"btn_{key}", help=framework['name']):
                    st.session_state.selected_framework = key
                    set_custom_theme()
                    st.rerun()
            with col2:
                if key == st.session_state.selected_framework:
                    st.markdown(f"**{framework['name']}**")
                else:
                    st.markdown(framework['name'])
        
        # Framework information
        st.markdown("---")
        current_framework = FRAMEWORKS[st.session_state.selected_framework]
        
        st.markdown(f"""
        <div class="framework-card">
            <h3>{current_framework['emoji']} {current_framework['name']}</h3>
            <p>{current_framework['description']}</p>
            <a href="{current_framework['docs_url']}" target="_blank">📖 Official Documentation</a>
        </div>
        """, unsafe_allow_html=True)
        
        # Clear conversation
        if st.button("🗑️ Clear Conversation"):
            st.session_state.messages = []
            st.rerun()

def display_typing_animation():
    """Display a typing animation"""
    message_placeholder = st.empty()
    for _ in range(3):
        for dots in [".", "..", "..."]:
            message_placeholder.markdown(f"Processing{dots}")
            time.sleep(0.3)
    message_placeholder.empty()

def main():
    initialize_session_state()
    set_custom_theme()
    create_sidebar()
    
    # Title container
    st.markdown(f"""
    <div class="title-container">
        <h1>{FRAMEWORKS[st.session_state.selected_framework]['emoji']} Ask about Framework Documentation</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Main container
    container = st.container()
    
    # Chat area
    with container:
        if not st.session_state.messages:
            # Welcome message
            current_framework = FRAMEWORKS[st.session_state.selected_framework]
            st.markdown(f"""
            <div style="text-align: center; padding: 3rem; color: #b8b9ba;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">{current_framework['emoji']}</div>
                <h2>Welcome to the Interactive Documentation for {current_framework['name']}</h2>
                <p>Ask a question below to learn more about {current_framework['name']}.</p>
            </div>
            """, unsafe_allow_html=True)
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar="🧑‍💻" if message["role"] == "user" else FRAMEWORKS[st.session_state.selected_framework]['emoji']):
                st.markdown(message["content"])
        
        # User input
        if prompt := st.chat_input("Ask a question about the documentation..."):
            # Add user question
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="🧑‍💻"):
                st.markdown(prompt)
            
            # Process response
            with st.chat_message("assistant", avatar=FRAMEWORKS[st.session_state.selected_framework]['emoji']):
                with st.spinner("Searching documentation..."):
                    # Use RAG Engine to process the question
                    result = st.session_state.rag_engine.query(
                        prompt,
                        st.session_state.selected_framework
                    )
                    
                    if result["error"]:
                        st.error(result["error"])
                        return
                    
                    st.markdown(result["answer"])
                    
                    if result["sources"]:
                        with st.expander("🔍 Sources", expanded=False):
                            st.markdown(result["sources"])
            
            # Add response to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"{result['answer']}\n\n---\n\n🔍 **Sources:**\n{result['sources']}"
            })

if __name__ == "__main__":
    main() 