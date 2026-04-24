from pathlib import Path


def test_deploy_script_matches_vite_output_path():
    project_root = Path(__file__).resolve().parent.parent
    deploy_script = (project_root / 'deploy.bat').read_text(encoding='utf-8')
    vite_config = (project_root / 'frontend' / 'vite.config.js').read_text(encoding='utf-8')

    assert "outDir: path.resolve(__dirname, '../src/static')" in vite_config
    assert 'frontend\\dist\\*' not in deploy_script
    assert 'call npm install --legacy-peer-deps' in deploy_script
