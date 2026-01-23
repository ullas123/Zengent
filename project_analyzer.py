import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field
import logging

@dataclass
class ClassInfo:
    name: str
    file_path: str
    line_number: int
    methods: List[str] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)

@dataclass
class FunctionInfo:
    name: str
    file_path: str
    line_number: int
    calls: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    is_method: bool = False
    class_name: Optional[str] = None

@dataclass
class DataFlowNode:
    name: str
    node_type: str
    file_path: str
    line_number: int
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    transformations: List[str] = field(default_factory=list)

@dataclass
class SQLTable:
    name: str
    alias: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    source_type: str = "table"

@dataclass
class SQLDataFlow:
    source_tables: List[SQLTable] = field(default_factory=list)
    target_table: Optional[str] = None
    operation: str = "SELECT"
    joins: List[Dict] = field(default_factory=list)
    transformations: List[str] = field(default_factory=list)

class PythonAnalyzer(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.classes: List[ClassInfo] = []
        self.functions: List[FunctionInfo] = []
        self.imports: List[str] = []
        self.current_class: Optional[str] = None
        self.function_calls: Dict[str, List[str]] = {}
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        module = node.module or ''
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(f"{self._get_attr_name(base)}")
        
        class_info = ClassInfo(
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            base_classes=base_classes,
            methods=[],
            attributes=[]
        )
        
        self.current_class = node.name
        
        for item in node.body:
            if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
                class_info.methods.append(item.name)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_info.attributes.append(target.id)
        
        self.classes.append(class_info)
        self.generic_visit(node)
        self.current_class = None
    
    def visit_FunctionDef(self, node):
        self._process_function(node)
        
    def visit_AsyncFunctionDef(self, node):
        self._process_function(node)
    
    def _process_function(self, node):
        params = []
        for arg in node.args.args:
            params.append(arg.arg)
        
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if call_name:
                    calls.append(call_name)
        
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        func_info = FunctionInfo(
            name=node.name,
            file_path=self.file_path,
            line_number=node.lineno,
            calls=list(set(calls)),
            parameters=params,
            returns=returns,
            is_method=self.current_class is not None,
            class_name=self.current_class
        )
        
        self.functions.append(func_info)
        self.generic_visit(node)
    
    def _get_call_name(self, node) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return self._get_attr_name(node.func)
        return None
    
    def _get_attr_name(self, node) -> str:
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))


class PySparkAnalyzer:
    def __init__(self):
        self.data_flows: List[DataFlowNode] = []
        self.spark_operations = [
            'read', 'write', 'load', 'save', 'csv', 'parquet', 'json', 'jdbc',
            'select', 'filter', 'where', 'groupBy', 'agg', 'join', 'union',
            'withColumn', 'drop', 'distinct', 'orderBy', 'sort', 'limit',
            'createOrReplaceTempView', 'sql', 'cache', 'persist', 'collect',
            'show', 'count', 'first', 'take', 'toPandas', 'repartition', 'coalesce'
        ]
        
    def analyze_file(self, file_path: str, content: str) -> List[DataFlowNode]:
        data_flows = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for op in self.spark_operations:
                pattern = rf'\.{op}\s*\('
                if re.search(pattern, line):
                    node = self._parse_spark_operation(line, op, file_path, line_num)
                    if node:
                        data_flows.append(node)
            
            if 'spark.read' in line or 'SparkSession' in line:
                node = DataFlowNode(
                    name=f"spark_read_{line_num}",
                    node_type="data_source",
                    file_path=file_path,
                    line_number=line_num,
                    inputs=[],
                    outputs=[self._extract_variable(line)],
                    transformations=["read"]
                )
                data_flows.append(node)
            
            if '.write.' in line or '.save(' in line or '.saveAsTable(' in line:
                node = DataFlowNode(
                    name=f"spark_write_{line_num}",
                    node_type="data_sink",
                    file_path=file_path,
                    line_number=line_num,
                    inputs=[self._extract_dataframe(line)],
                    outputs=[self._extract_output_path(line)],
                    transformations=["write"]
                )
                data_flows.append(node)
        
        return data_flows
    
    def _parse_spark_operation(self, line: str, operation: str, file_path: str, line_num: int) -> Optional[DataFlowNode]:
        var_name = self._extract_variable(line)
        input_df = self._extract_dataframe(line)
        
        return DataFlowNode(
            name=f"{operation}_{line_num}",
            node_type="transformation",
            file_path=file_path,
            line_number=line_num,
            inputs=[input_df] if input_df else [],
            outputs=[var_name] if var_name else [],
            transformations=[operation]
        )
    
    def _extract_variable(self, line: str) -> str:
        match = re.match(r'^\s*(\w+)\s*=', line)
        return match.group(1) if match else ""
    
    def _extract_dataframe(self, line: str) -> str:
        match = re.search(r'(\w+)\.(?:select|filter|where|groupBy|join|union|withColumn)', line)
        return match.group(1) if match else ""
    
    def _extract_output_path(self, line: str) -> str:
        match = re.search(r'["\']([^"\']+)["\']', line)
        return match.group(1) if match else "output"


class SQLAnalyzer:
    def __init__(self):
        self.data_flows: List[SQLDataFlow] = []
    
    def analyze_content(self, content: str, file_path: str = "") -> List[SQLDataFlow]:
        data_flows = []
        
        sql_blocks = self._extract_sql_blocks(content)
        
        for sql in sql_blocks:
            flow = self._parse_sql(sql)
            if flow:
                data_flows.append(flow)
        
        return data_flows
    
    def _extract_sql_blocks(self, content: str) -> List[str]:
        blocks = []
        
        triple_quote_pattern = r'"""(.*?)"""'
        for match in re.finditer(triple_quote_pattern, content, re.DOTALL | re.IGNORECASE):
            sql = match.group(1).strip()
            if self._is_sql(sql):
                blocks.append(sql)
        
        single_quote_pattern = r"'''(.*?)'''"
        for match in re.finditer(single_quote_pattern, content, re.DOTALL | re.IGNORECASE):
            sql = match.group(1).strip()
            if self._is_sql(sql):
                blocks.append(sql)
        
        spark_sql_pattern = r'\.sql\s*\(\s*["\']([^"\']+)["\']'
        for match in re.finditer(spark_sql_pattern, content):
            blocks.append(match.group(1))
        
        if file_path := content:
            if self._is_sql(content):
                blocks.append(content)
        
        return blocks
    
    def _is_sql(self, text: str) -> bool:
        sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'FROM', 'WHERE', 'JOIN']
        text_upper = text.upper()
        return any(keyword in text_upper for keyword in sql_keywords)
    
    def _parse_sql(self, sql: str) -> Optional[SQLDataFlow]:
        sql_upper = sql.upper()
        
        if 'SELECT' in sql_upper:
            return self._parse_select(sql)
        elif 'INSERT' in sql_upper:
            return self._parse_insert(sql)
        elif 'CREATE' in sql_upper and 'TABLE' in sql_upper:
            return self._parse_create_table(sql)
        
        return None
    
    def _parse_select(self, sql: str) -> SQLDataFlow:
        flow = SQLDataFlow(operation="SELECT")
        
        from_pattern = r'FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        for match in re.finditer(from_pattern, sql, re.IGNORECASE):
            table = SQLTable(name=match.group(1), alias=match.group(2))
            flow.source_tables.append(table)
        
        join_pattern = r'(?:LEFT|RIGHT|INNER|OUTER|CROSS)?\s*JOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        for match in re.finditer(join_pattern, sql, re.IGNORECASE):
            table = SQLTable(name=match.group(1), alias=match.group(2))
            flow.source_tables.append(table)
            flow.joins.append({'table': match.group(1), 'alias': match.group(2)})
        
        into_pattern = r'INTO\s+(\w+)'
        match = re.search(into_pattern, sql, re.IGNORECASE)
        if match:
            flow.target_table = match.group(1)
        
        return flow
    
    def _parse_insert(self, sql: str) -> SQLDataFlow:
        flow = SQLDataFlow(operation="INSERT")
        
        into_pattern = r'INSERT\s+INTO\s+(\w+)'
        match = re.search(into_pattern, sql, re.IGNORECASE)
        if match:
            flow.target_table = match.group(1)
        
        if 'SELECT' in sql.upper():
            select_flow = self._parse_select(sql)
            flow.source_tables = select_flow.source_tables
        
        return flow
    
    def _parse_create_table(self, sql: str) -> SQLDataFlow:
        flow = SQLDataFlow(operation="CREATE TABLE")
        
        create_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
        match = re.search(create_pattern, sql, re.IGNORECASE)
        if match:
            flow.target_table = match.group(1)
        
        if 'AS' in sql.upper() and 'SELECT' in sql.upper():
            select_flow = self._parse_select(sql)
            flow.source_tables = select_flow.source_tables
        
        return flow


class ShellAnalyzer:
    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.data_flows: List[DataFlowNode] = []
    
    def analyze_file(self, file_path: str, content: str) -> Tuple[List[FunctionInfo], List[DataFlowNode]]:
        functions = []
        data_flows = []
        lines = content.split('\n')
        
        func_pattern = re.compile(r'^(\w+)\s*\(\s*\)\s*\{?', re.MULTILINE)
        func_pattern2 = re.compile(r'^function\s+(\w+)', re.MULTILINE)
        
        for match in func_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            func_name = match.group(1)
            if func_name not in ['if', 'while', 'for', 'case', 'then', 'else', 'fi', 'do', 'done']:
                functions.append(FunctionInfo(
                    name=func_name,
                    file_path=file_path,
                    line_number=line_num,
                    calls=self._find_function_calls(content, func_name),
                    parameters=[],
                    is_method=False
                ))
        
        for match in func_pattern2.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            functions.append(FunctionInfo(
                name=match.group(1),
                file_path=file_path,
                line_number=line_num,
                calls=self._find_function_calls(content, match.group(1)),
                parameters=[],
                is_method=False
            ))
        
        for line_num, line in enumerate(lines, 1):
            if 'spark-submit' in line or 'pyspark' in line:
                data_flows.append(DataFlowNode(
                    name=f"spark_submit_{line_num}",
                    node_type="spark_job",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["spark-submit"]
                ))
            
            if re.search(r'>\s*\S+|>>\s*\S+', line):
                match = re.search(r'>\s*(\S+)|>>\s*(\S+)', line)
                if match:
                    output_file = match.group(1) or match.group(2)
                    data_flows.append(DataFlowNode(
                        name=f"file_write_{line_num}",
                        node_type="file_output",
                        file_path=file_path,
                        line_number=line_num,
                        outputs=[output_file],
                        transformations=["write"]
                    ))
            
            if re.search(r'<\s*\S+|\$\(cat\s+\S+\)', line):
                data_flows.append(DataFlowNode(
                    name=f"file_read_{line_num}",
                    node_type="file_input",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["read"]
                ))
            
            if '|' in line:
                data_flows.append(DataFlowNode(
                    name=f"pipe_{line_num}",
                    node_type="pipe",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["pipe"]
                ))
        
        return functions, data_flows
    
    def _find_function_calls(self, content: str, func_name: str) -> List[str]:
        calls = []
        call_pattern = re.compile(r'\b(\w+)\s*(?:\(|\s+\w+|\s*$)', re.MULTILINE)
        for match in call_pattern.finditer(content):
            called = match.group(1)
            if called != func_name and called not in ['if', 'while', 'for', 'case', 'echo', 'exit', 'return', 'then', 'else', 'fi', 'do', 'done', 'in']:
                calls.append(called)
        return list(set(calls))[:20]


class JavaAnalyzer:
    def __init__(self):
        self.classes: List[ClassInfo] = []
        self.functions: List[FunctionInfo] = []
        self.data_flows: List[DataFlowNode] = []
    
    def analyze_file(self, file_path: str, content: str) -> Tuple[List[ClassInfo], List[FunctionInfo], List[DataFlowNode]]:
        classes = []
        functions = []
        data_flows = []
        
        class_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
            re.MULTILINE
        )
        
        for match in class_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            class_name = match.group(1)
            base_class = match.group(2) if match.group(2) else None
            interfaces = match.group(3).split(',') if match.group(3) else []
            
            base_classes = []
            if base_class:
                base_classes.append(base_class.strip())
            base_classes.extend([i.strip() for i in interfaces if i.strip()])
            
            class_start = match.start()
            brace_count = 0
            class_end = class_start
            in_class = False
            for i, char in enumerate(content[class_start:]):
                if char == '{':
                    brace_count += 1
                    in_class = True
                elif char == '}':
                    brace_count -= 1
                    if in_class and brace_count == 0:
                        class_end = class_start + i
                        break
            
            class_content = content[class_start:class_end]
            
            methods = self._extract_methods(class_content)
            attributes = self._extract_attributes(class_content)
            
            classes.append(ClassInfo(
                name=class_name,
                file_path=file_path,
                line_number=line_num,
                methods=methods,
                base_classes=base_classes,
                attributes=attributes
            ))
            
            for method in methods:
                functions.append(FunctionInfo(
                    name=method,
                    file_path=file_path,
                    line_number=line_num,
                    calls=self._find_method_calls(class_content, method),
                    parameters=[],
                    is_method=True,
                    class_name=class_name
                ))
        
        interface_pattern = re.compile(
            r'(?:public\s+)?interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?',
            re.MULTILINE
        )
        for match in interface_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            interface_name = match.group(1)
            
            classes.append(ClassInfo(
                name=interface_name,
                file_path=file_path,
                line_number=line_num,
                methods=[],
                base_classes=[],
                attributes=[]
            ))
        
        jdbc_pattern = re.compile(r'(?:executeQuery|executeUpdate|prepareStatement)\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
        for match in jdbc_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            sql = match.group(1)
            data_flows.append(DataFlowNode(
                name=f"jdbc_query_{line_num}",
                node_type="jdbc_operation",
                file_path=file_path,
                line_number=line_num,
                transformations=[sql[:50]]
            ))
        
        file_pattern = re.compile(r'(?:FileInputStream|FileOutputStream|FileReader|FileWriter|BufferedReader|BufferedWriter)\s*\(\s*["\']?([^"\')\s]+)', re.IGNORECASE)
        for match in file_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            data_flows.append(DataFlowNode(
                name=f"file_io_{line_num}",
                node_type="file_operation",
                file_path=file_path,
                line_number=line_num,
                transformations=["file_io"]
            ))
        
        return classes, functions, data_flows
    
    def _extract_methods(self, class_content: str) -> List[str]:
        methods = []
        method_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:\w+(?:<[\w,\s<>]+>)?)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{',
            re.MULTILINE
        )
        for match in method_pattern.finditer(class_content):
            method_name = match.group(1)
            if method_name not in ['if', 'while', 'for', 'switch', 'catch', 'try']:
                methods.append(method_name)
        return methods
    
    def _extract_attributes(self, class_content: str) -> List[str]:
        attributes = []
        attr_pattern = re.compile(
            r'(?:public\s+|private\s+|protected\s+)(?:static\s+)?(?:final\s+)?(\w+(?:<[\w,\s<>]+>)?)\s+(\w+)\s*[;=]',
            re.MULTILINE
        )
        for match in attr_pattern.finditer(class_content):
            attr_name = match.group(2)
            attributes.append(attr_name)
        return attributes[:50]
    
    def _find_method_calls(self, content: str, method_name: str) -> List[str]:
        calls = []
        call_pattern = re.compile(r'(?:\w+\.)?(\w+)\s*\(', re.MULTILINE)
        for match in call_pattern.finditer(content):
            called = match.group(1)
            if called != method_name and called not in ['if', 'while', 'for', 'switch', 'catch', 'try', 'new', 'return']:
                calls.append(called)
        return list(set(calls))[:20]


class BatchAnalyzer:
    def __init__(self):
        self.functions: List[FunctionInfo] = []
        self.data_flows: List[DataFlowNode] = []
    
    def analyze_file(self, file_path: str, content: str) -> Tuple[List[FunctionInfo], List[DataFlowNode]]:
        functions = []
        data_flows = []
        lines = content.split('\n')
        
        label_pattern = re.compile(r'^:(\w+)', re.MULTILINE | re.IGNORECASE)
        for match in label_pattern.finditer(content):
            line_num = content[:match.start()].count('\n') + 1
            label_name = match.group(1)
            if label_name.upper() not in ['EOF', 'END']:
                functions.append(FunctionInfo(
                    name=label_name,
                    file_path=file_path,
                    line_number=line_num,
                    calls=self._find_goto_calls(content),
                    parameters=[],
                    is_method=False
                ))
        
        for line_num, line in enumerate(lines, 1):
            if re.search(r'>\s*\S+|>>\s*\S+', line, re.IGNORECASE):
                match = re.search(r'>\s*(\S+)|>>\s*(\S+)', line)
                if match:
                    output_file = match.group(1) or match.group(2)
                    data_flows.append(DataFlowNode(
                        name=f"file_write_{line_num}",
                        node_type="file_output",
                        file_path=file_path,
                        line_number=line_num,
                        outputs=[output_file],
                        transformations=["write"]
                    ))
            
            if re.search(r'\btype\b|\bfind\b|\bdir\b', line, re.IGNORECASE):
                data_flows.append(DataFlowNode(
                    name=f"file_read_{line_num}",
                    node_type="file_input",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["read"]
                ))
            
            if '|' in line:
                data_flows.append(DataFlowNode(
                    name=f"pipe_{line_num}",
                    node_type="pipe",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["pipe"]
                ))
            
            if re.search(r'\bcall\b\s+:?\w+', line, re.IGNORECASE):
                data_flows.append(DataFlowNode(
                    name=f"call_{line_num}",
                    node_type="subroutine_call",
                    file_path=file_path,
                    line_number=line_num,
                    transformations=["call"]
                ))
        
        return functions, data_flows
    
    def _find_goto_calls(self, content: str) -> List[str]:
        calls = []
        goto_pattern = re.compile(r'\bgoto\s+:?(\w+)', re.IGNORECASE)
        call_pattern = re.compile(r'\bcall\s+:?(\w+)', re.IGNORECASE)
        
        for match in goto_pattern.finditer(content):
            calls.append(match.group(1))
        for match in call_pattern.finditer(content):
            calls.append(match.group(1))
        
        return list(set(calls))


class ProjectAnalyzer:
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.logger = logging.getLogger(__name__)
        self.python_files: List[str] = []
        self.sql_files: List[str] = []
        self.shell_files: List[str] = []
        self.batch_files: List[str] = []
        self.java_files: List[str] = []
        self.classes: List[ClassInfo] = []
        self.functions: List[FunctionInfo] = []
        self.data_flows: List[DataFlowNode] = []
        self.sql_flows: List[SQLDataFlow] = []
        self.sql_statements: List[Dict] = []
        
    def analyze(self) -> Dict:
        self._discover_files()
        self._analyze_python_files()
        self._analyze_sql_files()
        self._analyze_shell_files()
        self._analyze_batch_files()
        self._analyze_java_files()
        
        return {
            'classes': self.classes,
            'functions': self.functions,
            'data_flows': self.data_flows,
            'sql_flows': self.sql_flows,
            'sql_statements': self.sql_statements,
            'summary': {
                'total_python_files': len(self.python_files),
                'total_sql_files': len(self.sql_files),
                'total_shell_files': len(self.shell_files),
                'total_batch_files': len(self.batch_files),
                'total_java_files': len(self.java_files),
                'total_classes': len(self.classes),
                'total_functions': len(self.functions),
                'total_data_flows': len(self.data_flows),
                'total_sql_flows': len(self.sql_flows)
            }
        }
    
    def _discover_files(self):
        python_extensions = ['.py', '.pyw', '.pyspark']
        sql_extensions = ['.sql', '.pls', '.plsql', '.pks', '.pkb']
        shell_extensions = ['.sh', '.bash', '.ksh', '.zsh']
        batch_extensions = ['.bat', '.cmd', '.ps1']
        java_extensions = ['.java', '.jsp', '.jspx']
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != 'node_modules']
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                if ext in python_extensions:
                    self.python_files.append(file_path)
                elif ext in sql_extensions:
                    self.sql_files.append(file_path)
                elif ext in shell_extensions:
                    self.shell_files.append(file_path)
                elif ext in batch_extensions:
                    self.batch_files.append(file_path)
                elif ext in java_extensions:
                    self.java_files.append(file_path)
    
    def _analyze_python_files(self):
        pyspark_analyzer = PySparkAnalyzer()
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                try:
                    tree = ast.parse(content)
                    analyzer = PythonAnalyzer(file_path)
                    analyzer.visit(tree)
                    
                    self.classes.extend(analyzer.classes)
                    self.functions.extend(analyzer.functions)
                except SyntaxError:
                    self.logger.warning(f"Syntax error in {file_path}")
                
                if 'pyspark' in content.lower() or 'spark' in content.lower():
                    spark_flows = pyspark_analyzer.analyze_file(file_path, content)
                    self.data_flows.extend(spark_flows)
                
                sql_analyzer = SQLAnalyzer()
                sql_flows = sql_analyzer.analyze_content(content, file_path)
                self.sql_flows.extend(sql_flows)
                
            except Exception as e:
                self.logger.error(f"Error analyzing {file_path}: {e}")
    
    def _analyze_sql_files(self):
        sql_analyzer = SQLAnalyzer()
        
        for file_path in self.sql_files:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                flows = sql_analyzer.analyze_content(content, file_path)
                self.sql_flows.extend(flows)
                
                self.sql_statements.append({
                    'sql': content,
                    'file_path': file_path
                })
                
            except Exception as e:
                self.logger.error(f"Error analyzing SQL file {file_path}: {e}")
    
    def _analyze_shell_files(self):
        shell_analyzer = ShellAnalyzer()
        sql_analyzer = SQLAnalyzer()
        
        for file_path in self.shell_files:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                functions, data_flows = shell_analyzer.analyze_file(file_path, content)
                self.functions.extend(functions)
                self.data_flows.extend(data_flows)
                
                sql_patterns = [
                    r'(?i)(SELECT\s+.+?\s+FROM\s+\w+.*?)(?:;|$|\n\n)',
                    r'(?i)(INSERT\s+INTO\s+\w+.*?)(?:;|$|\n\n)',
                    r'(?i)(UPDATE\s+\w+\s+SET.*?)(?:;|$|\n\n)',
                    r'(?i)(DELETE\s+FROM\s+\w+.*?)(?:;|$|\n\n)',
                    r'(?i)(CREATE\s+TABLE\s+\w+.*?)(?:;|$|\n\n)'
                ]
                for pattern in sql_patterns:
                    for match in re.finditer(pattern, content, re.DOTALL | re.MULTILINE):
                        sql_text = match.group(1).strip()
                        if len(sql_text) > 10:
                            self.sql_statements.append({
                                'sql': sql_text,
                                'file_path': file_path
                            })
                
                sql_flows = sql_analyzer.analyze_content(content, file_path)
                self.sql_flows.extend(sql_flows)
                
            except Exception as e:
                self.logger.error(f"Error analyzing shell file {file_path}: {e}")
    
    def _analyze_batch_files(self):
        batch_analyzer = BatchAnalyzer()
        
        for file_path in self.batch_files:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                functions, data_flows = batch_analyzer.analyze_file(file_path, content)
                self.functions.extend(functions)
                self.data_flows.extend(data_flows)
                
            except Exception as e:
                self.logger.error(f"Error analyzing batch file {file_path}: {e}")
    
    def _analyze_java_files(self):
        java_analyzer = JavaAnalyzer()
        sql_analyzer = SQLAnalyzer()
        
        for file_path in self.java_files:
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
                
                classes, functions, data_flows = java_analyzer.analyze_file(file_path, content)
                self.classes.extend(classes)
                self.functions.extend(functions)
                self.data_flows.extend(data_flows)
                
                sql_flows = sql_analyzer.analyze_content(content, file_path)
                self.sql_flows.extend(sql_flows)
                
            except Exception as e:
                self.logger.error(f"Error analyzing Java file {file_path}: {e}")
    
    def generate_class_diagram_data(self) -> Dict:
        nodes = []
        edges = []
        
        for cls in self.classes:
            nodes.append({
                'id': cls.name,
                'label': cls.name,
                'type': 'class',
                'methods': cls.methods[:10],
                'attributes': cls.attributes[:10],
                'file': os.path.basename(cls.file_path)
            })
            
            for base in cls.base_classes:
                edges.append({
                    'from': cls.name,
                    'to': base,
                    'type': 'inheritance'
                })
        
        return {'nodes': nodes, 'edges': edges}
    
    def generate_function_call_graph(self) -> Dict:
        nodes = []
        edges = []
        node_set = set()
        
        for func in self.functions:
            func_id = f"{func.class_name}.{func.name}" if func.class_name else func.name
            if func_id not in node_set:
                nodes.append({
                    'id': func_id,
                    'label': func.name,
                    'type': 'method' if func.is_method else 'function',
                    'class': func.class_name,
                    'file': os.path.basename(func.file_path)
                })
                node_set.add(func_id)
            
            for call in func.calls:
                edges.append({
                    'from': func_id,
                    'to': call,
                    'type': 'calls'
                })
        
        return {'nodes': nodes, 'edges': edges}
    
    def generate_data_flow_diagram(self) -> Dict:
        nodes = []
        edges = []
        node_set = set()
        
        for flow in self.data_flows:
            if flow.name not in node_set:
                nodes.append({
                    'id': flow.name,
                    'label': flow.transformations[0] if flow.transformations else flow.name,
                    'type': flow.node_type,
                    'file': os.path.basename(flow.file_path)
                })
                node_set.add(flow.name)
            
            for inp in flow.inputs:
                if inp and inp not in node_set:
                    nodes.append({
                        'id': inp,
                        'label': inp,
                        'type': 'dataframe'
                    })
                    node_set.add(inp)
                if inp:
                    edges.append({'from': inp, 'to': flow.name, 'type': 'data'})
            
            for out in flow.outputs:
                if out and out not in node_set:
                    nodes.append({
                        'id': out,
                        'label': out,
                        'type': 'dataframe'
                    })
                    node_set.add(out)
                if out:
                    edges.append({'from': flow.name, 'to': out, 'type': 'data'})
        
        for sql_flow in self.sql_flows:
            flow_id = f"sql_{sql_flow.operation}_{len(nodes)}"
            nodes.append({
                'id': flow_id,
                'label': sql_flow.operation,
                'type': 'sql_operation'
            })
            
            for table in sql_flow.source_tables:
                table_id = table.name
                if table_id not in node_set:
                    nodes.append({
                        'id': table_id,
                        'label': table.name,
                        'type': 'table'
                    })
                    node_set.add(table_id)
                edges.append({'from': table_id, 'to': flow_id, 'type': 'reads'})
            
            if sql_flow.target_table:
                if sql_flow.target_table not in node_set:
                    nodes.append({
                        'id': sql_flow.target_table,
                        'label': sql_flow.target_table,
                        'type': 'table'
                    })
                    node_set.add(sql_flow.target_table)
                edges.append({'from': flow_id, 'to': sql_flow.target_table, 'type': 'writes'})
        
        return {'nodes': nodes, 'edges': edges}
