"""
LEAD PROCESSOR PRO - FULL BACKUP
Created: {current_date}
Contains all application components in a single file
"""

# --------------------------
# IMPORTS & DEPENDENCIES
# --------------------------
import streamlit as st
import pandas as pd
import requests
import json
from io import StringIO
from typing import Dict, List
from pathlib import Path
import re

# --------------------------
# CORE DATA PROCESSING FUNCTIONS
# --------------------------

def load_and_validate_data(uploaded_file) -> pd.DataFrame:
    """Load and validate CSV data with error handling"""
    try:
        content = uploaded_file.getvalue().decode('utf-8-sig')
        return pd.read_csv(StringIO(content), sep=None, engine='python')
    except Exception as e:
        raise ValueError(f"File Error: {str(e)}")

def process_data(df: pd.DataFrame, mappings: Dict, target_columns: List) -> pd.DataFrame:
    """Transform data based on column mappings"""
    processed = pd.DataFrame()
    for target in target_columns:
        source = mappings.get(target)
        processed[target] = df[source] if source else None
    return processed

def verify_emails(df: pd.DataFrame, api_key: str) -> pd.DataFrame:
    """Email verification using NeverBounce API"""
    if 'Email' not in df.columns:
        return df
    
    status_col = []
    for email in df['Email']:
        try:
            res = requests.post(
                'https://api.neverbounce.com/v4/single/check',
                params={'key': api_key, 'email': email},
                timeout=5
            )
            status_col.append(res.json().get('result', 'invalid'))
        except Exception:
            status_col.append('error')
    
    df['Email Status'] = status_col
    return df[df['Email Status'] == 'valid']

# --------------------------
# TEMPLATE MANAGEMENT FUNCTIONS
# --------------------------
def load_templates() -> Dict:
    """Load templates from JSON file with error handling"""
    try:
        Path("templates").mkdir(exist_ok=True)
        templates = {}
        for file in Path("templates").glob("*.json"):
            with open(file) as f:
                templates[file.stem] = json.load(f)
        return templates
    except Exception as e:
        st.error(f"Template loading error: {str(e)}")
        return {}

def save_template(name: str, mappings: Dict):
    """Save template to file with validation"""
    try:
        if not name:
            raise ValueError("Template name cannot be empty")
        
        # Sanitize filename
        valid_name = re.sub(r'[^\w-]', '', name.strip())[:50]
        if not valid_name:
            raise ValueError("Invalid template name")
            
        filepath = Path(f"templates/{valid_name}.json")
        if filepath.exists():
            raise ValueError("Template name already exists")
            
        with open(filepath, 'w') as f:
            json.dump(mappings, f)
            
        st.toast(f"✅ Template '{valid_name}' saved successfully!", icon="💾")
    except Exception as e:
        st.error(f"Save failed: {str(e)}")

def delete_template(name: str):
    """Delete template file with confirmation"""
    try:
        filepath = Path(f"templates/{name}.json")
        if filepath.exists():
            filepath.unlink()
            st.toast(f"🗑️ Template '{name}' deleted", icon="⚠️")
    except Exception as e:
        st.error(f"Delete failed: {str(e)}")

# --------------------------
# UI COMPONENTS
# --------------------------

def render_sidebar(templates: Dict) -> tuple:
    """Improved sidebar with template management"""
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key = st.text_input("NeverBounce API Key", type="password")
        
        # Template management section
        st.divider()
        st.subheader("📁 Template Management")
        
        # Template creation
        with st.expander("➕ Create New Template", expanded=True):
            new_name = st.text_input(
                "Template Name", 
                help="Use descriptive names (e.g. 'LinkedIn Leads Format')",
                placeholder="Enter template name..."
            )
            
            # Display current mappings preview
            if st.session_state.get('mappings'):
                active_mappings = {k:v for k,v in st.session_state.mappings.items() if v}
                st.caption(f"Mapped columns: {len(active_mappings)}")
                if active_mappings:
                    st.json(active_mappings, expanded=False)
            
            if st.button(
                "💾 Save Current Mapping", 
                disabled=not new_name or not st.session_state.mappings,
                help="Save current column mappings as template"
            ):
                save_template(new_name, st.session_state.mappings)
                templates = load_templates()
                st.rerun()

        # Template selection
        st.divider()
        st.subheader("📂 Saved Templates")
        
        if not templates:
            st.info("No templates saved yet", icon="ℹ️")
        else:
            for tpl_name, tpl_data in templates.items():
                cols = st.columns([5, 1])
                with cols[0]:
                    with st.expander(f"📄 {tpl_name}", expanded=False):
                        st.caption(f"Mapped columns: {len(tpl_data)}")
                        st.json(tpl_data, expanded=False)
                        
                        if st.button(
                            "🔄 Load", 
                            key=f"load_{tpl_name}",
                            help="Apply this template to current mapping"
                        ):
                            st.session_state.mappings = tpl_data
                            st.rerun()
                            
                with cols[1]:
                    st.button(
                        "🗑️", 
                        key=f"del_{tpl_name}",
                        on_click=delete_template,
                        args=(tpl_name,),
                        help="Delete template"
                    )

        return api_key, None  # Removed selected_template as we're using direct load

def render_file_management(df: pd.DataFrame, uploaded_file):
    """File rename and management controls"""
    with st.expander("📁 File Management", expanded=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            new_name = st.text_input(
                "Rename File", 
                value=uploaded_file.name,
                help="Edit the filename before processing"
            )
            st.caption(f"Total Records: {len(df):,}")
        with col2:
            st.markdown("""<div style="height: 27px"></div>""", unsafe_allow_html=True)  # Vertical spacer
            if st.button(
                "🗑️ Remove File", 
                type="secondary",
                use_container_width=True,
                help="Clear current file and start over"
            ):
                st.session_state.uploaded_file = None
                st.rerun()
        return new_name

def render_column_mapping(df: pd.DataFrame, target_columns: List, mappings: Dict):
    """Interactive column mapping interface"""
    # CSS styling for mapping interface
    st.markdown("""
    <style>
    .mapping-row {
        display: flex;
        align-items: center;
        margin: 8px 0;
        padding: 12px;
        background: #1A1A1A;
        border-radius: 8px;
        transition: all 0.2s;
    }
    .mapping-row:hover {
        background: #252525;
    }
    .target-col {
        flex: 0 0 200px;
        font-weight: 500;
        color: #FFF;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .status-dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .required-star {
        color: #FF5252;
        font-size: 1.2em;
    }
    </style>
    """, unsafe_allow_html=True)

    used_sources = [v for v in mappings.values() if v and v != "--- Ignore ---"]
    
    for target in target_columns:
        current_source = mappings.get(target)
        required = target == "Email"
        status_color = "#4CAF50" if current_source else "#FF5252" if required else "#666"
        
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 1])
            
            with col1:
                st.markdown(f"""
                <div class="target-col">
                    <div class="status-dot" style="background: {status_color}"></div>
                    {target}
                    {"<span class='required-star'>*</span>" if required else ""}
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                available_cols = [c for c in df.columns if c not in used_sources or c == current_source]
                source_options = ["--- Ignore ---"] + sorted(available_cols)
                selected = st.selectbox(
                    f"map_{target}",
                    options=source_options,
                    index=source_options.index(current_source) if current_source in source_options else 0,
                    label_visibility="collapsed",
                    key=f"mapping_{target}"
                )
                
                if selected != "--- Ignore ---":
                    mappings[target] = selected
                    if selected not in used_sources:
                        used_sources.append(selected)
                else:
                    mappings[target] = None
            
            with col3:
                if mappings.get(target):
                    if st.button("✕", 
                               key=f"clear_{target}",
                               help="Clear mapping",
                               type="secondary"):
                        mappings[target] = None
                        st.rerun()

# --------------------------
# MAIN APPLICATION
# --------------------------

def main():
    """Main application workflow"""
    # Initialize session state
    if 'templates' not in st.session_state:
        st.session_state.templates = load_templates()
    if 'mappings' not in st.session_state:
        st.session_state.mappings = {}
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None

    # Load schema
    try:
        with open('schema.json') as f:
            TARGET_COLUMNS = json.load(f).get('columns', [])
    except FileNotFoundError:
        st.error("Missing schema.json file!")
        st.stop()

    # App configuration
    st.set_page_config(
        page_title="Cleanlist: Format CSV Files",
        page_icon="📁",
        layout="wide"
    )
    st.title("📁 Cleanlist: Format CSV Files")

    # Main workflow
    api_key, _ = render_sidebar(st.session_state.templates)

    # File handling
    if not st.session_state.uploaded_file:
        uploaded_file = st.file_uploader("Upload CSV", type="csv", label_visibility="collapsed")
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file
            st.rerun()
    else:
        try:
            df = load_and_validate_data(st.session_state.uploaded_file)
            new_filename = render_file_management(df, st.session_state.uploaded_file)
            
            # Show data preview
            with st.expander("📄 Raw Data Preview", expanded=True):
                st.dataframe(df.head(3), use_container_width=True)
                st.caption(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            
            # Column mapping
            st.subheader("Column Mapping")
            render_column_mapping(df, TARGET_COLUMNS, st.session_state.mappings)
            
            # Processing controls
            with st.expander("⚙️ Processing Options", expanded=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    verify_emails = st.checkbox("Verify Email Addresses", True)
                with col2:
                    if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                        processed_df = process_data(df, st.session_state.mappings, TARGET_COLUMNS)
                        if api_key and verify_emails:
                            processed_df = verify_emails(processed_df, api_key)
                        
                        # Store results in session state
                        st.session_state.processed_data = {
                            'df': processed_df,
                            'filename': new_filename.rsplit('.', 1)[0] + "_clean.csv"
                        }
                        st.rerun()

            # Show results after processing
            if 'processed_data' in st.session_state:
                st.subheader("Processed Data")
                processed_df = st.session_state.processed_data['df']
                st.dataframe(processed_df, use_container_width=True)
                
                # Generate download
                csv = processed_df.to_csv(index=False)
                st.download_button(
                    "Download Clean CSV",
                    data=csv,
                    file_name=st.session_state.processed_data['filename'],
                    mime="text/csv"
                )
                
                # Show metrics
                st.success(f"✅ Processing complete! Valid records: {len(processed_df):,}")
            
        except Exception as e:
            st.error(str(e))

if __name__ == "__main__":
    main() 