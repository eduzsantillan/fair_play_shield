#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log) 2>&1

echo "=========================================="
echo "Fair Play Shield - EC2 Setup"
echo "=========================================="

yum update -y
yum install -y docker git

systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

yum install -y amazon-ssm-agent
systemctl enable amazon-ssm-agent
systemctl start amazon-ssm-agent

cd /home/ec2-user
git clone https://github.com/eduzsantillan/fair_play_shield.git
cd fair_play_shield

cat > .env << EOF
DB_HOST=${db_host}
DB_PORT=5432
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
AWS_REGION=${aws_region}
S3_BUCKET=${s3_bucket}
MLFLOW_TRACKING_URI=http://localhost:5001
EOF

aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin 806332783326.dkr.ecr.${aws_region}.amazonaws.com

chown -R ec2-user:ec2-user /home/ec2-user/fair_play_shield

docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "=========================================="
echo "Setup complete!"
echo "Dashboard: http://$PUBLIC_IP:8050"
echo ""
echo "Código clonado desde GitHub"
echo "Usando docker-compose.prod.yml del repo"
echo "=========================================="
