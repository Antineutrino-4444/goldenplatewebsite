def test_direct_school_resource_links(client, monkeypatch, tmp_path):
    monkeypatch.setattr(client.application, 'static_folder', str(tmp_path))
    (tmp_path / 'index.html').write_text('<main>Golden Plate</main>')
    resources = tmp_path / 'resources'
    resources.mkdir()
    (resources / 'assembly.pdf').write_bytes(b'%PDF-1.7')

    for path in ('/resources', '/resources/', '/export', '/export/', '/export?format=pdf&school=school-1', '/getting-started', '/website-guide'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == 'text/html'
        assert response.data == b'<main>Golden Plate</main>'

    download = client.get('/resources/assembly.pdf')
    assert download.status_code == 200
    assert download.mimetype == 'application/pdf'
    assert download.data == b'%PDF-1.7'
    assert client.get('/resources/missing.pdf').status_code == 404


def test_policy_links_open_static_documents(client, monkeypatch, tmp_path):
    monkeypatch.setattr(client.application, 'static_folder', str(tmp_path))
    (tmp_path / 'index.html').write_text('<main>Golden Plate</main>')
    for page in ('privacy', 'terms'):
        content = f'<h1>{page}</h1>'
        (tmp_path / f'{page}.html').write_text(content)
        for url in (f'/{page}', f'/{page}/', f'/{page}?source=google', f'/{page}.html'):
            response = client.get(url)
            assert response.status_code == 200
            assert response.mimetype == 'text/html'
            assert response.get_data(as_text=True) == content
