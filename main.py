from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_restful import Api, Resource
import uuid
import os

app = Flask(__name__)
api = Api(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'heic'}


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
        for index, selected in selections.items():
            if selected:
                receipts[receipt_id]['selections'].setdefault(int(index), []).append(user)
        return {'status': 'updated'}, 200

api.add_resource(ReceiptResource, '/api/receipt/<string:receipt_id>')


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
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # In a real application, you would process the image here
            # For now, we'll just redirect to the OCR result page
            return redirect(url_for('ocr_result'))
        else:
            return render_template('index.html', message='Invalid file type')
    return render_template('index.html')

@app.route('/ocr_result')
def ocr_result():
    # Hardcoded OCR results
    items = [
        {'name': 'Pizza', 'price': '$20'},
        {'name': 'Soda', 'price': '$5'}
    ]
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