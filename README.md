# Golden Plate Recorder

## Overview
Golden Plate Recorder is a web application for tracking student attendance and category-based events. The system combines a Flask backend with a modern React frontend and supports barcode scanners, CSV roster uploads, and role-based administration.

## Features
- Multi-role authentication system (Super Admin, Admin, User, Guest)
- Invite-only registration and account deletion workflow
- Session creation and switching with default names
- CSV roster upload with ID and name matching
- CLEAN, DIRTY, and RED category recording with barcode scanner support
- Real-time history display and CSV export
- Administrative panel for user, invite code, and session management

## Architecture
- **Backend:** Flask 3 with SQLAlchemy and SQLite located in `src/`
- **Frontend:** React 19 with Vite and Tailwind CSS located in `frontend/`
- **Tests:** Pytest suite in `tests/`

## Prerequisites
- Python 3.11+
- Node.js 18+
- npm or pnpm

## Installation
```bash
# Clone repository and enter directory
# python -m venv venv
# source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cd frontend
npm install --legacy-peer-deps
npm run build
cd ..

# Copy compiled frontend to Flask static directory
cp -r frontend/dist/* src/static/

# Start the application
python src/main.py
```

## Development
```bash
# Run backend
python src/main.py

# Run frontend in development mode
cd frontend
npm run dev
```

## Testing
```bash
pytest
```

## License
This project is released under the MIT License.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Support
For questions or feedback, please open an issue in this repository.
