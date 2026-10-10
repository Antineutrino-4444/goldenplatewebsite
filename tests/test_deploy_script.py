from pathlib import Path


def test_deploy_script_matches_vite_output_path():
    project_root = Path(__file__).resolve().parent.parent
    deploy_script = (project_root / 'deploy.bat').read_text(encoding='utf-8')
    vite_config = (project_root / 'frontend' / 'vite.config.js').read_text(encoding='utf-8')

    assert "outDir: path.resolve(__dirname, '../src/static')" in vite_config
    assert 'frontend\\dist\\*' not in deploy_script
    assert 'call npm install --legacy-peer-deps' in deploy_script


def test_both_deployment_scripts_start_application_directly():
    root = Path(__file__).resolve().parent.parent
    assert 'python src\\main.py' in (root / 'deploy.bat').read_text()
    assert 'python src/main.py' in (root / 'deploy_local.sh').read_text()
