from flask import Flask, send_file
import breakout_analysis
import os
import traceback

app = Flask(__name__)

@app.route('/')
def run_script():
    try:
        output_path = breakout_analysis.run()
        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True)
        else:
            return "❌ File not found: " + output_path, 500
    except Exception as e:
        return f"❌ Error:\n{traceback.format_exc()}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)