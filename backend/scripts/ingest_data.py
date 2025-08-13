#!/usr/bin/env python3
"""
Data ingestion script for the bakery chatbot.

This script processes various data formats (text, CSV, JSON) and converts
them into searchable chunks with metadata for the RAG pipeline.
"""

import os
import json
import csv
import uuid
from typing import List, Dict, Any
from datetime import datetime

# Configuration
CHUNK_SIZE = 250  # Target tokens per chunk
CHUNK_OVERLAP = 50  # Overlap between chunks
INPUT_DIR = "../data/raw"
OUTPUT_DIR = "../data/processed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "chunks.json")

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into chunks of approximately chunk_size tokens with overlap.
    
    Args:
        text: Text to chunk
        chunk_size: Target number of tokens per chunk
        overlap: Number of tokens to overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Simple sentence-based chunking
    import re
    sentences = re.split(r'[.!?]+', text)
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        sentence_length = len(sentence.split())
        
        # If adding this sentence would exceed chunk size, finalize current chunk
        if current_length + sentence_length > chunk_size and current_chunk:
            # Add chunk to results
            chunks.append('. '.join(current_chunk) + '.')
            
            # Start new chunk with overlap
            overlap_sentences = max(1, len(current_chunk) // 3)  # Take about 1/3 as overlap
            current_chunk = current_chunk[-overlap_sentences:] if overlap_sentences < len(current_chunk) else []
            current_length = sum(len(s.split()) for s in current_chunk)
        
        # Add sentence to current chunk
        current_chunk.append(sentence)
        current_length += sentence_length
    
    # Add final chunk if it has content
    if current_chunk:
        chunks.append('. '.join(current_chunk) + '.')
    
    return chunks

def process_text_file(filepath: str, branch: str = "main") -> List[Dict[str, Any]]:
    """
    Process a text file and convert to chunks with metadata.
    
    Args:
        filepath: Path to the text file
        branch: Branch name for metadata
        
    Returns:
        List of document chunks with metadata
    """
    print(f"Processing text file: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content into sections (assuming sections are separated by === headers)
    import re
    sections = re.split(r'===\s*(.*?)\s*===', content)
    
    chunks = []
    section_title = "General"
    
    for i, section in enumerate(sections):
        if i % 2 == 1:  # Odd indices are section titles
            section_title = section.strip()
        else:  # Even indices are content
            section_content = section.strip()
            if section_content:
                section_chunks = chunk_text(section_content)
                for chunk in section_chunks:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "branch": branch,
                        "category": "general_info",
                        "text": chunk,
                        "source": f"{os.path.basename(filepath)}#{section_title}",
                        "timestamp": datetime.now().isoformat()
                    })
    
    print(f"Generated {len(chunks)} chunks from {filepath}")
    return chunks

def process_csv_file(filepath: str, branch: str = "main") -> List[Dict[str, Any]]:
    """
    Process a CSV file and convert to chunks with metadata.
    
    Args:
        filepath: Path to the CSV file
        branch: Branch name for metadata
        
    Returns:
        List of document chunks with metadata
    """
    print(f"Processing CSV file: {filepath}")
    
    chunks = []
    
    # Read CSV file
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Convert row to descriptive text
            description_parts = []
            for key, value in row.items():
                if value and str(value).strip():
                    description_parts.append(f"{key}: {value}")
            
            if description_parts:
                description_text = "; ".join(description_parts)
                item_chunks = chunk_text(description_text)
                
                for chunk in item_chunks:
                    chunks.append({
                        "id": str(uuid.uuid4()),
                        "branch": branch,
                        "category": "menu" if "menu" in filepath.lower() else "general_info",
                        "text": chunk,
                        "source": f"{os.path.basename(filepath)}#row_{i+1}",
                        "timestamp": datetime.now().isoformat()
                    })
    
    print(f"Generated {len(chunks)} chunks from {filepath}")
    return chunks

def process_json_file(filepath: str, branch: str = "main") -> List[Dict[str, Any]]:
    """
    Process a JSON file and convert to chunks with metadata.
    
    Args:
        filepath: Path to the JSON file
        branch: Branch name for metadata
        
    Returns:
        List of document chunks with metadata
    """
    print(f"Processing JSON file: {filepath}")
    
    chunks = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, list):
        # List of objects
        for i, item in enumerate(data):
            if isinstance(item, dict):
                # Convert dict to descriptive text
                description_parts = []
                for key, value in item.items():
                    if value and str(value).strip():
                        description_parts.append(f"{key}: {value}")
                
                if description_parts:
                    description_text = "; ".join(description_parts)
                    item_chunks = chunk_text(description_text)
                    
                    for chunk in item_chunks:
                        chunks.append({
                            "id": str(uuid.uuid4()),
                            "branch": branch,
                            "category": "faq" if "faq" in filepath.lower() else "locations" if "location" in filepath.lower() else "general_info",
                            "text": chunk,
                            "source": f"{os.path.basename(filepath)}#item_{i+1}",
                            "timestamp": datetime.now().isoformat()
                        })
    elif isinstance(data, dict):
        # Single object - flatten it
        description_parts = []
        for key, value in data.items():
            if isinstance(value, (str, int, float)) and str(value).strip():
                description_parts.append(f"{key}: {value}")
            elif isinstance(value, list):
                # Handle list values
                list_text = f"{key}: " + ", ".join([str(v) for v in value if str(v).strip()])
                description_parts.append(list_text)
        
        if description_parts:
            description_text = "; ".join(description_parts)
            item_chunks = chunk_text(description_text)
            
            for chunk in item_chunks:
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "branch": branch,
                    "category": "general_info",
                    "text": chunk,
                    "source": f"{os.path.basename(filepath)}",
                    "timestamp": datetime.now().isoformat()
                })
    
    print(f"Generated {len(chunks)} chunks from {filepath}")
    return chunks

def process_directory(input_dir: str, output_file: str, branch: str = "main"):
    """
    Process all files in a directory and save chunks to output file.
    
    Args:
        input_dir: Directory containing input files
        output_file: Path to output JSON file
        branch: Branch name for metadata
    """
    print(f"Processing directory: {input_dir}")
    
    all_chunks = []
    
    # Process each file in the directory
    for filename in os.listdir(input_dir):
        filepath = os.path.join(input_dir, filename)
        
        if not os.path.isfile(filepath):
            continue
            
        # Determine file type and process accordingly
        if filename.endswith('.txt'):
            chunks = process_text_file(filepath, branch)
            all_chunks.extend(chunks)
        elif filename.endswith('.csv'):
            chunks = process_csv_file(filepath, branch)
            all_chunks.extend(chunks)
        elif filename.endswith('.json'):
            chunks = process_json_file(filepath, branch)
            all_chunks.extend(chunks)
        else:
            print(f"Skipping unsupported file type: {filename}")
    
    # Save all chunks to output file
    print(f"Saving {len(all_chunks)} chunks to {output_file}")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    
    print("Processing completed!")

def main():
    """Main function to run the ingestion pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest bakery data into RAG pipeline')
    parser.add_argument('--input', '-i', default=INPUT_DIR,
                        help='Input directory containing raw data files')
    parser.add_argument('--output', '-o', default=OUTPUT_FILE,
                        help='Output file for processed chunks')
    parser.add_argument('--branch', '-b', default='main',
                        help='Branch name for metadata')
    
    args = parser.parse_args()
    
    # Process directory
    process_directory(args.input, args.output, args.branch)

if __name__ == '__main__':
    main()
