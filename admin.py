import streamlit as st
import requests
import base64
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
import json

# Configure page
st.set_page_config(
    page_title="RAG Chatbot Data Admin",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1 style="color: white; margin: 0;">🤖 RAG Chatbot Data Admin Panel</h1>
    <p style="color: white; margin: 0; opacity: 0.8;">Upload and manage datasets for your Dubai-based RAG chatbot</p>
</div>
""", unsafe_allow_html=True)

# Backend Configuration (Using Environment Variables)
# Set these in Streamlit Cloud secrets or environment variables
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"] if "GITHUB_TOKEN" in st.secrets else os.getenv("GITHUB_TOKEN", "")
    REPO_OWNER = st.secrets.get("REPO_OWNER", os.getenv("REPO_OWNER", ""))
    REPO_NAME = st.secrets.get("REPO_NAME", os.getenv("REPO_NAME", ""))
    BRANCH_NAME = st.secrets.get("BRANCH_NAME", os.getenv("BRANCH_NAME", "main"))
    UPLOAD_PATH = st.secrets.get("UPLOAD_PATH", os.getenv("UPLOAD_PATH", "data/"))
    COMMIT_MESSAGE_TEMPLATE = st.secrets.get("COMMIT_MESSAGE_TEMPLATE", os.getenv("COMMIT_MESSAGE_TEMPLATE", "Add dataset: {filename} - {timestamp}"))
except:
    # Fallback to environment variables only
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    REPO_OWNER = os.getenv("REPO_OWNER", "")
    REPO_NAME = os.getenv("REPO_NAME", "")
    BRANCH_NAME = os.getenv("BRANCH_NAME", "main")
    UPLOAD_PATH = os.getenv("UPLOAD_PATH", "data/")
    COMMIT_MESSAGE_TEMPLATE = os.getenv("COMMIT_MESSAGE_TEMPLATE", "Add dataset: {filename} - {timestamp}")

# Assign backend config to variables
github_token = GITHUB_TOKEN
repo_owner = REPO_OWNER
repo_name = REPO_NAME
branch_name = BRANCH_NAME
upload_path = UPLOAD_PATH
commit_message_template = COMMIT_MESSAGE_TEMPLATE

# File Upload Section
st.header("📁 File Upload")

uploaded_files = st.file_uploader(
    "Choose files to upload",
    accept_multiple_files=True,
    type=['xlsx', 'csv', 'json', 'txt', 'pdf', 'docx'],
    help="Supported formats: Excel, CSV, JSON, TXT, PDF, DOCX"
)

if uploaded_files:
    st.subheader("📋 Upload Summary")
    
    total_size = 0
    file_info = []
    
    for file in uploaded_files:
        file_size_mb = file.size / (1024 * 1024)
        total_size += file_size_mb
        upload_method = "Direct Upload" if file_size_mb < 25 else "Git LFS"
        
        file_info.append({
            "name": file.name,
            "size_mb": file_size_mb,
            "method": upload_method
        })
    
    # Display file information
    for info in file_info:
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            st.write(f"📄 {info['name']}")
        with col2:
            st.write(f"{info['size_mb']:.2f} MB")
        with col3:
            method_color = "🟢" if info['method'] == "Direct Upload" else "🟡"
            st.write(f"{method_color} {info['method']}")
    
    st.info(f"Total size: {total_size:.2f} MB | Files: {len(uploaded_files)}")

# Helper Functions
def validate_config():
    """Validate the backend configuration"""
    if not GITHUB_TOKEN:
        st.error("❌ GitHub token not found. Please configure GITHUB_TOKEN in Streamlit secrets.")
        st.info("💡 Go to Streamlit Cloud → Settings → Secrets and add: GITHUB_TOKEN = 'your_token_here'")
        return False
    if not REPO_OWNER:
        st.error("❌ Repository owner not configured. Please set REPO_OWNER in Streamlit secrets.")
        return False
    if not REPO_NAME:
        st.error("❌ Repository name not configured. Please set REPO_NAME in Streamlit secrets.")
        return False
    return True

def check_git_lfs():
    """Check if Git LFS is available"""
    try:
        result = subprocess.run(['git', 'lfs', 'version'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def upload_small_file(file_content, filename, path):
    """Upload file directly via GitHub API (< 25MB)"""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{path}"
    
    # Check if file exists
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    sha = None
    if response.status_code == 200:
        sha = response.json()["sha"]
    
    # Prepare commit data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = commit_message_template.format(
        filename=filename,
        timestamp=timestamp
    )
    
    data = {
        "message": commit_message,
        "content": base64.b64encode(file_content).decode(),
        "branch": branch_name
    }
    
    if sha:
        data["sha"] = sha
    
    response = requests.put(url, headers=headers, json=data)
    return response.status_code == 201 or response.status_code == 200, response

def upload_large_file_lfs(file_content, filename, path):
    """Upload large file using Git LFS"""
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone repository
            clone_url = f"https://{github_token}@github.com/{repo_owner}/{repo_name}.git"
            subprocess.run(['git', 'clone', '--depth', '1', '-b', branch_name, clone_url, temp_dir], 
                         check=True, capture_output=True)
            
            # Change to repo directory
            os.chdir(temp_dir)
            
            # Configure git
            subprocess.run(['git', 'config', 'user.email', 'admin@chatbot.com'], check=True)
            subprocess.run(['git', 'config', 'user.name', 'Chatbot Admin'], check=True)
            
            # Initialize LFS if not already
            subprocess.run(['git', 'lfs', 'install'], check=True)
            
            # Create directory if needed
            file_dir = os.path.dirname(path)
            if file_dir:
                os.makedirs(file_dir, exist_ok=True)
            
            # Write file
            with open(path, 'wb') as f:
                f.write(file_content)
            
            # Track with LFS
            file_extension = os.path.splitext(filename)[1]
            subprocess.run(['git', 'lfs', 'track', f"*{file_extension}"], check=True)
            
            # Add and commit
            subprocess.run(['git', 'add', '.gitattributes'], check=True)
            subprocess.run(['git', 'add', path], check=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_message = commit_message_template.format(
                filename=filename,
                timestamp=timestamp
            )
            
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            
            # Push
            subprocess.run(['git', 'push', 'origin', branch_name], check=True)
            
            return True, None
            
    except subprocess.CalledProcessError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

# Upload Button and Processing
if uploaded_files and st.button("🚀 Upload Files to GitHub", type="primary"):
    if not validate_config():
        st.stop()
    
    # Check Git LFS availability for large files
    large_files = [f for f in uploaded_files if f.size > 25 * 1024 * 1024]
    if large_files and not check_git_lfs():
        st.error("❌ Git LFS is not available. Please install Git LFS to upload files larger than 25MB.")
        st.info("Install Git LFS: https://git-lfs.github.io/")
        st.stop()
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_container = st.container()
    
    success_count = 0
    error_count = 0
    
    for i, file in enumerate(uploaded_files):
        file_content = file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        file_path = os.path.join(upload_path, file.name).replace('\\', '/')
        
        with status_container:
            st.write(f"📤 Uploading: {file.name} ({file_size_mb:.2f} MB)")
        
        try:
            if file_size_mb < 25:
                # Direct upload
                success, response = upload_small_file(file_content, file.name, file_path)
                if success:
                    success_count += 1
                    st.success(f"✅ {file.name} uploaded successfully (Direct)")
                else:
                    error_count += 1
                    st.error(f"❌ Failed to upload {file.name}: {response.text}")
            else:
                # LFS upload
                success, error = upload_large_file_lfs(file_content, file.name, file_path)
                if success:
                    success_count += 1
                    st.success(f"✅ {file.name} uploaded successfully (Git LFS)")
                else:
                    error_count += 1
                    st.error(f"❌ Failed to upload {file.name}: {error}")
        
        except Exception as e:
            error_count += 1
            st.error(f"❌ Error uploading {file.name}: {str(e)}")
        
        # Update progress
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    # Final summary
    st.header("📊 Upload Summary")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Successful", success_count)
    with col2:
        st.metric("❌ Failed", error_count)
    with col3:
        st.metric("📁 Total Files", len(uploaded_files))
    
    if success_count > 0:
        st.success(f"🎉 Successfully uploaded {success_count} file(s) to your repository!")
        st.info(f"Check your repository: https://github.com/{repo_owner}/{repo_name}")

# Information Section
st.header("ℹ️ Information")

with st.expander("📖 How to use this admin panel"):
    st.markdown("""
    ### Simple Upload Process:
    1. **Select Files**: Choose one or multiple files to upload
    2. **Preview**: Review file sizes and upload methods
    3. **Upload**: Click the upload button to add files to the repository
    
    ### File Handling:
    - Files < 25MB: Direct upload (fast)
    - Files ≥ 25MB: Git LFS handling (automatic)
    
    ### Supported File Types:
    - Excel files (.xlsx)
    - CSV files (.csv)
    - JSON files (.json)
    - Text files (.txt)
    - PDF files (.pdf)
    - Word documents (.docx)
    
    ### Repository Information:
    - Target Repository: `{repo_owner}/{repo_name}`
    - Upload Path: `{upload_path}`
    - Branch: `{branch_name}`
    """.format(repo_owner=REPO_OWNER, repo_name=REPO_NAME, upload_path=UPLOAD_PATH, branch_name=BRANCH_NAME))

with st.expander("🔒 Admin Information"):
    st.markdown("""
    ### Backend Configuration:
    This application is pre-configured to upload files to your repository.
    
    ### Security Features:
    - GitHub credentials are stored securely in backend
    - Users cannot access or modify repository settings
    - All uploads are logged with timestamps
    
    ### File Storage:
    - Repository: `{repo_owner}/{repo_name}`
    - Upload directory: `{upload_path}`
    - Branch: `{branch_name}`
    """.format(repo_owner=REPO_OWNER, repo_name=REPO_NAME, upload_path=UPLOAD_PATH, branch_name=BRANCH_NAME))

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "RAG Chatbot Data Admin Panel | Built for Dubai-based GenAI Solutions"
    "</div>", 
    unsafe_allow_html=True
)
