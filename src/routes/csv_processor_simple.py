from flask import Blueprint, jsonify, request, session, send_file
import csv
import os
import uuid
import json
from datetime import datetime
import tempfile
import io

csv_bp = Blueprint('csv_processor', __name__)

# In-memory storage for session data (in production, use Redis or database)
session_data = {}

@csv_bp.route('/session/create', methods=['POST'])
def create_session():
    """Create a new session for CSV processing"""
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    session_data[session_id] = {
        'created_at': datetime.now().isoformat(),
        'csv_data': None,
        'processed_records': [],
        'current_category': 'category1',
        'scan_history': [],
        'export_data': []
    }
    return jsonify({
        'session_id': session_id,
        'status': 'created',
        'message': 'Session created successfully'
    }), 201

@csv_bp.route('/csv/upload', methods=['POST'])
def upload_csv():
    """Upload and process CSV file"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Read CSV file using built-in csv module
        file_content = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(file_content))
        
        # Convert to list of dictionaries
        csv_data = list(csv_reader)
        columns = csv_reader.fieldnames if csv_reader.fieldnames else []
        
        # Store in session
        session_id = session['session_id']
        session_data[session_id]['csv_data'] = csv_data
        session_data[session_id]['columns'] = columns
        
        return jsonify({
            'status': 'success',
            'message': 'CSV uploaded and processed successfully',
            'rows_count': len(csv_data),
            'columns': columns,
            'sample_data': csv_data[:5] if len(csv_data) > 5 else csv_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 500

@csv_bp.route('/csv/data', methods=['GET'])
def get_csv_data():
    """Get processed CSV data"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    data = session_data[session_id]
    return jsonify({
        'csv_data': data['csv_data'],
        'columns': data.get('columns', []),
        'current_category': data['current_category'],
        'processed_records': data['processed_records']
    }), 200

@csv_bp.route('/input/scan', methods=['POST'])
def process_scan():
    """Process barcode scanner input"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    data = request.json
    if not data or 'barcode' not in data:
        return jsonify({'error': 'Barcode data required'}), 400
    
    barcode = data['barcode'].strip()
    session_id = session['session_id']
    
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    # Add to scan history
    scan_record = {
        'barcode': barcode,
        'timestamp': datetime.now().isoformat(),
        'category': session_data[session_id]['current_category']
    }
    session_data[session_id]['scan_history'].append(scan_record)
    
    return jsonify({
        'status': 'success',
        'barcode': barcode,
        'timestamp': scan_record['timestamp']
    }), 200

@csv_bp.route('/data/lookup/<barcode>', methods=['GET'])
def lookup_data(barcode):
    """Lookup data by barcode in CSV"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    csv_data = session_data[session_id]['csv_data']
    if not csv_data:
        return jsonify({'error': 'No CSV data loaded'}), 400
    
    # Search for barcode in CSV data
    matching_records = []
    for record in csv_data:
        # Check all columns for the barcode
        for key, value in record.items():
            if str(value).strip() == barcode.strip():
                matching_records.append(record)
                break
    
    if matching_records:
        # Store the lookup result
        lookup_result = {
            'barcode': barcode,
            'matches': matching_records,
            'timestamp': datetime.now().isoformat(),
            'category': session_data[session_id]['current_category']
        }
        session_data[session_id]['processed_records'].append(lookup_result)
        
        return jsonify({
            'status': 'found',
            'barcode': barcode,
            'data': matching_records,
            'count': len(matching_records)
        }), 200
    else:
        return jsonify({
            'status': 'not_found',
            'barcode': barcode,
            'message': 'No matching records found'
        }), 404

@csv_bp.route('/category/switch', methods=['POST'])
def switch_category():
    """Switch between categories"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    data = request.json
    if not data or 'category' not in data:
        return jsonify({'error': 'Category required'}), 400
    
    category = data['category']
    valid_categories = ['category1', 'category2', 'category3']
    
    if category not in valid_categories:
        return jsonify({'error': f'Invalid category. Must be one of: {valid_categories}'}), 400
    
    session_id = session['session_id']
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data[session_id]['current_category'] = category
    
    return jsonify({
        'status': 'success',
        'current_category': category,
        'message': f'Switched to {category}'
    }), 200

@csv_bp.route('/export/csv', methods=['GET'])
def export_csv():
    """Export processed data as CSV"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    data = session_data[session_id]
    
    # Prepare export data
    export_records = []
    for record in data['processed_records']:
        for match in record['matches']:
            export_record = {
                'barcode': record['barcode'],
                'timestamp': record['timestamp'],
                'category': record['category'],
                **match  # Include all CSV columns
            }
            export_records.append(export_record)
    
    if not export_records:
        return jsonify({'error': 'No data to export'}), 400
    
    # Create CSV content using built-in csv module
    output = io.StringIO()
    if export_records:
        fieldnames = export_records[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_records)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    temp_file.write(output.getvalue())
    temp_file.close()
    
    return send_file(
        temp_file.name,
        as_attachment=True,
        download_name=f'processed_data_{session_id[:8]}.csv',
        mimetype='text/csv'
    )

@csv_bp.route('/session/status', methods=['GET'])
def session_status():
    """Get current session status"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'}), 400
    
    session_id = session['session_id']
    if session_id not in session_data:
        return jsonify({'error': 'Session not found'}), 404
    
    data = session_data[session_id]
    return jsonify({
        'session_id': session_id,
        'created_at': data['created_at'],
        'current_category': data['current_category'],
        'has_csv_data': data['csv_data'] is not None,
        'csv_rows': len(data['csv_data']) if data['csv_data'] else 0,
        'processed_records_count': len(data['processed_records']),
        'scan_history_count': len(data['scan_history'])
    }), 200

