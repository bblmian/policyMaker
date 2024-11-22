import streamlit as st
import pandas as pd
import numpy as np
from .database import Database
import io

def export_clauses(clauses, format):
    """导出选中的条款"""
    db = Database()
    clause_uuids = [clause['UUID'] for clause in clauses]
    return db.export_selected_clauses(clause_uuids, format)

def render_clause_manager():
    st.markdown("""
    <style>
    .stDataFrame {
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 初始化数据库
    db = Database()
    
    # 初始化session state
    if 'selected_clauses' not in st.session_state:
        st.session_state.selected_clauses = []
    if 'selected_indices' not in st.session_state:
        st.session_state.selected_indices = set()
    if 'previous_selection' not in st.session_state:
        st.session_state.previous_selection = []
    
    # 创建两列布局
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("条款管理")
        
        # 数据库操作
        db_col1, db_col2, db_col3 = st.columns(3)
        with db_col1:
            if st.button("清空数据库"):
                db.clear_database()
                st.session_state.selected_clauses = []
                st.session_state.selected_indices = set()
                st.success("数据库已清空")
                st.rerun()
        
        with db_col2:
            exported_db = db.export_database()
            if exported_db:
                st.download_button(
                    "导出数据库",
                    exported_db,
                    file_name="clauses.db",
                    mime="application/octet-stream"
                )
        
        with db_col3:
            uploaded_db = st.file_uploader("导入数据库", type=['db'])
            if uploaded_db:
                db.import_database(uploaded_db.read())
                st.success("数据库导入成功")
                st.rerun()
        
        # 文件上传
        uploaded_file = st.file_uploader("导入条款库", type=['csv', 'xlsx'])
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                db.import_clauses(df)
                st.success("条款库导入成功！")
            except Exception as e:
                st.error(f"文件导入错误：{str(e)}")
        
        # 获取所有条款
        clauses_df = db.export_clauses('dataframe')
        if not clauses_df.empty:
            # 创建筛选条件
            st.subheader("筛选条件")
            filter_cols = st.columns(3)
            
            # 动态生成筛选框
            filters = {}
            exclude_columns = ['UUID', 'PINYIN', 'QUANPIN', '扩展条款正文', '序号', '版本号']
            filter_columns = [col for col in clauses_df.columns if col not in exclude_columns]
            
            for i, col in enumerate(filter_columns):
                with filter_cols[i % 3]:
                    unique_values = sorted(clauses_df[col].unique())
                    filters[col] = st.multiselect(
                        f"选择{col}",
                        options=unique_values,
                        key=f"filter_{col}"
                    )
            
            # 搜索框
            search_term = st.text_input(
                "搜索条款",
                placeholder="输入条款名称、拼音或关键词",
                help="支持条款名称、拼音首字母和全拼搜索"
            )
            
            # 应用筛选条件
            filtered_df = clauses_df.copy()
            
            # 应用搜索条件
            if search_term:
                search_term = search_term.lower()
                mask = (
                    filtered_df['扩展条款标题'].str.contains(search_term, na=False, case=False) |
                    filtered_df['PINYIN'].str.contains(search_term, na=False, case=False) |
                    filtered_df['QUANPIN'].str.contains(search_term, na=False, case=False)
                )
                filtered_df = filtered_df[mask]
            
            # 应用筛选条件
            for col, selected_values in filters.items():
                if selected_values:
                    filtered_df = filtered_df[filtered_df[col].isin(selected_values)]
            
            if not filtered_df.empty:
                # 分页设置
                ITEMS_PER_PAGE = 20
                total_pages = max(1, (len(filtered_df) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
                
                page_cols = st.columns([1, 4])
                with page_cols[0]:
                    current_page = st.number_input("页码", min_value=1, max_value=total_pages, value=1)
                
                start_idx = (current_page - 1) * ITEMS_PER_PAGE
                end_idx = min(start_idx + ITEMS_PER_PAGE, len(filtered_df))
                
                # 显示分页信息
                st.write(f"显示第 {start_idx + 1} 到 {end_idx} 条，共 {len(filtered_df)} 条")
                
                # 准备当前页的数据
                display_df = filtered_df.iloc[start_idx:end_idx].copy()
                display_df = display_df.reset_index(drop=True)
                
                # 全选功能
                select_all = st.checkbox("全选当前筛选结果", key="select_all")
                
                if select_all:
                    # 全选时，将所有筛选后的条款添加到已选列表
                    st.session_state.selected_indices = set(filtered_df.index.tolist())
                    st.session_state.selected_clauses = filtered_df.to_dict('records')
                    st.rerun()
                
                # 使用container和custom CSS来控制表格宽度
                with st.container():
                    st.markdown("""
                    <style>
                        .stDataFrame {
                            width: 75% !important;
                        }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # 创建数据表格，确保选择列是布尔类型
                    selection_array = np.zeros(len(display_df), dtype=bool)
                    for i in range(len(display_df)):
                        if display_df.index[i] in st.session_state.selected_indices:
                            selection_array[i] = True
                    
                    edited_df = pd.DataFrame({
                        "选择": selection_array,
                        "序号": display_df['序号'].astype(str),
                        "条款名称": display_df['扩展条款标题'],
                        "条款正文": display_df['扩展条款正文'].str[:100] + '...',
                        "版本": display_df['版本号'].astype(str)
                    })
                    
                    # 显示数据表格
                    edited_result = st.data_editor(
                        edited_df,
                        hide_index=True,
                        use_container_width=True,
                        key=f"data_editor_{current_page}",
                        column_config={
                            "选择": st.column_config.CheckboxColumn(
                                "选择",
                                help="选择条款",
                                default=False,
                                width="small"
                            ),
                            "序号": st.column_config.TextColumn(
                                "序号",
                                help="条款序号",
                                disabled=True,
                                width="small"
                            ),
                            "条款名称": st.column_config.TextColumn(
                                "条款名称",
                                help="条款标题",
                                disabled=True,
                                width="medium"
                            ),
                            "条款正文": st.column_config.TextColumn(
                                "条款正文预览",
                                help="条款内容预览",
                                disabled=True,
                                width="large"
                            ),
                            "版本": st.column_config.TextColumn(
                                "版本号",
                                help="条款版本",
                                disabled=True,
                                width="small"
                            )
                        }
                    )
                
                # 更新选择状态
                if not select_all:
                    # 获取当前页面选中的行的实际索引
                    current_page_selected = set()
                    for i, is_selected in enumerate(edited_result['选择']):
                        if is_selected:
                            actual_idx = filtered_df.index[start_idx + i]
                            current_page_selected.add(actual_idx)
                    
                    # 更新总的选择状态
                    st.session_state.selected_indices = (
                        st.session_state.selected_indices - set(filtered_df.index[start_idx:end_idx]) | 
                        current_page_selected
                    )
                    
                    # 更新选中的条款
                    st.session_state.selected_clauses = [
                        filtered_df.iloc[idx].to_dict()
                        for idx in sorted(st.session_state.selected_indices)
                    ]
                    
                    # 检查选择状态是否发生变化
                    current_selection = [c['UUID'] for c in st.session_state.selected_clauses]
                    if current_selection != st.session_state.previous_selection:
                        st.session_state.previous_selection = current_selection
                        st.rerun()
            else:
                st.info("没有找到匹配的条款")
        else:
            st.info("数据库中暂无条款，请先导入条款库")
    
    # 在右侧显示已选条款列表
    with col2:
        st.header("已选条款")
        if st.session_state.selected_clauses:
            # 导出选项
            export_format = st.selectbox(
                "导出格式",
                ["XLSX", "DOCX", "Markdown"],
                key="export_format"
            )
            
            if st.button("导出选中条款"):
                export_data = export_clauses(
                    st.session_state.selected_clauses,
                    export_format.lower()
                )
                
                if export_format == "XLSX":
                    st.download_button(
                        "下载Excel文件",
                        export_data,
                        file_name="selected_clauses.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                elif export_format == "DOCX":
                    st.download_button(
                        "下载Word文件",
                        export_data,
                        file_name="selected_clauses.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                elif export_format == "Markdown":
                    st.download_button(
                        "下载Markdown文件",
                        export_data,
                        file_name="selected_clauses.md",
                        mime="text/markdown"
                    )
            
            # 显示已选条款
            for i, clause in enumerate(st.session_state.selected_clauses):
                with st.expander(f"{i+1}. {clause['扩展条款标题']} (版本 {clause['版本号']})", expanded=False):
                    # 获取条款版本历史
                    versions = db.get_clause_versions(clause['UUID'])
                    version_numbers = [v.version_number for v in versions]
                    
                    # 版本选择
                    selected_version = st.selectbox(
                        "选择版本",
                        version_numbers,
                        index=version_numbers.index(clause['版本号']) if clause['版本号'] in version_numbers else 0,
                        key=f"version_{i}"
                    )
                    
                    # 显示当前版本内容
                    edited_content = st.text_area(
                        "编辑条款内容",
                        value=clause['扩展条款正文'],
                        height=300,
                        key=f"edit_{i}"
                    )
                    
                    cols = st.columns([1, 1, 1])
                    with cols[0]:
                        if st.button("保存", key=f"save_{i}"):
                            db.update_clause(
                                clause['UUID'],
                                content=edited_content
                            )
                            st.success("保存成功")
                            st.rerun()
                    
                    with cols[1]:
                        if st.button("激活此版本", key=f"activate_{i}"):
                            db.activate_clause_version(
                                clause['UUID'],
                                selected_version
                            )
                            st.success("版本已激活")
                            st.rerun()
                    
                    with cols[2]:
                        if st.button("删除", key=f"delete_{i}"):
                            st.session_state.selected_clauses.pop(i)
                            if i in st.session_state.selected_indices:
                                st.session_state.selected_indices.remove(i)
                            st.rerun()
        else:
            st.info("还未选择任何条款")
