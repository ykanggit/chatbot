# Kotaemon Developer Guide

This guide helps developers get started with the Kotaemon project right after a fresh git clone.

## Prerequisites

- **Git**: Latest version
- **Docker**: Version 20.10+ (for Docker builds)
- **Python**: 3.10+ (for local development)
- **Operating System**: Linux, macOS, or Windows

## Quick Start

### 1. Building Docker Images

After cloning the repository, you can build Docker images from the source code.

#### Available Build Targets

The project supports three Docker image variants:

- **`lite`** (default): Minimal version with basic dependencies
- **`full`**: Includes additional packages for document processing (OCR, unstructured, etc.)
- **`ollama`**: Full version plus bundled Ollama server for local LLMs

#### Building Commands

**Linux/macOS:**
```bash
# Build lite version (recommended for most users)
docker build -t kotaemon:lite .

# Build full version (with additional document processing capabilities)
docker build --target full -t kotaemon:full .

# Build ollama version (includes local LLM support)
docker build --target ollama -t kotaemon:ollama .

# Build for specific platform
docker buildx build --platform linux/amd64 -t kotaemon:latest .
docker buildx build --platform linux/arm64 -t kotaemon:latest .  # For Apple Silicon Macs
```

**Windows:**
```cmd
# Build lite version
docker build -t kotaemon:lite .

# Build full version
docker build --target full -t kotaemon:full .

# Build ollama version
docker build --target ollama -t kotaemon:ollama .
```

#### Multi-Platform Build (Optional - Linux/macOS only)

This section is **optional** and only needed if you want to build images for multiple architectures or use advanced caching features.

```bash
# Build for both AMD64 and ARM64 architectures
docker buildx build --platform linux/amd64,linux/arm64 -t kotaemon:latest .

# Build with caching for faster rebuilds
docker buildx build --cache-from type=gha --cache-to type=gha,mode=max -t kotaemon:latest .
```

**Note**: For most developers, the basic build commands above are sufficient. Multi-platform builds are typically used for:
- Distributing images to different architectures
- CI/CD pipelines
- Advanced Docker optimization

### 2. Running Docker Images Locally

#### Basic Run Commands

**Linux/macOS:**
```bash
# Run lite version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:lite

# Run full version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:full

# Run ollama version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:ollama
```

**Windows:**
```cmd
# Run lite version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:lite

# Run full version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:full

# Run ollama version
docker run -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:ollama
```

#### Advanced Run Options

**Linux/macOS:**
```bash
# Run with custom environment variables
docker run \
  -e GRADIO_SERVER_NAME=0.0.0.0 \
  -e GRADIO_SERVER_PORT=7860 \
  -v ./ktem_app_data:/app/ktem_app_data \
  -p 7860:7860 \
  kotaemon:lite

# Run in detached mode
docker run -d -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:lite

# Run with specific platform (for Apple Silicon Macs)
docker run --platform linux/arm64 -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:lite
```

**Windows:**
```cmd
# Run with custom environment variables
docker run -e GRADIO_SERVER_NAME=0.0.0.0 -e GRADIO_SERVER_PORT=7860 -v ./ktem_app_data:/app/ktem_app_data -p 7860:7860 kotaemon:lite

# Run in detached mode
docker run -d -p 7860:7860 -v ./ktem_app_data:/app/ktem_app_data kotaemon:lite
```

#### Accessing the Application

After running the Docker container, access the application at:
- **URL**: `http://localhost:7860`
- **Default credentials**: `admin` / `admin`

### 3. Workspace Cleanup

Use the provided cleanup script to restore the project to source code mode.

#### Running the Cleanup Script

The cleanup script has two modes:

**Safe Mode (Default) - Preserves User Data:**
```bash
# Make the script executable (first time only)
chmod +x purges.sh

# Run in safe mode (preserves user data)
./purges.sh
```

**Complete Cleanup Mode - Removes Everything:**
```bash
# Remove ALL files including user data (dangerous!)
./purges.sh --everything
```

**Help:**
```bash
# Show usage information
./purges.sh --help
```

**Linux/macOS:**
```bash
# Safe mode (recommended)
./purges.sh

# Complete cleanup (removes user data)
./purges.sh --everything
```

**Windows:**
```cmd
# Safe mode (recommended)
bash purges.sh

# Complete cleanup (removes user data)
bash purges.sh --everything
```

**Note**: The `--everything` flag will prompt for confirmation before removing user data.

#### What the Cleanup Script Removes

The `purges.sh` script has two modes with different behaviors:

**Safe Mode (Default) - Preserves User Data:**
- **Development Artifacts**: `__pycache__/`, `*.pyc`, `build/`, `dist/`, etc.
- **Cache Directories**: `.theflow/`, `.ruff_cache/`, `.mypy_cache/`, etc.
- **IDE Files**: `.idea/`, `.vscode/`, `*.swp`, `*.swo`
- **OS Files**: `.DS_Store`, `Thumbs.db`
- **Virtual Environments**: `venv/`, `.venv/`, `env/`
- **Installation Artifacts**: `install_dir/`, `doc_env/`
- **Environment Files**: `.env` (preserves `.env.example`)

**Complete Cleanup Mode (`--everything`) - Removes Everything:**
- **All of the above** PLUS:
- **User Data (Permanently deleted):**
  - **Uploaded Documents**: All files uploaded to the application
  - **Chat Conversations**: Complete chat history and conversations
  - **User Settings**: All user configurations and preferences
  - **Application Databases**: SQLite databases with user data
  - **Indexed Documents**: All document embeddings and search indices
- **Application Data:**
  - `ktem_app_data/` - Contains all user data, conversations, settings
  - `gradio_tmp/` - Temporary files from the web interface
  - `storage/` - Document storage and vector databases

#### Cleanup Summary

The script provides a detailed summary showing:
- Total files deleted
- Total directories deleted
- Total items removed

Example output:
```
📊 CLEANUP SUMMARY
==================
[SUCCESS] Total files deleted: 23
[SUCCESS] Total directories deleted: 12
[SUCCESS] Total items removed: 35
==================
```

### 4. API Key Configuration

To use LLM models, you need to configure API keys for your preferred providers.

#### Supported LLM Providers

1. **OpenAI**
2. **Azure OpenAI**
3. **Cohere**
4. **Ollama** (local)
5. **Groq**

#### Configuration Methods

##### Method 1: Environment Variables

Create a `.env` file in the project root:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_CHAT_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDINGS_MODEL=text-embedding-ada-002

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here
AZURE_OPENAI_API_KEY=your_azure_api_key_here
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-35-turbo
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002

# Cohere Configuration
COHERE_API_KEY=your_cohere_api_key_here

# Groq Configuration
GROQ_API_KEY=your_groq_api_key_here
```

##### Method 2: Web UI Configuration

1. Start the application
2. Go to the **Resources** tab
3. Navigate to **LLMs and Embeddings**
4. Set your API keys directly in the web interface

#### API Key Setup by Provider

##### OpenAI

1. **Get API Key**: Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Configure**: Add to `.env` file or web UI
3. **Models**: Supports GPT-3.5, GPT-4, and embedding models

```bash
# .env file
OPENAI_API_KEY=sk-your-key-here
OPENAI_CHAT_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDINGS_MODEL=text-embedding-ada-002
```

##### Azure OpenAI

1. **Get API Key**: Visit [Azure OpenAI Service](https://portal.azure.com/)
2. **Configure**: Add endpoint and API key to `.env` file
3. **Models**: Supports GPT models deployed on Azure

```bash
# .env file
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-35-turbo
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
```

##### Cohere

1. **Get API Key**: Visit [Cohere Platform](https://dashboard.cohere.com/)
2. **Configure**: Add API key to `.env` file or web UI
3. **Models**: Supports Cohere's chat and embedding models

```bash
# .env file
COHERE_API_KEY=your-cohere-api-key
```

##### Ollama (Local)

1. **Install Ollama**: Follow [Ollama Installation Guide](https://ollama.ai/download)
2. **Pull Models**: Download your preferred models
3. **Configure**: Set model names in web UI

```bash
# Install Ollama (macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Start Ollama server
ollama serve
```

##### Groq

1. **Get API Key**: Visit [Groq Console](https://console.groq.com/)
2. **Configure**: Add API key to `.env` file or web UI
3. **Models**: Supports Groq's fast inference models

```bash
# .env file
GROQ_API_KEY=your-groq-api-key
```

#### Verification

After configuring API keys:

1. **Start the application**
2. **Go to Resources tab**
3. **Check LLMs and Embeddings section**
4. **Verify your models are available and set as default**

## Troubleshooting

### Docker Issues

**Linux/macOS:**
```bash
# Check Docker status
docker --version
docker ps

# Clean up Docker resources
docker system prune -a

# Rebuild with no cache
docker build --no-cache -t kotaemon:latest .
```

**Windows:**
```cmd
# Check Docker status
docker --version
docker ps

# Clean up Docker resources
docker system prune -a

# Rebuild with no cache
docker build --no-cache -t kotaemon:latest .
```

### API Key Issues

1. **Check API key format**: Ensure no extra spaces or characters
2. **Verify provider status**: Check if the service is operational
3. **Test connectivity**: Try a simple API call to verify access
4. **Check quotas**: Ensure you haven't exceeded API limits

### Cleanup Issues

If the cleanup script fails:

**Linux/macOS:**
```bash
# Manual cleanup
rm -rf ktem_app_data/ gradio_tmp/ storage/ install_dir/
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
```

**Windows:**
```cmd
# Manual cleanup
rmdir /s /q ktem_app_data gradio_tmp storage install_dir
```

## Next Steps

After setting up:

1. **Upload documents** in the Files tab
2. **Start chatting** with your documents
3. **Configure retrieval settings** in the Settings tab
4. **Explore advanced features** like GraphRAG and LightRAG

## Additional Resources

- [User Guide](https://cinnamon.github.io/kotaemon/)
- [Developer Guide](https://cinnamon.github.io/kotaemon/development/)
- [GitHub Repository](https://github.com/Cinnamon/kotaemon)
- [Issues & Feedback](https://github.com/Cinnamon/kotaemon/issues) 