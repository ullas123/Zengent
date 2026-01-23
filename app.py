import streamlit as st
import tempfile
import os
from pathlib import Path
import time
from datetime import datetime
from codescan import CodeAnalyzer
from utils import display_code_with_highlights, create_file_tree
from project_analyzer import ProjectAnalyzer
from styles import apply_custom_styles
import base64
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import pandas as pd
import zipfile

# Page config
st.set_page_config(
    page_title="CodeLens - Code Utility",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom styles
apply_custom_styles()

# Creator information
st.sidebar.markdown("""
### Created by:
**Zensar Project Diamond Team**
""")

def get_file_download_link(file_path):
    """Generate a download link for a file"""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        data = f.read()
    b64 = base64.b64encode(data.encode()).decode()
    return f'<a href="data:text/html;base64,{b64}" download="{os.path.basename(file_path)}" class="download-button">Download</a>'

def parse_timestamp_from_filename(filename):
    """Extract timestamp from filename format app_name_code_analysis_YYYYMMDD_HHMMSS"""
    try:
        # Extract date and time part
        date_time_str = filename.split('_')[-2] + '_' + filename.split('_')[-1].split('.')[0]
        return datetime.strptime(date_time_str, '%Y%m%d_%H%M%S')
    except:
        return datetime.min

def create_dashboard_charts(results):
    """Create visualization charts for the dashboard"""
    # Summary Stats at the top
    st.subheader("Summary")
    stats_cols = st.columns(4)
    stats_cols[0].metric("Files Analyzed", results['summary']['files_analyzed'])
    stats_cols[1].metric("Demographic Fields", results['summary']['demographic_fields_found'])
    stats_cols[2].metric("Integration Patterns", results['summary']['integration_patterns_found'])
    stats_cols[3].metric("Unique Fields", len(results['summary']['unique_demographic_fields']))

    st.markdown("----")  # Add a separator line

    # 1. Demographic Fields Distribution - Side by side charts
    field_frequencies = {}
    for file_data in results['demographic_data'].values():
        for field_name, data in file_data.items():
            if field_name not in field_frequencies:
                field_frequencies[field_name] = len(data['occurrences'])
            else:
                field_frequencies[field_name] += len(data['occurrences'])

    # Create two columns for side-by-side charts
    col1, col2 = st.columns(2)

    with col1:
        # Pie Chart
        fig_demo_pie = px.pie(
            values=list(field_frequencies.values()),
            names=list(field_frequencies.keys()),
            title="Distribution of Demographic Fields (Pie Chart)",
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_demo_pie, use_container_width=True)

    with col2:
        # Bar Chart
        fig_demo_bar = px.bar(
            x=list(field_frequencies.keys()),
            y=list(field_frequencies.values()),
            title="Distribution of Demographic Fields (Bar Chart)",
            labels={'x': 'Field Name', 'y': 'Occurrences'},
            color=list(field_frequencies.keys()),
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_demo_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_demo_bar, use_container_width=True)

    # 2. Files by Language Bar Chart
    file_extensions = [Path(file['file_path']).suffix for file in results['summary']['file_details']]
    file_counts = Counter(file_extensions)

    fig_files = px.bar(
        x=list(file_counts.keys()),
        y=list(file_counts.values()),
        title="Files by Language",
        labels={'x': 'File Extension', 'y': 'Count'},
        color=list(file_counts.keys()),
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig_files.update_layout(showlegend=False)
    st.plotly_chart(fig_files)

    # 3. Integration Patterns Line Graph
    pattern_types = Counter(pattern['pattern_type'] for pattern in results['integration_patterns'])

    fig_patterns = go.Figure()
    fig_patterns.add_trace(go.Scatter(
        x=list(pattern_types.keys()),
        y=list(pattern_types.values()),
        mode='lines+markers',
        name='Pattern Count',
        line=dict(color='#0066cc', width=2),
        marker=dict(size=10)
    ))
    fig_patterns.update_layout(
        title="Integration Patterns Distribution",
        xaxis_title="Pattern Type",
        yaxis_title="Count",
        showlegend=False
    )
    st.plotly_chart(fig_patterns)

    # 4. Files and Fields Correlation
    fig_correlation = go.Figure()

    # Extract data for each file
    file_names = [os.path.basename(detail['file_path']) for detail in results['summary']['file_details']]
    demographic_counts = [detail['demographic_fields_found'] for detail in results['summary']['file_details']]
    integration_counts = [detail['integration_patterns_found'] for detail in results['summary']['file_details']]

    fig_correlation.add_trace(go.Bar(
        name='Demographic Fields',
        x=file_names,
        y=demographic_counts,
        marker_color='#0066cc'
    ))
    fig_correlation.add_trace(go.Bar(
        name='Integration Patterns',
        x=file_names,
        y=integration_counts,
        marker_color='#90EE90'
    ))

    fig_correlation.update_layout(
        title="Fields and Patterns by File",
        xaxis_title="File Name",
        yaxis_title="Count",
        barmode='group'
    )
    st.plotly_chart(fig_correlation)

def main():
    st.title("🔍 CodeLens")
    st.markdown("### Code Analysis Utility")

    # Sidebar
    # Add navigation in sidebar
    st.sidebar.header("Navigation")
    page = st.sidebar.selectbox(
        "Select Page",
        ["Code Analysis", "Excel Demographic Analysis", "Project Analysis", "Documentation"]
    )

    if page == "Code Analysis":
        st.sidebar.header("Analysis Settings")
        # Input method selection
        input_method = st.sidebar.radio(
            "Choose Input Method",
            ["Upload Files", "Repository Path"]
        )
    elif page == "Excel Demographic Analysis":
        st.header("📊 Excel Demographic Data Analysis")
        st.markdown("Upload an Excel file to analyze demographic data based on attr_description and export to 20 files.")

        # Sample file download
        st.subheader("📋 Sample Excel Format")
        st.markdown("""
        **Expected Columns:** `Legacy_Table`, `Attrribute`, `C360_Mapping`, `Mapping_in_C360`

        Download the sample Excel file to understand the expected format:
        """)

        if os.path.exists('sample_demographic_data.xlsx'):
            with open('sample_demographic_data.xlsx', 'rb') as f:
                st.download_button(
                    label="📥 Download Sample Excel Format",
                    data=f.read(),
                    file_name="sample_demographic_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("Sample file not found. Please create it first by running the application setup.")

        st.markdown("---")

        # Application name input for Excel analysis
        excel_app_name = st.sidebar.text_input("Application Name for Excel Analysis", "C360_Demographics")

        # Excel file upload
        uploaded_excel = st.sidebar.file_uploader(
            "Upload Excel File",
            type=['xlsx', 'xls'],
            help="Upload an Excel file containing demographic data with attr_description column"
        )

        # Option to upload source code for field search
        st.sidebar.markdown("---")
        st.sidebar.subheader("Source Code for Field Search")
        uploaded_source_zip = st.sidebar.file_uploader(
            "Upload Source Code (ZIP)",
            type=['zip'],
            key="source_zip",
            help="Upload source code ZIP to search for fields identified in Excel"
        )

        if uploaded_excel and st.sidebar.button("Analyze Excel Data"):
            try:
                # Save uploaded file temporarily
                temp_excel_path = f"temp_{uploaded_excel.name}"
                with open(temp_excel_path, 'wb') as f:
                    f.write(uploaded_excel.getbuffer())

                # Handle source code upload if provided
                source_repo_path = None
                if uploaded_source_zip:
                    source_temp_dir = tempfile.mkdtemp()
                    zip_path = os.path.join(source_temp_dir, uploaded_source_zip.name)
                    with open(zip_path, 'wb') as f:
                        f.write(uploaded_source_zip.getbuffer())
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(source_temp_dir)
                    os.remove(zip_path)
                    source_repo_path = source_temp_dir

                with st.spinner("Analyzing Excel demographic data (all sheets)..."):
                    analyzer = CodeAnalyzer(".", excel_app_name)
                    excel_results = analyzer.analyze_excel_demographic_data(temp_excel_path)

                    # Display results
                    st.subheader("Excel Analysis Results")

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Records", excel_results['summary']['total_records'])
                    col2.metric("Sheets Analyzed", excel_results['summary']['sheets_count'])
                    col3.metric("Fields Extracted", excel_results['summary']['fields_extracted'])
                    col4.metric("Files Exported", len(excel_results['summary']['exported_files']))

                    # Dashboard: Fields by Sheet
                    if excel_results.get('field_list'):
                        st.subheader("Dashboard: Fields Distribution")
                        field_df = pd.DataFrame(excel_results['field_list'])
                        field_df = field_df.drop(columns=['full_record'], errors='ignore')
                        
                        # Chart: Fields per Sheet
                        col1, col2 = st.columns(2)
                        with col1:
                            sheet_counts = field_df['sheet'].value_counts().reset_index()
                            sheet_counts.columns = ['Sheet', 'Fields Count']
                            fig_sheet = px.pie(sheet_counts, values='Fields Count', names='Sheet', 
                                             title='Fields by Sheet')
                            st.plotly_chart(fig_sheet, use_container_width=True)
                        
                        with col2:
                            # Chart: Top Tables
                            if 'table_name' in field_df.columns:
                                table_counts = field_df['table_name'].value_counts().head(15).reset_index()
                                table_counts.columns = ['Table Name', 'Fields Count']
                                fig_table = px.bar(table_counts, x='Table Name', y='Fields Count',
                                                  title='Top 15 Tables by Field Count')
                                st.plotly_chart(fig_table, use_container_width=True)
                        
                        # Sheets Analyzed
                        st.subheader("Sheets Analyzed")
                        st.info(f"Sheets: {', '.join(excel_results['sheets_analyzed'])}")
                        
                        # Field List Table
                        st.subheader("All Fields Extracted")
                        st.dataframe(field_df, use_container_width=True)

                        # Search fields in source code if provided
                        if source_repo_path:
                            st.subheader("Field Search in Source Code (with SQL Alias Detection)")
                            with st.spinner("Searching for fields in source code..."):
                                search_results = analyzer.search_fields_in_source_code(
                                    excel_results['field_list'],
                                    source_repo_path
                                )
                                
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Fields Searched", search_results['summary']['fields_searched'])
                                col2.metric("Fields Found", search_results['summary']['fields_found'])
                                col3.metric("Total Occurrences", search_results['summary']['total_occurrences'])
                                
                                # Chart: Match Types Distribution
                                if search_results['field_occurrences']:
                                    match_type_counts = {}
                                    for field_result in search_results['field_occurrences']:
                                        for occ in field_result['occurrences']:
                                            mt = occ.get('match_type', 'unknown')
                                            if 'alias' in mt:
                                                mt = 'alias.field'
                                            match_type_counts[mt] = match_type_counts.get(mt, 0) + 1
                                    
                                    if match_type_counts:
                                        mt_df = pd.DataFrame(list(match_type_counts.items()), columns=['Match Type', 'Count'])
                                        fig_mt = px.pie(mt_df, values='Count', names='Match Type',
                                                       title='Match Types (field_name, table.field, alias.field)')
                                        st.plotly_chart(fig_mt, use_container_width=True)
                                    
                                    # Show occurrences
                                    st.subheader("Field Occurrences in Source Code")
                                    for field_result in search_results['field_occurrences']:
                                        if field_result['occurrences']:
                                            with st.expander(f"Field: {field_result['field_name']} (Table: {field_result['table_name']}) - {len(field_result['occurrences'])} occurrences"):
                                                for occ in field_result['occurrences'][:20]:
                                                    st.markdown(f"**{occ['match_type']}** in `{os.path.basename(occ['file_path'])}` (Line {occ['line_number']})")
                                                    st.code(occ['code_snippet'])
                                else:
                                    st.info("No field occurrences found in source code.")

                        # Generate HTML Report
                        st.subheader("Download Analysis Report")
                        
                        def generate_excel_analysis_html_report():
                            from datetime import datetime
                            import plotly.io as pio
                            
                            sheet_counts = field_df['sheet'].value_counts().reset_index()
                            sheet_counts.columns = ['Sheet', 'Fields Count']
                            fig_sheet = px.pie(sheet_counts, values='Fields Count', names='Sheet', title='Fields by Sheet')
                            pie_chart_html = pio.to_html(fig_sheet, full_html=False, include_plotlyjs='cdn')
                            
                            bar_chart_html = ""
                            if 'table_name' in field_df.columns:
                                table_counts = field_df['table_name'].value_counts().head(15).reset_index()
                                table_counts.columns = ['Table Name', 'Fields Count']
                                fig_table = px.bar(table_counts, x='Table Name', y='Fields Count', title='Top 15 Tables by Field Count')
                                bar_chart_html = pio.to_html(fig_table, full_html=False, include_plotlyjs=False)
                            
                            field_table_html = field_df.to_html(index=False, classes='data-table')
                            
                            source_code_section = ""
                            if source_repo_path and 'search_results' in dir():
                                source_code_section = "<h2>Source Code Field Search</h2>"
                                source_code_section += f"<p>Fields Searched: {search_results['summary']['fields_searched']}</p>"
                                source_code_section += f"<p>Fields Found: {search_results['summary']['fields_found']}</p>"
                                source_code_section += f"<p>Total Occurrences: {search_results['summary']['total_occurrences']}</p>"
                            
                            html = f"""<!DOCTYPE html>
<html><head><title>Excel Demographic Analysis Report</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
h2 {{ color: #555; margin-top: 30px; }}
.summary {{ display: flex; gap: 20px; margin: 20px 0; }}
.metric {{ background: #e8f5e9; padding: 20px; border-radius: 8px; text-align: center; flex: 1; }}
.metric h3 {{ margin: 0; color: #2e7d32; font-size: 24px; }}
.metric p {{ margin: 5px 0 0; color: #666; }}
.charts {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.chart {{ flex: 1; min-width: 400px; }}
.data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
.data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
.data-table th {{ background: #4CAF50; color: white; }}
.data-table tr:nth-child(even) {{ background: #f9f9f9; }}
.sheets {{ background: #e3f2fd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
</style></head><body>
<div class="container">
<h1>Excel Demographic Analysis Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="summary">
<div class="metric"><h3>{excel_results['summary']['total_records']}</h3><p>Total Records</p></div>
<div class="metric"><h3>{excel_results['summary']['sheets_count']}</h3><p>Sheets Analyzed</p></div>
<div class="metric"><h3>{excel_results['summary']['fields_extracted']}</h3><p>Fields Extracted</p></div>
</div>

<div class="sheets">
<strong>Sheets Analyzed:</strong> {', '.join(excel_results['sheets_analyzed'])}
</div>

<h2>Fields Distribution</h2>
<div class="charts">
<div class="chart">{pie_chart_html}</div>
<div class="chart">{bar_chart_html}</div>
</div>

<h2>All Fields Extracted</h2>
{field_table_html}

{source_code_section}
</div></body></html>"""
                            return html
                        
                        html_report = generate_excel_analysis_html_report()
                        st.download_button(
                            label="Download HTML Analysis Report",
                            data=html_report,
                            file_name=f"excel_demographic_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html"
                        )
                    else:
                        st.warning("No fields found in the uploaded Excel file. Make sure it has 'Legacy_Table' and 'Attrribute' columns.")

                # Clean up temp file
                os.remove(temp_excel_path)

            except Exception as e:
                st.error(f"Error analyzing Excel file: {str(e)}")
                if 'temp_excel_path' in locals() and os.path.exists(temp_excel_path):
                    os.remove(temp_excel_path)

        return

    elif page == "Project Analysis":
        st.header("📐 Project Analysis - Data Flow & Diagrams")
        st.markdown("""
        Analyze PySpark, Python, and SQL projects to generate:
        - **Class Diagrams** - Shows class hierarchy and relationships
        - **Function Call Graphs** - Shows which functions call other functions
        - **Data Flow Diagrams** - Shows how data moves through Spark/SQL transformations
        """)
        
        st.sidebar.subheader("Upload Project")
        project_zip = st.sidebar.file_uploader(
            "Upload Project ZIP",
            type=['zip'],
            key="project_analysis_zip",
            help="Upload a ZIP file containing your PySpark/Python/SQL project"
        )
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Filter by Excel (Optional)")
        filter_excel = st.sidebar.file_uploader(
            "Upload Excel for Filtering",
            type=['xlsx', 'xls'],
            key="project_filter_excel",
            help="Upload Excel with Legacy_Table and Attrribute columns to filter analysis results"
        )
        
        excel_filter_fields = []
        excel_sheets_data = {}
        if filter_excel:
            try:
                temp_excel = f"temp_filter_{filter_excel.name}"
                with open(temp_excel, 'wb') as f:
                    f.write(filter_excel.getbuffer())
                
                excel_file = pd.ExcelFile(temp_excel)
                all_fields = []
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(temp_excel, sheet_name=sheet_name)
                    table_col = None
                    field_col = None
                    c360_mapping_col = None
                    mapping_in_c360_col = None
                    for col in df.columns:
                        col_lower = col.strip().lower()
                        if col_lower == 'legacy_table':
                            table_col = col
                        if col_lower == 'attrribute' or col_lower == 'attribute':
                            field_col = col
                        if col_lower == 'c360_mapping':
                            c360_mapping_col = col
                        if col_lower == 'mapping_in_c360':
                            mapping_in_c360_col = col
                    
                    sheet_fields = []
                    if table_col or field_col:
                        for idx, row in df.iterrows():
                            table_name = str(row[table_col]).strip() if table_col and pd.notna(row[table_col]) else ''
                            field_value = str(row[field_col]).strip() if field_col and pd.notna(row[field_col]) else ''
                            c360_mapping = str(row[c360_mapping_col]).strip() if c360_mapping_col and pd.notna(row[c360_mapping_col]) else ''
                            mapping_in_c360 = str(row[mapping_in_c360_col]).strip() if mapping_in_c360_col and pd.notna(row[mapping_in_c360_col]) else ''
                            
                            individual_fields = field_value.split() if field_value else []
                            if not individual_fields and table_name:
                                individual_fields = ['']
                            
                            skip_values = ['na', 'n/a', 'nil', 'nill', 'null', '', ' ', '-', 'none']
                            
                            for field_name in individual_fields:
                                field_name = field_name.strip()
                                if field_name.lower() in skip_values:
                                    continue
                                if table_name or field_name:
                                    field_data = {
                                        'table': table_name, 
                                        'field': field_name,
                                        'original_cell': field_value if len(individual_fields) > 1 else '',
                                        'sheet': sheet_name,
                                        'c360_mapping': c360_mapping,
                                        'mapping_in_c360': mapping_in_c360
                                    }
                                    all_fields.append(field_data)
                                    sheet_fields.append(field_data)
                    
                    if sheet_fields:
                        excel_sheets_data[sheet_name] = sheet_fields
                
                excel_filter_fields = all_fields
                os.remove(temp_excel)
                st.sidebar.success(f"Loaded {len(excel_filter_fields)} fields from {len(excel_sheets_data)} sheets")
            except Exception as e:
                st.sidebar.error(f"Error reading Excel: {str(e)}")
        
        if project_zip and st.sidebar.button("Analyze Project"):
            try:
                temp_dir = tempfile.mkdtemp()
                zip_path = os.path.join(temp_dir, project_zip.name)
                with open(zip_path, 'wb') as f:
                    f.write(project_zip.getbuffer())
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                os.remove(zip_path)
                
                with st.spinner("Analyzing project structure..."):
                    analyzer = ProjectAnalyzer(temp_dir)
                    results = analyzer.analyze()
                
                st.subheader("Analysis Summary")
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Python Files", results['summary']['total_python_files'])
                col2.metric("SQL Files", results['summary']['total_sql_files'])
                col3.metric("Java Files", results['summary'].get('total_java_files', 0))
                col4.metric("Shell Files", results['summary'].get('total_shell_files', 0))
                col5.metric("Batch Files", results['summary'].get('total_batch_files', 0))
                
                col6, col7, col8, col9 = st.columns(4)
                col6.metric("Classes Found", results['summary']['total_classes'])
                col7.metric("Functions Found", results['summary']['total_functions'])
                col8.metric("Data Flows", results['summary']['total_data_flows'])
                col9.metric("SQL Flows", results['summary']['total_sql_flows'])
                
                if excel_filter_fields:
                    tab1, tab2, tab3, tab4 = st.tabs(["Class Diagram", "Function Calls", "Data Flow", "Excel Field Search"])
                else:
                    tab1, tab2, tab3 = st.tabs(["Class Diagram", "Function Calls", "Data Flow"])
                
                with tab1:
                    st.subheader("Class Diagram")
                    class_data = analyzer.generate_class_diagram_data()
                    
                    if class_data['nodes']:
                        import plotly.graph_objects as go
                        import math
                        
                        nodes = class_data['nodes']
                        n_nodes = len(nodes)
                        
                        node_x = []
                        node_y = []
                        for i, node in enumerate(nodes):
                            angle = 2 * math.pi * i / n_nodes
                            node_x.append(math.cos(angle))
                            node_y.append(math.sin(angle))
                        
                        node_labels = {node['label']: i for i, node in enumerate(nodes)}
                        
                        edge_x = []
                        edge_y = []
                        for edge in class_data['edges']:
                            if edge['from'] in node_labels and edge['to'] in node_labels:
                                x0, y0 = node_x[node_labels[edge['from']]], node_y[node_labels[edge['from']]]
                                x1, y1 = node_x[node_labels[edge['to']]], node_y[node_labels[edge['to']]]
                                edge_x.extend([x0, x1, None])
                                edge_y.extend([y0, y1, None])
                        
                        fig = go.Figure()
                        
                        if edge_x:
                            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                                line=dict(width=2, color='#888'), hoverinfo='none', name='Inheritance'))
                        
                        node_text = [f"{n['label']}<br>Attrs: {len(n['attributes'])}<br>Methods: {len(n['methods'])}" for n in nodes]
                        node_sizes = [20 + len(n['attributes']) + len(n['methods']) for n in nodes]
                        
                        fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text',
                            marker=dict(size=node_sizes, color='#4CAF50', line=dict(width=2, color='white')),
                            text=[n['label'] for n in nodes], textposition='top center',
                            hovertext=node_text, hoverinfo='text', name='Classes'))
                        
                        fig.update_layout(title='Class Diagram', showlegend=False, 
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            height=500)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader("Class Details")
                        for node in class_data['nodes']:
                            with st.expander(f"Class: {node['label']} ({node['file']})"):
                                if node['attributes']:
                                    st.markdown("**Attributes:**")
                                    for attr in node['attributes']:
                                        st.markdown(f"  - {attr}")
                                if node['methods']:
                                    st.markdown("**Methods:**")
                                    for method in node['methods']:
                                        st.markdown(f"  - {method}()")
                        
                        if class_data['edges']:
                            st.subheader("Inheritance Relationships")
                            inherit_df = pd.DataFrame([{'Child': e['from'], 'Parent': e['to']} for e in class_data['edges']])
                            st.dataframe(inherit_df, use_container_width=True)
                    else:
                        st.info("No classes found in the project.")
                
                with tab2:
                    st.subheader("Function Call Graph")
                    func_data = analyzer.generate_function_call_graph()
                    
                    if func_data['nodes']:
                        import plotly.graph_objects as go
                        import math
                        
                        nodes = func_data['nodes']
                        n_nodes = len(nodes)
                        
                        node_x = []
                        node_y = []
                        for i, node in enumerate(nodes):
                            angle = 2 * math.pi * i / max(n_nodes, 1)
                            radius = 1 + (i % 3) * 0.3
                            node_x.append(radius * math.cos(angle))
                            node_y.append(radius * math.sin(angle))
                        
                        node_labels = {node['label']: i for i, node in enumerate(nodes)}
                        
                        edge_x = []
                        edge_y = []
                        for edge in func_data['edges'][:200]:
                            if edge['from'] in node_labels and edge['to'] in node_labels:
                                x0, y0 = node_x[node_labels[edge['from']]], node_y[node_labels[edge['from']]]
                                x1, y1 = node_x[node_labels[edge['to']]], node_y[node_labels[edge['to']]]
                                edge_x.extend([x0, x1, None])
                                edge_y.extend([y0, y1, None])
                        
                        fig = go.Figure()
                        
                        if edge_x:
                            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                                line=dict(width=1, color='#888'), hoverinfo='none', name='Calls'))
                        
                        type_colors = {'function': '#2196F3', 'method': '#FF9800', 'shell_function': '#9C27B0', 'batch_function': '#E91E63'}
                        node_colors = [type_colors.get(n['type'], '#4CAF50') for n in nodes]
                        node_text = [f"{n['label']}<br>Type: {n['type']}<br>File: {n.get('file', '-')}" for n in nodes]
                        
                        fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text',
                            marker=dict(size=15, color=node_colors, line=dict(width=1, color='white')),
                            text=[n['label'][:20] for n in nodes], textposition='top center', textfont=dict(size=8),
                            hovertext=node_text, hoverinfo='text', name='Functions'))
                        
                        fig.update_layout(title='Function Call Graph', showlegend=False,
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            height=500)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        type_counts = {}
                        for n in nodes:
                            t = n['type']
                            type_counts[t] = type_counts.get(t, 0) + 1
                        type_df = pd.DataFrame(list(type_counts.items()), columns=['Function Type', 'Count'])
                        fig2 = px.pie(type_df, values='Count', names='Function Type', title='Function Types Distribution')
                        st.plotly_chart(fig2, use_container_width=True)
                        
                        st.subheader("Function Details")
                        func_df = pd.DataFrame([{
                            'Function': n['label'],
                            'Type': n['type'],
                            'Class': n.get('class', '-'),
                            'File': n.get('file', '-')
                        } for n in func_data['nodes']])
                        st.dataframe(func_df, use_container_width=True)
                        
                        if func_data['edges']:
                            st.subheader("Function Calls Table")
                            call_df = pd.DataFrame([{
                                'Caller': e['from'],
                                'Calls': e['to']
                            } for e in func_data['edges'][:100]])
                            st.dataframe(call_df, use_container_width=True)
                    else:
                        st.info("No functions found in the project.")
                
                with tab3:
                    st.subheader("Data Flow Diagram")
                    flow_data = analyzer.generate_data_flow_diagram()
                    
                    if flow_data['nodes']:
                        import plotly.graph_objects as go
                        import math
                        
                        nodes = flow_data['nodes']
                        n_nodes = len(nodes)
                        
                        type_groups = {}
                        for i, node in enumerate(nodes):
                            t = node['type']
                            if t not in type_groups:
                                type_groups[t] = []
                            type_groups[t].append(i)
                        
                        node_x = [0] * n_nodes
                        node_y = [0] * n_nodes
                        y_offset = 0
                        for t, indices in type_groups.items():
                            for j, idx in enumerate(indices):
                                node_x[idx] = j - len(indices) / 2
                                node_y[idx] = y_offset
                            y_offset -= 1.5
                        
                        node_labels = {node['label']: i for i, node in enumerate(nodes)}
                        
                        edge_x = []
                        edge_y = []
                        for edge in flow_data['edges'][:200]:
                            if edge['from'] in node_labels and edge['to'] in node_labels:
                                x0, y0 = node_x[node_labels[edge['from']]], node_y[node_labels[edge['from']]]
                                x1, y1 = node_x[node_labels[edge['to']]], node_y[node_labels[edge['to']]]
                                edge_x.extend([x0, x1, None])
                                edge_y.extend([y0, y1, None])
                        
                        fig = go.Figure()
                        
                        if edge_x:
                            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                                line=dict(width=1.5, color='#666'), hoverinfo='none', name='Data Flow'))
                        
                        type_colors = {'table': '#4CAF50', 'column': '#2196F3', 'dataframe': '#FF9800', 
                                      'variable': '#9C27B0', 'file': '#E91E63', 'spark_read': '#00BCD4',
                                      'spark_write': '#FF5722', 'sql_table': '#795548'}
                        node_colors = [type_colors.get(n['type'], '#607D8B') for n in nodes]
                        node_text = [f"{n['label']}<br>Type: {n['type']}<br>File: {n.get('file', '-')}" for n in nodes]
                        
                        fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text',
                            marker=dict(size=18, color=node_colors, line=dict(width=1, color='white'), symbol='square'),
                            text=[n['label'][:25] for n in nodes], textposition='top center', textfont=dict(size=8),
                            hovertext=node_text, hoverinfo='text', name='Data Nodes'))
                        
                        fig.update_layout(title='Data Flow Diagram', showlegend=False,
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            height=600)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            type_counts = pd.DataFrame([n['type'] for n in flow_data['nodes']]).value_counts().reset_index()
                            type_counts.columns = ['Node Type', 'Count']
                            fig2 = px.pie(type_counts, values='Count', names='Node Type', title='Data Flow Node Types')
                            st.plotly_chart(fig2, use_container_width=True)
                        
                        with col2:
                            if flow_data['edges']:
                                edge_types = pd.DataFrame([e['type'] for e in flow_data['edges']]).value_counts().reset_index()
                                edge_types.columns = ['Edge Type', 'Count']
                                fig3 = px.bar(edge_types, x='Edge Type', y='Count', title='Data Flow Edge Types')
                                st.plotly_chart(fig3, use_container_width=True)
                        
                        st.subheader("Data Flow Details")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Data Nodes:**")
                            node_df = pd.DataFrame([{
                                'Name': n['label'],
                                'Type': n['type'],
                                'File': n.get('file', '-')
                            } for n in flow_data['nodes']])
                            st.dataframe(node_df, use_container_width=True)
                        
                        with col2:
                            st.markdown("**Data Edges:**")
                            if flow_data['edges']:
                                edge_df = pd.DataFrame([{
                                    'From': e['from'],
                                    'To': e['to'],
                                    'Type': e['type']
                                } for e in flow_data['edges']])
                                st.dataframe(edge_df, use_container_width=True)
                    else:
                        st.info("No data flows found. Make sure the project contains PySpark or SQL code.")
                
                if excel_filter_fields:
                    with tab4:
                        st.subheader("Excel Field Search in Project")
                        st.markdown(f"Searching for **{len(excel_filter_fields)}** fields from **{len(excel_sheets_data)}** sheets in the project code...")
                        
                        import re
                        flow_data = analyzer.generate_data_flow_diagram()
                        
                        def search_field_in_code(field_name, table_name):
                            matches = []
                            matched_classes = []
                            matched_functions = []
                            matched_dataflows = []
                            
                            def get_file_info(file_path):
                                fname = os.path.basename(file_path) if file_path and file_path != '-' else '-'
                                return fname, file_path
                            
                            for cls in results['classes']:
                                cls_matched = False
                                fname, fpath = get_file_info(cls.file_path)
                                if field_name.lower() in cls.name.lower():
                                    matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                    cls_matched = True
                                for attr in cls.attributes:
                                    if field_name.lower() in attr.lower():
                                        matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                        cls_matched = True
                                for method in cls.methods:
                                    if field_name.lower() in method.lower():
                                        matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                        cls_matched = True
                                if cls_matched:
                                    matched_classes.append(cls)
                            
                            for func in results['functions']:
                                func_matched = False
                                fname, fpath = get_file_info(func.file_path)
                                if field_name.lower() in func.name.lower():
                                    matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                    func_matched = True
                                for param in func.parameters:
                                    if field_name.lower() in param.lower():
                                        matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                        func_matched = True
                                if func_matched:
                                    matched_functions.append(func)
                            
                            for node in flow_data['nodes']:
                                if field_name.lower() in node['label'].lower() or (table_name and table_name.lower() in node['label'].lower()):
                                    fname, fpath = get_file_info(node.get('file', '-'))
                                    matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                                    matched_dataflows.append(node)
                            
                            for sql_info in results.get('sql_statements', []):
                                sql_text = sql_info.get('sql', '').lower()
                                fname, fpath = get_file_info(sql_info.get('file_path', '-'))
                                if field_name.lower() in sql_text or (table_name and table_name.lower() in sql_text):
                                    matches.append({'attribute': field_name, 'file_name': fname, 'file_path': fpath})
                            
                            unique_matches = []
                            seen = set()
                            for m in matches:
                                key = (m['attribute'], m['file_name'], m['file_path'])
                                if key not in seen:
                                    seen.add(key)
                                    unique_matches.append(m)
                            
                            return unique_matches, matched_classes, matched_functions, matched_dataflows
                        
                        all_sheet_results = {}
                        total_matches = 0
                        total_fields_found = 0
                        
                        for sheet_name, sheet_fields in excel_sheets_data.items():
                            sheet_results = []
                            for field_info in sheet_fields:
                                table_name = field_info['table']
                                field_name = field_info['field']
                                c360_mapping = field_info.get('c360_mapping', '')
                                mapping_in_c360 = field_info.get('mapping_in_c360', '')
                                if not field_name:
                                    continue
                                matches, matched_classes, matched_functions, matched_dataflows = search_field_in_code(field_name, table_name)
                                if matches:
                                    sheet_results.append({
                                        'table': table_name,
                                        'field': field_name,
                                        'c360_mapping': c360_mapping,
                                        'mapping_in_c360': mapping_in_c360,
                                        'matches': matches,
                                        'match_count': len(matches),
                                        'classes': matched_classes,
                                        'functions': matched_functions,
                                        'dataflows': matched_dataflows
                                    })
                                    total_matches += len(matches)
                                    total_fields_found += 1
                            all_sheet_results[sheet_name] = sheet_results
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Total Fields", len(excel_filter_fields))
                        col2.metric("Sheets Analyzed", len(excel_sheets_data))
                        col3.metric("Fields Found", total_fields_found)
                        col4.metric("Total Matches", total_matches)
                        
                        def generate_html_report():
                            from datetime import datetime
                            import plotly.io as pio
                            
                            sheet_summary_data = []
                            for sheet_name, sheet_results in all_sheet_results.items():
                                sheet_summary_data.append({
                                    'Sheet': sheet_name,
                                    'Fields': len(excel_sheets_data.get(sheet_name, [])),
                                    'Fields Found': len(sheet_results),
                                    'Matches': sum(r['match_count'] for r in sheet_results)
                                })
                            
                            summary_df = pd.DataFrame(sheet_summary_data)
                            fig_summary = px.bar(summary_df, x='Sheet', y=['Fields', 'Fields Found', 'Matches'],
                                        title='Field Analysis by Sheet', barmode='group')
                            summary_chart_html = pio.to_html(fig_summary, full_html=False, include_plotlyjs='cdn')
                            
                            html = f"""<!DOCTYPE html>
<html><head><title>Project Analysis Report</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
.container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
h2, h3 {{ color: #555; }}
.sheet {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #fafafa; }}
.field {{ margin: 10px 0; padding: 15px; background: white; border-left: 4px solid #4CAF50; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.mapping {{ background: #fff3e0; padding: 10px; margin: 10px 0; border-radius: 5px; }}
.mapping strong {{ color: #e65100; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #4CAF50; color: white; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.class-info, .func-info, .flow-info {{ margin: 5px 0; padding: 10px; background: #e8f5e9; border-radius: 4px; }}
.summary {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; display: flex; gap: 20px; }}
.metric {{ flex: 1; text-align: center; padding: 15px; background: white; border-radius: 8px; }}
.metric h3 {{ margin: 0; color: #1976d2; font-size: 28px; }}
.metric p {{ margin: 5px 0 0; color: #666; }}
</style></head><body>
<div class="container">
<h1>Project Analysis Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="summary">
<div class="metric"><h3>{len(excel_filter_fields)}</h3><p>Total Fields</p></div>
<div class="metric"><h3>{len(excel_sheets_data)}</h3><p>Sheets Analyzed</p></div>
<div class="metric"><h3>{total_fields_found}</h3><p>Fields Found</p></div>
<div class="metric"><h3>{total_matches}</h3><p>Total Matches</p></div>
</div>

<h2>Summary by Sheet</h2>
{summary_chart_html}

<h2>Field Mapping Summary</h2>
<table>
<tr><th>Sheet</th><th>Field</th><th>Table</th><th>C360_Mapping</th><th>Mapping_in_C360</th><th>Matches</th></tr>
"""
                            for sheet_name, sheet_results in all_sheet_results.items():
                                for sr in sheet_results:
                                    html += f'<tr><td>{sheet_name}</td><td>{sr["field"]}</td><td>{sr["table"]}</td><td>{sr.get("c360_mapping", "")}</td><td>{sr.get("mapping_in_c360", "")}</td><td>{sr["match_count"]}</td></tr>'
                            html += '</table>'
                            
                            for sheet_name, sheet_results in all_sheet_results.items():
                                html += f'<div class="sheet"><h2>Sheet: {sheet_name}</h2>'
                                html += f'<p>Fields in sheet: {len(excel_sheets_data.get(sheet_name, []))}, Fields found: {len(sheet_results)}</p>'
                                
                                if sheet_results:
                                    for sr in sheet_results:
                                        html += f'<div class="field"><h3>Field: {sr["field"]} (Table: {sr["table"]})</h3>'
                                        
                                        if sr.get('c360_mapping') or sr.get('mapping_in_c360'):
                                            html += '<div class="mapping">'
                                            if sr.get('c360_mapping'):
                                                html += f'<strong>C360_Mapping:</strong> {sr["c360_mapping"]}<br>'
                                            if sr.get('mapping_in_c360'):
                                                html += f'<strong>Mapping_in_C360:</strong> {sr["mapping_in_c360"]}'
                                            html += '</div>'
                                        
                                        html += f'<p><strong>Total Matches:</strong> {sr["match_count"]}</p>'
                                        
                                        html += '<table><tr><th>Attribute</th><th>File Name</th><th>File Path</th></tr>'
                                        for m in sr['matches']:
                                            html += f'<tr><td>{m.get("attribute", "-")}</td><td>{m.get("file_name", "-")}</td><td>{m.get("file_path", "-")}</td></tr>'
                                        html += '</table>'
                                        
                                        if sr['classes']:
                                            html += '<h4>Class Details:</h4>'
                                            for cls in sr['classes']:
                                                html += f'<div class="class-info"><strong>{cls.name}</strong> ({cls.file_path})<br>'
                                                html += f'Attributes: {", ".join(cls.attributes) if cls.attributes else "None"}<br>'
                                                html += f'Methods: {", ".join(cls.methods) if cls.methods else "None"}</div>'
                                        
                                        if sr['functions']:
                                            html += '<h4>Function Calls:</h4>'
                                            for func in sr['functions']:
                                                html += f'<div class="func-info"><strong>{func.name}</strong> ({func.file_path})<br>'
                                                html += f'Parameters: {", ".join(func.parameters) if func.parameters else "None"}<br>'
                                                html += f'Calls: {", ".join(func.calls) if func.calls else "None"}</div>'
                                        
                                        if sr['dataflows']:
                                            html += '<h4>Data Flows:</h4>'
                                            for df in sr['dataflows']:
                                                html += f'<div class="flow-info">{df["label"]} (File: {df.get("file", "-")})</div>'
                                        
                                        html += '</div>'
                                else:
                                    html += '<p>No fields found in code.</p>'
                                html += '</div>'
                            
                            html += '</div></body></html>'
                            return html
                        
                        if total_fields_found > 0:
                            html_report = generate_html_report()
                            st.download_button(
                                label="Download HTML Report",
                                data=html_report,
                                file_name=f"project_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                                mime="text/html"
                            )
                        
                        sheet_summary = []
                        for sheet_name, sheet_results in all_sheet_results.items():
                            sheet_summary.append({
                                'Sheet': sheet_name,
                                'Fields': len(excel_sheets_data.get(sheet_name, [])),
                                'Fields Found': len(sheet_results),
                                'Matches': sum(r['match_count'] for r in sheet_results)
                            })
                        
                        if sheet_summary:
                            st.subheader("Summary by Sheet")
                            summary_df = pd.DataFrame(sheet_summary)
                            st.dataframe(summary_df, use_container_width=True)
                            
                            fig = px.bar(summary_df, x='Sheet', y=['Fields', 'Fields Found', 'Matches'],
                                        title='Field Analysis by Sheet', barmode='group')
                            st.plotly_chart(fig, use_container_width=True)
                        
                        st.subheader("Detailed Analysis by Sheet")
                        sheet_tabs = st.tabs(list(excel_sheets_data.keys()))
                        
                        for i, (sheet_name, sheet_fields) in enumerate(excel_sheets_data.items()):
                            with sheet_tabs[i]:
                                sheet_results = all_sheet_results.get(sheet_name, [])
                                
                                st.markdown(f"**Sheet: {sheet_name}** - {len(sheet_fields)} fields, {len(sheet_results)} found in code")
                                
                                if sheet_results:
                                    match_type_counts = {}
                                    for sr in sheet_results:
                                        for m in sr['matches']:
                                            mt = m['type']
                                            match_type_counts[mt] = match_type_counts.get(mt, 0) + 1
                                    
                                    if match_type_counts:
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            mt_df = pd.DataFrame(list(match_type_counts.items()), columns=['Match Type', 'Count'])
                                            fig = px.pie(mt_df, values='Count', names='Match Type', title='Match Types')
                                            st.plotly_chart(fig, use_container_width=True)
                                        with col2:
                                            field_summary = pd.DataFrame([{
                                                'Field': r['field'],
                                                'Table': r['table'],
                                                'C360_Mapping': r.get('c360_mapping', ''),
                                                'Mapping_in_C360': r.get('mapping_in_c360', ''),
                                                'Matches': r['match_count']
                                            } for r in sheet_results])
                                            st.dataframe(field_summary, use_container_width=True)
                                    
                                    st.markdown("**Field Details with File Paths:**")
                                    for sr in sheet_results:
                                        expander_title = f"{sr['field']} (Table: {sr['table']})"
                                        if sr.get('c360_mapping'):
                                            expander_title += f" | C360: {sr['c360_mapping']}"
                                        expander_title += f" - {sr['match_count']} matches"
                                        
                                        with st.expander(expander_title):
                                            if sr.get('c360_mapping') or sr.get('mapping_in_c360'):
                                                st.info(f"**C360_Mapping:** {sr.get('c360_mapping', 'N/A')} | **Mapping_in_C360:** {sr.get('mapping_in_c360', 'N/A')}")
                                            
                                            match_df = pd.DataFrame(sr['matches'])
                                            st.dataframe(match_df, use_container_width=True)
                                            
                                            if sr['classes']:
                                                st.markdown("**Related Classes:**")
                                                for cls in sr['classes']:
                                                    st.markdown(f"- **{cls.name}** - `{cls.file_path}`")
                                                    st.markdown(f"  - Attributes: {', '.join(cls.attributes) if cls.attributes else 'None'}")
                                                    st.markdown(f"  - Methods: {', '.join(cls.methods) if cls.methods else 'None'}")
                                            
                                            if sr['functions']:
                                                st.markdown("**Related Functions:**")
                                                for func in sr['functions']:
                                                    st.markdown(f"- **{func.name}** - `{func.file_path}`")
                                                    st.markdown(f"  - Parameters: {', '.join(func.parameters) if func.parameters else 'None'}")
                                                    st.markdown(f"  - Calls: {', '.join(func.calls) if func.calls else 'None'}")
                                            
                                            if sr['dataflows']:
                                                st.markdown("**Related Data Flows:**")
                                                for df in sr['dataflows']:
                                                    st.markdown(f"- {df['label']} - `{df.get('file', '-')}`")
                                else:
                                    st.info(f"No fields from sheet '{sheet_name}' found in the project code.")
                
            except Exception as e:
                st.error(f"Error analyzing project: {str(e)}")
        
        return

    elif page == "Documentation":
        st.header("📖 Documentation")

        doc_section = st.sidebar.radio(
            "Select Section",
            ["Overview", "README File", "Installation Steps", "Features"]
        )

        if doc_section == "Overview":
            st.subheader("CodeLens - Advanced Code Analysis Utility")
            st.markdown("""
            ### Key Features
            - Demographic data detection in source code
            - Integration pattern analysis
            - ZIP folder upload support for bulk file analysis
            - Excel demographic data analysis with attr_description
            - Export to multiple files (20 files for Excel analysis)
            - Interactive dashboards
            - Detailed reports generation
            - Multi-language support (Java, Python, JavaScript, TypeScript, C#, PHP, Ruby, XSD)
            - Advanced pattern recognition with fuzzy matching algorithms

            ### Built by Zensar Project Diamond Team
            A comprehensive web-based source code analysis tool designed to extract demographic data and integration patterns across multiple programming languages.
            """)

        elif doc_section == "README File":
            st.subheader("📄 Complete README Documentation")

            # Read and display the README file content
            try:
                with open('README.md', 'r', encoding='utf-8') as f:
                    readme_content = f.read()
                st.markdown(readme_content)
            except FileNotFoundError:
                st.error("README.md file not found")
            except Exception as e:
                st.error(f"Error reading README.md: {str(e)}")

        elif doc_section == "Installation Steps":
            st.subheader("🛠 Installation & Setup Guide")
            
            st.markdown("""
            ### Prerequisites
            - **Python 3.11+** installed on your system
            - **Web Browser** with JavaScript enabled

            ### Installation Steps
            1. **Download/Clone** the project files to your local machine
            2. **Install Dependencies**:
               ```bash
               pip install streamlit plotly pandas openpyxl pygments fuzzywuzzy python-levenshtein
               ```
            3. **Run the Application**:
               ```bash
               streamlit run app.py --server.address 0.0.0.0 --server.port 5000
               ```
            4. **Access**: Navigate to `http://localhost:5000` in your browser

            ### Alternative Installation
            You can also install dependencies using pip with the following packages:
            - streamlit - Web application framework
            - plotly - Interactive visualizations
            - pandas - Data manipulation and analysis
            - openpyxl - Excel file handling
            - pygments - Code syntax highlighting
            - fuzzywuzzy - Fuzzy string matching
            - python-levenshtein - String distance calculations

            ### Quick Start Guide
            This application is designed to run seamlessly on any Python environment. Simply:
            1. **Download the project** files to your system
            2. **Install dependencies** using pip as shown above
            3. **Run the application** using the streamlit command
            4. **Access your application** at `http://0.0.0.0:5000`

            ### Dependencies
            The following packages are automatically installed:
            - `streamlit` - Web application framework
            - `plotly` - Interactive visualizations
            - `pandas` - Data manipulation and analysis
            - `openpyxl` - Excel file handling
            - `pygments` - Code syntax highlighting
            - `fuzzywuzzy` - Fuzzy string matching
            - `python-levenshtein` - String distance calculations
            """)

        elif doc_section == "Features":
            st.subheader("🚀 Detailed Features Overview")

            st.markdown("""
            ### Core Analysis Capabilities
            - **Multi-Language Support**: Analyzes code across 8+ programming languages
              - Java, Python, JavaScript, TypeScript, C#, PHP, Ruby, XSD
            - **Demographic Data Detection**: Advanced pattern recognition for personal information
            - **Integration Pattern Analysis**: Identifies REST APIs, SOAP services, database operations, messaging systems
            - **ZIP File Support**: Upload entire project folders as ZIP files for bulk analysis
            - **Excel Analysis**: Demographic data extraction from Excel files using fuzzy matching algorithms

            ### Data Types Detected

            #### Personal Information
            - **Names**: Embossed Name, Primary Name, Secondary Name, Legal Name, DBA Name, Double Byte Name
            - **Identity**: Gender, Date of Birth (DOB), Government IDs, SSN, Tax ID, Passport
            - **Contact Information**: Multiple phone types, email addresses, preference language

            #### Address Information  
            - **Multiple Address Types**: Home, Business, Alternate, Temporary, Other
            - **Address Arrays**: Support for multiple address entries

            #### Advanced Analysis
            - **Fuzzy Matching Algorithm**: Identifies demographic data with variations in naming
            - **Pattern Confidence Scoring**: Provides match reliability metrics
            - **Export Capabilities**: Generate reports in multiple formats (HTML, JSON, Excel)

            ### Interactive Dashboard
            - **Visual Analytics**: Pie charts, bar graphs, line charts for data distribution
            - **File Statistics**: Language distribution and analysis metrics
            - **Integration Patterns**: Visual representation of detected patterns
            - **Real-time Analysis**: Live progress tracking during code scanning

            ### Export & Reporting
            - **Multi-Format Export**: HTML, JSON, Excel support
            - **Batch Processing**: Handle multiple files simultaneously
            - **Historical Reports**: Timestamped report management
            - **Download Management**: Organized file download system
            """)

            # Add download button for README file
            st.markdown("---")
            st.subheader("📥 Download Documentation")
            try:
                with open('README.md', 'rb') as f:
                    st.download_button(
                        label="Download Complete README.md",
                        data=f.read(),
                        file_name="CodeLens_README.md",
                        mime="text/markdown"
                    )
            except FileNotFoundError:
                st.info("README.md file not available for download")
        return

    # Application name input
    app_name = st.sidebar.text_input("Application Name", "MyApp")

    analysis_triggered = False
    temp_dir = None

    if input_method == "Upload Files":
        # Comprehensive list of supported extensions
        supported_types = [
            'py', 'pyw', 'java', 'js', 'ts', 'tsx', 'jsx', 'cs', 'php', 'rb', 'xsd',
            'sql', 'pls', 'plsql', 'pks', 'pkb', 'cob', 'cbl', 'cpy', 'cobol', 'jcl', 'proc',
            'c', 'h', 'cpp', 'hpp', 'cc', 'vb', 'vbs', 'bas', 'cls', 'frm',
            'go', 'rs', 'scala', 'kt', 'kts', 'groovy', 'gvy',
            'xml', 'xsl', 'xslt', 'wsdl', 'json', 'yaml', 'yml', 'properties', 'config', 'cfg', 'ini',
            'sh', 'bash', 'ps1', 'psm1', 'bat', 'cmd',
            'asp', 'aspx', 'cshtml', 'vbhtml', 'jsp', 'jspx', 'html', 'htm', 'css', 'scss', 'sass', 'less',
            'swift', 'm', 'mm', 'r', 'lua', 'perl', 'pl', 'pm', 'tcl', 'awk', 'sed',
            'mak', 'mk', 'gradle', 'maven', 'pom', 'sbt', 'dart', 'ex', 'exs', 'erl', 'hrl',
            'clj', 'cljs', 'fs', 'fsx', 'ml', 'mli', 'hs', 'lhs', 'vue', 'svelte',
            'tf', 'tfvars', 'proto', 'graphql', 'gql', 'zip'
        ]
        uploaded_files = st.sidebar.file_uploader(
            "Upload ZIP Folder (recommended) or Code Files",
            accept_multiple_files=True,
            type=supported_types,
            help="Upload a ZIP file containing your entire project folder for complete scanning"
        )

        if uploaded_files:
            temp_dir = tempfile.mkdtemp()
            for uploaded_file in uploaded_files:
                if uploaded_file.name.endswith('.zip'):
                    # Handle ZIP file extraction
                    zip_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(zip_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())

                    # Extract ZIP contents
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)

                    # Remove the ZIP file after extraction
                    os.remove(zip_path)
                else:
                    # Handle regular files
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())

            # Store temp_dir in session state for extension discovery
            if 'repo_path' not in st.session_state or st.session_state.get('temp_dir') != temp_dir:
                st.session_state['temp_dir'] = temp_dir
                st.session_state['repo_path'] = temp_dir
                # Discover extensions
                analyzer_temp = CodeAnalyzer(temp_dir, app_name)
                st.session_state['discovered_extensions'] = analyzer_temp.discover_extensions()
            
            repo_path = temp_dir
            
            # Show extension filter if extensions discovered
            if st.session_state.get('discovered_extensions'):
                st.sidebar.markdown("---")
                st.sidebar.subheader("File Extensions Filter")
                st.sidebar.caption("Uncheck extensions to exclude from analysis")
                
                discovered = st.session_state['discovered_extensions']
                excluded_extensions = set()
                
                for ext, count in discovered.items():
                    ext_lower = ext.lower()
                    # Check if it's a known/supported extension
                    is_supported = ext_lower in CodeAnalyzer(".", "temp").supported_extensions
                    default_checked = is_supported
                    
                    include = st.sidebar.checkbox(
                        f"{ext} ({count} files) {'✓' if is_supported else ''}",
                        value=default_checked,
                        key=f"ext_{ext}"
                    )
                    if not include:
                        excluded_extensions.add(ext_lower)
                
                st.session_state['excluded_extensions'] = excluded_extensions
            
            if st.sidebar.button("Run Analysis"):
                analysis_triggered = True

    else:
        repo_path = st.sidebar.text_input("Enter Repository Path")
        if repo_path:
            # Discover extensions for repository path
            if 'repo_path_input' not in st.session_state or st.session_state.get('repo_path_input') != repo_path:
                st.session_state['repo_path_input'] = repo_path
                if os.path.exists(repo_path):
                    analyzer_temp = CodeAnalyzer(repo_path, app_name)
                    st.session_state['discovered_extensions'] = analyzer_temp.discover_extensions()
            
            # Show extension filter
            if st.session_state.get('discovered_extensions'):
                st.sidebar.markdown("---")
                st.sidebar.subheader("File Extensions Filter")
                st.sidebar.caption("Uncheck extensions to exclude from analysis")
                
                discovered = st.session_state['discovered_extensions']
                excluded_extensions = set()
                
                for ext, count in discovered.items():
                    ext_lower = ext.lower()
                    is_supported = ext_lower in CodeAnalyzer(".", "temp").supported_extensions
                    default_checked = is_supported
                    
                    include = st.sidebar.checkbox(
                        f"{ext} ({count} files) {'✓' if is_supported else ''}",
                        value=default_checked,
                        key=f"ext_path_{ext}"
                    )
                    if not include:
                        excluded_extensions.add(ext_lower)
                
                st.session_state['excluded_extensions'] = excluded_extensions
            
            if st.sidebar.button("Run Analysis"):
                analysis_triggered = True

    if analysis_triggered:
        try:
            with st.spinner("Analyzing code..."):
                analyzer = CodeAnalyzer(repo_path, app_name)
                
                # Apply excluded extensions
                if st.session_state.get('excluded_extensions'):
                    analyzer.set_excluded_extensions(st.session_state['excluded_extensions'])
                
                progress_bar = st.progress(0)

                # Run analysis
                results = analyzer.scan_repository()
                progress_bar.progress(100)
                
                # Show extensions summary
                st.info(f"Extensions included: {', '.join([ext for ext in analyzer.supported_extensions.keys() if ext not in analyzer.excluded_extensions])}")

                # Create tabs for Dashboard, Analysis Results, and Export Reports
                tab1, tab2, tab3 = st.tabs(["Dashboard", "Analysis Results", "Export Reports"])

                with tab1:
                    st.header("Analysis Dashboard")
                    st.markdown("""
                    This dashboard provides visual insights into the code analysis results,
                    showing distributions of files, demographic fields, and integration patterns.
                    """)
                    create_dashboard_charts(results)

                with tab2:
                    # Summary Stats
                    st.subheader("Summary")
                    stats_cols = st.columns(4)
                    stats_cols[0].metric("Files Analyzed", results['summary']['files_analyzed'])
                    stats_cols[1].metric("Demographic Fields", results['summary']['demographic_fields_found'])
                    stats_cols[2].metric("Integration Patterns", results['summary']['integration_patterns_found'])
                    stats_cols[3].metric("Unique Fields", len(results['summary']['unique_demographic_fields']))

                    # Demographic Fields Summary Table
                    st.subheader("Demographic Fields Summary")
                    demographic_files = [f for f in results['summary']['file_details'] if f['demographic_fields_found'] > 0]
                    if demographic_files:
                        cols = st.columns([0.5, 2, 1, 2])
                        cols[0].markdown("**#**")
                        cols[1].markdown("**File Analyzed**")
                        cols[2].markdown("**Fields Found**")
                        cols[3].markdown("**Fields**")

                        for idx, file_detail in enumerate(demographic_files, 1):
                            file_path = file_detail['file_path']
                            unique_fields = []
                            if file_path in results['demographic_data']:
                                unique_fields = list(results['demographic_data'][file_path].keys())

                            cols = st.columns([0.5, 2, 1, 2])
                            cols[0].text(str(idx))
                            cols[1].text(os.path.basename(file_path))
                            cols[2].text(str(file_detail['demographic_fields_found']))
                            cols[3].text(', '.join(unique_fields))

                    # Integration Patterns Summary Table
                    st.subheader("Integration Patterns Summary")
                    integration_files = [f for f in results['summary']['file_details'] if f['integration_patterns_found'] > 0]
                    if integration_files:
                        cols = st.columns([0.5, 2, 1, 2])
                        cols[0].markdown("**#**")
                        cols[1].markdown("**File Name**")
                        cols[2].markdown("**Patterns Found**")
                        cols[3].markdown("**Pattern Details**")

                        for idx, file_detail in enumerate(integration_files, 1):
                            file_path = file_detail['file_path']
                            pattern_details = set()
                            for pattern in results['integration_patterns']:
                                if pattern['file_path'] == file_path:
                                    pattern_details.add(f"{pattern['pattern_type']}: {pattern['sub_type']}")

                            cols = st.columns([0.5, 2, 1, 2])
                            cols[0].text(str(idx))
                            cols[1].text(os.path.basename(file_path))
                            cols[2].text(str(file_detail['integration_patterns_found']))
                            cols[3].text(', '.join(pattern_details))

                with tab3:
                    st.header("Available Reports")

                    # Get all report files and filter by app_name
                    report_files = [
                        f for f in os.listdir()
                        if f.endswith('.html')
                        and 'CodeLens' in f
                        and f.startswith(app_name)
                    ]

                    # Sort files by timestamp in descending order
                    report_files.sort(key=parse_timestamp_from_filename, reverse=True)

                    if report_files:
                        # Create a table with five columns
                        cols = st.columns([1, 3, 2, 2, 2])
                        cols[0].markdown("**S.No**")
                        cols[1].markdown("**File Name**")
                        cols[2].markdown("**Date**")
                        cols[3].markdown("**Time**")
                        cols[4].markdown("**Download**")

                        # List all reports
                        for idx, report_file in enumerate(report_files, 1):
                            cols = st.columns([1, 3, 2, 2, 2])

                            # Serial number column
                            cols[0].text(f"{idx}")

                            # File name column without .html extension
                            display_name = report_file.replace('.html', '')
                            cols[1].text(display_name)

                            # Extract timestamp and format date and time separately
                            timestamp = parse_timestamp_from_filename(report_file)
                            # Date in DD-MMM-YYYY format
                            cols[2].text(timestamp.strftime('%d-%b-%Y'))
                            # Time in 12-hour format with AM/PM
                            cols[3].text(timestamp.strftime('%I:%M:%S %p'))

                            # Download button column (last)
                            cols[4].markdown(
                                get_file_download_link(report_file),
                                unsafe_allow_html=True
                            )
                    else:
                        st.info("No reports available for this application.")

        except Exception as e:
            st.error(f"Error during analysis: {str(e)}")

        finally:
            if temp_dir:
                import shutil
                shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()