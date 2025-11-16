#!/usr/bin/env python3
"""
Generate index with paragraph summaries (aggregated from subparagraphs and chunks)
"""
import redis
import json
from datetime import datetime
from collections import defaultdict

# Redis credentials
REDIS_HOST = "redis-13515.fcrce173.eu-west-1-1.ec2.redns.redis-cloud.com"
REDIS_PORT = 13515
REDIS_PASSWORD = "WNWF6sNqFg5e2N5wjWLvoMfdBuMGTdKT"
OUTPUT_FILE = "REDIS_DATABASE_INDEX_COMPLETE.md"

print("📊 Generating Complete Redis Index with Content Summaries...\n")

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
print("  → Fetching keys...")
doc_keys = list(r.keys("doc:*"))  # Only doc:* pattern (doc_* doesn't exist in DB)
ch_keys = sorted(r.keys("ch:*"))
p_keys = sorted(r.keys("p:*"))
sp_keys = r.keys("sp:*")
chunk_keys = r.keys("chunk:*")

print(f"  ✓ Found {len(doc_keys)} documents")
print(f"  ✓ Found {len(ch_keys)} chapters")
print(f"  ✓ Found {len(p_keys)} paragraphs")
print(f"  ✓ Found {len(sp_keys)} subparagraphs")
print(f"  ✓ Found {len(chunk_keys)} chunks\n")

# Index all content recursively
print("  → Building recursive content index...")

# First: Index all subparagraphs and chunks by direct parent
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

# Second: Recursively collect all content for each paragraph
def collect_all_content(key, visited=None):
    """Recursively collect all content from a key and its descendants"""
    if visited is None:
        visited = set()
    
    if key in visited:
        return []
    visited.add(key)
    
    all_content = []
    
    # Get direct children
    for child in direct_children.get(key, []):
        if child['content']:
            all_content.append(child['content'])
        # Recursively get content from this child's children
        all_content.extend(collect_all_content(child['key'], visited))
    
    return all_content

# Build aggregated content for each paragraph
children_content = {}
for p_key in p_keys:
    all_content = collect_all_content(p_key)
    if all_content:
        children_content[p_key] = all_content

print(f"  ✓ Collected recursive content for {len(children_content)}/{len(p_keys)} paragraphs\n")

# Start building markdown
md = []
md.append("# Redis Database - Complete Index with Content Summaries")
md.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
md.append(f"\n**Method:** Direct Redis connection with aggregated content")
md.append(f"\n**Total Keys:** {len(r.keys('*'))}")
md.append("\n> Document → Chapter → Paragraph hierarchy with content summaries aggregated from subparagraphs and chunks.")
md.append("\n---\n")

# Table of Contents
md.append("## 📋 Table of Contents\n")
md.append("1. [Overview](#overview)")
md.append("2. [Documents](#documents)")
md.append("3. [Chapters with Paragraphs](#chapters-with-paragraphs)")
md.append("\n---\n")

# Overview
md.append("## 📊 Overview\n")
md.append(f"- **Documents:** {len(doc_keys)}")
md.append(f"- **Chapters:** {len(ch_keys)}")
md.append(f"- **Paragraphs:** {len(p_keys)} (with content summaries)")
md.append(f"- **Subparagraphs:** {len(sp_keys)} (content aggregated)")
md.append(f"- **Chunks:** {len(chunk_keys)} (content aggregated)")
md.append(f"- **Total Keys:** {len(r.keys('*'))}")
md.append("\n---\n")

# Documents
md.append("## 📚 Documents\n")

for doc_key in doc_keys:
    print(f"  → Processing {doc_key}")
    doc_data = json.loads(r.execute_command('JSON.GET', doc_key))
    
    md.append(f"### {doc_data.get('title', 'Untitled')}\n")
    md.append(f"**Key:** `{doc_key}`\n")
    
    if 'metadata' in doc_data:
        meta = doc_data['metadata']
        if meta.get('author'):
            md.append(f"- **Author:** {meta['author']}")
        if meta.get('created'):
            md.append(f"- **Created:** {meta['created']}")
        if meta.get('category'):
            md.append(f"- **Category:** {meta['category']}")
    
    md.append("")

md.append("\n---\n")

# Chapters with Paragraphs
md.append("## 📖 Chapters with Paragraphs\n")

# Group paragraphs by parent chapter
paragraphs_by_chapter = defaultdict(list)

print("  → Organizing paragraphs by chapter...")
for p_key in p_keys:
    p_data = json.loads(r.execute_command('JSON.GET', p_key))
    parent = p_data.get('parent', 'unknown')
    paragraphs_by_chapter[parent].append((p_key, p_data))

# Process each chapter
for ch_key in ch_keys:
    # Skip Communication Rules (empty structure, no content in DB)
    if ch_key == "ch:communication_rules:001":
        print(f"  → Skipping: Communication Rules (no content)")
        continue
        
    ch_data = json.loads(r.execute_command('JSON.GET', ch_key))
    title = ch_data.get('title', 'Untitled Chapter')
    
    print(f"  → Processing chapter: {title}")
    
    md.append(f"\n### {title}\n")
    md.append(f"**Key:** `{ch_key}`")
    md.append(f"**Parent:** `{ch_data.get('parent', 'N/A')}`")
    md.append("")
    
    # Get paragraphs for this chapter
    chapter_paragraphs = paragraphs_by_chapter.get(ch_key, [])
    
    # Sort by position number
    chapter_paragraphs.sort(key=lambda x: x[1].get('position', 999))
    
    if chapter_paragraphs:
        md.append(f"#### 📄 Paragraphs ({len(chapter_paragraphs)})\n")
        
        for p_key, p_data in chapter_paragraphs:
            p_title = p_data.get('title', p_key.split(':')[1].replace('_', ' ').title())
            
            md.append(f"##### {p_title}\n")
            md.append(f"**Key:** `{p_key}`\n")
            
            # Get aggregated content from children (subparagraphs and chunks)
            child_contents = children_content.get(p_key, [])
            
            if child_contents:
                # Combine all content
                combined_content = " ".join(child_contents)
                
                # Create summary (first 400 characters)
                summary = combined_content[:400].strip()
                if len(combined_content) > 400:
                    summary += "..."
                
                md.append(f"**📝 Content Summary** ({len(child_contents)} sub-elements):")
                md.append(f"> {summary}")
            else:
                md.append("_No content found for this paragraph._")
            
            md.append("")
    else:
        md.append("_No paragraphs found for this chapter._\n")
    
    md.append("---\n")

# Statistics
md.append("\n## 📈 Statistics\n")
md.append(f"- **Total Documents:** {len(doc_keys)}")
md.append(f"- **Total Chapters:** {len(ch_keys)}")
md.append(f"- **Total Paragraphs:** {len(p_keys)}")
md.append(f"- **Paragraphs with Content:** {len([p for p in p_keys if children_content.get(p)])}")
md.append(f"- **Total Subparagraphs & Chunks:** {len(sp_keys) + len(chunk_keys)}")

md.append("\n---\n")
md.append(f"\n*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')} with aggregated content summaries*\n")

# Write to file
output_path = f"/Users/oskarschiermeister/Desktop/Database Project/{OUTPUT_FILE}"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))

print(f"\n✅ Index with content summaries generated!")
print(f"📄 Output: {OUTPUT_FILE}")
print(f"📊 Documents: {len(doc_keys)}, Chapters: {len(ch_keys)}, Paragraphs: {len(p_keys)}")
print(f"📝 Paragraphs with content: {len([p for p in p_keys if children_content.get(p)])}")

