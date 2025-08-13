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

# Configuration Section
st.header("⚙️ Configuration")

# Create columns for configuration
col1, col2 = st.columns(2)

with col1:
    github_token = st.text_input(
        "GitHub Personal Access Token", 
        type="password", 
        help="Generate a token with 'repo' permissions from GitHub Settings > Developer settings > Personal access tokens"
    )
    
    repo_owner = st.text_input(
        "Repository Owner", 
        placeholder="your-username",
        help="GitHub username or organization name"
    )

with col2:
    repo_name = st.text_input(
        "Repository Name", 
        placeholder="your-repo-name",
        help="Name of your repository"
    )
    
    branch_name = st.text_input(
        "Branch Name", 
        value="main",
        help="Target branch for uploads"
    )

# Advanced settings in expander
with st.expander("🔧 Advanced Settings"):
    upload_path = st.text_input(
        "Upload Path in Repository", 
        value="data/",
        help="Path where files will be uploaded (e.g., 'data/' or 'datasets/raw/')"
    )
    
    commit_message_template = st.text_input(
        "Commit Message Template",
        value="Add dataset: {filename} - {timestamp}",
        help="Use {filename} and {timestamp} placeholders"
    )

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
    """Validate the configuration"""
    if not all([github_token, repo_owner, repo_name, branch_name]):
        st.error("❌ Please fill in all required configuration fields")
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
    ### Setup Instructions:
    1. **GitHub Token**: Generate a Personal Access Token with 'repo' permissions
        - Go to GitHub Settings → Developer settings → Personal access tokens
        - Generate new token with full 'repo' access
    
    2. **Repository Details**: Enter your repository owner and name
    
    3. **File Upload**: 
        - Files < 25MB: Direct upload via GitHub API
        - Files ≥ 25MB: Automatic Git LFS handling
    
    ### Supported File Types:
    - Excel files (.xlsx)
    - CSV files (.csv)
    - JSON files (.json)
    - Text files (.txt)
    - PDF files (.pdf)
    - Word documents (.docx)
    
    ### Git LFS Requirements:
    For files larger than 25MB, Git LFS must be installed on the server running this application.
    """)

with st.expander("🔒 Security Notes"):
    st.markdown("""
    ### Important Security Considerations:
    - Never share your GitHub token with others
    - Use tokens with minimal required permissions
    - Consider using environment variables for sensitive data in production
    - Regularly rotate your access tokens
    - Monitor repository access and commits
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "RAG Chatbot Data Admin Panel | Built for Dubai-based GenAI Solutions"
    "</div>", 
    unsafe_allow_html=True
)