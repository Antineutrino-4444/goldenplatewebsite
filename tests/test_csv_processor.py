import io


def test_csv_upload_and_lookup(client, sample_session):
    csv_content = 'barcode,name\n123,Apple\n456,Banana\n'
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'test.csv')
    }
    response = client.post('/api/csv/csv/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 200

    response = client.get('/api/csv/data/lookup/123')
    assert response.status_code == 200
    result = response.get_json()
    assert result['status'] == 'found'
    assert result['data'][0]['barcode'] == '123' or '123' in str(result['data'][0])
