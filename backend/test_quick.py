#!/usr/bin/env python
import os
import sys
sys.path.insert(0, '/workspaces/IPD-25-26/backend')

from core.extractor import extract_raw_text, query_groq, GROQ_API_KEY

print("✓ Imports successful")
print(f"✓ GROQ_API_KEY set: {bool(GROQ_API_KEY)}")
print(f"✓ GROQ_API_KEY value: {GROQ_API_KEY[:10]}..." if GROQ_API_KEY else "✗ GROQ_API_KEY not set")

# Test file exists
pdf_path = "testCases/Form16.pdf"
if os.path.exists(pdf_path):
    print(f"✓ PDF file exists at {pdf_path}")
    print(f"  File size: {os.path.getsize(pdf_path):,} bytes")
else:
    print(f"✗ PDF file NOT found at {pdf_path}")
    sys.exit(1)

# Test output directory
output_dir = "output"
if os.path.exists(output_dir):
    print(f"✓ Output directory exists: {output_dir}")
else:
    os.makedirs(output_dir, exist_ok=True)
    print(f"✓ Created output directory: {output_dir}")

print("\n✓ All prerequisite checks passed!")
