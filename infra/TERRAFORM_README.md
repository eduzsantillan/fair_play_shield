# Terraform Infrastructure - Fair Play Shield

Documentación completa de la infraestructura AWS desplegada con Terraform.

---

## Arquitectura AWS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud (us-east-1)                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         VPC (10.0.0.0/16)                           │   │
│  │                                                                      │   │
│  │  ┌──────────────────────┐      ┌──────────────────────┐            │   │
│  │  │   Public Subnet      │      │   Private Subnet     │            │   │
│  │  │   10.0.1.0/24        │      │   10.0.2.0/24        │            │   │
│  │  │                      │      │                      │            │   │
│  │  │  ┌──────────────┐   │      │  ┌──────────────┐   │            │   │
│  │  │  │   EC2        │   │      │  │   RDS        │   │            │   │
│  │  │  │  t3.micro    │◄──┼──────┼──►  PostgreSQL  │   │            │   │
│  │  │  │  Dashboard   │   │      │  │  db.t3.micro │   │            │   │
│  │  │  └──────────────┘   │      │  └──────────────┘   │            │   │
│  │  │         ▲           │      │                      │            │   │
│  │  └─────────┼───────────┘      └──────────────────────┘            │   │
│  │            │                                                       │   │
│  └────────────┼───────────────────────────────────────────────────────┘   │
│               │                                                             │
│  ┌────────────┼────────┐    ┌─────────────┐    ┌─────────────────────┐    │
│  │   Elastic IP        │    │     S3      │    │    EventBridge      │    │
│  │   (IP Pública)      │    │   Bucket    │    │    (Lunes 6am)      │    │
│  └─────────────────────┘    └─────────────┘    └──────────┬──────────┘    │
│                                                           │               │
│                                                           ▼               │
│                                                  ┌─────────────────┐      │
│                                                  │     Lambda      │      │
│                                                  │  (Trigger SSM)  │      │
│                                                  └─────────────────┘      │
│                                                                             │
│  ┌─────────────────────┐                                                   │
│  │        ECR          │  ◄── Docker images (fair-play-shield:latest)      │
│  └─────────────────────┘                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

         │
         │ Internet
         ▼
    ┌─────────┐
    │  User   │  http://EC2_IP:8050
    └─────────┘
```

---

## Archivos Terraform

| Archivo | Propósito |
|---------|-----------|
| `main.tf` | VPC, Subnets, Internet Gateway, Route Tables, Security Groups |
| `ec2.tf` | EC2 instance, IAM Role, Instance Profile, Elastic IP |
| `rds.tf` | RDS PostgreSQL, DB Subnet Group |
| `s3.tf` | S3 Bucket, Versioning, Encryption, Lifecycle |
| `lambda.tf` | Lambda function, EventBridge rule, IAM policies |
| `variables.tfvars.example` | Ejemplo de variables |
| `terraform.tfvars` | Variables del usuario (gitignored) |

---

## Recursos Creados

### 1. VPC y Networking (`main.tf`)

```hcl
VPC: 10.0.0.0/16
├── Public Subnet:  10.0.1.0/24  (EC2)
├── Private Subnet: 10.0.2.0/24  (RDS)
├── Internet Gateway
└── Route Table (0.0.0.0/0 → IGW)
```

**Security Groups:**

| SG | Puerto | Origen | Propósito |
|----|--------|--------|-----------|
| `ec2-sg` | 22 | Tu IP | SSH |
| `ec2-sg` | 8050 | 0.0.0.0/0 | Dashboard |
| `ec2-sg` | 5001 | 0.0.0.0/0 | MLflow (futuro) |
| `ec2-sg` | 8080 | 0.0.0.0/0 | Airflow (futuro) |
| `rds-sg` | 5432 | ec2-sg | PostgreSQL |

### 2. EC2 Instance (`ec2.tf`)

```hcl
resource "aws_instance" "app" {
  ami                    = "ami-0c02fb55956c7d316"  # Amazon Linux 2023
  instance_type          = "t3.micro"               # Free Tier (1 vCPU, 1GB RAM)
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.ssh_key_name

  root_block_device {
    volume_size = 30    # GB (Free Tier limit)
    volume_type = "gp3"
  }

  user_data = templatefile("../scripts/setup_ec2.sh", {
    db_host     = aws_db_instance.main.address
    db_name     = aws_db_instance.main.db_name
    db_user     = aws_db_instance.main.username
    db_password = var.db_password
    aws_region  = var.aws_region
    s3_bucket   = aws_s3_bucket.data.id
  })
}
```

**IAM Role del EC2:**
- `AmazonSSMManagedInstanceCore` - Para SSM (Lambda trigger)
- `ecr:GetAuthorizationToken`, `ecr:BatchGetImage` - Pull de ECR
- `logs:*` - CloudWatch Logs
- `s3:*` en el bucket del proyecto

### 3. RDS PostgreSQL (`rds.tf`)

```hcl
resource "aws_db_instance" "main" {
  identifier             = "fair-play-shield-db"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"    # Free Tier
  allocated_storage      = 20               # GB (Free Tier limit)
  storage_type           = "gp2"
  
  db_name                = "fairplayshield"
  username               = "postgres"
  password               = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  skip_final_snapshot    = true
  publicly_accessible    = false
  backup_retention_period = 0               # Free Tier
}
```

**Conexión desde EC2:**
```bash
psql -h fair-play-shield-db.xxxxx.us-east-1.rds.amazonaws.com -U postgres -d fairplayshield
```

### 4. S3 Bucket (`s3.tf`)

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "fair-play-shield-data-${random_string.suffix.result}"
}
```

**Configuración:**
- Versioning habilitado
- Encryption AES-256
- Public access bloqueado
- Lifecycle: objetos a Glacier después de 90 días

**Estructura del bucket:**
```
s3://fair-play-shield-data-xxxxx/
├── raw/              # Datos crudos
├── processed/        # Datos procesados
├── models/           # Modelos entrenados
└── logs/             # Logs de ejecución
```

### 5. Lambda + EventBridge (`lambda.tf`)

**Trigger semanal (Lunes 6:00 AM UTC):**

```hcl
resource "aws_cloudwatch_event_rule" "weekly" {
  name                = "fair-play-shield-weekly-trigger"
  schedule_expression = "cron(0 6 ? * MON *)"
}
```

**Lambda function:**
```python
def lambda_handler(event, context):
    ssm = boto3.client('ssm')
    response = ssm.send_command(
        InstanceIds=[EC2_INSTANCE_ID],
        DocumentName='AWS-RunShellScript',
        Parameters={
            'commands': [
                'cd /home/ec2-user/fair_play_shield',
                'python main.py --step all --seasons 1'
            ]
        }
    )
    return {'statusCode': 200}
```

---

## Variables de Configuración

### `terraform.tfvars`

```hcl
aws_region       = "us-east-1"
project_name     = "fair-play-shield"
environment      = "dev"
db_password      = "TuPasswordSeguro123"  # Sin @, #, $
ssh_key_name     = "aws-dev"
allowed_ssh_cidr = "0.0.0.0/0"            # O tu IP: "1.2.3.4/32"
```

**Reglas para `db_password`:**
- Mínimo 8 caracteres
- Sin caracteres especiales problemáticos: `@`, `#`, `$`, `/`, `\`
- Ejemplo válido: `MiPassword2024Seguro`

---

## Comandos Terraform

### Inicializar (primera vez)

```bash
cd infra/terraform
terraform init
```

### Ver plan de cambios

```bash
terraform plan -var-file=terraform.tfvars
```

### Aplicar infraestructura

```bash
terraform apply -var-file=terraform.tfvars -auto-approve
```

### Ver outputs

```bash
terraform output

# Outputs:
# ec2_public_ip = "52.202.249.31"
# dashboard_url = "http://52.202.249.31:8050"
# rds_endpoint  = "fair-play-shield-db.xxxxx.rds.amazonaws.com:5432"
# s3_bucket_name = "fair-play-shield-data-xxxxx"
```

### Destruir todo

```bash
terraform destroy -var-file=terraform.tfvars
```

### Reemplazar EC2 (redeploy)

```bash
terraform apply -var-file=terraform.tfvars -auto-approve -replace=aws_instance.app
```

---

## Setup Script del EC2

El archivo `infra/scripts/setup_ec2.sh` se ejecuta automáticamente al crear la instancia:

```bash
#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log) 2>&1

# 1. Instalar Docker y Docker Compose
yum update -y
yum install -y docker git
systemctl start docker
systemctl enable docker

curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 2. Clonar repositorio
cd /home/ec2-user
git clone https://github.com/eduzsantillan/fair_play_shield.git
cd fair_play_shield

# 3. Crear .env con variables de Terraform
cat > .env << EOF
DB_HOST=${db_host}
DB_PORT=5432
DB_NAME=${db_name}
DB_USER=${db_user}
DB_PASSWORD=${db_password}
AWS_REGION=${aws_region}
S3_BUCKET=${s3_bucket}
EOF

# 4. Login a ECR y levantar dashboard
aws ecr get-login-password --region ${aws_region} | \
  docker login --username AWS --password-stdin 806332783326.dkr.ecr.${aws_region}.amazonaws.com

docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

---

## Costos AWS Free Tier

| Servicio | Límite Free Tier | Este proyecto |
|----------|------------------|---------------|
| EC2 t3.micro | 750 hrs/mes | ✅ 1 instancia |
| RDS db.t3.micro | 750 hrs/mes | ✅ 1 instancia |
| S3 | 5 GB | ✅ ~100 MB |
| Lambda | 1M requests/mes | ✅ 4 calls/mes |
| ECR | 500 MB | ✅ ~300 MB |

**Costo estimado:** $0/mes dentro de Free Tier (primer año)

---

## Troubleshooting

### EC2 no inicia el dashboard

```bash
# Ver logs del setup
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "cat /var/log/user-data.log"

# Ver estado de Docker
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "sudo docker ps -a"

# Ver logs del container
ssh -i ~/.ssh/aws-dev.pem ec2-user@<EC2_IP> "sudo docker logs fps-dashboard"
```

### Error "no matching manifest for linux/amd64"

```bash
# Rebuild con platform específico
docker buildx build --platform linux/amd64 \
  -t 806332783326.dkr.ecr.us-east-1.amazonaws.com/fair-play-shield:latest \
  -f Dockerfile.prod . --push
```

### RDS conexión rechazada

1. Verificar Security Group permite puerto 5432 desde EC2
2. Verificar que EC2 está en la misma VPC
3. Verificar password sin caracteres especiales

### Terraform state corrupto

```bash
# Backup del state actual
cp terraform.tfstate terraform.tfstate.backup

# Reimportar recursos si es necesario
terraform import aws_instance.app i-xxxxxxxxxxxx
```

### Recrear infraestructura desde cero

```bash
# 1. Destruir todo
terraform destroy -var-file=terraform.tfvars

# 2. Limpiar state local
rm -rf .terraform terraform.tfstate*

# 3. Reinicializar
terraform init
terraform apply -var-file=terraform.tfvars -auto-approve
```

---

## Flujo de Despliegue

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PRIMER DESPLIEGUE                               │
└─────────────────────────────────────────────────────────────────────┘

1. aws configure                    # Configurar credenciales
2. Crear key pair (aws-dev)         # Para SSH
3. Crear repo ECR                   # Para imágenes Docker
4. Build + push imagen              # docker buildx build --platform linux/amd64
5. terraform init                   # Inicializar
6. terraform apply                  # Crear infraestructura
7. curl http://EC2_IP:8050          # Verificar dashboard

┌─────────────────────────────────────────────────────────────────────┐
│                     ACTUALIZAR CÓDIGO                               │
└─────────────────────────────────────────────────────────────────────┘

1. git push                         # Subir cambios a GitHub
2. docker buildx build + push       # Nueva imagen
3. ssh ec2-user@EC2_IP              # Conectar a EC2
4. cd fair_play_shield && git pull  # Actualizar código
5. docker-compose pull && up -d     # Reiniciar container

┌─────────────────────────────────────────────────────────────────────┐
│                     DESTRUIR / RECREAR                              │
└─────────────────────────────────────────────────────────────────────┘

terraform destroy                   # Elimina TODO (EC2, RDS, S3, etc.)
terraform apply                     # Recrea TODO desde cero
```

---

## Seguridad

### Qué NO está en git (`.gitignore`):
- `terraform.tfvars` (contiene passwords)
- `*.tfstate` (contiene secrets)
- `.terraform/` (providers locales)

### Mejores prácticas aplicadas:
- RDS no es públicamente accesible
- S3 bucket con public access bloqueado
- EC2 en subnet pública pero con SG restrictivo
- Encryption at rest en S3 y RDS
- IAM roles con permisos mínimos necesarios

---

## Referencia Rápida

```bash
# Desplegar
cd infra/terraform && terraform apply -var-file=terraform.tfvars -auto-approve

# Destruir
cd infra/terraform && terraform destroy -var-file=terraform.tfvars

# SSH a EC2
ssh -i ~/.ssh/aws-dev.pem ec2-user@$(terraform output -raw ec2_public_ip)

# Ver dashboard URL
terraform output dashboard_url

# Redeploy EC2
terraform apply -var-file=terraform.tfvars -auto-approve -replace=aws_instance.app
```
