"""
Streaming Utilities
For processing large files in chunks to avoid memory issues
"""
import os
from typing import Iterator, Optional, Tuple
import re

CHUNK_SIZE = 1024 * 1024  # 1MB chunks

def read_file_in_chunks(file_path: str, chunk_size: int = CHUNK_SIZE) -> Iterator[bytes]:
    """
    Read a file in chunks to avoid loading entire file into memory
    
    Args:
        file_path: Path to the file
        chunk_size: Size of each chunk in bytes
        
    Yields:
        Chunks of file content as bytes
    """
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        print(f"Error reading file in chunks: {e}")
        raise

def read_text_file_streaming(file_path: str, encoding: str = 'utf-8') -> Iterator[str]:
    """
    Read a text file in chunks and yield lines
    
    Args:
        file_path: Path to the text file
        encoding: File encoding
        
    Yields:
        Lines of text
    """
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            buffer = ''
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    if buffer:
                        yield buffer
                    break
                
                buffer += chunk
                lines = buffer.split('\n')
                buffer = lines[-1]  # Keep incomplete line in buffer
                
                for line in lines[:-1]:
                    if line.strip():
                        yield line
    except Exception as e:
        print(f"Error streaming text file: {e}")
        raise

def process_subtitle_streaming(file_path: str) -> Iterator[str]:
    """
    Process subtitle file in streaming fashion
    Extracts text content from SRT/VTT files without loading entire file
    
    Args:
        file_path: Path to subtitle file
        
    Yields:
        Text lines from subtitle
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            buffer = ''
            in_subtitle_block = False
            
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    if buffer:
                        yield buffer
                    break
                
                buffer += chunk
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    
                    # Skip timestamp lines and empty lines
                    if not line or re.match(r'^\d+$', line) or '-->' in line:
                        continue
                    
                    # Skip HTML tags
                    line = re.sub(r'<[^>]+>', '', line)
                    line = re.sub(r'\[[^\]]*\]', '', line)
                    
                    if line:
                        yield line
    except Exception as e:
        print(f"Error processing subtitle stream: {e}")
        raise

def get_file_size_mb(file_path: str) -> float:
    """Get file size in megabytes"""
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except:
        return 0.0

def should_use_streaming(file_path: str, threshold_mb: float = 10.0) -> bool:
    """
    Determine if streaming should be used based on file size
    
    Args:
        file_path: Path to file
        threshold_mb: Size threshold in MB (default 10MB)
        
    Returns:
        True if file is larger than threshold
    """
    return get_file_size_mb(file_path) > threshold_mb
