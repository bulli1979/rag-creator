#!/usr/bin/env python3
"""
Batch ingest folder into RAG via API, looping through all files.
Usage: python ingest_folder_batch.py <folder_path> [batch_size]
"""
import sys
import requests
import json
import time

def ingest_folder(folder_path: str, batch_size: int = 200, api_base: str = "http://127.0.0.1:8000"):
    offset = 0
    total_submitted = 0
    
    while True:
        print(f"\n[Batch] Offset={offset}, BatchSize={batch_size}")
        
        try:
            resp = requests.post(
                f"{api_base}/api/documents/upload-folder-path",
                json={
                    "folder_path": folder_path,
                    "tags": ["NOT_Knowledge_Base"],
                    "source": "lokal",
                    "offset": offset,
                    "batch_size": batch_size,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            
            # Print response
            file_count = data.get("fileCount", 0)
            next_offset = data.get("nextOffset", offset + batch_size)
            done = data.get("done", False)
            
            print(f"  Submitted: {file_count} files")
            print(f"  Total so far: {total_submitted + file_count}")
            print(f"  Done: {done}")
            
            if done:
                print(f"\n✅ All files submitted! Total: {total_submitted + file_count}")
                break
            
            total_submitted += file_count
            offset = next_offset
            
            # Small delay between batches to avoid overload
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <folder_path> [batch_size]")
        sys.exit(1)
    
    folder = sys.argv[1]
    batch = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    ingest_folder(folder, batch_size=batch)
