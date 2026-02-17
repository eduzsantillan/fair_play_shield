#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log) 2>&1

echo "=========================================="
echo "Fair Play Shield - EC2 Setup"
echo "=========================================="

yum update -y
yum install -y docker git python3.11 python3.11-pip

systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

cd /home/ec2-user
git clone https://github.com/YOUR_USERNAME/fair_play_shield.git || echo "Repo already exists"
cd fair_play_shield

cat > .env << 'ENVFILE'
DB_HOST=${db_host}
DB_PORT=5432
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}

AWS_REGION=${aws_region}
S3_BUCKET=${s3_bucket}

MLFLOW_TRACKING_URI=http://localhost:5001
MLFLOW_S3_ENDPOINT_URL=https://s3.${aws_region}.amazonaws.com

AIRFLOW_UID=1000
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow
ENVFILE

chown -R ec2-user:ec2-user /home/ec2-user/fair_play_shield

sudo -u ec2-user docker-compose build
sudo -u ec2-user docker-compose up -d

echo "=========================================="
echo "Setup complete!"
echo "Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8050"
echo "MLflow:    http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):5001"
echo "Airflow:   http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
echo "=========================================="
