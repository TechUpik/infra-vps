FROM prefecthq/prefect:3-latest

USER root

# Dependências de sistema + ODBC SQL Server (Ubuntu 22.04 / jammy)
RUN apt-get update && \
    apt-get install -y \
      curl \
      gnupg \
      ca-certificates \
      apt-transport-https \
      unixodbc \
      unixodbc-dev && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" \
      > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18 && \
    rm -rf /var/lib/apt/lists/*

# Dependências Python
RUN pip install --no-cache-dir \
    prefect \
    pymongo \
    azure-storage-blob \
    pyodbc
