# 🤖 AI Coding Agent - Streamlit Interface

A beautiful web interface for the AI Coding Agent with real-time logging and interactive features.

## 🚀 Quick Start

### Default Mode (Streamlit Interface)
```bash
python main.py
```

This will automatically launch the Streamlit web interface at `http://localhost:8501`

### CLI Mode (Traditional Command Line)
```bash
python main.py --cli -q "your query here" -d /path/to/project
```

## 🌟 Features

### 🖥️ Web Interface
- **Beautiful UI**: Clean, modern interface built with Streamlit
- **Real-time Logs**: Live streaming of agent processing logs
- **Directory Browser**: Visual directory selection and validation
- **Response Display**: Formatted output with code highlighting
- **Log Download**: Export complete logs for analysis

### 📊 Live Monitoring
- **Real-time Updates**: See logs as they happen (500ms refresh)
- **Progress Tracking**: Visual indicators of processing status
- **Error Handling**: Clear error messages and recovery options
- **Timeout Protection**: 2-minute timeout with graceful handling

### 🔧 Configuration
- **Working Directory**: Set project directory via UI or command line
- **Query Input**: Multi-line text area for complex requests
- **Mock Mode**: Automatic fallback when PocketFlow isn't available

## 📋 Usage Examples

### Web Interface
1. Launch: `python main.py`
2. Set working directory in the sidebar
3. Enter your coding request
4. Click "🚀 Run Agent"
5. Watch real-time logs and get your response!

### Command Line Interface
```bash
# Use CLI mode with query
python main.py --cli -q "Find all TODO comments in Python files"

# Use CLI mode with custom directory
python main.py --cli -d /path/to/my/project -q "Add error handling to main.py"

# Interactive CLI mode
python main.py --cli
```

## 🎯 Interface Features

### Sidebar Configuration
- 📁 **Working Directory**: Browse and select project directory
- ✅ **Directory Validation**: Real-time verification
- 📋 **Contents Preview**: Shows first 10 items in directory

### Main Interface
- 💬 **Query Input**: Large text area for detailed requests
- 🚀 **Run Button**: Execute agent with visual feedback
- 📊 **Status Display**: Real-time processing information

### Results Display
- 🎯 **Agent Response**: Formatted response with code highlighting
- 📝 **Live Logs**: Real-time log streaming during processing
- 📜 **Complete Logs**: Expandable full log history
- 📥 **Download Logs**: Export logs as timestamped text file

## 🛠️ Technical Details

### Architecture
- **Frontend**: Streamlit web interface
- **Backend**: Existing PocketFlow agent system
- **Logging**: Custom StreamlitLogHandler for real-time logs
- **Threading**: Separate thread for agent processing
- **Queue**: Thread-safe log communication

### Mock Mode
When PocketFlow isn't available, the interface automatically switches to mock mode:
- Simulates agent processing with realistic delays
- Shows sample logs and responses
- Perfect for testing and demonstration

### Error Handling
- **Import Errors**: Graceful fallback to mock mode
- **Directory Issues**: Clear validation messages  
- **Processing Errors**: Detailed error display
- **Timeouts**: 2-minute limit with user notification

## 🔄 Migration from CLI

The CLI functionality is preserved:
```bash
# Old way (still works)
python main.py --cli -q "your query"

# New default way
python main.py  # Launches Streamlit interface
```

## 🎨 Interface Preview

```
🤖 AI Coding Agent
AI-powered coding assistant with real-time logging

⚙️ Configuration          |  💬 Your Request
📁 Working Directory       |  What would you like me to help you with?
✅ Directory exists        |  [Large text input area]
📋 Contents (X items):     |  🚀 Run Agent
📁 src/                    |
📄 main.py                 |  📊 Agent Status
📄 README.md               |  🔄 Processing... (X log entries)
...                        |

📝 Live Logs
[Real-time log stream in code format]

📋 Response
🎯 Agent Response
[Formatted response with code highlighting]

📜 Complete Logs
📥 Download Logs  [Expandable log history]
```

## 🚀 Getting Started

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python main.py
   ```

3. **Open your browser** to `http://localhost:8501`

4. **Start coding** with AI assistance!

---
*Built with ❤️ using Streamlit and AI*