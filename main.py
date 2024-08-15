from flask import Flask, render_template, request, redirect, url_for, jsonify, session, g
from flask_restful import Api, Resource
import sqlite3
import os
import uuid
import json
import google.generativeai as genai
from IPython.display import Image
import logging

app = Flask(__name__)
api = Api(app)

logging.basicConfig(filename='flaskapp.log', level=logging.DEBUG)

app.secret_key = os.urandom(24)

assert os.environ['GEMINI_API_KEY'], "API KEY NOT SET"
genai.configure(api_key=os.environ['GEMINI_API_KEY'])

_MODEL = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"})

_PROMPT = """
    Extract the lines of this receipt and output in JSON format using this schema:
        [{"count": int, "name": str, "total_price": float}]
"""

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

basedir = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(basedir, 'receipts.db')

os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS receipts
            (id TEXT PRIMARY KEY, items TEXT, selections TEXT)
        ''')
        db.commit()

init_db()

class ReceiptResource(Resource):
    def get(self, receipt_id):
        db = get_db()
        receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if receipt:
            data = {
                'items': json.loads(receipt['items']),
                'selections': json.loads(receipt['selections'])
            }
            print("Receipt data being sent:", data)  # Add this line
            return data
        return {'error': 'Receipt not found'}, 404

    def post(self, receipt_id):
        db = get_db()
        data = request.json
        print("Received data:", data)  # Add this line
        receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
        if receipt:
            current_selections = json.loads(receipt['selections'])
            print("Current selections:", current_selections)  # Add this line
            for index, quantity in data['selections'].items():
                if index not in current_selections:
                    current_selections[index] = {}
                current_selections[index][data['user']] = quantity
            print("Updated selections:", current_selections)  # Add this line
            db.execute('UPDATE receipts SET selections = ? WHERE id = ?',
                    (json.dumps(current_selections), receipt_id))
        else:
            db.execute('INSERT INTO receipts (id, items, selections) VALUES (?, ?, ?)',
                    (receipt_id, json.dumps([]), json.dumps(data['selections'])))
        db.commit()
        return {'status': 'updated'}, 200

api.add_resource(ReceiptResource, '/api/receipt/<string:receipt_id>')

@app.route('/api/calculate/<string:receipt_id>')
def calculate_amounts(receipt_id):
    db = get_db()
    receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
    if not receipt:
        return jsonify({'error': 'Receipt not found'}), 404
    
    items = json.loads(receipt['items'])
    selections = json.loads(receipt['selections'])
    amounts_owed = {}

    for index, item in enumerate(items):
        price = float(item['total_price'])
        item_selections = selections.get(str(index), {})
        total_quantity = sum(int(qty) for qty in item_selections.values())
        
        if total_quantity > 0:
            price_per_unit = price / total_quantity
            for user, quantity in item_selections.items():
                if user not in amounts_owed:
                    amounts_owed[user] = 0
                amounts_owed[user] += price_per_unit * int(quantity)

    amounts_owed = {user: round(amount, 2) for user, amount in amounts_owed.items()}

    return jsonify(amounts_owed)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

                session['ocr_results'] = response_json
            except json.JSONDecodeError:
                print("Error decoding JSON from Gemini AI response")
                session['ocr_results'] = []

            # Return JSON response with redirect URL
            return jsonify({'redirect': url_for('ocr_result')})
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    # For GET requests, render the upload form
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
    db = get_db()
    db.execute('INSERT INTO receipts (id, items, selections) VALUES (?, ?, ?)',
               (receipt_id, json.dumps(items), json.dumps({})))
    db.commit()
    return jsonify({'link': f'/split/{receipt_id}'})

@app.route('/split/<receipt_id>')
def split_receipt(receipt_id):
    db = get_db()
    receipt = db.execute('SELECT * FROM receipts WHERE id = ?', (receipt_id,)).fetchone()
    if not receipt:
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