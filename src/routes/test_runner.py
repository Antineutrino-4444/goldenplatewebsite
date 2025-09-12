from flask import Blueprint, jsonify
import subprocess
import time


test_runner_bp = Blueprint('test_runner', __name__)

@test_runner_bp.route('/test/run', methods=['POST'])
def run_tests():
    start = time.time()
    result = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
    duration = time.time() - start
    stdout = result.stdout.strip().splitlines()[-20:]
    stderr = result.stderr.strip().splitlines()[-20:]
    return jsonify({
        "exit_code": result.returncode,
        "duration": duration,
        "stdout": "\n".join(stdout),
        "stderr": "\n".join(stderr)
    })
