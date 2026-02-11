from prefect import flow, task
from prefect.variables import Variable
from datetime import datetime
from pymongo import MongoClient
from bson import json_util
from azure.storage.blob import BlobServiceClient
import pyodbc
import gzip
import io

@task(retries=3, retry_delay_seconds=10)
def backup_full_database():
    """Exporta todas as collections do database 'prod' em um único .json.gz"""
    mongo_cfg = Variable.get("mongodb")
    client = MongoClient(mongo_cfg["ConnectionString"])
    db = client["prod"]

    collection_names = db.list_collection_names()
    all_collections = {}
    total_docs = 0

    for name in collection_names:
        docs = list(db[name].find({}, {"_id": 0}))
        all_collections[name] = docs
        total_docs += len(docs)

    payload = {
        "database": "prod",
        "collections": list(all_collections.keys()),
        "created_at": datetime.utcnow().isoformat(),
        "total_docs": total_docs,
        "data": all_collections,  # { "col1": [...], "col2": [...], ... }
    }

    raw = json_util.dumps(payload, ensure_ascii=False).encode("utf-8")

    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(raw)
    buffer.seek(0)

    client.close()
    return buffer.read(), total_docs, len(collection_names)

@task
def upload_to_azure_blob(data: bytes):
    blob_cfg = Variable.get("upikblob")

    blob_service = BlobServiceClient.from_connection_string(
        blob_cfg["StorageConnectionString"]
    )

    # Ajuste aqui para o container correto do backup full
    container_name = blob_cfg.get("ContainerBackupProdDb", blob_cfg["ContainerBackupAmbB2b"])
    container = blob_service.get_container_client(container_name)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    blob_name = f"prod_full_backup_{timestamp}.json.gz"

    container.upload_blob(
        name=blob_name,
        data=data,
        overwrite=True,
    )

    return blob_name

@task
def log_backup_sql(blob_name: str, total_docs: int, total_collections: int):
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
        "prod (full database)",
        blob_name,
        total_docs,
        datetime.utcnow(),
    )

    conn.commit()
    cursor.close()
    conn.close()

@flow(name="backup-prod-database")
def backup_prod_database_flow():
    data, total_docs, total_collections = backup_full_database()
    blob_name = upload_to_azure_blob(data)
    log_backup_sql(blob_name, total_docs, total_collections)
