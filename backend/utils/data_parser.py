import os


def summarize_data_file(file_path: str) -> str:
    """Read a CSV/Excel file and produce a statistical summary."""
    try:
        import pandas as pd

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            return f"[Unsupported file type: {ext}]"

        parts = []
        parts.append(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        parts.append(f"\nColumn types:\n{df.dtypes.to_string()}")
        parts.append(f"\nDescriptive statistics:\n{df.describe(include='all').to_string()}")
        parts.append(f"\nMissing values:\n{df.isnull().sum().to_string()}")

        # Correlations for numeric columns
        numeric_cols = df.select_dtypes(include="number")
        if len(numeric_cols.columns) >= 2:
            parts.append(f"\nCorrelation matrix:\n{numeric_cols.corr().to_string()}")

        # Sample rows
        parts.append(f"\nFirst 5 rows:\n{df.head().to_string()}")

        return "\n".join(parts)

    except Exception as e:
        return f"[Error parsing data file: {e}]"
