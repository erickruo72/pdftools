# app/wordtopdf.py

import os
from docx2pdf import convert
import json
from worker import redis_conn

def perform_word_to_pdf(input_path, output_path):
    try:
        convert(input_path, output_path)

        # Mark job status as complete
        job_id = os.environ.get('RQ_JOB_ID')
        if job_id:
            redis_conn.set(f'job_status:{job_id}', json.dumps({
                'status': 'finished',
                'result': os.path.basename(output_path)
            }))

        return os.path.basename(output_path)
    except Exception as e:
        # Mark job as failed
        job_id = os.environ.get('RQ_JOB_ID')
        if job_id:
            redis_conn.set(f'job_status:{job_id}', json.dumps({
                'status': 'failed',
                'result': str(e)
            }))
        raise
