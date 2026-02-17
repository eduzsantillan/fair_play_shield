#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log) 2>&1

echo "=========================================="
echo "Fair Play Shield - EC2 Setup (ECR)"
echo "=========================================="

yum update -y
yum install -y docker

systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

cd /home/ec2-user
mkdir -p fair_play_shield
cd fair_play_shield

aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin 806332783326.dkr.ecr.${aws_region}.amazonaws.com

cat > docker-compose.yml << 'COMPOSEFILE'
services:
  dashboard:
    image: 806332783326.dkr.ecr.${aws_region}.amazonaws.com/fair-play-shield:latest
    container_name: fps-dashboard
    ports:
      - "8050:8050"
    environment:
      - DB_HOST=${db_host}
      - DB_PORT=5432
      - DB_NAME=${db_name}
      - DB_USER=${db_user}
      - DB_PASSWORD=${db_password}
      - AWS_REGION=${aws_region}
      - S3_BUCKET=${s3_bucket}
    restart: unless-stopped

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.9.2
    container_name: fps-mlflow
    ports:
      - "5001:5000"
    environment:
      - MLFLOW_S3_ENDPOINT_URL=https://s3.${aws_region}.amazonaws.com
      - AWS_DEFAULT_REGION=${aws_region}
    command: mlflow server --host 0.0.0.0 --port 5000
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    container_name: fps-postgres
    environment:
      - POSTGRES_USER=airflow
      - POSTGRES_PASSWORD=airflow
      - POSTGRES_DB=airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  airflow-init:
    image: apache/airflow:2.7.3-python3.11
    container_name: fps-airflow-init
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
    entrypoint: /bin/bash -c "airflow db init && airflow users create --username airflow --password airflow --firstname Admin --lastname User --role Admin --email admin@example.com || true"
    depends_on:
      - postgres

  airflow-webserver:
    image: apache/airflow:2.7.3-python3.11
    container_name: fps-airflow-webserver
    ports:
      - "8080:8080"
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
      - AIRFLOW__WEBSERVER__SECRET_KEY=fps_secret_key_2024
    command: airflow webserver
    depends_on:
      - airflow-init
    restart: unless-stopped

  airflow-scheduler:
    image: apache/airflow:2.7.3-python3.11
    container_name: fps-airflow-scheduler
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
    command: airflow scheduler
    depends_on:
      - airflow-init
    restart: unless-stopped

volumes:
  postgres_data:
COMPOSEFILE

chown -R ec2-user:ec2-user /home/ec2-user/fair_play_shield

docker pull 806332783326.dkr.ecr.${aws_region}.amazonaws.com/fair-play-shield:latest
docker-compose up -d

echo "=========================================="
echo "Setup complete!"
echo "Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8050"
echo "MLflow:    http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):5001"
echo "Airflow:   http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
echo "=========================================="
