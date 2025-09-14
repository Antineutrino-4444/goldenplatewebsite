# 🏆 Golden Plate Recorder

A comprehensive student attendance tracking system with barcode scanner support, built with Flask (Python) backend and React frontend.

## 🌟 Features

### 🔐 Authentication & User Management
- **Multi-role system**: Super Admin, Admin, and User roles
- **User registration**: Self-service account creation
- **Session-based authentication**: Secure login/logout
- **Role-based access control**: Different permissions per role

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
- **User management**: View all users and their roles
- **System monitoring**: Track all sessions across users
- **Role badges**: Visual distinction for different user types
- **System analytics**: Usage statistics and monitoring

## 🚀 Live Demo

**Website**: [https://g8h3ilc38pe1.manus.space](https://g8h3ilc38pe1.manus.space)

The application includes multiple user roles with different access levels:
- **Super Administrator**: Complete system control and user management
- **Administrator**: Admin panel access and session oversight  
- **Regular Users**: Standard attendance tracking features

Create your own account using the signup feature, or contact your system administrator for access credentials.

## 🛠️ Technology Stack

### Backend (Flask)
- **Python 3.11+**
- **Flask**: Web framework
- **Session-based authentication**
- **CSV processing**: File upload and data parsing
- **RESTful API**: All operations via API endpoints

### Frontend (React)
- **React 18+**: Modern hooks-based architecture
- **Vite**: Build tool and development server
- **Tailwind CSS**: Utility-first CSS framework
- **Responsive design**: Mobile-first approach
- **Real-time updates**: Live data synchronization

## 📦 Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm

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
- `SECRET_KEY`: Flask secret key for sessions (auto-generated if not set)

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
- **User Management**: View and monitor all users
- **Session Oversight**: Access all sessions across the system
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

- **Session-based authentication**: Secure login system
- **Role-based access control**: Different permissions per user type
- **Input validation**: Prevents malicious data entry
- **Session isolation**: Users can only access their own data
- **Admin oversight**: Controlled access to system functions

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
- No database required - uses in-memory storage
- Scalable architecture for educational environments

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support and questions, please create an issue in this repository.

---

**Golden Plate Recorder** - Professional student attendance tracking made simple. 🎓✨

