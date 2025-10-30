"""Extract patterns from DOCX files to text files."""

import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:
    print("Error: python-docx not installed")
    print("Install with: pip install python-docx")
    sys.exit(1)


def extract_from_docx(docx_path: str, output_path: str):
    """
    Extract text content from DOCX file.

    Args:
        docx_path: Path to DOCX file
        output_path: Path to output text file
    """
    try:
        doc = Document(docx_path)

        with open(output_path, "w", encoding="utf-8") as f:
            for para in doc.paragraphs:
                f.write(para.text + "\n")

        print(f"✅ Extracted to {output_path}")

    except FileNotFoundError:
        print(f"❌ File not found: {docx_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error extracting: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)

    # Check if DOCX files exist
    quick_ref = "Quick_Card_Reference.docx"
    xml_summary = "Summary_XML_meaning.docx"

    if Path(quick_ref).exists():
        extract_from_docx(quick_ref, "data/quick_reference.txt")
    else:
        print(f"⚠️  {quick_ref} not found, skipping")

    if Path(xml_summary).exists():
        extract_from_docx(xml_summary, "data/xml_meaning_summary.txt")
    else:
        print(f"⚠️  {xml_summary} not found, skipping")

    # Use ProjecInfomationRelative files as fallback
    if Path("ProjecInfomationRelative_1.txt").exists():
        import shutil

        shutil.copy("ProjecInfomationRelative_1.txt", "data/quick_reference.txt")
        print("✅ Copied ProjecInfomationRelative_1.txt to data/quick_reference.txt")

    if Path("ProjecInfomationRelative_2.txt").exists():
        import shutil

        shutil.copy("ProjecInfomationRelative_2.txt", "data/xml_meaning_summary.txt")
        print("✅ Copied ProjecInfomationRelative_2.txt to data/xml_meaning_summary.txt")


if __name__ == "__main__":
    main()
