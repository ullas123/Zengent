 # Code Lens - Data Imaging

A powerful Streamlit application for scanning source code repositories to identify legacy table and field references, with integrated data lineage visualization and interactive SQL diagrams.

---

## Features

### 1. Legacy Table/Field Scanning
- Upload an Excel mapping file with legacy table names and field/attribute names
- Upload a source code repository as a ZIP file
- Scan PySpark, Python, Shell, SQL, HQL, and Hive files for table and field references
- **Alias-aware SQL matching** — correctly attributes fields like `d.mbr_since_dt` to parent tables by parsing SQL aliases (e.g., `gdr_card_acct d`)
- **Multi-line query detection** — handles continuation keywords (JOIN, FROM, WHERE) and comma-separated column lists
- Multiple result views: by table/field, by file, detailed filterable table, SQL queries, and occurrence summary
- Export scan results to CSV

### 2. Service ID Search
- Search for specific Service IDs across the entire codebase
- Results displayed with file location and context

### 3. Data Lineage Diagram
- Parses PySpark and SQL/HQL files to extract data flow (sources and targets per block)
- Builds dependency graph using NetworkX
- Graphviz visualization showing tables read/written by scripts
- Filter by keyword, center on a specific node, and control hop distance
- Download lineage as DOT file or JSON

### 4. Workflow Diagram
- Graphviz SVG diagram showing script dependencies and imports
- Option to include tables in the workflow view
- Download as DOT or SVG

### 5. Interactive SQL Diagrams (Cytoscape.js)
- **ETL Flow Diagram** — Extract, Transform, Load pipeline showing data movement through stages
- **Data Flow Diagram (DFD)** — Data movement between data stores and processes
- **Query Dependency Graph** — Shows which queries depend on outputs of other queries
- **Entity Relationship Diagram (ERD)** — Tables with fields and JOIN/feed relationships
- **Control Flow Diagram** — Per-file sequential execution order with conditional/loop detection
- All diagrams are interactive: zoom, pan, drag, and click for details
- Download DOT files for each diagram

### 6. Auto-Generated DOT Files
- When generating lineage, DOT files are automatically created:
  - `lineage_diagram.dot`
  - `workflow_diagram.dot`
  - `etl_flow.dot`
  - `data_flow_dfd.dot`
  - `erd.dot`
- Download all DOT files as a single ZIP

#### Converting DOT Files to PNG

After downloading DOT files, you can convert them to PNG images using the Graphviz `dot` command:

```bash
# Convert a single DOT file to PNG
dot -Tpng lineage_diagram.dot -o lineage_diagram.png

# Convert with higher resolution (300 DPI)
dot -Tpng -Gdpi=300 lineage_diagram.dot -o lineage_diagram.png

# Convert all DOT files in a folder to PNG
for file in *.dot; do dot -Tpng "$file" -o "${file%.dot}.png"; done

# Other supported output formats
dot -Tsvg lineage_diagram.dot -o lineage_diagram.svg   # SVG format
dot -Tpdf lineage_diagram.dot -o lineage_diagram.pdf   # PDF format
dot -Tjpg lineage_diagram.dot -o lineage_diagram.jpg   # JPEG format
```

> **Note:** The `dot` command requires the Graphviz system package to be installed (see Installation section).

### 7. Progress Tracking
- Progress bars for file scanning, graph building, DOT generation, and diagram rendering
- Phase-by-phase status updates for large repositories
- Large graph warnings with filtering suggestions

---

## Supported File Types

| Extension | Language |
|-----------|----------|
| `.py` | Python |
| `.pyspark` | PySpark |
| `.sh` | Shell |
| `.sql` | SQL |
| `.hql` | HiveQL |
| `.hive` | Hive |
| `.scala` | Scala |
| `.java` | Java |
| `.conf`, `.cfg` | Configuration |
| `.yaml`, `.yml` | YAML |
| `.json` | JSON |
| `.txt` | Text |

---

## Installation

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)

### Step 1: Download

Download the `code_lens.zip` file and extract it, or clone the repository.

### Step 2: Install Python Dependencies

```bash
pip install streamlit pandas openpyxl networkx graphviz sqlparse
```

### Step 3: Install Graphviz System Package

The Graphviz system package is required for lineage and workflow diagram rendering:

- **Ubuntu/Debian:**
  ```bash
  sudo apt-get install graphviz
  ```
- **macOS (Homebrew):**
  ```bash
  brew install graphviz
  ```
- **Windows (Chocolatey):**
  ```bash
  choco install graphviz
  ```

### Step 4: Run the Application

```bash
streamlit run app.py --server.port 5000
```

The application will open in your browser at `http://localhost:5000`.

---

## Usage

### Scanning a Repository

1. **Upload Excel Mapping File** — An Excel file with at least two columns: Legacy Table Name (column 1) and Field/Attribute Name (column 2). All sheets are read automatically.
2. **Upload Source Code ZIP** — A ZIP archive containing your source code repository.
3. **Click "Scan Repository"** — The app scans all supported files and matches table/field references.
4. **View Results** — Switch between tabs to see results by table, by file, detailed view, SQL queries, or occurrence summary.
5. **Export** — Download results as CSV.

### Generating Lineage & Diagrams

1. After scanning, navigate to the **Data Lineage & Workflow** section.
2. Click **"Generate Lineage Diagrams"** — progress bars show scanning, graph building, and DOT file generation.
3. Browse the tabs:
   - **Overview** — Summary metrics and node/edge counts
   - **Lineage Diagram** — Visual graph of table dependencies
   - **Workflow Diagram** — Script orchestration and imports
   - **SQL Diagrams** — Interactive ETL, DFD, Query Dependency, ERD, and Control Flow diagrams
4. **Download DOT files** individually or as a ZIP for use in external tools (Graphviz, VS Code extensions, online viewers).

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web application framework |
| `pandas` | Data manipulation and Excel reading |
| `openpyxl` | Excel file parsing |
| `networkx` | Graph construction for lineage |
| `graphviz` | Static diagram rendering (lineage, workflow) |
| `sqlparse` | SQL statement parsing |
| Cytoscape.js (CDN) | Interactive SQL diagrams (loaded automatically) |

---

## Project Structure

```
CodeLens Data/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .streamlit/
│   └── config.toml        # Streamlit server configuration
└── README.md              # This file
```

---

## License

This project is provided as-is for internal use.
