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
cp .env.example .env
pip install -r requirements.txt

cd frontend
npm run build
cd ..

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

## Passwords and Environment Mode
The app has a built-in development super admin account for local setup:
- Username: `greenguys`
- Password: `begreendogood`

This default login is only meant for development. Environment mode controls whether it works:
- `APP_ENV=development` enables the built-in development login and shows a warning banner in the site.
- `APP_ENV=production` disables the built-in development login. Set this on the live server.

Before switching a live site to production mode, make sure a real admin account exists with a known strong password. To change an existing account username or password, run:
```bash
venv/bin/python scripts/change_user_credentials.py
```

The `SECRET_KEY` value is separate from user passwords. It secures Flask session cookies and should be a long random string in production. Keep it stable after deployment; changing it logs users out but does not change database passwords.

## License
This project is released under the MIT License.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Support
For questions or feedback, please open an issue in this repository.
