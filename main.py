import os
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()

# --------------------------------------------------
# App Setup
# --------------------------------------------------

app = Flask(__name__)

# Environment variables (NEVER hardcode secrets)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FILE_SEARCH_STORE_NAME = os.getenv("FILE_SEARCH_STORE_NAME")

print(f"GEMINI_API_KEY: {GEMINI_API_KEY}")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set")

if not FILE_SEARCH_STORE_NAME:
    raise ValueError("FILE_SEARCH_STORE_NAME is not set")

# Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# Thread pool for blocking Gemini calls
executor = ThreadPoolExecutor(max_workers=10)

# file_search_store = None#client.file_search_stores.create(config={'display_name': 'your-fileSearchStore-name'})

files_to_upload = [
    "we.pdf",
    "side.html",
]

stores = client.file_search_stores.list()

for store in stores:
    print(store.name)
    # if store.name != "fileSearchStores/yourfilesearchstorename-rnzl6kqraia7":
        # empty the store
        # for document in client.file_search_stores.documents.list(parent=store.name):
        #     client.file_search_stores.documents.delete(name=document.name)
        #     print(f"Deleted document {document.name} from file search store {store.name}")

        # # delete it
        # client.file_search_stores.delete(name=store.name, config=types.DeleteFileSearchStoreConfig(force=True))
        # print(f"Deleted file search store {store.name}")
    file_search_store = store

# for filename in files_to_upload:
#     client.file_search_stores.upload_to_file_search_store(
#         file=filename,
#         file_search_store_name=file_search_store.name,
#         config={
#             "display_name": filename
#         }
#     )
#     print(f"Uploaded {filename} to file search store {file_search_store.name}")
    # Wait for operation to complete
    # operation = client.operations.get(operation)
    # while not operation.done:
    #     operation = client.operations.get(operation)

# --------------------------------------------------
# Gemini Query Function
# --------------------------------------------------

def generate_response(user_query: str):
    # print(file_search_store.name)
    # response = client.models.generate_content(
    #     model="gemini-2.0-flash",
    #     contents=user_query,
    #     config=types.GenerateContentConfig(
    #         system_instruction=(
    #             "You are a precise website assistant. "
    #             "Use provided documents to answer questions. "
    #             "Do not make up answers. "
    #             'Do not say "based on the provided documents".'
    #         ),
    #         tools=[
    #             types.Tool(
    #                 file_search=types.FileSearch(
    #                     file_search_store_names=[file_search_store.name]
    #                 )
    #             )
    #         ]
    #     )
    # )
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=user_query,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a precise website assistant. "
                "Use provided documents to answer questions but you can use internet if needed"
                "Don't make up answers if you don't know the answer. "
                'don not say "based on the provided documents" or "based on the information in the documents" '
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


# --------------------------------------------------
# Routes
# --------------------------------------------------

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
    return render_template("admin.html")

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

# --------------------------------------------------
# Run App
# --------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)