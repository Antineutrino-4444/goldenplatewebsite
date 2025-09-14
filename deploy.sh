#!/bin/bash

# Golden Plate Recorder Deployment Script
# This script helps deploy the application on any Linux server

set -e

echo "🏆 Golden Plate Recorder Deployment Script"
echo "=========================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root for security reasons"
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Docker
install_docker() {
    echo "📦 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "✅ Docker installed successfully"
    echo "⚠️  Please log out and log back in for Docker permissions to take effect"
}

# Function to install Docker Compose
install_docker_compose() {
    echo "📦 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed successfully"
}

# Function to setup application
setup_application() {
    echo "🔧 Setting up Golden Plate Recorder..."
    
    # Create data directory
    mkdir -p data
    chmod 755 data
    
    # Generate secret key if not exists
    if [ ! -f .env ]; then
        echo "🔑 Creating environment configuration..."
        SECRET_KEY=$(openssl rand -hex 32)
        cat > .env << EOF
# Golden Plate Recorder Configuration
FLASK_ENV=production
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=sqlite:///data/golden_plate_recorder.db

# For PostgreSQL (uncomment and configure if needed)
# DATABASE_URL=postgresql://gpr_user:secure_password_change_this@db:5432/golden_plate_recorder

# Security Settings
SESSION_TIMEOUT=3600
MAX_UPLOAD_SIZE=10485760

# Application Settings
STORAGE_TYPE=database
DATA_DIRECTORY=./data
EOF
        echo "✅ Environment configuration created"
    fi
    
    # Build and start application
    echo "🚀 Building and starting application..."
    docker-compose up -d --build
    
    echo "✅ Application started successfully!"
    echo ""
    echo "🌐 Access your application at: http://localhost:5000"
    echo "👤 Default super admin credentials:"
    echo "   Username: antineutrino"
    echo "   Password: b-decay"
    echo ""
    echo "⚠️  IMPORTANT: Change the default password after first login!"
}

# Function to show status
show_status() {
    echo "📊 Application Status:"
    docker-compose ps
    echo ""
    echo "📋 Logs (last 20 lines):"
    docker-compose logs --tail=20 app
}

# Function to stop application
stop_application() {
    echo "🛑 Stopping Golden Plate Recorder..."
    docker-compose down
    echo "✅ Application stopped"
}

# Function to update application
update_application() {
    echo "🔄 Updating Golden Plate Recorder..."
    git pull origin main
    docker-compose down
    docker-compose up -d --build
    echo "✅ Application updated successfully!"
}

# Function to backup data
backup_data() {
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    echo "💾 Creating backup..."
    cp -r data "$BACKUP_DIR/"
    tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"
    rm -rf "$BACKUP_DIR"
    
    echo "✅ Backup created: ${BACKUP_DIR}.tar.gz"
}

# Function to restore data
restore_data() {
    if [ -z "$1" ]; then
        echo "❌ Please specify backup file: ./deploy.sh restore backup_file.tar.gz"
        exit 1
    fi
    
    if [ ! -f "$1" ]; then
        echo "❌ Backup file not found: $1"
        exit 1
    fi
    
    echo "🔄 Restoring from backup: $1"
    docker-compose down
    
    # Backup current data
    if [ -d "data" ]; then
        mv data "data_backup_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Extract backup
    tar -xzf "$1"
    BACKUP_DIR=$(basename "$1" .tar.gz)
    mv "$BACKUP_DIR/data" ./
    rm -rf "$BACKUP_DIR"
    
    docker-compose up -d
    echo "✅ Data restored successfully!"
}

# Main menu
case "${1:-menu}" in
    "install")
        echo "🔧 Installing dependencies..."
        
        # Check and install Docker
        if ! command_exists docker; then
            install_docker
        else
            echo "✅ Docker already installed"
        fi
        
        # Check and install Docker Compose
        if ! command_exists docker-compose; then
            install_docker_compose
        else
            echo "✅ Docker Compose already installed"
        fi
        
        setup_application
        ;;
    
    "start")
        echo "🚀 Starting Golden Plate Recorder..."
        docker-compose up -d
        echo "✅ Application started!"
        ;;
    
    "stop")
        stop_application
        ;;
    
    "restart")
        echo "🔄 Restarting Golden Plate Recorder..."
        docker-compose restart
        echo "✅ Application restarted!"
        ;;
    
    "status")
        show_status
        ;;
    
    "logs")
        echo "📋 Application Logs:"
        docker-compose logs -f app
        ;;
    
    "update")
        update_application
        ;;
    
    "backup")
        backup_data
        ;;
    
    "restore")
        restore_data "$2"
        ;;
    
    "uninstall")
        echo "🗑️  Uninstalling Golden Plate Recorder..."
        docker-compose down -v
        docker rmi $(docker images -q goldenplatewebsite_app) 2>/dev/null || true
        echo "✅ Application uninstalled (data preserved in ./data directory)"
        ;;
    
    "menu"|*)
        echo ""
        echo "Available commands:"
        echo "  ./deploy.sh install    - Install dependencies and setup application"
        echo "  ./deploy.sh start      - Start the application"
        echo "  ./deploy.sh stop       - Stop the application"
        echo "  ./deploy.sh restart    - Restart the application"
        echo "  ./deploy.sh status     - Show application status"
        echo "  ./deploy.sh logs       - Show application logs"
        echo "  ./deploy.sh update     - Update application to latest version"
        echo "  ./deploy.sh backup     - Create data backup"
        echo "  ./deploy.sh restore    - Restore from backup"
        echo "  ./deploy.sh uninstall  - Remove application (keeps data)"
        echo ""
        echo "Quick start: ./deploy.sh install"
        ;;
esac

