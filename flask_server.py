import shutil
import sys
from musecoco_text2midi_service.control import Text2Midi
from musecoco_text2midi_service.dao import load_config_from_file
from flask import Flask, request, jsonify, send_file
from flask_restx import Api, Resource, fields
import threading
import uuid
import os

def delete_folder_contents(folder_path):
    """
    Deletes all contents of the specified folder.
    """
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        os.makedirs(folder_path)  # Recreate the folder after deletion

delete_folder_contents("storage/tmp")

# Initialize Flask app
app = Flask(__name__)
api = Api(app, version='1.0', title='Text2Midi API', description='A simple Text to MIDI conversion API')

# Load configuration for Text2Midi service
config_path = "storage/config/main_config.yaml"
config = load_config_from_file(config_path)

# Initialize Text2Midi service
text2midi = Text2Midi(config)

# Simulated job store
job_store = {}

def generate_midi(job_id, input_text):
    try:
        midi_data, meta_data = text2midi.text_to_midi(input_text, return_midi=True)
        midi_file_path = meta_data.get('file_path')

        # Remove 'file_path' from meta_data before storing it in 'metaData'
        if 'file_path' in meta_data:
            del meta_data['file_path']

        job_store[job_id]['status'] = 'completed'
        job_store[job_id]['result'] = {
            'metaData': meta_data,
            'midiFilePath': midi_file_path
        }
    except Exception as e:
        job_store[job_id]['status'] = 'failed'
        job_store[job_id]['error'] = str(e)

# Define API models
text_input = api.model('TextInput', {
    'text': fields.String(required=True, description='The text to convert to MIDI')
})

job_status = api.model('JobStatus', {
    'jobId': fields.String(description='The job ID'),
    'status': fields.String(description='The status of the job')
})

job_result = api.model('JobResult', {
    'jobId': fields.String(description='The job ID'),
    'status': fields.String(description='The status of the job'),
    'metaData': fields.Raw(description='Metadata of the generated MIDI')
})

@api.route('/submit-text')
class SubmitText(Resource):
    @api.expect(text_input)
    @api.response(202, 'Job submitted', job_status)
    @api.response(400, 'Invalid input')
    def post(self):
        # Delete contents of storage/tmp and storage/generation after each turn
        delete_folder_contents("storage/generation")
        
        data = request.json
        input_text = data.get('text')
        if not input_text:
            return {'error': 'Text input is required.'}, 400

        job_id = str(uuid.uuid4())
        job_store[job_id] = {'status': 'submitted'}

        # Start background thread for MIDI generation
        threading.Thread(target=generate_midi, args=(job_id, input_text)).start()

        return {'jobId': job_id, 'status': 'submitted'}, 202

@api.route('/check-status/<job_id>')
class CheckStatus(Resource):
    @api.response(200, 'Job status', job_status)
    @api.response(404, 'Job ID not found')
    def get(self, job_id):
        job = job_store.get(job_id)
        if not job:
            return {'error': 'Job ID not found.'}, 404

        return {'jobId': job_id, 'status': job['status']}, 200

@api.route('/get-result/<job_id>')
class GetResult(Resource):
    @api.response(200, 'Job result', job_result)
    @api.response(404, 'Job ID not found')
    @api.response(400, 'MIDI generation is not complete yet')
    def get(self, job_id):
        job = job_store.get(job_id)
        if not job:
            return {'error': 'Job ID not found.'}, 404

        if job['status'] != 'completed':
            return {'error': 'MIDI generation is not complete yet.'}, 400

        return {
            'jobId': job_id,
            'status': job['status'],
            'metaData': job['result']['metaData']
        }, 200

@api.route('/download-midi/<job_id>')
class DownloadMidi(Resource):
    @api.response(200, 'MIDI file')
    @api.response(404, 'Job ID not found')
    @api.response(400, 'MIDI generation is not complete yet')
    def get(self, job_id):
        job = job_store.get(job_id)
        if not job:
            return {'error': 'Job ID not found.'}, 404

        if job['status'] != 'completed':
            return {'error': 'MIDI generation is not complete yet.'}, 400

        midi_file_path = job['result']['midiFilePath']
        if not os.path.exists(midi_file_path):
            return {'error': 'MIDI file not found.'}, 404

        return send_file(midi_file_path, as_attachment=True)

def main():
    app.run(debug=True, use_reloader=False)

if __name__ == "__main__":
    main()
