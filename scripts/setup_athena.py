import boto3
import time
import sys

def run_query(athena, query, database, workgroup, results_bucket):
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
                reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                print(f"Query {state}: {reason}")
                return None
            return execution_id
        time.sleep(2)

def setup_athena_table(logs_bucket, database, workgroup):
    athena = boto3.client('athena', region_name='us-east-2')
    
    drop_query = f"DROP TABLE IF EXISTS {database}.application_logs"
    print("Dropping existing table if present...")
    run_query(athena, drop_query, database, workgroup, None)
    
    create_query = f"""
    CREATE EXTERNAL TABLE IF NOT EXISTS {database}.application_logs (
        timestamp string,
        level string,
        method string,
        endpoint string,
        status_code int,
        response_time_ms int,
        ip_address string,
        user_agent string,
        request_id string,
        service string
    )
    ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
    LOCATION 's3://{logs_bucket}/logs/'
    TBLPROPERTIES ('has_encrypted_data'='false')
    """
    
    print("Creating Athena table...")
    result = run_query(athena, create_query, database, workgroup, None)
    if result:
        print(f"Table created successfully")
    
    count_query = f"SELECT COUNT(*) as total_records FROM {database}.application_logs"
    print("Counting records...")
    execution_id = run_query(athena, count_query, database, workgroup, None)
    
    if execution_id:
        results = athena.get_query_results(QueryExecutionId=execution_id)
        count = results['ResultSet']['Rows'][1]['Data'][0]['VarCharValue']
        print(f"Total records in table: {count}")

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python setup_athena.py <logs_bucket> <database> <workgroup>")
        sys.exit(1)
    
    logs_bucket = sys.argv[1]
    database = sys.argv[2]
    workgroup = sys.argv[3]
    
    setup_athena_table(logs_bucket, database, workgroup)