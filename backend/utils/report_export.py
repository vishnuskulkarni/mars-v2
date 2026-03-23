import os


def save_report_markdown(session_id: str, content: str) -> str:
    """Save the synthesis report as a markdown file. Returns the file path."""
    report_dir = os.path.join("reports", session_id)
    os.makedirs(report_dir, exist_ok=True)
    file_path = os.path.join(report_dir, "report.md")
    with open(file_path, "w") as f:
        f.write(content)
    return file_path
