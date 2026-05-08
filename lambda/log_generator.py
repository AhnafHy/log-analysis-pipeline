import json
import boto3
import random
import time
import os
from datetime import datetime, timezone

firehose = boto3.client('firehose', region_name=os.environ.get('AWS_REGION', 'us-east-2'))
STREAM_NAME = os.environ.get('FIREHOSE_STREAM_NAME', 'log-analysis-stream')

ENDPOINTS = [
    '/api/users', '/api/products', '/api/orders',
    '/api/checkout', '/api/search', '/health',
    '/api/auth/login', '/api/auth/logout'
]

STATUS_CODES = [200, 200, 200, 200, 201, 301, 400, 401, 403, 404, 500, 503]
HTTP_METHODS = ['GET', 'GET', 'GET', 'POST', 'PUT', 'DELETE']
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)',
    'PostmanRuntime/7.32.0',
    'python-requests/2.31.0'
]

def generate_ip():
    return f"{random.randint(1,254)}.{random.randint(0,254)}.{random.randint(0,254)}.{random.randint(1,254)}"

def generate_log_event():
    status = random.choice(STATUS_CODES)
    endpoint = random.choice(ENDPOINTS)
    method = random.choice(HTTP_METHODS)
    response_time = random.randint(10, 2000) if status < 500 else random.randint(2000, 10000)
    
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': 'ERROR' if status >= 500 else 'WARN' if status >= 400 else 'INFO',
        'method': method,
        'endpoint': endpoint,
        'status_code': status,
        'response_time_ms': response_time,
        'ip_address': generate_ip(),
        'user_agent': random.choice(USER_AGENTS),
        'request_id': f"req-{random.randint(100000, 999999)}",
        'service': random.choice(['api-gateway', 'auth-service', 'product-service', 'order-service'])
    }

def lambda_handler(event, context):
    batch_size = int(os.environ.get('BATCH_SIZE', '100'))
    records = []
    
    for _ in range(batch_size):
        log_event = generate_log_event()
        records.append({
            'Data': (json.dumps(log_event) + '\n').encode('utf-8')
        })
    
    response = firehose.put_record_batch(
        DeliveryStreamName=STREAM_NAME,
        Records=records
    )
    
    failed = response.get('FailedPutCount', 0)
    print(f"Sent {batch_size} records to Firehose. Failed: {failed}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'sent': batch_size,
            'failed': failed
        })
    }