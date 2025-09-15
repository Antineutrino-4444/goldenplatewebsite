# 🏆 Golden Plate Recorder

A comprehensive student attendance tracking system with barcode scanner support, built with Flask (Python) backend and React frontend. Features a modern React UI with Tailwind CSS, SQLite database integration, and role-based access control.

## 🌟 Features

### 🔐 Authentication & User Management
- **Multi-role system**: Super Admin, Admin, User, and Guest roles
- **Invite-based registration**: Secure account creation with invite codes
- **Session-based authentication**: Secure login/logout with Flask sessions
- **Role-based access control**: Different permissions per user role
- **Account deletion requests**: Users can request account deletion through admin approval
- **SQLite database**: Persistent user data storage with Flask-SQLAlchemy

### 📊 Session Management
- **Default naming**: `Golden_Plate_Month_Day_Year` format
- **Custom session names**: User-defined session names
- **Multiple sessions**: Create, switch, and delete sessions
- **Session privacy**: Users see only their own sessions
- **Admin oversight**: Admins can view all sessions

### 📝 Data Input & Processing
- **CSV database**: Upload student data (Last, First, Student ID format)
- **Dual input mode**: Support for both Student ID and Name input
- **Smart matching**: Searches CSV by both ID and name
- **Manual entries**: Fallback for students not in CSV
- **Duplicate prevention**: No repeat entries per session

### 🎯 Category Recording
- **Three categories**: CLEAN (gold), DIRTY (neutral), RED (red)
- **Popup workflow**: Click → popup → enter → done
- **Barcode scanner support**: HID device compatible
- **Mobile optimized**: Large touch-friendly buttons
- **Real-time counters**: Live update of record counts

### 📈 Scan History & Reporting
- **Real-time scan history**: Shows time, name, and ID for each scan
- **Category tracking**: Visual badges for each category
- **CSV export**: Three-column format (CLEAN, DIRTY, RED)
- **Name format**: "First Last" without separation
- **Session-specific exports**: Export current session data

### 👑 Admin Panel
- **User management**: View all users and their roles with SQLite backend
- **System monitoring**: Track all sessions across users
- **Role badges**: Visual distinction for different user types  
- **Invite code management**: Generate and manage user invite codes
- **Delete request management**: Approve/deny user account deletion requests
- **System analytics**: Usage statistics and monitoring
- **Auto-session joining**: Seamless session management for admins

## 🚀 Live Demo

**Website**: [https://20.151.74.59/]

The application includes multiple user roles with different access levels:
- **Super Administrator**: Complete system control and user management
- **Administrator**: Admin panel access and session oversight  
- **Regular Users**: Standard attendance tracking features

Create your own account using the signup feature, or contact your system administrator for access credentials.

## 🛠️ Technology Stack

### Backend (Flask)
- **Python 3.11+**
- **Flask 3.1.1**: Web framework with CORS support
- **Flask-SQLAlchemy**: Database ORM with SQLite
- **Session-based authentication**: Secure user sessions
- **CSV processing**: File upload and data parsing
- **RESTful API**: All operations via API endpoints

### Frontend (React)
- **React 19.1.0**: Modern hooks-based architecture  
- **Vite 7.1.5**: Build tool and development server
- **Tailwind CSS v4**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **Lucide React**: Beautiful icon library
- **Responsive design**: Mobile-first approach
- **Real-time updates**: Live data synchronization

### Database
- **SQLite**: Lightweight file-based database
- **Flask-SQLAlchemy 3.1.1**: ORM for database operations
- **User management**: Persistent user data storage
- **Session data**: File-based session storage

## 📦 Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

### Setup & Build
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
# source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Build the frontend
cd frontend
npm install --legacy-peer-deps
# or use pnpm install
npm run build
cd ..

# Copy built frontend to Flask static directory
# On Windows
xcopy /E /I frontend\dist\* src\static\
# On macOS/Linux
# cp -r frontend/dist/* src/static/

# Run the Flask application
python src/main.py
```

## 🔧 Configuration

### Environment Variables
- `FLASK_ENV`: Set to `development` for development mode
- `SECRET_KEY`: Flask secret key for sessions (default provided)
- `SQLALCHEMY_DATABASE_URI`: SQLite database path (auto-configured)

### Database Setup
- **SQLite database**: Automatically created at `src/database/app.db`
- **Auto-initialization**: Database tables created on first run
- **User roles**: Supports user, admin, superadmin, and guest roles

### CSV Format
The application expects CSV files with the following columns:
```csv
Last,First,Student ID
Smith,John,20230105
Johnson,Sarah,20230106
```

## 📱 Usage

### Basic Workflow
1. **Login** with your credentials
2. **Upload CSV** file with student data
3. **Select category** (CLEAN/DIRTY/RED)
4. **Scan or enter** Student ID or Name
5. **View scan history** in real-time
6. **Export results** when finished

### Barcode Scanner Setup
- Use any HID-compatible barcode scanner
- Scanner should be configured to send data followed by Enter key
- No additional software required - works like keyboard input

### Admin Functions
- **User Management**: View and monitor all users with SQLite persistence
- **Invite Code Generation**: Create secure invite codes for new users
- **Delete Request Management**: Handle user account deletion requests
- **Session Oversight**: Access all sessions across the system
- **Auto-Session Management**: Automatically join sessions for seamless workflow
- **System Analytics**: Monitor usage and activity

## 🎯 Key Features Explained

### Smart Input Processing
- **ID Lookup**: Searches CSV for exact Student ID match
- **Name Lookup**: Searches CSV for "First Last" name combinations
- **Manual Entry**: Creates entries for students not in CSV
- **Duplicate Prevention**: Prevents repeat entries in same session

### Mobile Optimization
- **Touch-friendly**: Large buttons for mobile devices
- **Responsive design**: Works on phones, tablets, and desktops
- **Auto-focus**: Input fields ready for barcode scanners
- **Professional UI**: Clean, modern interface

### Export Features
- **Three-column CSV**: Separate columns for each category
- **Name format**: "First Last" format for easy processing
- **Session-specific**: Export only current session data
- **Clean output**: No extra metadata or timestamps

## 🔒 Security Features

- **Session-based authentication**: Secure login system with Flask sessions
- **Role-based access control**: Different permissions per user type
- **Invite-only registration**: Secure user registration with invite codes
- **Input validation**: Prevents malicious data entry
- **Session isolation**: Users can only access their own data
- **Admin oversight**: Controlled access to system functions
- **SQLite database security**: Local database with proper user isolation
- **Account deletion workflow**: Secure process for account removal

## 🧪 Testing

The application includes a comprehensive test suite with pytest:

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_auth.py          # Authentication tests
pytest tests/test_admin.py         # Admin functionality tests  
pytest tests/test_recording.py     # Recording feature tests
pytest tests/test_sessions.py      # Session management tests
pytest tests/test_student_security.py  # Security tests
```

### Test Coverage
- **Authentication**: User login, registration, and role management
- **Admin Functions**: Admin panel features and user management
- **Recording System**: CSV processing and data recording
- **Session Management**: Session creation, switching, and deletion
- **Security**: Role-based access control and data isolation

## 🚀 Deployment

### Local Development
```bash
# Backend
python src/main.py

# Frontend (development)
cd frontend && npm run dev
```

### Production Deployment
- Built for deployment on any Python hosting service
- Static files served by Flask
- SQLite database for persistent data storage
- Scalable architecture for educational environments
- Docker-ready configuration available

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support and questions, please create an issue in this repository.

---

## 🆕 Recent Updates

### Version 2.0 Features
- **Database Integration**: Migrated from in-memory to persistent SQLite database
- **Enhanced Admin Panel**: Improved user management with persistent storage  
- **Invite System**: Secure user registration with invite codes
- **Account Management**: User deletion requests and admin approval workflow
- **Auto-Session Features**: Streamlined session management for administrators
- **Modern UI Components**: Updated to React 19 and Tailwind CSS v4
- **Component Library**: Comprehensive Radix UI component integration

### Latest Improvements (September 2024)
- Fixed admin panel button visibility and functionality
- Enhanced session deletion handling with proper admin alerts
- Improved auto-session joining for better user experience
- Streamlined header navigation and removed redundant elements
- Better error handling and user feedback systems

---

**Golden Plate Recorder** - Professional student attendance tracking made simple. 🎓✨

