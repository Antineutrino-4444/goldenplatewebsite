# 🏆 Golden Plate Recorder - Independent Deployment

A comprehensive student attendance tracking system with barcode scanner support, built with Flask (Python) backend and React frontend.

**✅ COMPLETELY INDEPENDENT** - No external dependencies or platform requirements.

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

## 🛠️ Technology Stack

### Backend (Flask)
- **Python 3.11+**
- **Flask**: Web framework
- **SQLAlchemy**: Database ORM with SQLite/PostgreSQL support
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
- pnpm (recommended) or npm

### Quick Start (Local Development)

```bash
# Clone the repository
git clone https://github.com/Antineutrino-4444/goldenplatewebsite.git
cd goldenplatewebsite

# Backend setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd frontend
pnpm install  # or npm install
pnpm run build  # or npm run build
cd ..

# Copy built frontend to Flask static directory
mkdir -p src/static
cp -r frontend/dist/* src/static/

# Run the application
python src/main.py
```

Open http://localhost:5000 in your browser.

### Production Deployment

#### Option 1: Traditional Server (Ubuntu/CentOS)

```bash
# Install system dependencies
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm nginx

# Clone and setup
git clone https://github.com/Antineutrino-4444/goldenplatewebsite.git
cd goldenplatewebsite

# Backend setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt gunicorn

# Frontend setup
cd frontend
npm install
npm run build
cd ..
cp -r frontend/dist/* src/static/

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

#### Option 2: Docker Deployment

```dockerfile
# Dockerfile
FROM node:18 AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

# Copy backend code
COPY src/ ./src/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist ./src/static

# Expose port
EXPOSE 5000

# Run application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "src.main:app"]
```

```bash
# Build and run
docker build -t golden-plate-recorder .
docker run -p 5000:5000 -v $(pwd)/data:/app/data golden-plate-recorder
```

#### Option 3: Cloud Deployment (Heroku)

```bash
# Install Heroku CLI and login
heroku login

# Create app
heroku create your-app-name

# Add buildpacks
heroku buildpacks:add heroku/nodejs
heroku buildpacks:add heroku/python

# Deploy
git push heroku main
```

#### Option 4: VPS/Cloud Server (DigitalOcean, AWS, etc.)

```bash
# SSH into your server
ssh user@your-server-ip

# Follow "Traditional Server" setup above
# Configure nginx as reverse proxy
sudo nano /etc/nginx/sites-available/golden-plate-recorder

# Nginx configuration
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site and restart nginx
sudo ln -s /etc/nginx/sites-available/golden-plate-recorder /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database Configuration (choose one)
# SQLite (default)
DATABASE_URL=sqlite:///data/app.db

# PostgreSQL
# DATABASE_URL=postgresql://user:password@localhost/golden_plate_recorder

# MySQL
# DATABASE_URL=mysql://user:password@localhost/golden_plate_recorder

# Storage Configuration
STORAGE_TYPE=database  # or 'file' for file-based storage
DATA_DIRECTORY=./data

# Security
SESSION_TIMEOUT=3600
MAX_UPLOAD_SIZE=10485760  # 10MB
```

### Database Setup

#### SQLite (Default - No setup required)
```bash
# Database file will be created automatically
mkdir -p data
```

#### PostgreSQL
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE golden_plate_recorder;
CREATE USER gpr_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE golden_plate_recorder TO gpr_user;
\q

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://gpr_user:your_password@localhost/golden_plate_recorder
```

#### MySQL
```bash
# Install MySQL
sudo apt install mysql-server

# Create database and user
sudo mysql
CREATE DATABASE golden_plate_recorder;
CREATE USER 'gpr_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON golden_plate_recorder.* TO 'gpr_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;

# Update DATABASE_URL in .env
DATABASE_URL=mysql://gpr_user:your_password@localhost/golden_plate_recorder
```

## 📱 Usage

### Default Admin Account
On first run, a super admin account is created:
- **Username**: `admin`
- **Password**: `admin123`

**⚠️ IMPORTANT**: Change this password immediately after first login!

### Basic Workflow
1. **Login** with admin credentials
2. **Create user accounts** for your team
3. **Upload CSV** file with student data
4. **Select category** (CLEAN/DIRTY/RED)
5. **Scan or enter** Student ID or Name
6. **View scan history** in real-time
7. **Export results** when finished

### CSV Format
```csv
Last,First,Student ID
Smith,John,20230105
Johnson,Sarah,20230106
Williams,David,20230107
```

### Barcode Scanner Setup
- Use any HID-compatible barcode scanner
- Configure scanner to send data followed by Enter key
- No additional software required - works like keyboard input

## 🔒 Security Features

- **Secure authentication**: Session-based with configurable timeout
- **Role-based access**: Different permissions per user type
- **Input validation**: Prevents malicious data entry
- **Session isolation**: Users can only access their own data
- **Admin oversight**: Controlled access to system functions
- **Password hashing**: Secure password storage
- **CSRF protection**: Built-in Flask security features

## 🚀 Performance & Scaling

### Single Server (Up to 100 concurrent users)
- Default configuration with SQLite
- Suitable for small to medium schools

### Multi-Server (100+ concurrent users)
- Use PostgreSQL or MySQL
- Deploy multiple app instances behind load balancer
- Shared database for data consistency

### High Availability
- Database replication
- Multiple app servers
- Redis for session storage
- CDN for static assets

## 🔧 Maintenance

### Backup
```bash
# SQLite backup
cp data/app.db data/app_backup_$(date +%Y%m%d).db

# PostgreSQL backup
pg_dump golden_plate_recorder > backup_$(date +%Y%m%d).sql

# Full application backup
tar -czf golden_plate_backup_$(date +%Y%m%d).tar.gz .
```

### Updates
```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
cp -r frontend/dist/* src/static/

# Restart application
sudo systemctl restart golden-plate-recorder
```

### Monitoring
- Check application logs: `tail -f logs/app.log`
- Monitor database size: `du -sh data/`
- Check system resources: `htop`

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

For support and questions, please create an issue in this repository.

---

**Golden Plate Recorder** - Professional student attendance tracking made simple. 🎓✨

**✅ 100% Independent - No external platform dependencies**

