# Backend Documentation

## Overview

The Golden Plate Recorder backend is built using **Flask 3** with **SQLAlchemy** and provides a RESTful API for tracking student attendance and managing a weighted lottery system for clean/dirty plate recording. The backend uses JSON file-based persistent storage for sessions and user data.

## Architecture

### Technology Stack
- **Framework**: Flask 3.1.1
- **Database ORM**: SQLAlchemy 2.0.41 with Flask-SQLAlchemy 3.1.1
- **Database**: SQLite (for user model) + JSON file storage (for sessions)
- **CORS**: Flask-CORS 6.0.0
- **Python Version**: 3.11+

### Project Structure
```
src/
├── main.py                    # Flask application entry point
├── models/
│   └── user.py               # SQLAlchemy User model
├── routes/
│   ├── user.py               # User CRUD API endpoints
│   ├── golden_plate_recorder.py  # Main application logic
│   ├── csv_processor.py      # CSV processing utilities
│   └── csv_processor_simple.py   # Simplified CSV processing
├── database/
│   └── app.db               # SQLite database
└── static/                   # Frontend build output
```

## Application Setup

### main.py
The entry point configures Flask, registers blueprints, and sets up database connections:

```python
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database/app.db'
```

**Key Components:**
1. **CORS Configuration**: Enables cross-origin requests with credentials
2. **Blueprint Registration**: 
   - `/api` routes for user management (`user_bp`)
   - `/api` routes for recorder functionality (`recorder_bp`)
3. **Static File Serving**: Serves React frontend from `/static`
4. **Database Initialization**: Creates tables on startup

## Data Storage

The application uses a hybrid storage approach:

### SQLite Database
- **Purpose**: User model storage (legacy, minimal usage)
- **Location**: `src/database/app.db`
- **Models**: User model with id, username, email, role

### JSON File Storage
The primary storage mechanism uses JSON files in the `persistent_data/` directory:

1. **sessions.json**: Stores all session data including:
   - Session metadata (name, owner, creation time)
   - Clean, dirty, and red plate records
   - Faculty clean records
   - Scan history
   - Draw information (winners, tickets)
   
2. **users.json**: Authentication and user data:
   - Username/password (plain text - security note!)
   - User role (superadmin, admin, user, guest)
   - Account status
   - Display name

3. **invite_codes.json**: One-time invite codes for registration:
   - Code UUID
   - Issuer
   - Usage status
   - Assigned role

4. **delete_requests.json**: Pending session deletion requests:
   - Request metadata
   - Requester information
   - Session statistics

5. **global_csv_data.json**: Student roster database:
   - Student records (Preferred, Last, Grade, Advisor, House, Clan, Student ID)
   - Upload metadata

6. **teacher_list.json**: Faculty roster:
   - Teacher names
   - Upload metadata

### File Storage Functions
```python
def save_data_to_file(file_path, data):
    """Atomic write with temp file and rename"""
    
def load_data_from_file(file_path, default_data):
    """Load with fallback to defaults"""
```

## Authentication System

### User Roles
1. **Guest**: View-only access to public sessions
2. **User**: Create/manage own sessions, record plates
3. **Admin**: Manage users, sessions, upload CSVs, conduct draws
4. **Super Admin**: Full system access including role changes and draw overrides

### Authentication Flow

#### Login
```
POST /api/auth/login
Body: { username, password }
Returns: { status, user: { username, name, role } }
```
- Validates credentials against `users.json`
- Stores `user_id` in Flask session
- Checks account status (active/disabled)

#### Guest Access
```
POST /api/auth/guest
Returns: { status, user: { username: 'guest', role: 'guest' } }
```
- Sets `guest_access` flag in session
- No persistent account required

#### Signup (Invite-Only)
```
POST /api/auth/signup
Body: { username, password, name, invite_code }
Returns: { status, message }
```
- Validates invite code from `invite_codes.json`
- Creates user account with role from invite code
- Marks invite code as used

#### Authorization Helpers
```python
def require_auth(): 
    """Check if user is authenticated"""
    
def require_admin():
    """Check if user is admin or super admin"""
    
def require_superadmin():
    """Check if user is super admin"""
```

## Session Management

### Session Data Structure
```python
{
    'session_name': str,
    'owner': str,  # username
    'created_at': ISO datetime,
    'is_public': bool,
    'clean_records': [StudentRecord],
    'dirty_count': int,
    'red_records': [StudentRecord],
    'faculty_clean_records': [FacultyRecord],
    'scan_history': [Record],
    'is_discarded': bool,
    'discard_metadata': {},
    'draw_info': DrawInfo
}
```

### StudentRecord Structure
```python
{
    'preferred_name': str,
    'first_name': str,  # alias for preferred_name
    'last_name': str,
    'grade': str,
    'advisor': str,
    'house': str,
    'clan': str,
    'student_id': str,
    'student_key': str,  # normalized key for matching
    'category': str,  # 'clean' or 'red'
    'timestamp': ISO datetime,
    'recorded_by': str,
    'is_manual_entry': bool
}
```

### Key Operations

#### Create Session
```
POST /api/session/create
Body: { session_name?, is_public? }
```
- Generates UUID for session
- Auto-generates name: `Golden_Plate_{Month_Day_Year}` if not provided
- Sets current user as owner
- Initializes empty record arrays

#### List Sessions
```
GET /api/session/list
Returns: { sessions: [SessionSummary], has_global_csv: bool }
```
- Guests see only public sessions
- Returns statistics: clean_count, dirty_count, percentages
- Includes deletion request status

#### Switch Session
```
POST /api/session/switch/<session_id>
```
- Sets `session_id` in Flask session
- Validates access (public check for guests)

## Recording System

### Categories
1. **Clean**: Student returned clean plate
2. **Dirty**: Anonymous dirty plate (no student tracking)
3. **Red**: Student returned very dirty plate
4. **Faculty**: Faculty member with clean plate (separate tracking)

### Recording Flow

#### Record Student (Clean/Red)
```
POST /api/record/<category>
Body: { 
    input_value?,     # Name or ID
    student_id?, 
    student_key?,
    preferred_name?, 
    last_name? 
}
```

**Process:**
1. **Student Lookup**: Match against global CSV by:
   - Student ID (exact match)
   - Name (Preferred + Last, case-insensitive)
   - Student key (normalized identifier)

2. **Profile Building**: Extract/infer student details:
   - Grade, Advisor, House, Clan
   - Generate student_key for deduplication

3. **Duplicate Check**: Prevent re-recording same student in session:
   - Match by student_id (if available)
   - Match by student_key
   - Match by full profile

4. **Record Storage**: Add to appropriate category array and scan_history

5. **Manual Entry Flag**: Set if student not found in CSV

#### Record Dirty Plate
```
POST /api/record/dirty
```
- Increments `dirty_count` counter
- No student identity stored (privacy)
- Adds anonymous entry to scan_history

#### Record Faculty
```
POST /api/record/faculty
Body: { input_value: "First Last" }
```
- Parses name into preferred/last
- Stores in `faculty_clean_records`
- Duplicate check by name

### Student Lookup System

#### Student Key Generation
```python
def make_student_key(preferred_name, last_name, student_id):
    """Creates normalized lookup key"""
    if student_id:
        return f"id:{student_id.lower()}"
    return f"{preferred.lower()}|{last.lower()}"
```

#### Student Lookup Cache
```python
student_lookup = {}  # Dict[student_key, StudentProfile]

def update_student_lookup():
    """Builds lookup cache from global_csv_data"""
```
- Built when CSV uploaded
- Enables fast eligibility checks
- Used for profile enrichment

## CSV Upload System

### Student Roster Upload
```
POST /api/csv/upload
Content-Type: multipart/form-data
File: CSV with required columns
```

**Required Columns:**
- Student ID
- Last
- Preferred
- Grade
- Advisor
- House
- Clan

**Process:**
1. Validate file extension (.csv)
2. Parse CSV with DictReader
3. Validate required columns
4. Store in `global_csv_data.json`
5. Rebuild `student_lookup` cache
6. Save upload metadata (uploader, timestamp)

**Access Control:** Admin/Super Admin only

### Student Names API
```
GET /api/csv/student-names
Returns: { status, names: [StudentName] }
```
- Returns all students for autocomplete
- Includes display_name, preferred, last, student_id, key

### CSV Preview
```
GET /api/csv/preview?page=1&per_page=50
Returns: { status, data, pagination, metadata }
```
- Paginated student roster view
- Excludes Student ID from response (privacy)
- Shows upload metadata

### Teacher List Upload
```
POST /api/teachers/upload
Content-Type: multipart/form-data
File: CSV or TXT with teacher names
```
- One name per line
- Stores in `global_teacher_data.json`
- Used for faculty recording autocomplete

## Drawing/Lottery System

### Ticket System

The drawing system implements a weighted lottery based on plate history:

#### Ticket Rules
1. **Clean Plate**: +1 ticket
2. **Red Plate**: Reset to 0 tickets
3. **Absent (not in session)**: ÷2 tickets (if > 0)
4. **Draw Winner (finalized)**: Reset to 0 tickets
5. **Discarded Session**: Not counted in rollup

#### Ticket Rollup Calculation
```python
def compute_ticket_rollups():
    """Calculate running ticket totals across all sessions"""
```

**Algorithm:**
1. Sort sessions by creation date
2. Initialize current_tickets = {}
3. For each session (in order):
   - Mark students present in session
   - Add +1 ticket for clean records
   - Set 0 tickets for red records
   - Halve tickets for absent students
   - If winner finalized, reset winner to 0
4. Generate snapshot per session

#### Ticket Summary Response
```python
{
    'session_id': str,
    'session_name': str,
    'created_at': ISO datetime,
    'is_discarded': bool,
    'tickets_snapshot': Dict[student_key, float],
    'total_tickets': float,
    'candidates': [Candidate],
    'top_candidates': [Candidate],  # Top 3
    'eligible_count': int,
    'excluded_records': int,
    'generated_at': ISO datetime
}
```

#### Candidate Structure
```python
{
    'key': str,
    'tickets': float,
    'display_name': str,
    'preferred_name': str,
    'last_name': str,
    'grade': str,
    'advisor': str,
    'house': str,
    'clan': str,
    'student_id': str,
    'probability': float  # Percentage
}
```

### Draw Operations

#### Start Random Draw
```
POST /api/session/<session_id>/draw/start
Returns: { status, winner, draw_info, summary }
```

**Algorithm:**
1. Get ticket summary for session
2. Calculate cumulative distribution
3. Generate random number: `0 <= r < total_tickets`
4. Select winner using weighted random selection:
   ```python
   cumulative = 0
   target = random() * total_tickets
   for key, tickets in tickets_snapshot:
       cumulative += tickets
       if target <= cumulative:
           return key
   ```
5. Store winner in `draw_info` (not finalized)
6. Record in draw history

**Access Control:** Admin/Super Admin only

#### Finalize Draw
```
POST /api/session/<session_id>/draw/finalize
Returns: { status, finalized, draw_info, summary }
```
- Marks draw as finalized
- Triggers ticket reset for winner in future rollups
- Records finalization in history

**Access Control:** Admin/Super Admin only

#### Reset Draw
```
POST /api/session/<session_id>/draw/reset
Returns: { status, reset, draw_info, summary }
```
- Clears current winner
- Restores tickets
- Only Super Admin can reset finalized draws

#### Override Draw
```
POST /api/session/<session_id>/draw/override
Body: { student_key?, student_id?, input_value?, preferred_name?, last_name? }
Returns: { status, override, winner, draw_info, summary }
```
- Manually select winner (bypasses random selection)
- Auto-finalizes
- Must select student from CSV roster
- Records as override in history

**Access Control:** Super Admin only

#### Discard Session
```
POST /api/session/<session_id>/draw/discard
Body: { discarded: bool }
Returns: { status, discarded, message, draw_info, summary }
```
- Excludes session from ticket rollup calculations
- Preserves session data
- Can be reversed (restore)

**Access Control:** Super Admin only

### Draw Info Structure
```python
{
    'winner': WinnerData?,
    'winner_timestamp': ISO datetime?,
    'selected_by': str?,
    'method': str?,  # 'random'
    'finalized': bool,
    'finalized_at': ISO datetime?,
    'finalized_by': str?,
    'override': bool,
    'tickets_at_selection': float?,
    'probability_at_selection': float?,
    'eligible_pool_size': int?,
    'history': [HistoryEntry]
}
```

## API Endpoints

### Authentication
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | None | User login |
| `/api/auth/logout` | POST | None | User logout |
| `/api/auth/guest` | POST | None | Guest access |
| `/api/auth/signup` | POST | None | Register (invite-only) |
| `/api/auth/status` | GET | None | Check auth status |

### Session Management
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/session/create` | POST | User | Create new session |
| `/api/session/list` | GET | User/Guest | List sessions |
| `/api/session/switch/<id>` | POST | User/Guest | Switch active session |
| `/api/session/delete/<id>` | DELETE | User | Delete own session |
| `/api/session/status` | GET | User/Guest | Get current session stats |
| `/api/session/history` | GET | User/Guest | Get scan history |
| `/api/session/request-delete` | POST | User | Request deletion |

### Recording
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/record/clean` | POST | User | Record clean plate |
| `/api/record/dirty` | POST | User | Record dirty plate |
| `/api/record/red` | POST | User | Record red plate |
| `/api/record/faculty` | POST | User | Record faculty clean |

### CSV/Data Management
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/csv/upload` | POST | Admin | Upload student roster |
| `/api/csv/preview` | GET | Admin | Preview roster |
| `/api/csv/student-names` | GET | User | Get student list |
| `/api/teachers/upload` | POST | Admin | Upload teacher list |
| `/api/teachers/list` | GET | User | Get teacher names |
| `/api/teachers/preview` | GET | Admin | Preview teacher list |

### Export
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/export/csv` | GET | User | Export session CSV |
| `/api/export/csv/detailed` | GET | User | Export detailed CSV |

### Drawing System
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/session/<id>/draw/summary` | GET | User/Guest | Get draw summary |
| `/api/session/<id>/draw/start` | POST | Admin | Start random draw |
| `/api/session/<id>/draw/finalize` | POST | Admin | Finalize winner |
| `/api/session/<id>/draw/reset` | POST | Admin | Reset draw |
| `/api/session/<id>/draw/override` | POST | Super Admin | Override winner |
| `/api/session/<id>/draw/discard` | POST | Super Admin | Toggle discard |

### Admin
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/users` | GET | Admin | List all users |
| `/api/admin/invite` | POST | Admin | Generate invite code |
| `/api/admin/sessions` | GET | Admin | List all sessions |
| `/api/admin/sessions/<id>` | DELETE | Admin | Delete any session |
| `/api/admin/delete-requests` | GET | Admin | List delete requests |
| `/api/admin/delete-requests/<id>/approve` | POST | Admin | Approve deletion |
| `/api/admin/delete-requests/<id>/reject` | POST | Admin | Reject deletion |
| `/api/admin/overview` | GET | Admin | Get overview data |
| `/api/admin/manage-account-status` | POST | Admin | Enable/disable users |

### Super Admin
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/superadmin/change-role` | POST | Super Admin | Change user role |
| `/api/superadmin/delete-account` | POST | Super Admin | Delete user account |

### User CRUD (Legacy SQLAlchemy)
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/users` | GET | None | List users |
| `/api/users` | POST | None | Create user |
| `/api/users/<id>` | GET | None | Get user |
| `/api/users/<id>` | PUT | None | Update user |
| `/api/users/<id>` | DELETE | None | Delete user |

## Database Models

### User Model (SQLAlchemy)
```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')
```

**Note:** This model is legacy and not actively used by the main application. The `users.json` file-based storage is the primary user management system.

## Security Considerations

### Current Security Issues
1. **Plain Text Passwords**: Passwords stored in `users.json` without hashing
2. **Hardcoded Secret Key**: `SECRET_KEY` in source code
3. **No HTTPS Enforcement**: No SSL/TLS configuration
4. **Session Security**: Flask sessions vulnerable without secure configuration
5. **No Rate Limiting**: API endpoints unprotected from abuse
6. **CSV Injection**: No sanitization of CSV inputs

### Recommendations
1. Implement password hashing (bcrypt/argon2)
2. Move secrets to environment variables
3. Add HTTPS/TLS support
4. Configure secure session cookies
5. Implement rate limiting
6. Add input validation and sanitization
7. Implement CSRF protection
8. Add request logging and monitoring

## Data Flow Examples

### Recording a Clean Plate
```
1. User scans barcode or enters name
2. Frontend: POST /api/record/clean { input_value: "John Doe" }
3. Backend:
   a. Extract/normalize name
   b. Search global_csv_data for match
   c. Build student profile (enrich with CSV data)
   d. Check for duplicates in session
   e. Create record with category='clean'
   f. Append to clean_records and scan_history
   g. Save session_data
4. Return: { status, student details, is_manual_entry }
```

### Conducting a Draw
```
1. Admin: GET /api/session/<id>/draw/summary
   - Compute ticket rollups across all sessions
   - Return candidates with ticket counts

2. Admin: POST /api/session/<id>/draw/start
   - Get ticket snapshot
   - Weighted random selection
   - Store winner (not finalized)
   - Return winner details

3. Review winner, then:
   Admin: POST /api/session/<id>/draw/finalize
   - Mark as finalized
   - Winner tickets reset to 0 in future rollups
```

### Session Lifecycle
```
1. Create: POST /api/session/create
   - Generate UUID and name
   - Initialize empty records
   - Save to sessions.json

2. Record: Multiple POST /api/record/<category>
   - Add student records
   - Update counters
   - Append to history

3. Export: GET /api/export/csv
   - Format as CSV
   - Return as file download

4. Draw: Draw API sequence (if admin)
   - Calculate tickets
   - Select winner
   - Finalize

5. Delete: DELETE /api/session/delete/<id> or request/approve flow
   - Remove from sessions.json
   - Clear from Flask session if active
```

## Error Handling

### HTTP Status Codes
- `200`: Success
- `201`: Created (signup, invite code)
- `204`: No Content (delete)
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (not authenticated)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (session/user not found)
- `409`: Conflict (duplicate record)

### Error Response Format
```json
{
    "error": "Error message string"
}
```

### Common Error Scenarios
1. **No Active Session**: Recording without switching to session
2. **Duplicate Record**: Student already recorded in session
3. **Invalid Category**: Unknown category in record endpoint
4. **No CSV Data**: Recording without uploaded student roster
5. **Invalid Invite Code**: Signup with used/invalid code
6. **Permission Denied**: User action requires admin/superadmin role

## Performance Considerations

### Bottlenecks
1. **File I/O**: Every save operation writes to disk
2. **No Caching**: Ticket rollups computed on every request
3. **Large CSV**: Student lookup rebuilds entire dictionary
4. **Session Data Growth**: Scan history grows unbounded

### Optimization Opportunities
1. Implement in-memory caching for ticket rollups
2. Use Redis for session storage
3. Add database indexes for User model
4. Implement pagination for scan history
5. Archive old sessions to separate files
6. Use background tasks for CSV processing

## Configuration

### Environment Variables (Recommended)
```bash
SECRET_KEY=<random-secret-key>
DATABASE_URL=sqlite:///database/app.db
DATA_DIR=/path/to/persistent_data
FLASK_ENV=production
```

### Current Hardcoded Values
- Secret Key: `'asdf#FGSgvasgf$5$WGT'`
- Port: `5000`
- Host: `0.0.0.0`
- Debug: `True`

## Testing

### Test Files
- `tests/` - Pytest test suite
- `test_csv_access_control.py` - CSV access control tests

### Running Tests
```bash
pytest
```

## Development Notes

### Adding a New Endpoint
1. Add route to appropriate blueprint in `src/routes/`
2. Implement authorization checks
3. Parse request data with `request.get_json()`
4. Perform business logic
5. Update persistent storage with `save_*()` functions
6. Return JSON response with status

### Adding a New Role Permission
1. Update `require_*()` helper functions
2. Add permission checks to endpoints
3. Update frontend to show/hide UI elements
4. Document in API endpoint table

### Modifying Session Structure
1. Update `ensure_session_structure()` function
2. Add migration logic for existing sessions
3. Update serialization functions
4. Update API responses
5. Test with existing session data

## Deployment

### Production Checklist
- [ ] Replace hardcoded SECRET_KEY
- [ ] Disable Flask debug mode
- [ ] Implement password hashing
- [ ] Configure HTTPS/SSL
- [ ] Set up reverse proxy (nginx/Apache)
- [ ] Configure CORS for production domain
- [ ] Set up backup for persistent_data/
- [ ] Implement logging and monitoring
- [ ] Add rate limiting
- [ ] Review and fix security issues
- [ ] Use production WSGI server (gunicorn/uWSGI)

### Running in Production
```bash
# Using gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app

# Using uWSGI
uwsgi --http 0.0.0.0:5000 --module src.main:app --processes 4
```

## Troubleshooting

### Common Issues

**Issue: Session data not persisting**
- Check `persistent_data/` directory exists and is writable
- Verify `save_*()` functions are called after modifications
- Check for JSON serialization errors in logs

**Issue: User cannot login**
- Verify username exists in `users.json`
- Check account status is 'active'
- Verify password matches exactly (case-sensitive)

**Issue: CSV upload fails**
- Verify all required columns present
- Check CSV encoding (UTF-8)
- Ensure file size is reasonable
- Verify admin/superadmin role

**Issue: Draw calculation incorrect**
- Check session is not discarded
- Verify previous draws are finalized
- Ensure global CSV is uploaded
- Check ticket rollup logic in `compute_ticket_rollups()`

## Future Enhancements

### Suggested Improvements
1. **Real Database**: Migrate from JSON files to PostgreSQL/MySQL
2. **Password Security**: Implement proper password hashing
3. **WebSocket Support**: Real-time updates for scan history
4. **API Rate Limiting**: Protect against abuse
5. **Audit Log**: Track all admin actions
6. **Backup System**: Automated backups of persistent data
7. **Multi-tenancy**: Support for multiple schools/organizations
8. **Email Notifications**: For draw results, delete requests
9. **Mobile App**: Native iOS/Android apps
10. **Analytics Dashboard**: Statistics and insights

## Support and Maintenance

### Monitoring
- Check `persistent_data/` disk usage
- Monitor session count growth
- Review application logs for errors
- Track API response times

### Backup Strategy
```bash
# Backup persistent data
cp -r persistent_data/ backup/persistent_data_$(date +%Y%m%d)

# Backup database
sqlite3 src/database/app.db .dump > backup/app_$(date +%Y%m%d).sql
```

### Database Maintenance
```bash
# Check database integrity
sqlite3 src/database/app.db "PRAGMA integrity_check;"

# Compact database
sqlite3 src/database/app.db "VACUUM;"
```

## Contributing

When contributing to the backend:
1. Follow PEP 8 style guidelines
2. Add docstrings to functions
3. Write tests for new features
4. Update this documentation
5. Test with existing session data
6. Verify authorization checks
7. Test error cases

## License

MIT License - See LICENSE file for details
