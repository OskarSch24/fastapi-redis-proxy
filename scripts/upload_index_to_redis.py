#!/usr/bin/env python3
"""
Upload the complete index to Redis as index:database_schema
This will REPLACE the old index with the new one containing paragraph summaries
"""
import redis
import json
from datetime import datetime
from collections import defaultdict

# Redis credentials
REDIS_HOST = "redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com"
REDIS_PORT = 13515
REDIS_PASSWORD = "WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT"

print("📤 Uploading Enhanced Index to Redis...\n")

# Connect to Redis
print("  → Connecting to Redis...")
r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    ssl=False,
    decode_responses=True,
    socket_timeout=10
)
r.ping()
print("  ✓ Connected!\n")

# Get all keys
print("  → Fetching current database structure...")
doc_keys = r.keys("doc:*")
ch_keys = sorted(r.keys("ch:*"))
p_keys = sorted(r.keys("p:*"))
sp_keys = r.keys("sp:*")
chunk_keys = r.keys("chunk:*")

print(f"  ✓ Found {len(doc_keys)} documents")
print(f"  ✓ Found {len(ch_keys)} chapters")
print(f"  ✓ Found {len(p_keys)} paragraphs\n")

# Build recursive content collector
print("  → Building content index...")
direct_children = defaultdict(list)

for sp_key in sp_keys:
    sp_data = json.loads(r.execute_command('JSON.GET', sp_key))
    parent = sp_data.get('parent')
    content = sp_data.get('content', sp_data.get('text', ''))
    if parent:
        direct_children[parent].append({'key': sp_key, 'content': content})

for chunk_key in chunk_keys:
    chunk_data = json.loads(r.execute_command('JSON.GET', chunk_key))
    parent = chunk_data.get('parent')
    content = chunk_data.get('text', chunk_data.get('content', ''))
    if parent:
        direct_children[parent].append({'key': chunk_key, 'content': content})

def collect_all_content(key, visited=None):
    """Recursively collect all content"""
    if visited is None:
        visited = set()
    if key in visited:
        return []
    visited.add(key)
    
    all_content = []
    for child in direct_children.get(key, []):
        if child['content']:
            all_content.append(child['content'])
        all_content.extend(collect_all_content(child['key'], visited))
    
    return all_content

# Build the enhanced index structure
index_data = {
    "generated_at": datetime.now().strftime('%Y-%m-%d'),
    "version": "2.0",
    "total_keys": len(r.keys('*')),
    "documents": [],
    "key_patterns": {
        "doc": "Document level - top level content containers",
        "ch": "Chapter level - major sections within documents",
        "p": "Paragraph level - main content blocks with summaries",
        "sp": "Subparagraph level - detailed subsections",
        "ssp": "Sub-subparagraph level - finest granularity",
        "chunk": "Text chunks - small searchable pieces"
    }
}

# Process documents
for doc_key in doc_keys:
    doc_data = json.loads(r.execute_command('JSON.GET', doc_key))
    
    doc_entry = {
        "key": doc_key,
        "title": doc_data.get('title', 'Untitled'),
        "author": doc_data.get('metadata', {}).get('author', ''),
        "created": doc_data.get('metadata', {}).get('created', ''),
        "total_chapters": doc_data.get('total_chapters', 0),
        "chapters": []
    }
    
    # Get chapters for this document
    for ch_key in ch_keys:
        # Skip Communication Rules (no content)
        if ch_key == "ch:communication_rules:001":
            continue
            
        ch_data = json.loads(r.execute_command('JSON.GET', ch_key))
        
        if ch_data.get('parent') == doc_key:
            ch_entry = {
                "key": ch_key,
                "title": ch_data.get('title', 'Untitled'),
                "position": ch_data.get('position', 0),
                "paragraphs": []
            }
            
            # Get paragraphs for this chapter
            for p_key in p_keys:
                p_data = json.loads(r.execute_command('JSON.GET', p_key))
                
                if p_data.get('parent') == ch_key:
                    # Collect content
                    all_content = collect_all_content(p_key)
                    
                    # Create summary
                    summary = ""
                    if all_content:
                        combined = " ".join(all_content)
                        summary = combined[:400].strip()
                        if len(combined) > 400:
                            summary += "..."
                    
                    p_entry = {
                        "key": p_key,
                        "title": p_data.get('title', 'Untitled'),
                        "position": p_data.get('position', 0),
                        "summary": summary,
                        "has_content": len(all_content) > 0,
                        "sub_elements": len(all_content)
                    }
                    
                    ch_entry["paragraphs"].append(p_entry)
            
            # Sort paragraphs by position
            ch_entry["paragraphs"].sort(key=lambda x: x['position'])
            
            doc_entry["chapters"].append(ch_entry)
    
    # Sort chapters by position
    doc_entry["chapters"].sort(key=lambda x: x['position'])
    
    index_data["documents"].append(doc_entry)

print(f"  ✓ Built index structure\n")

# Upload to Redis
print("  → Uploading to Redis as index:database_schema...")
r.execute_command('JSON.SET', 'index:database_schema', '$', json.dumps(index_data))
print("  ✓ Uploaded!\n")

# Verify
print("  → Verifying upload...")
verify = r.execute_command('JSON.GET', 'index:database_schema')
verify_data = json.loads(verify)

print(f"  ✓ Verified!")
print(f"\n📊 New Index Stats:")
print(f"  - Documents: {len(verify_data['documents'])}")
print(f"  - Chapters: {sum(len(doc['chapters']) for doc in verify_data['documents'])}")
total_paras = sum(len(ch['paragraphs']) for doc in verify_data['documents'] for ch in doc['chapters'])
print(f"  - Paragraphs: {total_paras}")
paras_with_content = sum(1 for doc in verify_data['documents'] for ch in doc['chapters'] for p in ch['paragraphs'] if p['has_content'])
print(f"  - Paragraphs with content: {paras_with_content}")

print(f"\n✅ Index successfully updated in Redis!")
print(f"   Key: index:database_schema")
print(f"   Version: 2.0")

