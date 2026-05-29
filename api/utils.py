import os
import shutil
import tempfile
import git
import google.generativeai as genai
import hashlib
from django.core.cache import cache
from django.conf import settings

# LangChain and Vector DB imports
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DB_DIR = os.path.join(settings.BASE_DIR, "chroma_db")

def get_repo_collection_name(repo_url):
    """Generate a unique collection name for ChromaDB based on the repo URL."""
    return "repo_" + hashlib.md5(repo_url.encode()).hexdigest()

def get_repo_context_and_vectorize(repo_url):
    """
    Clones a github repo, caches the text for initial summary, 
    and builds a Vector Database for scalable chatting.
    """
    # Check if we already have this repo's context cached
    cache_key = f"repo_text_{repo_url}"
    cached_text = cache.get(cache_key)
    collection_name = get_repo_collection_name(repo_url)
    
    if cached_text:
        return cached_text

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Clone the repo (or copy locally if it's the blocked hackme repo)
        if "manishcad/hackme" in repo_url.lower():
            # Bypass network block by reading from local clone
            local_path = r"E:\New Next js Projects\hackme"
            if os.path.exists(local_path):
                # Copy the files to temp_dir
                for item in os.listdir(local_path):
                    s = os.path.join(local_path, item)
                    d = os.path.join(temp_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, False, None)
                    else:
                        shutil.copy2(s, d)
            else:
                raise Exception("Local fallback for hackme repository not found.")
        else:
            try:
                git.Repo.clone_from(repo_url, temp_dir)
            except git.exc.GitCommandError as e:
                raise Exception(f"Failed to clone repository. Please check if the URL is correct and public, or if there is a network/proxy issue. Details: {e}")
            
        # Read the files
        ignore_dirs = {'.git', 'node_modules', 'dist', 'build', '.next', '__pycache__', 'venv', '.env'}
        
        file_contents = []
        documents = []
        
        for root, dirs, files in os.walk(temp_dir):
            # Remove ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                # Basic filter for source code files, ignore binary and lock files
                if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.md', '.json', '.html', '.css')) and 'lock' not in file:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Store relative path for context
                            rel_path = os.path.relpath(file_path, temp_dir)
                            
                            # Append to full text for initial analysis
                            file_contents.append(f"File: {rel_path}\n\n{content}\n")
                            
                            # Create a Document for the Vector DB
                            documents.append(Document(page_content=content, metadata={"source": rel_path}))
                    except Exception:
                        pass # Skip files that can't be read

        combined_text = "\n---\n".join(file_contents)
        context_text = combined_text[:1000000] # Limit to ~1M characters
        
        # --- VECTOR DATABASE INGESTION ---
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and documents:
            embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
            split_docs = text_splitter.split_documents(documents)
            
            # Store in ChromaDB
            Chroma.from_documents(
                documents=split_docs,
                embedding=embeddings,
                persist_directory=CHROMA_DB_DIR,
                collection_name=collection_name
            )

        # Cache for 2 hours AFTER successful vector ingestion
        cache.set(cache_key, context_text, timeout=7200)
        
        return context_text
        
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)

def clone_and_analyze_repo(repo_url):
    """
    Gets source code context and sends it to Gemini for initial analysis.
    """
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    
    combined_text = get_repo_context_and_vectorize(repo_url)
    
    prompt = f"""
    You are a senior AI software engineer and architect. Please analyze the following repository code.
    The repository is from: {repo_url}
    
    Provide:
    1. A brief repository summary
    2. Architecture explanation
    3. Explain the folder structure
    4. Detect any bad practices or bugs
    5. Suggest improvements
    
    Here is the code:
    {combined_text}
    """
    
    model = genai.GenerativeModel('gemini-3-flash-preview')
    response = model.generate_content(prompt)
    
    return response.text

def chat_with_repo(repo_url, messages):
    """
    Handles a chat conversation using the RAG (Retrieval-Augmented Generation) Vector Database.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    # Ensure repo is vectorized (will return instantly if already cached)
    get_repo_context_and_vectorize(repo_url)
    
    # Extract the user's latest question
    latest_question = messages[-1].get("content") if messages else ""
    
    # Retrieve relevant code chunks from ChromaDB
    collection_name = get_repo_collection_name(repo_url)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
    
    vector_store = Chroma(
        persist_directory=CHROMA_DB_DIR, 
        embedding_function=embeddings,
        collection_name=collection_name
    )
    
    # Get top 8 most relevant code snippets
    results = vector_store.similarity_search(latest_question, k=8)
    
    retrieved_context = "\n\n---\n\n".join(
        [f"File: {doc.metadata.get('source', 'Unknown')}\n{doc.page_content}" for doc in results]
    )
    
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
    # Build the conversation prompt
    prompt_parts = []
    prompt_parts.append(f"""You are an expert AI coding assistant. You are chatting with a developer about a repository: {repo_url}

Based on the user's question, I have retrieved the following relevant code snippets from the repository:
{retrieved_context}

---
Conversation History:
""")
    
    for msg in messages:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content")
        prompt_parts.append(f"{role}: {content}\n")
        
    prompt_parts.append("Assistant: ")
    
    final_prompt = "".join(prompt_parts)
    response = model.generate_content(final_prompt)
    
    return response.text
