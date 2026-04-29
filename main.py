import os
import time
import concurrent.futures
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
from dotenv import load_dotenv
import security
from llm import *
from llm import _get_client_ip
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.route("/query", methods=["POST"])
def query():
    print("➡️ REQUEST STARTED")

    try:
        user_query = request.form.get("query")
        print("STEP 1: got query")

        if not user_query:
            return jsonify({"error": "Missing query"}), 400

        client_ip = _get_client_ip(request)
        print("STEP 2: got IP")

        # SECURITY (NO REDIS VERSION)
        sec_result = security.analyze_query(user_query, client_ip)
        print("STEP 3: security done")

        # OPTIONAL: you could block here if needed
        if sec_result.decision == "BLOCK":
            return jsonify({"error": "Blocked"}), 403

        if sec_result.decision == "LIMIT":
            time.sleep(2)

        result = generate_website_answer(sec_result.sanitized_query)
        print("STEP 4: LLM done")

        return jsonify({
            "response": result,
            "risk": sec_result.score,
            "decision": sec_result.decision
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": "Server error"}), 500


@app.route("/")
def home():
    return render_template("index.html")

# --------------------------------------------------
# ADMIN (unchanged)
# --------------------------------------------------

@app.route("/admin")
def admin_page():
    try:
        files = client.file_search_stores.documents.list(
            parent=FILE_SEARCH_STORE_NAME
        )
        return render_template("admin.html", files=files)
    except Exception:
        return render_template("admin.html", files=[])


@app.route("/admin/files", methods=["GET"])
def list_files():
    try:
        files = client.file_search_stores.documents.list(
            parent=FILE_SEARCH_STORE_NAME
        )

        file_list = [
            {
                "name": f.name,
                "display_name": getattr(f, "display_name", None),
                "state": getattr(f, "state", None),
            }
            for f in files
        ]

        return jsonify({"files": file_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No filename"}), 400

    try:
        os.makedirs("temp_uploads", exist_ok=True)
        temp_path = os.path.join("temp_uploads", secure_filename(file.filename))

        file.save(temp_path)

        try:
            client.file_search_stores.upload_to_file_search_store(
                file=temp_path,
                file_search_store_name=FILE_SEARCH_STORE_NAME,
                config={"display_name": file.filename},
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return jsonify({"message": "Upload successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/files", methods=["DELETE"])
def delete_file():
    data = request.get_json()
    file_name = data.get("file_name") if data else None

    if not file_name:
        return jsonify({"error": "Missing file_name"}), 400

    try:
        client.file_search_stores.documents.delete(
            name=file_name,
            config=types.DeleteDocumentConfig(force=True),
        )

        return jsonify({"message": "File deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)