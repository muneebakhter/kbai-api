#!/usr/bin/env python3
"""
Sample data generation script - equivalent to DARKBO's create_sample_data
Creates sample projects, knowledge base articles, and FAQs for testing
"""

import json
import os
import uuid
from pathlib import Path
from typing import List, Dict

def create_sample_data():
    """Create sample data for testing the KBAI API system"""
    
    # Get data directory from environment or use default
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create project mapping file
    proj_mapping_file = data_dir / "proj_mapping.txt"
    
    # Sample projects
    projects = [
        {"id": "tech-support", "name": "Technical Support Knowledge Base", "active": True},
        {"id": "hr-policies", "name": "HR Policies and Procedures", "active": True},
        {"id": "product-docs", "name": "Product Documentation", "active": True},
        {"id": "aspca-test", "name": "ASPCA Test Project", "active": False},  # Will be activated after file upload
    ]
    
    # Write project mapping
    mapping_content = []
    for project in projects:
        status = "1" if project["active"] else "0"
        mapping_content.append(f"{project['id']}|{project['name']}|{status}")
    
    proj_mapping_file.write_text("\n".join(mapping_content) + "\n", encoding="utf-8")
    print(f"✅ Created project mapping: {proj_mapping_file}")
    
    # Create project directories and sample data
    for project in projects:
        project_dir = data_dir / project["id"]
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (project_dir / "faqs").mkdir(exist_ok=True)
        (project_dir / "kb").mkdir(exist_ok=True)
        (project_dir / "ingest").mkdir(exist_ok=True)
        
        # Create sample FAQs
        if project["id"] == "tech-support":
            faqs = [
                {
                    "id": "password-reset",
                    "question": "How do I reset my password?",
                    "answer": "You can reset your password by clicking the 'Forgot Password' link on the login page and following the instructions sent to your email.",
                    "category": "Authentication",
                    "tags": ["password", "login", "reset"]
                },
                {
                    "id": "software-install",
                    "question": "How do I install the company software?",
                    "answer": "Download the installer from the company portal, run as administrator, and follow the setup wizard. Contact IT if you encounter issues.",
                    "category": "Software",
                    "tags": ["install", "software", "setup"]
                }
            ]
            
            for faq in faqs:
                faq_file = project_dir / "faqs" / f"{faq['id']}.json"
                faq_file.write_text(json.dumps(faq, indent=2), encoding="utf-8")
        
        elif project["id"] == "hr-policies":
            faqs = [
                {
                    "id": "vacation-policy",
                    "question": "What is the vacation policy?",
                    "answer": "Employees accrue 15 days of vacation per year, with additional days based on tenure. Vacation must be approved by your manager in advance.",
                    "category": "Benefits",
                    "tags": ["vacation", "pto", "time-off"]
                },
                {
                    "id": "remote-work",
                    "question": "Can I work remotely?",
                    "answer": "Remote work is available on a case-by-case basis with manager approval. Hybrid schedules are encouraged for better work-life balance.",
                    "category": "Work Policies",
                    "tags": ["remote", "work-from-home", "hybrid"]
                }
            ]
            
            for faq in faqs:
                faq_file = project_dir / "faqs" / f"{faq['id']}.json"
                faq_file.write_text(json.dumps(faq, indent=2), encoding="utf-8")
        
        # Create sample KB articles
        if project["id"] == "product-docs":
            kb_articles = [
                {
                    "id": "api-getting-started",
                    "title": "API Getting Started Guide",
                    "content": "Welcome to our API! This guide will help you get started with making your first API calls. First, obtain an API key from your dashboard...",
                    "category": "API Documentation",
                    "tags": ["api", "getting-started", "authentication"],
                    "source_url": "https://docs.example.com/api/getting-started"
                },
                {
                    "id": "rate-limits",
                    "title": "API Rate Limits",
                    "content": "Our API has rate limits to ensure fair usage. Free tier: 100 requests/hour. Pro tier: 1000 requests/hour. Enterprise: unlimited.",
                    "category": "API Documentation", 
                    "tags": ["api", "rate-limits", "quotas"],
                    "source_url": "https://docs.example.com/api/rate-limits"
                }
            ]
            
            for article in kb_articles:
                kb_file = project_dir / "kb" / f"{article['id']}.json"
                kb_file.write_text(json.dumps(article, indent=2), encoding="utf-8")
    
    # Create indexes directory
    indexes_dir = data_dir / "indexes"
    indexes_dir.mkdir(exist_ok=True)
    
    print(f"✅ Created sample data in {data_dir}")
    print(f"📁 Projects created: {len(projects)}")
    print("📋 Sample FAQs and KB articles generated")
    print("🔍 Ready for indexing and testing")
    
    return {
        "data_dir": str(data_dir),
        "projects": projects,
        "proj_mapping_file": str(proj_mapping_file)
    }

if __name__ == "__main__":
    result = create_sample_data()
    print(f"\n🎉 Sample data creation complete!")
    print(f"Data directory: {result['data_dir']}")
    print(f"Projects file: {result['proj_mapping_file']}")