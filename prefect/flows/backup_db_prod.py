from prefect import flow, task
from prefect.variables import Variable
from datetime import datetime
from pymongo import MongoClient
from bson import json_util
from azure.storage.blob import BlobServiceClient, BlobBlock
from azure.core.exceptions import ResourceExistsError
import pyodbc
import gzip
import io
import uuid
import base64

BATCH_SIZE = 500  # documentos por batch do cursor MongoDB
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB por bloco no Azure (máx 100MB, mín viável ~1MB)


def _build_blob_name() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"prod_full_backup_{timestamp}.json.gz"


@task(retries=3, retry_delay_seconds=30, timeout_seconds=3600)
def stream_backup_to_blob() -> tuple[str, int, int]:
    """
    Lê o MongoDB em batches, serializa JSON incrementalmente,
    comprime on-the-fly e faz upload para Azure em blocos (block blob).
    Nunca materializa o database inteiro na RAM.
    """
    mongo_cfg = Variable.get("mongodb")
    blob_cfg = Variable.get("upikblob")

    client = MongoClient(mongo_cfg["ConnectionString"])
    db = client["prod"]
    collection_names = db.list_collection_names()

    blob_service = BlobServiceClient.from_connection_string(
        blob_cfg["StorageConnectionString"]
    )
    container_name = blob_cfg.get(
        "ContainerBackupProdDb", blob_cfg["ContainerBackupAmbB2b"]
    )
    blob_name = _build_blob_name()
    blob_client = blob_service.get_blob_client(container_name, blob_name)

    block_ids: list[str] = []
    total_docs = 0

    # Buffer local que acumula dados comprimidos para enviar em blocos ao Azure
    upload_buffer = io.BytesIO()

    def flush_to_azure(gz_obj, force: bool = False):
        """Envia o buffer atual ao Azure como um bloco staged, se atingir CHUNK_SIZE."""
        nonlocal upload_buffer, block_ids

        # Força flush interno do gzip sem fechar o stream
        gz_obj.flush()

        upload_buffer.seek(0, 2)  # posição no fim
        size = upload_buffer.tell()

        if size >= CHUNK_SIZE or (force and size > 0):
            upload_buffer.seek(0)
            block_id = base64.b64encode(uuid.uuid4().bytes).decode()
            blob_client.stage_block(block_id=block_id, data=upload_buffer.read())
            block_ids.append(block_id)
            upload_buffer = io.BytesIO()  # reseta o buffer

    def write(gz_obj, data: bytes):
        gz_obj.write(data)
        flush_to_azure(gz_obj)

    created_at = datetime.utcnow().isoformat()

    with gzip.GzipFile(fileobj=upload_buffer, mode="wb", compresslevel=6) as gz:

        # --- cabeçalho ---
        header = (
            f'{{"database":"prod",'
            f'"collections":{json_util.dumps(collection_names)},'
            f'"created_at":"{created_at}",'
            f'"data":{{'
        )
        write(gz, header.encode("utf-8"))

        # --- collections ---
        for col_idx, name in enumerate(collection_names):
            prefix = b"" if col_idx == 0 else b","
            write(gz, prefix + f'"{name}":[\n'.encode("utf-8"))

            cursor = (
                db[name]
                .find({}, {"_id": 0})
                .batch_size(BATCH_SIZE)
                .allow_disk_use(True)
            )

            first_doc = True
            for doc in cursor:
                sep = b"" if first_doc else b","
                write(gz, sep + json_util.dumps(doc, ensure_ascii=False).encode("utf-8"))
                first_doc = False
                total_docs += 1

            write(gz, b"\n]")

        # --- fechamento do JSON ---
        write(gz, b"}}")

        # flush final antes de fechar o gzip
        flush_to_azure(gz, force=True)

    # Gzip fechado → garante que qualquer dado residual vá para o Azure
    # (o with-block já fechou; fazemos um flush do buffer remanescente)
    upload_buffer.seek(0)
    remaining = upload_buffer.read()
    if remaining:
        block_id = base64.b64encode(uuid.uuid4().bytes).decode()
        blob_client.stage_block(block_id=block_id, data=remaining)
        block_ids.append(block_id)

    # Commit de todos os blocos — só agora o blob fica visível e completo
    blob_client.commit_block_list(block_ids)

    client.close()
    return blob_name, total_docs, len(collection_names)


@task(retries=3, retry_delay_seconds=10)
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

    with pyodbc.connect(CONNECTION_STRING) as conn:
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


@flow(name="backup-prod-database", log_prints=True)
def backup_prod_database_flow():
    blob_name, total_docs, total_collections = stream_backup_to_blob()
    log_backup_sql(blob_name, total_docs, total_collections)
    print(f"Backup concluído: {blob_name} | {total_docs} docs | {total_collections} collections")
