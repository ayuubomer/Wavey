import os
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FILE_SEARCH_STORE_NAME = os.getenv("FILE_SEARCH_STORE_NAME")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")

if not FILE_SEARCH_STORE_NAME:
    raise ValueError("FILE_SEARCH_STORE_NAME is not set")

client = genai.Client(api_key=GEMINI_API_KEY)

executor = ThreadPoolExecutor(max_workers=10)


files_to_upload = [
    "we.pdf",
    "side.html",
]

stores = client.file_search_stores.list()

for store in stores:
    print(store.name)
    file_search_store = store


def generate_response(user_query: str):
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=user_query,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a precise website assistant. "
                "Use provided documents to answer questions but you can use internet if needed"
                "Don't make up answers if you don't know the answer. "
                "only respond in norwegian, don not respond in any other language. "
                'don not say "based on the provided documents" or "based on the information in the documents" '
                "you are an expert withing the e-commerce industry "
                "access all pages in https://ewaves.no/ and include information from the website in your knowledge. "
                "don't use markdown formatting in your response. "
                
            ),
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[FILE_SEARCH_STORE_NAME]
                    )
                )
            ]
        )
    )

    return response.text

@app.route("/query", methods=["POST"])
def query():
    user_query = request.form.get("query")

    if not user_query:
        return jsonify({"error": "Missing query"}), 400

    # user_query = data["query"]

    # Run Gemini call in thread pool (prevents blocking)
    future = executor.submit(generate_response, user_query)
    result = future.result()

    return jsonify({"response": result})


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/admin/files", methods=["GET"])
def list_files():

    try:
        files = client.file_search_stores.documents.list(
            parent=FILE_SEARCH_STORE_NAME
        )

        print(f"Files in store {FILE_SEARCH_STORE_NAME}: {files}")

        file_list = []
        for f in files:
            file_list.append({
                "name": f.name,
                "display_name": getattr(f, "display_name", None),
                "state": getattr(f, "state", None)
            })

        return jsonify({"files": file_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin")
def admin_page():
    files = client.file_search_stores.documents.list(parent=FILE_SEARCH_STORE_NAME)
    return render_template("admin.html", files=files)

@app.route("/admin/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    print(f"Received file: {file.filename}")

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        # Save the uploaded file to a temporary location
        
        temp_path = os.path.join("temp_uploads", file.filename)
        os.makedirs("temp_uploads", exist_ok=True)
        file.save(temp_path)

        # Upload to Gemini File Search Store
        client.file_search_stores.upload_to_file_search_store(
            file=temp_path,
            file_search_store_name=FILE_SEARCH_STORE_NAME,
            config={
                "display_name": file.filename
            }
        )

        # Remove the temporary file
        os.remove(temp_path)

        print(f"Uploaded {file.filename} to file search store {FILE_SEARCH_STORE_NAME}")

        return jsonify({"message": f"File {file.filename} uploaded successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/admin/files", methods=["DELETE"])
def delete_file():
    data = request.get_json()
    file_name = data.get("file_name")

    if not file_name:
        return jsonify({"error": "Missing file_name"}), 400

    try:
        # force delete the file from the file search store
        client.file_search_stores.documents.delete(
            name=file_name,
            config=types.DeleteDocumentConfig(force=True)
        )
        print(f"Deleted file {file_name} from file search store {FILE_SEARCH_STORE_NAME}")
        return jsonify({"message": f"File {file_name} deleted successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)