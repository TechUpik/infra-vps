from prefect import flow, task
from prefect.variables import Variable
from datetime import datetime
from pymongo import MongoClient
from bson import json_util  # ← Adicionar este import
from azure.storage.blob import BlobServiceClient
import pyodbc
import gzip
import io
import json

@task(retries=3, retry_delay_seconds=10)
def backup_mongo_collection():
    mongo_cfg = Variable.get("mongodb")
    mongo_conn = mongo_cfg["ConnectionString"]
    client = MongoClient(mongo_conn)
    db = client["prod"]
    collection = db["AmbientesB2b"]
    docs = list(collection.find({}, {"_id": 0}))
    
    payload = {
        "database": "prod",
        "collection": "AmbientesB2b",
        "created_at": datetime.utcnow().isoformat(),
        "count": len(docs),
        "data": docs,
    }
    
    # ↓ Usar json_util.dumps ao invés de json.dumps
    raw = json_util.dumps(payload, ensure_ascii=False).encode("utf-8")
    
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(raw)
    buffer.seek(0)
    return buffer.read(), len(docs)

@task
def upload_to_azure_blob(data: bytes):
    blob_cfg = Variable.get("upikblob")

    blob_service = BlobServiceClient.from_connection_string(
        blob_cfg["StorageConnectionString"]
    )

    container_name = blob_cfg["ContainerBackupAmbB2b"]
    container = blob_service.get_container_client(container_name)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    blob_name = f"ambientes_b2b_backup_{timestamp}.json.gz"

    container.upload_blob(
        name=blob_name,
        data=data,
        overwrite=True
    )

    return blob_name


@task
def log_backup_sql(blob_name: str, total_docs: int): 
    CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:upik-db-sql.database.windows.net,1433;"
    "Database=upik-db-prod;"
    "Uid=upik-db;"
    "Pwd=fRtKZ4YMXP77B_Qv91Na5L;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
    )

    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO backups_ambientes_b2b
        (collection_name, blob_name, total_docs, created_at)
        VALUES (?, ?, ?, ?)
        """,
        "AmbientesB2b",
        blob_name,
        total_docs,
        datetime.utcnow(),
    )

    conn.commit()
    cursor.close()
    conn.close()


@flow(name="backup-ambientes-b2b")
def backup_ambientes_b2b_flow():
    data, total_docs = backup_mongo_collection()
    blob_name = upload_to_azure_blob(data)
    log_backup_sql(blob_name, total_docs)
