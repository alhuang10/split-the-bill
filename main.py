from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_restful import Api, Resource
import uuid
import os
import json
import google.generativeai as genai

from IPython.display import Image

assert os.environ['GEMINI_API_KEY'], "API KEY NOT SET"
genai.configure(api_key=os.environ['GEMINI_API_KEY'])

_MODEL = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    # model_name="gemini-1.5-pro",
    generation_config={"response_mime_type": "application/json"})

_PROMPT = """
    Extract the lines of this receipt and output in JSON format using this schema:
        [{"count": int, "name": str, "total_price": float}]
"""

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Add this line to enable session usage
api = Api(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# In-memory store for simplicity. Replace with a database in production.
receipts = {}

class ReceiptResource(Resource):
    def get(self, receipt_id):
        return jsonify(receipts.get(receipt_id, {}))

    def post(self, receipt_id):
        if receipt_id not in receipts:
            return {'error': 'Receipt not found'}, 404
        user = request.json['user']
        selections = request.json['selections']
        for index, quantity in selections.items():
            index = int(index)
            if index not in receipts[receipt_id]['selections']:
                receipts[receipt_id]['selections'][index] = {}
            receipts[receipt_id]['selections'][index][user] = quantity
        return {'status': 'updated'}, 200

api.add_resource(ReceiptResource, '/api/receipt/<string:receipt_id>')

@app.route('/api/calculate/<string:receipt_id>')
def calculate_amounts(receipt_id):
    if receipt_id not in receipts:
        return jsonify({'error': 'Receipt not found'}), 404
    
    receipt = receipts[receipt_id]
    amounts_owed = {}

    for index, item in enumerate(receipt['items']):
        price = float(item['total_price'])
        selections = receipt['selections'].get(index, {})
        total_quantity = sum(selections.values())
        
        if total_quantity > 0:
            price_per_unit = price / total_quantity
            for user, quantity in selections.items():
                if user not in amounts_owed:
                    amounts_owed[user] = 0
                amounts_owed[user] += price_per_unit * quantity

    # Round to two decimal places
    amounts_owed = {user: round(amount, 2) for user, amount in amounts_owed.items()}

    return jsonify(amounts_owed)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='No file part')
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', message='No selected file')
        if file and allowed_file(file.filename):
            extension = file.filename.split(".")[-1]
            filename = f"{str(uuid.uuid4())}.{extension}"
            
            print(f"Saving file as {filename}")

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            image = Image(filepath)

            print(f"Sending image to API for OCR")
            response = _MODEL.generate_content([image, _PROMPT])
            print(f"Received response from API")

            try:
                response_json = json.loads(response.text)

                print(f"response JSON type: {type(response_json)}")
                print(f"response JSON: {response_json[0]}")

                for result in response_json:
                    result['name'] = f"{result['count']} {result['name']}"

                session['ocr_results'] = response_json  # Store results in session
            except json.JSONDecodeError:
                print("Error decoding JSON from Gemini AI response")
                session['ocr_results'] = []

            return redirect(url_for('ocr_result'))
        else:
            return render_template('index.html', message='Invalid file type')
    return render_template('index.html')

@app.route('/ocr_result')
def ocr_result():
    items = session.get('ocr_results', [])
    print(f"OCR results: {items}")
    return render_template('ocr_result.html', items=items)

@app.route('/finalize', methods=['POST'])
def finalize_receipt():
    items = request.json['items']
    receipt_id = str(uuid.uuid4())
    receipts[receipt_id] = {
        'items': items,
        'selections': {}
    }
    return jsonify({'link': f'/split/{receipt_id}'})

@app.route('/split/<receipt_id>')
def split_receipt(receipt_id):
    if receipt_id not in receipts:
        return "Receipt not found", 404
    return render_template('split.html', receipt_id=receipt_id)

@app.route('/update_item', methods=['POST'])
def update_item():
    data = request.json
    # In a real application, you would update the database here
    # For now, we'll just return the received data
    return jsonify(success=True, data=data)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)