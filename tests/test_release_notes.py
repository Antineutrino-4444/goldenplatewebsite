from src.services import release_notes

URL = '/api/release-notes'


def test_release_notes_remember_account_and_order_versions(client, login, tmp_path, monkeypatch):
    notes = tmp_path / 'RELEASE_NOTES.md'
    notes.write_text('## 1.2.0.0\n\n- Earlier\n', encoding='utf-8')
    monkeypatch.setattr(release_notes, 'RELEASE_NOTES_PATH', notes)

    assert client.get(URL).status_code == 401
    assert client.get(f'{URL}?view=history').json['entries'] == [{'version': '1.2.0.0', 'markdown': '- Earlier'}]
    assert client.post(f'{URL}?view=history', json={'version': '1.2.0.0'}).status_code == 401
    assert login().status_code == 200
    assert client.get(URL).json['entries'] == [{'version': '1.2.0.0', 'markdown': '- Earlier'}]
    assert client.post(URL, json={'version': '99.0.0.0'}).status_code == 400
    assert client.post(URL, json={'version': '1.2.0.0'}).status_code == 204
    assert client.get(URL).json['entries'] == []

    notes.write_text(
        '## 1.10.0.0\n\n- Newest\n\n## 1.2.0.0\n\n- Earlier\n\n## 1.9.0.0\n\n- Next\n',
        encoding='utf-8',
    )
    client.post('/api/auth/logout')
    assert login().status_code == 200
    unread = ['1.10.0.0', '1.9.0.0']
    assert [entry['version'] for entry in client.get(f'{URL}?view=history').json['entries']] == [
        *unread, '1.2.0.0',
    ]
    assert [entry['version'] for entry in client.get(URL).json['entries']] == unread
    assert client.post(URL, json={'version': '1.10.0.0'}).status_code == 204
    assert client.post(URL, json={'version': '1.9.0.0'}).status_code == 204
    assert client.get(URL).json['entries'] == []
