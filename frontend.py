import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Import your main function
from main import generate_leads

# Page configuration
st.set_page_config(
    page_title="Caprae Capital - Lead Generation Tool",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 2.5rem;
    }
    .main-header p {
        color: #e0e0e0;
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
    }
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .stButton > button {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 25px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .lead-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #2a5298;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'leads_df' not in st.session_state:
    st.session_state.leads_df = pd.DataFrame()
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'is_generating' not in st.session_state:
    st.session_state.is_generating = False

# Header
st.markdown("""
<div class="main-header">
    <h1>🎯 Caprae Capital Lead Generation Tool</h1>
    <p>AI-Powered Lead Discovery & Contact Intelligence</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔧 Configuration")
    
    # Search parameters
    st.subheader("Search Settings")
    num_results = st.slider("Number of Results", min_value=1, max_value=20, value=5, help="How many leads to generate")
    
    # Advanced options
    with st.expander("Advanced Options"):
        st.info("Current settings optimized for best results")
        st.write("• Relevance threshold: 60%")
        st.write("• Max retries: 3")
        st.write("• Scraping delay: 2 seconds")
    
    # Search history
    if st.session_state.search_history:
        st.subheader("📜 Search History")
        for i, search in enumerate(reversed(st.session_state.search_history[-5:])):
            if st.button(f"🔍 {search['query'][:30]}...", key=f"history_{i}"):
                st.session_state.search_query = search['query']
                st.rerun()

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🔍 Search for Leads")
    
    # Search form
    with st.form("search_form", clear_on_submit=False):
        search_query = st.text_input(
            "Enter your search query:",
            placeholder="e.g., SaaS companies in San Francisco, AI startups in NYC, marketing agencies in London",
            help="Be specific about industry, location, or company type for better results"
        )
        
        col_search, col_examples = st.columns([1, 1])
        
        with col_search:
            search_button = st.form_submit_button("🚀 Generate Leads", use_container_width=True)
        
        with col_examples:
            if st.form_submit_button("💡 Show Examples"):
                st.session_state.show_examples = True
    
    # Example queries
    if st.session_state.get('show_examples', False):
        st.info("""
        **Example Search Queries:**
        - "SaaS companies in San Francisco"
        - "AI startups in New York"
        - "Marketing agencies in London"
        - "E-commerce platforms in Toronto"
        - "Fintech companies in Singapore"
        - "Healthcare tech companies in Boston"
        """)

with col2:
    st.subheader("📊 Quick Stats")
    
    # Display metrics
    total_leads = len(st.session_state.leads_df)
    relevant_leads = len(st.session_state.leads_df[st.session_state.leads_df.get('is_relevant', False) == True]) if not st.session_state.leads_df.empty else 0
    
    col_metric1, col_metric2 = st.columns(2)
    with col_metric1:
        st.metric("Total Leads", total_leads)
    with col_metric2:
        st.metric("Relevant Leads", relevant_leads)
    
    if total_leads > 0:
        relevance_rate = (relevant_leads / total_leads) * 100
        st.metric("Relevance Rate", f"{relevance_rate:.1f}%")

# Search execution
if search_button and search_query:
    if not st.session_state.is_generating:
        st.session_state.is_generating = True
        
        # Add to search history
        st.session_state.search_history.append({
            'query': search_query,
            'timestamp': datetime.now(),
            'num_results': num_results
        })
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Update progress
            status_text.text("🔍 Searching for companies...")
            progress_bar.progress(20)
            
            # Generate leads
            with st.spinner("Generating leads... This may take a few minutes."):
                leads_df = generate_leads(search_query, num_results)
            
            progress_bar.progress(100)
            status_text.text("✅ Lead generation complete!")
            
            # Store results
            st.session_state.leads_df = leads_df
            
            # Success message
            if not leads_df.empty:
                st.success(f"🎉 Successfully generated {len(leads_df)} leads!")
            else:
                st.warning("⚠️ No leads found. Try a different search query.")
                
        except Exception as e:
            st.error(f"❌ Error generating leads: {str(e)}")
            st.info("Please check your API keys and internet connection.")
        
        finally:
            progress_bar.empty()
            status_text.empty()
            st.session_state.is_generating = False

# Display results
if not st.session_state.leads_df.empty:
    st.header("📋 Generated Leads")
    
    # Filter options
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        show_relevant_only = st.checkbox("Show relevant leads only", value=True)
    
    with col_filter2:
        industry_filter = st.selectbox(
            "Filter by Industry",
            ["All"] + list(st.session_state.leads_df['industry'].unique()) if 'industry' in st.session_state.leads_df.columns else ["All"]
        )
    
    with col_filter3:
        download_format = st.selectbox("Download Format", ["CSV", "Excel"])
    
    # Apply filters
    filtered_df = st.session_state.leads_df.copy()
    
    if show_relevant_only and 'is_relevant' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['is_relevant'] == True]
    
    if industry_filter != "All" and 'industry' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['industry'] == industry_filter]
    
    # Display filtered results
    if not filtered_df.empty:
        st.subheader(f"📊 Results ({len(filtered_df)} leads)")
        
        # Key columns to display
        display_columns = ['company_name', 'email', 'phone', 'linkedin', 'website', 'industry', 'description']
        available_display_columns = [col for col in display_columns if col in filtered_df.columns]
        
        # Display the dataframe
        st.dataframe(
            filtered_df[available_display_columns],
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        if download_format == "CSV":
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            # For Excel download, you'd need to install openpyxl
            st.info("Excel download requires openpyxl package. Use CSV for now.")
        
        # Detailed view
        st.subheader("🔍 Detailed Lead Information")
        
        # Lead selection
        if len(filtered_df) > 0:
            selected_lead_idx = st.selectbox(
                "Select a lead to view details:",
                range(len(filtered_df)),
                format_func=lambda x: filtered_df.iloc[x]['company_name']
            )
            
            selected_lead = filtered_df.iloc[selected_lead_idx]
            
            # Display selected lead details
            col_detail1, col_detail2 = st.columns(2)
            
            with col_detail1:
                st.markdown(f"""
                **Company:** {selected_lead.get('company_name', 'N/A')}
                
                **Industry:** {selected_lead.get('industry', 'N/A')}
                
                **Email:** {selected_lead.get('email', 'N/A')}
                
                **Phone:** {selected_lead.get('phone', 'N/A')}
                
                **LinkedIn:** {selected_lead.get('linkedin', 'N/A')}
                
                **Website:** {selected_lead.get('website', 'N/A')}
                """)
            
            with col_detail2:
                st.markdown(f"""
                **Address:** {selected_lead.get('address', 'N/A')}
                
                **Contact Person:** {selected_lead.get('contact_person', 'N/A')}
                
                **Company Size:** {selected_lead.get('company_size', 'N/A')}
                
                **Founded:** {selected_lead.get('founded_year', 'N/A')}
                
                **Services:** {selected_lead.get('services', 'N/A')}
                
                **Relevance:** {selected_lead.get('relevance_confidence', 0):.1%}
                """)
            
            # Description
            if selected_lead.get('description', 'N/A') != 'N/A':
                st.markdown(f"""
                **Description:**
                {selected_lead.get('description', 'N/A')}
                """)
    else:
        st.info("No leads match your current filters.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>🏢 <strong>Caprae Capital Partners</strong> | Enhanced Lead Generation Tool</p>
    <p>Built with ❤️ using Streamlit, Groq AI, and Selenium</p>
</div>
""", unsafe_allow_html=True)