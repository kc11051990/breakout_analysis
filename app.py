from flask import Flask, send_file
import breakout_analysis
import os

app = Flask(__name__)

@app.route('/')
def run_script():
    try:
        output_path = breakout_analysis.run()
        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True)
        else:
            return "❌ Error: File not found", 500
    except Exception as e:
        return f"❌ Error running script: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
