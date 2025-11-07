from flask import Flask, render_template, request, send_file, jsonify
from seating_model import SeatingPlanner
import json
import os
import traceback

app = Flask(__name__)
planner = SeatingPlanner()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_seating', methods=['POST'])
def generate_seating():
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        classes = data.get('classes', [])
        halls = data.get('halls', [])
        
        if not classes or not halls:
            return jsonify({'error': 'Please provide both classes and halls data'}), 400
        
        # Validate classes data
        for cls in classes:
            if 'name' not in cls or 'start_roll' not in cls or 'end_roll' not in cls:
                return jsonify({'error': 'Invalid class data format'}), 400
        
        # Validate halls data
        for hall in halls:
            if 'name' not in hall or 'rows' not in hall or 'columns' not in hall or 'students_per_desk' not in hall:
                return jsonify({'error': 'Invalid hall data format'}), 400
        
        # Generate seating arrangement
        result = planner.generate_arrangement(classes, halls)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    
    except Exception as e:
        print(f"Error in generate_seating: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/generate_exam_schedule', methods=['POST'])
def generate_exam_schedule():
    try:
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        classes = data.get('classes', [])
        halls = data.get('halls', [])
        teachers = data.get('teachers', [])
        class_subjects = data.get('class_subjects', [])
        date_mode = data.get('date_mode', 'auto')
        manual_dates = data.get('manual_dates', {})
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        exams_per_day = int(data.get('exams_per_day', 1))
        invigilators_per_hall = int(data.get('invigilators_per_hall', 2))
        
        if not classes or not halls or not teachers or not class_subjects:
            return jsonify({'error': 'Please provide all required data'}), 400
        
        # Generate complete exam schedule
        result = planner.generate_exam_schedule(
            classes=classes,
            halls=halls,
            teachers=teachers,
            class_subjects=class_subjects,
            date_mode=date_mode,
            manual_dates=manual_dates,
            start_date=start_date,
            end_date=end_date,
            exams_per_day=exams_per_day,
            invigilators_per_hall=invigilators_per_hall
        )
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    
    except Exception as e:
        print(f"Error in generate_exam_schedule: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    try:
        data = request.json
        arrangement = data.get('arrangement', {})
        
        if not arrangement:
            return jsonify({'error': 'No arrangement data provided'}), 400
        
        # Generate PDF
        pdf_path = planner.generate_pdf(arrangement)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name='seating_arrangement.pdf',
            mimetype='application/pdf'
        )
    
    except Exception as e:
        print(f"Error in download_pdf: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500

@app.route('/download_exam_schedule_pdf', methods=['POST'])
def download_exam_schedule_pdf():
    try:
        data = request.json
        exam_schedule = data.get('exam_schedule', {})
        
        if not exam_schedule:
            return jsonify({'error': 'No exam schedule data provided'}), 400
        
        # Generate comprehensive exam schedule PDF
        pdf_path = planner.generate_exam_schedule_pdf(exam_schedule)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name='exam_schedule_complete.pdf',
            mimetype='application/pdf'
        )
    
    except Exception as e:
        print(f"Error in download_exam_schedule_pdf: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    print("Starting Flask application...")
    print("Available routes:")
    print("  / - Main page")
    print("  /generate_seating - POST endpoint for generating seating")
    print("  /generate_exam_schedule - POST endpoint for generating exam schedule")
    print("  /download_pdf - POST endpoint for downloading seating PDF")
    print("  /download_exam_schedule_pdf - POST endpoint for downloading exam schedule PDF")
    
    app.run(debug=True, port=5000)