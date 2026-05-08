import boto3
import time
import sys
import json

def run_query(athena, query, database, workgroup):
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        WorkGroup=workgroup
    )
    execution_id = response['QueryExecutionId']
    
    while True:
        result = athena.get_query_execution(QueryExecutionId=execution_id)
        state = result['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            if state != 'SUCCEEDED':
                reason = result['QueryExecution']['Status'].get('StateChangeReason', '')
                print(f"  Query {state}: {reason}")
                return None
            data_scanned = result['QueryExecution']['Statistics'].get('DataScannedInBytes', 0)
            exec_time = result['QueryExecution']['Statistics'].get('EngineExecutionTimeInMillis', 0)
            print(f"  Scanned: {data_scanned/1024:.1f} KB | Execution time: {exec_time}ms")
            return execution_id
        time.sleep(2)

def print_results(athena, execution_id):
    results = athena.get_query_results(QueryExecutionId=execution_id)
    rows = results['ResultSet']['Rows']
    if len(rows) <= 1:
        print("  No results")
        return
    headers = [col['VarCharValue'] for col in rows[0]['Data']]
    print(f"  {' | '.join(headers)}")
    print(f"  {'-' * 60}")
    for row in rows[1:]:
        values = [col.get('VarCharValue', 'NULL') for col in row['Data']]
        print(f"  {' | '.join(values)}")

def run_analysis(database, workgroup):
    athena = boto3.client('athena', region_name='us-east-2')
    
    queries = [
        (
            "Error rate by status code",
            f"""SELECT status_code, COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
                FROM {database}.application_logs
                GROUP BY status_code
                ORDER BY count DESC"""
        ),
        (
            "Top 5 slowest endpoints (avg response time)",
            f"""SELECT endpoint, method,
                ROUND(AVG(response_time_ms), 0) as avg_ms,
                MAX(response_time_ms) as max_ms,
                COUNT(*) as request_count
                FROM {database}.application_logs
                GROUP BY endpoint, method
                ORDER BY avg_ms DESC
                LIMIT 5"""
        ),
        (
            "Error log breakdown by service",
            f"""SELECT service, level, COUNT(*) as count
                FROM {database}.application_logs
                WHERE level IN ('ERROR', 'WARN')
                GROUP BY service, level
                ORDER BY count DESC"""
        ),
        (
            "Request volume by hour",
            f"""SELECT SUBSTR(timestamp, 1, 13) as hour,
                COUNT(*) as requests,
                SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) as errors
                FROM {database}.application_logs
                GROUP BY SUBSTR(timestamp, 1, 13)
                ORDER BY hour DESC
                LIMIT 10"""
        ),
    ]
    
    for title, query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {title}")
        print(f"{'='*60}")
        execution_id = run_query(athena, query, database, workgroup)
        if execution_id:
            print_results(athena, execution_id)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python query_logs.py <database> <workgroup>")
        sys.exit(1)
    
    database = sys.argv[1]
    workgroup = sys.argv[2]
    run_analysis(database, workgroup)